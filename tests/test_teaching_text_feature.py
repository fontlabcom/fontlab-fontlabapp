# this_file: tests/test_teaching_text_feature.py
"""Feature Code Draft: text checks, lexer, export and the draft panel, on real offscreen Qt."""

import sys
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import lab  # noqa: F401


@pytest.fixture
def mod():
    from fontlabapp.fontui.teaching_text import feature

    return feature


@pytest.mark.parametrize("text,label", [("a\x00", "NUL"), ("a ", "NBSP"), ("a ", "U+2028"),
                                         ("a ", "U+2029"), ("a\r", "CR"), ("\ud800", "lone surrogate")])
def test_check_text_when_unsafe_then_class_named(mod, text, label):
    with pytest.raises(ValueError, match=__import__("re").escape(label)):
        mod.check_text(text)
    assert mod.check_text("fine\n") == "fine\n"


def test_feature_spans_when_comments_strings_keywords_then_shielded_and_utf16(mod):
    assert mod.feature_spans('feature liga { sub f i by f_i; } liga;') == [(0, 7, "keyword"), (15, 3, "keyword"), (23, 2, "keyword")]
    assert mod.feature_spans('# feature\n"sub by"') == [(0, 9, "comment"), (10, 8, "string")]
    assert mod.feature_spans('sub') == [(0, 3, "keyword")]
    assert mod.feature_spans('\U0001F600 sub') == [(3, 3, "keyword")]
    assert mod.feature_spans("sub.x @sub") == []


def test_export_new_when_relative_existing_or_unsafe_then_refused(mod, tmp_path):
    target = tmp_path / "out.fea"
    mod.export_new(str(target), "feature x {} x;\n")
    assert target.read_bytes() == b"feature x {} x;\n"
    with pytest.raises(FileExistsError):
        mod.export_new(str(target), "again")
    with pytest.raises(ValueError, match="absolute"):
        mod.export_new("rel.fea", "x")
    with pytest.raises(ValueError, match="NUL"):
        mod.export_new(str(tmp_path / "n.fea"), "\x00")


def test_capture_names_when_font_read_then_names(mod, monkeypatch):
    import fontlabapp.glyphs.catalog.model as model

    monkeypatch.setattr(model, "capture", lambda: NS(rows=[("A", "", ""), ("B", "", "")]))
    assert mod.capture_names() == ("A", "B")


@pytest.fixture
def feature(lab, monkeypatch):  # noqa: F811
    module, shown = lab("feature")
    qt = sys.modules["PythonQt"]
    parent = qt.QtGui.QWidget()
    qt.QtGui.QLineEdit.text = property(lambda self: qt.QtGui.QLineEdit.__mro__[1].text(self))
    yield module, qt, parent
    module._PANELS.clear()


def click(panel, qt, text):
    [b for b in panel.findChildren(qt.QtGui.QPushButton) if b.text() == text][0].click()


def test_set_plain_exact_when_qt_normalizes_then_old_text_restored(mod, feature):
    module, qt, parent = feature
    editor = qt.QtGui.QPlainTextEdit()
    editor.setPlainText("old")
    mod.set_plain_exact(editor, "new")
    assert editor.toPlainText() == "new"
    editor.toPlainText = lambda: "changed"
    seen = []
    editor.setPlainText = lambda t: seen.append(t)
    with pytest.raises(ValueError, match="normalization"):
        mod.set_plain_exact(editor, "next")
    assert seen == ["next", "changed"]


def test_panel_when_edited_then_dirty_and_close_refused_until_exported(feature, tmp_path):
    module, qt, parent = feature
    panel = module.show(qt, parent, embedded=True)
    assert panel in module._PANELS and not panel.dirty and panel.highlighter is not None
    panel.editor.setPlainText("feature liga {} liga;\n")
    assert panel.dirty and "Unsaved draft" in panel.status.text()
    event = NS(ignored=False, accepted=False)
    event.ignore, event.accept = (lambda: setattr(event, "ignored", True)), (lambda: setattr(event, "accepted", True))
    panel.closeEvent(event)
    assert event.ignored and panel in module._PANELS
    panel.destination.setText(str(tmp_path / "x.fea"))
    click(panel, qt, "Export New")
    assert not panel.dirty and (tmp_path / "x.fea").read_text() == "feature liga {} liga;\n"
    assert panel.status.text().startswith("Export saved")
    click(panel, qt, "Export New")  # exists now: error contained in the status line
    assert "exists" in panel.status.text().lower() or "File exists" in panel.status.text()
    panel.closeEvent(event)
    assert event.accepted and panel not in module._PANELS and panel.closed
    panel.closeEvent(NS(ignore=lambda: None, accept=lambda: None))  # a second close is harmless


