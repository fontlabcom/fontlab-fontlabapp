# this_file: tests/test_teaching_text_diff.py
"""Glyph Snapshot Diff: snapshot checks, diff rows and the paged panel, on real offscreen Qt."""

import sys
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import lab  # noqa: F401


@pytest.fixture
def mod():
    from fontlabapp.fontui.teaching_text import diff

    return diff


def table(rows, epochs=None):
    return NS(rows=rows, epochs=epochs)


@pytest.mark.parametrize("text", ["a\tb", "a\nb", "a\rb", "a\0b", "a b", "a b", "a b", "\ud800"])
def test_checked_when_unsafe_then_refused(mod, text):
    with pytest.raises((ValueError, UnicodeError)):
        mod.checked(text)


def test_codes_when_valid_then_sorted_distinct_and_bad_tokens_refused(mod):
    assert mod.codes("U+0042 U+0041 U+0041 U+1F600") == (0x41, 0x42, 0x1F600)
    assert mod.codes("") == ()
    for bad in ("0041", "U+41", "U+00G1", "U+1234567", "U+110000", "U+D800"):
        with pytest.raises(ValueError, match="Invalid Unicode"):
            mod.codes(bad)
    assert mod.unicode_text((0x41, 0x1F600)) == "U+0041 U+1F600"


def test_snapshot_when_complete_then_detached_records_else_refused(mod):
    snap = mod.snapshot(table([("A", "U+0041", "d1"), ("B", "", "")], (5, None)))
    assert snap == {"A": ((0x41,), "d1", 5), "B": ((), "", None)}
    assert mod.snapshot(table([("A", "", "")], None)) == {"A": ((), "", None)}
    for rows, epochs, message in (
        ([("A", "", "")], (1, 2), "cover every"),
        ([("A", "", ""), ("A", "", "")], (1, 2), "duplicate"),
        ([("", "", "")], (1,), "duplicate"),
        ([("A", "", "")], (1.5,), "integers"),
    ):
        with pytest.raises(ValueError, match=message):
            mod.snapshot(table(rows, epochs))


def test_diff_rows_when_all_kinds_then_ordered_and_both_facts_kept(mod):
    first = mod.snapshot(table([("A", "U+0041", "d1"), ("B", "U+0042", "d1"), ("C", "", "")], (1, 1, 1)))
    newest = mod.snapshot(table([("A", "U+0041 U+0061", "d2"), ("B", "U+0042", "d1"), ("D", "", "d3")], (2, 1, 3)))
    rows = mod.diff_rows(first, newest)
    assert [r[0] for r in rows] == ["Added", "Removed", "Re-encoded", "Modified"]
    assert rows[0] == ("Added", "D", "", "(unencoded)") and rows[1] == ("Removed", "C", "(unencoded)", "")
    assert rows[2][2:] == ("U+0041", "U+0041 U+0061") and rows[3][2:] == ("d1 [1 ms]", "d2 [2 ms]")
    assert mod.date_text(((), "", None)) == "(unset)"
    text = mod.diff_text(rows)
    assert text.startswith("Category\tGlyph\tFirst snapshot\tNewest snapshot\n") and text.count("\n") == 5


class World:
    def __init__(self, monkeypatch):
        import fontlabapp.core.scripting as scripting

        self.rows = [("A", "U+0041", "d1")]
        self.package = NS(id=7)
        self.calls = []
        self.fail_after = None
        monkeypatch.setattr(scripting, "current_package", self.current)

    def current(self, expected=None):
        self.calls.append(expected)
        if self.fail_after is not None and len(self.calls) > self.fail_after:
            return None
        return self.package if self.package is not None and expected in (None, self.package.id) else None

    def capture(self):
        return table(list(self.rows))


@pytest.fixture
def panel_world(lab, monkeypatch):  # noqa: F811
    module, shown = lab("diff")
    qt = sys.modules["PythonQt"]
    parent = qt.QtGui.QWidget()
    world = World(monkeypatch)
    yield module, qt, parent, world
    module._PANELS.clear()


def clicker(panel, qt, text):
    [b for b in panel.findChildren(qt.QtGui.QPushButton) if b.text() == text][0].click()


def test_panel_when_opened_then_first_capture_compared_and_buttons_work(panel_world, monkeypatch):
    module, qt, parent, world = panel_world
    panel = module.show(qt, parent, world.capture, embedded=True)
    assert panel in module._PANELS and panel.capture_number == 1
    assert panel.count_line.text().startswith("0 added") and "page 1/1" in panel.count_line.text()
    world.rows = [("A", "U+0041", "d2"), ("B", "", "")]
    hooks = []
    panel.lab_refresh_preview = lambda: hooks.append(1)
    clicker(panel, qt, "Capture Latest")
    assert panel.count_line.text().startswith("1 added · 0 removed · 0 re-encoded · 1 modified")
    assert panel.data_model.rowCount() == 2 and hooks == [1] and panel.capture_number == 2
    clicker(panel, qt, "Reset Baseline")
    assert panel.change_rows == () and panel.capture_number == 1 and panel.data_model.rowCount() == 0


