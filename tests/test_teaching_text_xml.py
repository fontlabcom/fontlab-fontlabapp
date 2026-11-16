# this_file: tests/test_teaching_text_xml.py
"""Glyph Inventory XML: text guards, report building and the table panel, on real offscreen Qt."""

import sys
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import lab  # noqa: F401

ROWS = (("A", "U+0041 U+0391", "2026-01-01"), ("B", "", "x"))


@pytest.fixture
def mod():
    from fontlabapp.fontui.teaching_text import xml

    return xml


@pytest.mark.parametrize("bad", ["a\0", "a\r", "a ", "a ", "a ", "\ud800"])
def test_checked_when_unpreservable_then_refused(mod, bad):
    with pytest.raises((ValueError, UnicodeError)):
        mod.checked(bad)
    assert mod.checked("ok") == "ok" and mod.build_rows(ROWS) is ROWS


def test_report_when_rows_then_xml_with_unicode_children_and_invalid_chars_refused(mod):
    text = mod.report((("A&", "U+0041 U+0391", "m"),))
    assert text.startswith("<?xml") and text.endswith("\n")
    assert 'name="A&amp;"' in text and text.count("<unicode>") == 2
    with pytest.raises(ValueError, match="invalid XML character"):
        mod.report((("A\x01", "", ""),))


@pytest.fixture
def xml(lab):  # noqa: F811
    module, shown = lab("xml")
    qt = sys.modules["PythonQt"]
    parent = qt.QtGui.QWidget()
    yield module, qt, parent
    module._PANELS.clear()


def click(panel, qt, text):
    [b for b in panel.findChildren(qt.QtGui.QPushButton) if b.text() == text][0].click()


def make(xml, rows=ROWS):
    module, qt, parent = xml
    return module.show(qt, parent, lambda: NS(rows=rows), embedded=True)


def test_panel_when_shown_then_rows_in_table_and_refresh_replaces_model(xml):
    module, qt, parent = xml
    panel = make(xml)
    assert panel.status_line.text() == "Captured 2 glyphs." and panel.owned_model.rowCount() == 2
    first = panel.owned_model
    hooks = []
    panel.lab_refresh_preview = lambda: hooks.append(1)
    click(panel, qt, "Refresh")
    assert panel.owned_model is not first and hooks == [1]


def test_panel_when_capture_or_staging_fails_then_old_result_kept(xml):
    module, qt, parent = xml
    panel = make(xml)
    kept = panel.owned_model
    panel.capture_font = lambda: NS(rows=(("A\0", "", ""),))
    with pytest.raises(ValueError):
        panel.refresh()
    assert panel.owned_model is kept
    with pytest.raises(ValueError):
        panel.stage((("A\0", "", ""),))
    failing = module.show(qt, parent, lambda: (_ for _ in ()).throw(RuntimeError("no font")), embedded=True)
    assert failing.status_line.text() == "no font" and failing.owned_model is None


def test_panel_when_copy_and_export_then_report_delivered_or_refused(xml, tmp_path, monkeypatch):
    module, qt, parent = xml
    empty = module.show(qt, parent, lambda: (_ for _ in ()).throw(ValueError("x")), embedded=True)
    for action in (empty.copy_report, empty.export_report):
        with pytest.raises(ValueError, match="Refresh first"):
            action()
    panel = make(xml)
    copied = []
    monkeypatch.setattr(qt.QtGui.QApplication, "clipboard", staticmethod(lambda: NS(setText=copied.append)))
    click(panel, qt, "Copy Report")
    assert copied[0].startswith("<?xml") and panel.status_line.text() == "Report copied."
    panel.export_field.setText("relative.xml")
    with pytest.raises(ValueError, match="absolute"):
        panel.export_report()
    target = tmp_path / "r.xml"
    panel.export_field.setText(str(target))
    panel.export_report()
    assert target.read_text().startswith("<?xml") and panel.status_line.text() == "Report exported."
    with pytest.raises(FileExistsError):
        panel.export_report()


def test_panel_close_and_destroy_paths(xml):
    module, qt, parent = xml
    panel = make(xml)
    event = NS(ignored=0, accepted=0)
    event.ignore, event.accept = (lambda: setattr(event, "ignored", 1)), (lambda: setattr(event, "accepted", 1))
    panel.scope.finish = lambda destroyed=False: False
    panel.closeEvent(event)
    assert event.ignored and panel in module._PANELS
    del panel.scope.finish
    panel.table_view.setModel = lambda m: (_ for _ in ()).throw(RuntimeError("busy"))
    event.ignored = 0
    panel.closeEvent(event)
    assert event.ignored and "Close paused: busy" in panel.status_line.text()
    del panel.table_view.setModel
    panel.closeEvent(event)
    assert event.accepted and panel not in module._PANELS and panel.owned_model is None
    other = make(xml)
    other.destroyed_owner()
    assert other not in module._PANELS
    other.destroyed_owner()


def test_close_button_show_failure_main_build(xml, monkeypatch):
    module, qt, parent = xml
    panel = make(xml)
    calls = []
    panel.lab_close = lambda: calls.append(1)
    click(panel, qt, "Close")
    assert calls == [1]
    module._PANELS.clear()
    with monkeypatch.context() as local:
        local.setattr(qt.QtGui, "QTableView", lambda *a: (_ for _ in ()).throw(RuntimeError("no table")))
        with pytest.raises(RuntimeError, match="no table"):
            module.show(qt, parent, lambda: NS(rows=ROWS))
    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: parent))
    seen = []
    monkeypatch.setattr(module, "show", lambda q, p, *a, **k: seen.append((p, k)))
    module.main()
    module.build(parent)
    assert seen == [(parent, {}), (parent, {"embedded": True})]
