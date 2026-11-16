# this_file: tests/test_teaching_text_review.py
"""Font Review Notes: checklist heading, load and the shared draft panel, on real offscreen Qt."""

import sys
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import lab  # noqa: F401


@pytest.fixture
def mod():
    from fontlabapp.fontui.teaching_text import review

    return review


def test_review_heading_when_names_then_checklist_else_refused(mod):
    assert mod.review_heading(("A", "B")) == "\n## Font review: 2 glyphs\n/A /B\n- [ ] \n"
    with pytest.raises(ValueError, match="no glyphs"):
        mod.review_heading(())


def test_capture_names_and_text_guards(mod, monkeypatch, tmp_path):
    import fontlabapp.glyphs.catalog.model as model

    monkeypatch.setattr(model, "capture", lambda: NS(rows=[("A", "", "")]))
    assert mod.capture_names() == ("A",)
    for bad, label in (("\x00", "NUL"), ("\ud800", "lone surrogate"), ("\r", "CR")):
        with pytest.raises(ValueError, match=label):
            mod.check_text(bad)
    mod.export_new(str(tmp_path / "n.md"), "ok")
    with pytest.raises(FileExistsError):
        mod.export_new(str(tmp_path / "n.md"), "ok")
    with pytest.raises(ValueError, match="absolute"):
        mod.export_new("n.md", "ok")


@pytest.fixture
def review(lab, monkeypatch):  # noqa: F811
    module, shown = lab("review")
    qt = sys.modules["PythonQt"]
    parent = qt.QtGui.QWidget()
    monkeypatch.setattr(module, "capture_names", lambda: ("A", "B"))
    yield module, qt, parent
    module._PANELS.clear()


def click(panel, qt, text):
    [b for b in panel.findChildren(qt.QtGui.QPushButton) if b.text() == text][0].click()


def test_panel_when_inserting_then_heading_and_checklist_added_and_dirty(review):
    module, qt, parent = review
    panel = module.show(qt, parent, embedded=True)
    assert panel in module._PANELS and not panel.dirty
    click(panel, qt, "Font Heading")
    assert "## Font review: 2 glyphs" in panel.editor.toPlainText() and panel.dirty
    click(panel, qt, "Checklist")
    assert panel.editor.toPlainText().endswith("\n- [ ] ")


def test_panel_when_names_unavailable_then_status_shows_reason(review, monkeypatch):
    module, qt, parent = review
    monkeypatch.setattr(module, "capture_names", lambda: (_ for _ in ()).throw(ValueError("No font")))
    panel = module.show(qt, parent, embedded=True)
    click(panel, qt, "Font Heading")
    assert panel.status.text() == "No font" and panel.editor.toPlainText() == ""


def test_panel_when_copy_and_export_then_text_checked_and_written(review, monkeypatch, tmp_path):
    module, qt, parent = review
    panel = module.show(qt, parent, embedded=True)
    panel.editor.setPlainText("- [ ] item")
    copied = []
    monkeypatch.setattr(qt.QtGui.QApplication, "clipboard", staticmethod(lambda: NS(setText=copied.append)))
    click(panel, qt, "Copy")
    assert copied == ["- [ ] item"]
    panel.destination.setText(str(tmp_path / "notes.md"))
    hooks = []
    panel.after_save = lambda: hooks.append(1)
    click(panel, qt, "Export New")
    assert (tmp_path / "notes.md").read_text() == "- [ ] item" and hooks == [1] and not panel.dirty
    click(panel, qt, "Export New")
    assert "exists" in panel.status.text().lower()


def test_panel_when_load_then_notes_failures_and_dirty_guard(review, tmp_path):
    module, qt, parent = review
    panel = module.show(qt, parent, embedded=True)
    source = tmp_path / "n.md"
    source.write_bytes(b"\xef\xbb\xbf# notes\r\n")
    panel.source.setText(str(source))
    click(panel, qt, "Load")
    assert panel.editor.toPlainText() == "# notes\n" and not panel.dirty
    assert panel.status.text() == "Loaded. Line endings converted to LF. BOM removed. Edits stay local until Export New."
    plain = tmp_path / "p.md"
    plain.write_text("x")
    panel.source.setText(str(plain))
    click(panel, qt, "Load")
    assert panel.status.text() == "Loaded. Edits stay local until Export New."
    panel.source.setText("rel.md")
    click(panel, qt, "Load")
    assert "absolute source" in panel.status.text()
    panel.editor.setPlainText("typed")
    click(panel, qt, "Load")
    assert "Export the draft" in panel.status.text()
    panel.dirty = False
    bad = tmp_path / "b.md"
    bad.write_bytes(b"a\xc2\xa0b")
    panel.source.setText(str(bad))
    click(panel, qt, "Load")
    assert "NBSP" in panel.status.text() and panel.editor.toPlainText() == "typed"


def test_panel_close_discard_and_failures(review):
    module, qt, parent = review
    panel = module.show(qt, parent, embedded=True)
    event = NS(ignored=False, accepted=False)
    event.ignore, event.accept = (lambda: setattr(event, "ignored", True)), (lambda: setattr(event, "accepted", True))
    panel.editor.setPlainText("draft")
    panel.closeEvent(event)
    assert event.ignored and "Unsaved draft" in panel.status.text()
    panel.dirty = False
    panel.connections.append((NS(disconnect=lambda s: (_ for _ in ()).throw(RuntimeError("busy"))), None))
    panel.closeEvent(event)
    assert "Close paused: busy" in panel.status.text()
    panel.connections.pop()
    calls = []
    panel.lab_close = lambda: calls.append(1)
    click(panel, qt, "Discard and Close")
    assert calls == [1]
    del panel.lab_close
    click(panel, qt, "Discard and Close")
    assert panel not in module._PANELS and panel.closed


def test_show_failure_visible_main_build(review, monkeypatch):
    module, qt, parent = review
    window = module.show(qt, parent)
    assert window.isVisible()
    window.close()
    module._PANELS.clear()
    monkeypatch.setattr(qt.QtGui, "QLineEdit", lambda *a: (_ for _ in ()).throw(RuntimeError("no entry")))
    with pytest.raises(RuntimeError, match="no entry"):
        module.show(qt, parent)
    assert module._PANELS == []
    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: parent))
    seen = []
    monkeypatch.setattr(module, "show", lambda q, p, **k: seen.append(p))
    module.main()
    assert seen == [parent]