def test_panel_when_many_changes_then_paged_and_copy_gets_all(panel_world, monkeypatch):
    module, qt, parent, world = panel_world
    panel = module.show(qt, parent, world.capture, embedded=True)
    world.rows = [("A", "U+0041", "d1")] + [(f"g{i:03d}", "", "") for i in range(250)]
    panel.capture_latest()
    assert panel.data_model.rowCount() == 100 and "page 1/3" in panel.count_line.text()
    clicker(panel, qt, "Next")
    clicker(panel, qt, "Next")
    clicker(panel, qt, "Next")  # clamped at the last page
    assert panel.data_model.rowCount() == 50 and "page 3/3" in panel.count_line.text()
    clicker(panel, qt, "Previous")
    assert "page 2/3" in panel.count_line.text()
    for _ in range(5):
        panel.change_page(-1)
    assert "page 1/3" in panel.count_line.text()
    copied = []
    monkeypatch.setattr(qt.QtGui.QApplication, "clipboard", staticmethod(lambda: NS(setText=copied.append)))
    clicker(panel, qt, "Copy All Diff")
    assert copied[0].count("\n") == 251 and panel.status_line.text() == "Complete first-to-newest diff copied."
    panel.baseline = None
    with pytest.raises(ValueError, match="baseline"):
        panel.copy_diff()


def test_panel_when_reflowed_page_then_unchanged_cells_reused(panel_world):
    module, qt, parent, world = panel_world
    panel = module.show(qt, parent, world.capture, embedded=True)
    world.rows = [("A", "U+0041", "d1"), ("B", "", "")]
    panel.capture_latest()
    first_item = panel.data_model.item(0, 1)
    panel.display_page()
    assert panel.data_model.item(0, 1) is first_item


def test_panel_when_font_changes_or_read_fails_then_refused_and_state_kept(panel_world):
    module, qt, parent, world = panel_world
    panel = module.show(qt, parent, world.capture, embedded=True)
    kept = panel.baseline
    world.package = NS(id=9)
    panel.perform(panel.capture_latest)
    assert "missing or changed" in panel.status_line.text() and panel.baseline is kept
    panel.perform(panel.reset_baseline)
    assert panel.package_id == 9
    world.package = NS(id=9)
    world.calls.clear()
    world.fail_after = 1
    panel.perform(panel.capture_latest)
    assert "changed during capture" in panel.status_line.text()


def test_show_when_first_capture_fails_then_panel_still_open_with_reason(panel_world):
    module, qt, parent, world = panel_world
    world.package = None
    panel = module.show(qt, parent, world.capture, embedded=True)
    assert "missing or changed" in panel.status_line.text() and panel.baseline is None
    default = module.show(qt, parent, world.capture)  # not embedded: shown
    assert default.isVisible()
    default.close()


def test_show_when_populate_fails_then_panel_closed_and_error_raised(panel_world, monkeypatch):
    module, qt, parent, world = panel_world
    monkeypatch.setattr(qt.QtGui, "QTableView", lambda *a: (_ for _ in ()).throw(RuntimeError("no view")))
    with pytest.raises(RuntimeError, match="no view"):
        module.show(qt, parent, world.capture, embedded=True)
    assert module._PANELS == []


def test_panel_when_destroyed_or_closed_then_released_or_retained(panel_world):
    module, qt, parent, world = panel_world
    panel = module.show(qt, parent, world.capture, embedded=True)
    event = NS(ignored=False, accepted=False)
    event.ignore, event.accept = (lambda: setattr(event, "ignored", True)), (lambda: setattr(event, "accepted", True))
    panel.scope.finish = lambda destroyed=False: False
    panel.closeEvent(event)
    assert event.ignored and panel in module._PANELS
    del panel.scope.finish
    panel.owner_destroyed()
    assert panel not in module._PANELS
    panel.closeEvent(event)
    assert event.accepted


def test_close_button_calls_lab_close(panel_world):
    module, qt, parent, world = panel_world
    panel = module.show(qt, parent, world.capture, embedded=True)
    calls = []
    panel.lab_close = lambda: calls.append(1)
    clicker(panel, qt, "Close")
    assert calls == [1]


def test_main_and_build(panel_world, monkeypatch):
    module, qt, parent, world = panel_world
    import fontlabapp.glyphs.catalog.model as catalogue
    import fontlabapp.qt.dialogs as dialogs

    monkeypatch.setattr(catalogue, "capture", world.capture)
    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: parent))
    assert module.build(None) in module._PANELS
    seen = []
    monkeypatch.setattr(module, "show", lambda q, p: "panel")
    assert module.main() == "panel"
    monkeypatch.setattr(module, "show", lambda q, p: (_ for _ in ()).throw(ValueError("nope")))
    monkeypatch.setattr(dialogs, "run_standard_message_box", lambda *a: seen.append(a[1:4]))
    assert module.main() is None
    assert seen[0][1:] == (module.TITLE, "nope")


def test_panel_when_changes_fill_exactly_one_page_then_single_page(panel_world):
    module, qt, parent, world = panel_world
    panel = module.show(qt, parent, world.capture, embedded=True)
    world.rows = [("A", "U+0041", "d1")] + [(f"g{i:03d}", "", "") for i in range(100)]  # 100 added glyphs = PAGE_SIZE changes
    panel.capture_latest()
    assert panel.data_model.rowCount() == 100 and "page 1/1" in panel.count_line.text()
    clicker(panel, qt, "Next")
    assert panel.data_model.rowCount() == 100 and "page 1/1" in panel.count_line.text()
