# this_file: tests/test_wp08_open_contours.py
"""S65 Open Contours: App-owned scan/render and a shell tab that selects the scanned glyphs."""

import importlib
import sys
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401

MODS = ("fontlabapp.contours.open_contours.model", "fontlabapp.contours.open_contours.native",
        "fontlabapp.fontui.open_contours")


def node(x, y):
    return NS(x=x, y=y)


def contour(closed, *points):
    return NS(closed=closed, nodes=lambda: [node(*p) for p in points])


class Glyph:
    def __init__(self, layers):
        self.layers = layers

    def findLayer(self, master):
        return self.layers.get(master)


def fake_package(package_id=7):
    open_two = contour(False, (0, 0), (3, 4))
    single = contour(False, (5, 5))
    glyphs = {"a": Glyph({"M1": NS(getContours=lambda: [contour(True, (0, 0), (1, 1)), open_two]),
                          "M2": None}),
              "b": Glyph({"M1": NS(getContours=lambda: [single])}),
              "c": Glyph({"M1": NS(getContours=lambda: [contour(True, (0, 0))])})}
    return NS(id=package_id, masters=["M1", "M2"], findName=glyphs.get)


FONT = NS(glyphs=[NS(name=n) for n in ("a", "b", "c", "gone")])


@pytest.fixture
def mods(studio_qt, monkeypatch):  # noqa: F811
    for name in MODS:
        monkeypatch.delitem(sys.modules, name, raising=False)
    loaded = [importlib.import_module(n) for n in MODS]
    yield loaded
    for shell in tuple(sys.modules["fontlabapp.fontui.snapshot_audit"]._HANDLES):
        shell.close()
    for name in MODS:
        sys.modules.pop(name, None)


def test_scan_when_open_contours_then_rows_with_gap_and_counts(mods):
    model = mods[0]
    rows = model.scan(FONT, fake_package())
    assert rows == (("a", "M1", 1, 2, 5.0), ("b", "M1", 0, 1, 0.0))


def test_render_when_rows_then_table_text_and_summary(mods):
    model = mods[0]
    report = model.OpenContoursReport(7, 2, model.scan(FONT, fake_package()))
    text = model.render(report)
    assert text.splitlines()[0] == "Glyph\tMaster\tContour\tNodes\tEnd gap"
    assert "a\tM1\t#2\t2\t5.0" in text and "b\tM1\t#1\t1\t0.0" in text
    assert model.summary(report) == "2 open contours in 2 glyphs across 2 masters."
    assert model.summary(model.OpenContoursReport(7, 1, ())) == "No open contours on any of 1 masters."
    one = model.OpenContoursReport(7, 1, (("a", "M1", 0, 2, 1.0),))
    assert model.summary(one) == "1 open contour in 1 glyph across 1 masters."


def test_capture_when_no_font_then_error(mods, monkeypatch):
    native = mods[1]
    monkeypatch.setattr(native.scripting, "current_package", lambda: None)
    with pytest.raises(ValueError, match="Open a font first."):
        native.capture()


def test_capture_when_font_then_report_bound_to_package_id(mods, monkeypatch):
    native = mods[1]
    monkeypatch.setattr(native.scripting, "current_package", lambda: fake_package(9))
    monkeypatch.setattr(native, "_native", lambda name: NS(CurrentFont=lambda: FONT))
    report = native.capture()
    assert report.package_id == 9 and report.masters == 2 and len(report.rows) == 2


def test_select_when_report_then_unique_glyph_names_selected_in_scanned_font(mods, monkeypatch):
    native = mods[1]
    calls = []
    monkeypatch.setattr(native.scripting, "select_glyphs",
                        lambda names, *, package_id: calls.append((list(names), package_id)) or list(names))
    model = mods[0]
    report = model.OpenContoursReport(9, 2, (("a", "M1", 0, 2, 1.0), ("a", "M1", 1, 2, 1.0), ("b", "M1", 0, 1, 0.0)))
    assert native.select(report) == ["a", "b"] and calls == [(["a", "b"], 9)]


def test_show_when_opened_then_report_rendered_and_select_button_selects(mods, monkeypatch):
    model, native, ui = mods
    report = model.OpenContoursReport(7, 2, model.scan(FONT, fake_package()))
    selected = []
    monkeypatch.setattr(native, "capture", lambda: report)
    monkeypatch.setattr(native, "select", lambda r: selected.append(r) or ["a", "b"])
    shell = ui.show()
    tab = shell.snapshot_tabs[0]
    assert "a\tM1\t#2\t2\t5.0" in tab.output.toPlainText()
    assert shell.status.text().startswith("2 open contours in 2 glyphs")
    assert tab.select_button.isEnabled()
    tab.select()
    assert selected == [report] and shell.status.text() == "Selected 2 glyphs."


def test_refresh_when_capture_fails_then_selection_refused(mods, monkeypatch):
    model, native, ui = mods
    report = model.OpenContoursReport(7, 2, (("a", "M1", 0, 2, 1.0),))
    state = {"fail": False}

    def capture():
        if state["fail"]:
            raise ValueError("Open a font first.")
        return report
    monkeypatch.setattr(native, "capture", capture)
    monkeypatch.setattr(native, "select", lambda r: pytest.fail("must not select"))
    shell = ui.show()
    tab = shell.snapshot_tabs[0]
    state["fail"] = True
    tab.refresh()
    assert tab.report is None and not tab.select_button.isEnabled()
    assert tab.output.toPlainText() == "" and shell.status.text() == "Open a font first."
    tab.select()
    assert shell.status.text() == "Refresh the report with an open font first."