def test_panel_when_copy_then_clipboard_and_hook(feature, monkeypatch):
    module, qt, parent = feature
    panel = module.show(qt, parent, embedded=True)
    copied, hooks = [], []
    monkeypatch.setattr(qt.QtGui.QApplication, "clipboard", staticmethod(lambda: NS(setText=copied.append)))
    panel.lab_refresh_preview = lambda: hooks.append(1)
    panel.editor.setPlainText("sub")
    click(panel, qt, "Copy")
    assert copied == ["sub"] and panel.status.text() == "Text copied." and hooks == [1]
    panel.copy_payload = lambda: "alt "
    click(panel, qt, "Copy")
    assert "NBSP" in panel.status.text() and copied == ["sub"]


def test_panel_when_load_then_bom_and_crlf_noted_and_failures_keep_draft(feature, tmp_path):
    module, qt, parent = feature
    panel = module.show(qt, parent, embedded=True)
    source = tmp_path / "a.fea"
    source.write_bytes(b"\xef\xbb\xbffeature x {\r\n} x;\r\n")
    panel.source.setText(str(source))
    click(panel, qt, "Load")
    assert panel.editor.toPlainText() == "feature x {\n} x;\n" and not panel.dirty
    assert panel.status.text() == "Loaded. Line endings converted to LF. BOM removed. Edits stay local until Export New."
    plain = tmp_path / "b.fea"
    plain.write_text("# only\n")
    panel.source.setText(str(plain))
    click(panel, qt, "Load")
    assert panel.status.text() == "Loaded. Edits stay local until Export New."
    panel.source.setText("relative.fea")
    click(panel, qt, "Load")
    assert "absolute source" in panel.status.text()
    panel.editor.setPlainText("typed")
    click(panel, qt, "Load")
    assert "Export the draft" in panel.status.text() and panel.editor.toPlainText() == "typed"
    panel.dirty = False
    bad = tmp_path / "c.fea"
    bad.write_bytes(b"a\xc2\xa0b")  # NBSP survives decoding but is refused
    panel.source.setText(str(bad))
    panel.dirty = True
    panel.dirty = False
    click(panel, qt, "Load")
    assert "NBSP" in panel.status.text() and panel.editor.toPlainText() == "typed" and not panel.dirty


def test_panel_when_insert_names_then_comment_added(feature, monkeypatch):
    module, qt, parent = feature
    panel = module.show(qt, parent, embedded=True)
    monkeypatch.setattr(module, "capture_names", lambda: ("A", "B"))
    click(panel, qt, "Insert Names")
    assert "# Font glyphs: A B" in panel.editor.toPlainText()
    monkeypatch.setattr(module, "capture_names", lambda: (_ for _ in ()).throw(ValueError("no font")))
    click(panel, qt, "Insert Names")
    assert panel.status.text() == "no font"


def test_panel_when_discard_then_lab_close_or_close(feature):
    module, qt, parent = feature
    panel = module.show(qt, parent, embedded=True)
    panel.editor.setPlainText("x")
    calls = []
    panel.lab_close = lambda: calls.append(1)
    click(panel, qt, "Discard and Close")
    assert calls == [1] and not panel.dirty
    del panel.lab_close
    click(panel, qt, "Discard and Close")
    assert panel not in module._PANELS


def test_panel_when_disconnect_fails_then_close_paused_and_retained(feature):
    module, qt, parent = feature
    panel = module.show(qt, parent, embedded=True)
    signal = NS(disconnect=lambda slot: (_ for _ in ()).throw(RuntimeError("busy")))
    panel.connections.append((signal, None))
    event = NS(ignored=False)
    event.ignore = lambda: setattr(event, "ignored", True)
    panel.closeEvent(event)
    assert event.ignored and "Close paused: busy" in panel.status.text() and panel in module._PANELS
    panel.connections.pop()


def test_show_when_unavailable_highlighter_then_status_note(feature, monkeypatch):
    module, qt, parent = feature
    monkeypatch.delattr(qt.QtGui, "QSyntaxHighlighter")
    panel = module.show(qt, parent, embedded=True)
    assert panel.status.text() == "Syntax colouring unavailable" and panel.highlighter is None
    panel.closeEvent(NS(ignore=lambda: None, accept=lambda: None))


def test_show_when_populate_fails_then_closed_and_raised(feature, monkeypatch):
    module, qt, parent = feature
    monkeypatch.setattr(qt.QtGui, "QPlainTextEdit", lambda *a: (_ for _ in ()).throw(RuntimeError("no editor")))
    with pytest.raises(RuntimeError, match="no editor"):
        module.show(qt, parent)
    assert module._PANELS == []


def test_show_when_not_embedded_then_visible_and_main_build(feature, monkeypatch):
    module, qt, parent = feature
    window = module.show(qt, parent)
    assert window.isVisible()
    window.close()
    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: parent))
    seen = []
    monkeypatch.setattr(module, "show", lambda q, p: seen.append(p))
    module.main()
    assert seen == [parent]
