# this_file: tests/test_teaching_text_handoff.py
"""Rich Text Handoff Letter: letter composition, font prefill and the shared draft panel, on real offscreen Qt."""

import sys
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import lab  # noqa: F401


@pytest.fixture
def mod():
    from fontlabapp.fontui.teaching_text import handoff

    return handoff


def test_handoff_letter_when_fields_have_markup_then_escaped_and_scope_counted(mod):
    html = mod.handoff_letter("A&B <x>", "Ann", "line1\nline2", ("a<b", "C"))
    assert "<h1>A&amp;B &lt;x&gt;</h1>" in html and "line1<br>line2" in html
    assert "Review scope: 2 glyphs" in html and "/a&lt;b /C" in html
    for args in (("", "r", "i", ()), ("p", " ", "i", ()), ("p", "r", "\n", ())):
        with pytest.raises(ValueError, match="Enter a project"):
            mod.handoff_letter(*args)
    with pytest.raises(ValueError, match="NBSP"):
        mod.handoff_letter("p", "r", "i", ("a ",))


def test_current_font_label_when_font_states_then_label_or_refusal(mod, monkeypatch):
    def font(family, major=1, minor=2):
        return NS(info=NS(familyName=family, versionMajor=major, versionMinor=minor))

    holder = NS(font=None)
    monkeypatch.setitem(sys.modules, "fontlab", NS(CurrentFont=lambda: holder.font))
    with pytest.raises(ValueError, match="Open a font"):
        mod.current_font_label()
    holder.font = font("Fam")
    assert mod.current_font_label() == "Fam 1.002"
    holder.font = font("Fam", "x", None)
    assert mod.current_font_label() == "Fam"
    holder.font = font("  ")
    with pytest.raises(ValueError, match="no family name"):
        mod.current_font_label()
    holder.font = font(None)
    with pytest.raises(ValueError, match="no family name"):
        mod.current_font_label()


@pytest.fixture
def handoff(lab, monkeypatch):  # noqa: F811
    module, shown = lab("handoff")
    qt = sys.modules["PythonQt"]
    parent = qt.QtGui.QWidget()
    monkeypatch.setattr(module, "capture_names", lambda: ("A", "B"))
    monkeypatch.setattr(module, "current_font_label", lambda: "Fam 1.000")
    yield module, qt, parent
    module._PANELS.clear()


def click(panel, qt, text):
    [b for b in panel.findChildren(qt.QtGui.QPushButton) if b.text() == text][0].click()


def test_panel_when_built_then_prefilled_letter_previewed_and_exported(handoff, tmp_path):
    module, qt, parent = handoff
    panel = module.show(qt, parent, embedded=True)
    assert panel.project.text == "Fam 1.000" and not panel.dirty
    panel.recipient.setText("Ann")
    panel.editor.setPlainText("Check kerning")
    assert panel.dirty
    click(panel, qt, "Build")
    assert panel.status.text().startswith("Letter ready") and "Review scope: 2 glyphs" in panel.letter
    assert "Check kerning" in panel.preview.toPlainText()
    panel.destination.setText(str(tmp_path / "letter.html"))
    click(panel, qt, "Export New")
    assert (tmp_path / "letter.html").read_text().startswith("<!DOCTYPE html>") and not panel.dirty


def test_panel_when_fields_blank_then_build_refused_in_status(handoff):
    module, qt, parent = handoff
    panel = module.show(qt, parent, embedded=True)
    click(panel, qt, "Build")
    assert panel.status.text() == "Enter a project, recipient and review instructions."


def test_panel_when_copy_then_plain_text_handoff_on_clipboard(handoff, monkeypatch):
    module, qt, parent = handoff
    panel = module.show(qt, parent, embedded=True)
    panel.recipient.setText("Ann")
    panel.editor.setPlainText("Please check")
    copied = []
    monkeypatch.setattr(qt.QtGui.QApplication, "clipboard", staticmethod(lambda: NS(setText=copied.append)))
    click(panel, qt, "Copy")
    assert copied == ["Fam 1.000\nTo: Ann\nPlease check\n2 glyphs\n/A /B"]


def test_panel_when_font_label_unavailable_then_status_explains(handoff, monkeypatch):
    module, qt, parent = handoff
    monkeypatch.setattr(module, "current_font_label", lambda: (_ for _ in ()).throw(ValueError("Open a font")))
    panel = module.show(qt, parent, embedded=True)
    assert panel.project.text == "" and panel.status.text() == "Open a font"


def test_panel_close_discard_and_failures(handoff, tmp_path):
    module, qt, parent = handoff
    panel = module.show(qt, parent, embedded=True)
    event = NS(ignored=False, accepted=False)
    event.ignore, event.accept = (lambda: setattr(event, "ignored", True)), (lambda: setattr(event, "accepted", True))
    panel.editor.setPlainText("draft")
    panel.closeEvent(event)
    assert event.ignored and panel in module._PANELS
    signal = NS(disconnect=lambda slot: (_ for _ in ()).throw(RuntimeError("busy")))
    panel.dirty = False
    panel.connections.append((signal, None))
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


def test_set_plain_exact_and_export_guards(mod, handoff, tmp_path):
    module, qt, parent = handoff
    editor = qt.QtGui.QPlainTextEdit()
    editor.setPlainText("keep")
    editor.toPlainText = lambda: "changed"
    seen = []
    editor.setPlainText = seen.append
    with pytest.raises(ValueError, match="normalization"):
        mod.set_plain_exact(editor, "x")
    assert seen == ["x", "changed"]
    target = tmp_path / "e.html"
    mod.export_new(str(target), "ok")
    with pytest.raises(FileExistsError):
        mod.export_new(str(target), "ok")
    with pytest.raises(ValueError, match="absolute"):
        mod.export_new("rel", "ok")
    with pytest.raises(ValueError, match="CR"):
        mod.check_text("a\r")


def test_show_failure_visible_main_build(handoff, monkeypatch):
    module, qt, parent = handoff
    window = module.show(qt, parent)
    assert window.isVisible()
    window.close()
    module._PANELS.clear()
    monkeypatch.setattr(qt.QtGui, "QTextBrowser", lambda *a: (_ for _ in ()).throw(RuntimeError("no browser")))
    with pytest.raises(RuntimeError, match="no browser"):
        module.show(qt, parent)
    assert module._PANELS == []
    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: parent))
    seen = []
    monkeypatch.setattr(module, "show", lambda q, p, **k: seen.append(p))
    module.main()
    assert seen == [parent]