def test_select_when_native_refuses_then_reason_shown(mods, monkeypatch):
    model, native, ui = mods
    report = model.OpenContoursReport(7, 2, (("a", "M1", 0, 2, 1.0),))
    monkeypatch.setattr(native, "capture", lambda: report)

    def refuse(r):
        raise ValueError("stale font")
    monkeypatch.setattr(native, "select", refuse)
    shell = ui.show()
    shell.snapshot_tabs[0].select()
    assert shell.status.text() == "stale font"


def test_show_when_no_open_contours_then_select_disabled(mods, monkeypatch):
    model, native, ui = mods
    monkeypatch.setattr(native, "capture", lambda: model.OpenContoursReport(7, 3, ()))
    shell = ui.show()
    assert not shell.snapshot_tabs[0].select_button.isEnabled()
    assert shell.status.text() == "No open contours on any of 3 masters."


def test_scan_when_glyph_has_two_open_contours_and_fractional_gap_then_rounded_rows_and_distinct_count(mods):
    model = mods[0]
    glyph = Glyph({"M1": NS(getContours=lambda: [contour(False, (0, 0), (1, 1)), contour(False, (0, 0), (0, 2.26))])})
    package = NS(id=1, masters=["M1"], findName={"d": glyph}.get)
    rows = model.scan(NS(glyphs=[NS(name="d")]), package)
    assert rows == (("d", "M1", 0, 2, 1.4), ("d", "M1", 1, 2, 2.3))
    report = model.OpenContoursReport(1, 1, rows)
    assert "d\tM1\t#1\t2\t1.4" in model.render(report)
    assert model.summary(report) == "2 open contours in 1 glyph across 1 masters."


def test_about_when_read_then_original_credit_and_no_parity_gap(mods):
    about = mods[2].ABOUT
    assert "Not yet restored" not in about and "Cozens" not in about and "FontLab App contributors" in about


def test_table_when_shown_then_rows_red_gaps_click_and_double_click_select(mods, monkeypatch):
    model, native, ui = mods
    rows = (("a", "M1", 0, 2, 1.5), ("b", "M1", 1, 3, 0.0), ("c", "M1", 0, 4, 2.0))
    report = model.OpenContoursReport(7, 1, rows)
    calls = []
    monkeypatch.setattr(native, "capture", lambda: report)
    monkeypatch.setattr(native, "select", lambda r, names=None: calls.append(names) or (names or ["a", "b", "c"]))
    shell = ui.show()
    tab = shell.snapshot_tabs[0]
    assert tab.table.rowCount() == 3 and tab.table.item(0, 0).text() == "a"
    assert tab.table.item(0, 2).text() == "#1" and tab.table.item(0, 4).text() == "1.5"
    red = [tab.table.item(r, 4).foreground().color().name() for r in range(3)]
    assert red[0] == "#dd3333" and red[2] == "#dd3333" and red[1] != "#dd3333"
    tab.select()
    assert calls[-1] is None and shell.status.text() == "Selected 3 glyphs."
    tab.table.selectRow(2)
    tab.select()
    assert calls[-1] == ["c"] and shell.status.text() == "Selected 1 glyph."
    tab.table.cellDoubleClicked.emit(1, 0)
    assert calls[-1] == ["b"]


def test_native_select_when_names_given_then_only_named_glyphs_are_selected(monkeypatch):
    model = importlib.import_module("fontlabapp.contours.open_contours.model")
    native = importlib.import_module("fontlabapp.contours.open_contours.native")
    seen = []
    monkeypatch.setattr(
        native.scripting, "select_glyphs", lambda names, package_id: seen.append((names, package_id)) or names
    )
    rows = (("a", "M1", 0, 2, 1.0), ("a", "M1", 1, 2, 1.0), ("b", "M1", 0, 1, 0.0), ("c", "M1", 0, 1, 0.0))
    report = model.OpenContoursReport(9, 1, rows)
    assert native.select(report, ["b"]) == ["b"]
    assert native.select(report, []) == []
    assert native.select(report) == ["a", "b", "c"]
    assert seen == [(["b"], 9), ([], 9), (["a", "b", "c"], 9)]


def test_table_when_shown_then_hint_and_numeric_columns_right_aligned(mods, monkeypatch):
    model, native, ui = mods
    report = model.OpenContoursReport(7, 2, model.scan(FONT, fake_package()))
    monkeypatch.setattr(native, "capture", lambda: report)
    shell = ui.show()
    tab = shell.snapshot_tabs[0]
    assert tab.hint.text() == "Double-click a row to select its glyph."
    align = [[bool(tab.table.item(0, c).textAlignment() & 0x2) for c in range(5)]]  # Qt.AlignRight
    assert align == [[False, False, False, True, True]]


def test_show_when_opened_then_text_pane_hidden_but_populated(mods, monkeypatch):
    """F41-1 (R41): the table is the one visible result list; the text stays filled."""
    model, native, ui = mods
    report = model.OpenContoursReport(7, 2, model.scan(FONT, fake_package()))
    monkeypatch.setattr(native, "capture", lambda: report)
    tab = ui.show().snapshot_tabs[0]
    assert tab.output.isHidden() and not tab.table.isHidden()
    assert "a\tM1\t#2\t2\t5.0" in tab.output.toPlainText()
