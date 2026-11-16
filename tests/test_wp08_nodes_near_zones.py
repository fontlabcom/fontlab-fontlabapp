# this_file: tests/test_wp08_nodes_near_zones.py
"""S66 Nodes Near Zones: App-owned scan/render, tolerance rescans and glyph selection."""

import importlib
import sys
from types import SimpleNamespace as NS

import pytest
from _studio_qt import studio_qt  # noqa: F401

from fontlabapp.qt import properties as props

MODS = ("fontlabapp.contours.nodes_near_zones.model", "fontlabapp.contours.nodes_near_zones.native",
        "fontlabapp.fontui.nodes_near_zones")


class Pt:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


def node(x, y, on=True):
    return NS(x=x, y=y, isOn=lambda: on)


def shape(*nodes, component=None, data=True, shift=0):
    contour = NS(nodes=lambda: list(nodes))
    return NS(shapeData=NS(componentGlyph=component) if data else None, getContours=lambda: [contour],
              transform=NS(map=lambda p: Pt(p.x(), p.y() + shift)))


class Glyph:
    def __init__(self, layers):
        self.layers = layers

    def findLayer(self, master):
        return self.layers.get(master)


METRICS = NS(xHeight=500, capsHeight=700, ascender=750, descender=-250)


def fake_package(package_id=7):
    near = shape(node(10, 2), node(20, 500), node(30, 497), node(40, 100, on=False), node(50, 3, on=False))
    skipped = shape(node(1, 1), component="a")
    shifted = shape(node(5, 0), shift=-3)
    glyphs = {"a": Glyph({"M1": NS(shapes=[near, skipped]), "M2": None}),
              "b": Glyph({"M1": NS(shapes=[shifted, shape(node(9, 9), data=False)])})}
    return NS(id=package_id, masters=["M1", "M2"], findName=glyphs.get)


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


def scanned(model, tolerance=4):
    return model.scan(fake_package(), ["a", "b", "gone"], tolerance, lambda master: METRICS, Pt)


def test_scan_when_nodes_near_zones_then_off_curve_components_and_exact_hits_skipped(mods):
    model = mods[0]
    rows = scanned(model)
    assert rows == (("a", "M1", "baseline", 0.0, 10, 2), ("a", "M1", "x-height", 500, 30, 497),
                    ("b", "M1", "baseline", 0.0, 5, -3))
    assert model.scan(fake_package(), ["a"], 1, lambda master: METRICS, Pt) == ()


def test_render_when_rows_then_signed_offsets_and_summary(mods):
    model = mods[0]
    report = model.NodesNearZonesReport(7, 3, 2, 4, scanned(model))
    lines = model.render(report).splitlines()
    assert lines[0] == "Glyph\tMaster\tZone\tZone y\tNode x\tNode y\tOff by"
    assert "a\tM1\tx-height\t500\t30\t497\t-3" in lines and "a\tM1\tbaseline\t0\t10\t2\t+2" in lines
    assert model.summary(report) == "3 near misses in 2 glyphs within 4 units (3 glyphs x 2 masters)."
    one = model.NodesNearZonesReport(7, 1, 1, 4, (("a", "M1", "baseline", 0.0, 1, 1),))
    assert model.summary(one) == "1 near miss in 1 glyph within 4 units (1 glyph x 1 masters)."
    none = model.NodesNearZonesReport(7, 2, 2, 1, ())
    assert model.summary(none) == "No nodes within 1 units of a zone (2 glyphs x 2 masters)."


def test_selected_names_when_selection_then_names_else_empty_on_native_errors(mods, monkeypatch):
    native = mods[1]
    font = [NS(name="a"), NS(name="b"), NS(name="c")]
    fl = NS(font=font, Selected=lambda i: i != 1)
    monkeypatch.setattr(native, "_native", lambda name: NS(fl=fl))
    assert native.selected_names() == ["a", "c"]

    def broken(name):
        raise RuntimeError("no FL")
    monkeypatch.setattr(native, "_native", broken)
    assert native.selected_names() == []


def test_capture_when_no_font_then_error(mods, monkeypatch):
    native = mods[1]
    monkeypatch.setattr(native.scripting, "current_package", lambda: None)
    with pytest.raises(ValueError, match="Open a font first."):
        native.capture(4)


@pytest.mark.parametrize(("selection", "expected"), [(["a"], 1), ([], 3)])
def test_capture_when_selection_then_selected_else_all_glyphs(mods, monkeypatch, selection, expected):
    native = mods[1]
    package = fake_package(9)
    fontlab = NS(CurrentFont=lambda: NS(glyphs=[NS(name="a"), NS(name="b"), NS(name="gone")]),
                 FontMetrics=lambda pkg, master: METRICS)
    monkeypatch.setattr(native.scripting, "current_package", lambda: package)
    monkeypatch.setattr(native, "selected_names", lambda: selection)
    natives = {"fontlab": fontlab, "PythonQt": NS(QtCore=NS(QPointF=Pt))}
    monkeypatch.setattr(native, "_native", natives.__getitem__)
    report = native.capture(4)
    assert native.capture(4, True).glyphs == 3
    assert report.package_id == 9 and report.glyphs == expected and report.masters == 2
    assert report.tolerance == 4 and report.rows[0][:3] == ("a", "M1", "baseline")


def test_select_when_report_then_unique_glyph_names_selected_in_scanned_font(mods, monkeypatch):
    model, native, _ = mods
    calls = []
    monkeypatch.setattr(native.scripting, "select_glyphs",
                        lambda names, *, package_id: calls.append((list(names), package_id)) or list(names))
    rows = (("a", "M1", "baseline", 0.0, 1, 1), ("a", "M1", "x-height", 5, 1, 1), ("b", "M1", "baseline", 0.0, 1, 1))
    assert native.select(model.NodesNearZonesReport(9, 2, 2, 4, rows)) == ["a", "b"]
    assert calls == [(["a", "b"], 9)]


def test_show_when_opened_then_tolerance_change_rescans_and_select_selects(mods, monkeypatch):
    model, native, ui = mods
    seen, selected, scopes = [], [], []

    def capture(tolerance, whole_font=False):
        seen.append(tolerance)
        scopes.append(whole_font)
        return model.NodesNearZonesReport(7, 3, 2, tolerance, scanned(model, tolerance))
    monkeypatch.setattr(native, "capture", capture)
    monkeypatch.setattr(native, "select", lambda r: selected.append(r) or ["a", "b"])
    shell = ui.show()
    tab = shell.snapshot_tabs[0]
    assert seen[0] == 4 and props.value(tab.tolerance, "value") == 4 and tab.select_button.isEnabled()
    assert "a\tM1\tx-height\t500\t30\t497\t-3" in tab.output.toPlainText()
    tab.tolerance.setValue(1)
    assert seen[-1] == 1 and shell.status.text().startswith("No nodes within 1 units")
    assert not tab.select_button.isEnabled()
    tab.tolerance.setValue(4)
    tab.scope.setCurrentIndex(1)
    assert scopes[-1] is True
    tab.scope.setCurrentIndex(0)
    assert scopes[-1] is False
    assert (tab.tolerance.minimum(), tab.tolerance.maximum()) == (1, 30)
    tab.select()
    assert len(selected) == 1 and shell.status.text() == "Selected 2 glyphs."


def test_select_when_stale_or_refused_then_reason_shown(mods, monkeypatch):
    model, native, ui = mods
    state = {"fail": False}

    def capture(tolerance, whole_font=False):
        if state["fail"]:
            raise ValueError("Open a font first.")
        return model.NodesNearZonesReport(7, 3, 2, tolerance, scanned(model))

    def refuse(report):
        raise ValueError("stale font")
    monkeypatch.setattr(native, "capture", capture)
    monkeypatch.setattr(native, "select", refuse)
    shell = ui.show()
    tab = shell.snapshot_tabs[0]
    tab.select()
    assert shell.status.text() == "stale font"
    state["fail"] = True
    tab.refresh()
    assert tab.report is None and not tab.select_button.isEnabled()
    tab.select()
    assert shell.status.text() == "Refresh the report with an open font first."


def test_scan_when_node_exactly_at_tolerance_then_included_and_beyond_excluded(mods):
    model = mods[0]
    pkg = NS(id=1, masters=["M1"], findName=lambda n: Glyph({"M1": NS(shapes=[shape(node(0, 4), node(1, 5))])}))
    rows = model.scan(pkg, ["a"], 4, lambda m: METRICS, Pt)
    assert [r[2:] for r in rows] == [("baseline", 0.0, 0, 4)]


def test_scan_when_many_glyphs_then_metrics_read_once_per_master(mods):
    model = mods[0]
    calls = []
    model.scan(fake_package(), ["a", "b", "a"], 4, lambda m: calls.append(m) or METRICS, Pt)
    assert sorted(calls) == ["M1"]


def test_table_when_shown_then_rows_and_double_click_selects_one_glyph(mods, monkeypatch):
    model, native, ui = mods
    calls = []
    monkeypatch.setattr(native, "capture", lambda tolerance, whole_font=False: model.NodesNearZonesReport(7, 3, 2, tolerance, scanned(model, tolerance)))
    monkeypatch.setattr(native, "select", lambda r, names=None: calls.append(names) or (names or ["a", "b"]))
    shell = ui.show()
    tab = shell.snapshot_tabs[0]
    assert tab.table.rowCount() == len(tab.report.rows) > 0
    first = tab.report.rows[0][0]
    tab.table.cellDoubleClicked.emit(0, 0)
    assert calls[-1] == [first] and shell.status.text() == "Selected 1 glyph."
    tab.select()
    assert calls[-1] is None


def test_table_when_shown_then_text_pane_hidden_but_populated(mods, monkeypatch):
    """F41-1 (R41): the table is the one visible result list; the text stays filled."""
    model, native, ui = mods
    monkeypatch.setattr(native, "capture", lambda tolerance, whole_font=False: model.NodesNearZonesReport(7, 3, 2, tolerance, scanned(model, tolerance)))
    tab = ui.show().snapshot_tabs[0]
    assert tab.output.isHidden() and not tab.table.isHidden()
    assert "a\tM1\tx-height\t500\t30\t497\t-3" in tab.output.toPlainText()


def test_native_select_when_names_given_then_only_named_glyphs_are_selected(monkeypatch):
    model = importlib.import_module("fontlabapp.contours.nodes_near_zones.model")
    native = importlib.import_module("fontlabapp.contours.nodes_near_zones.native")
    seen = []
    monkeypatch.setattr(
        native.scripting, "select_glyphs", lambda names, package_id: seen.append((names, package_id)) or names
    )
    rows = (("a", "M1", "x-height", 500.0, 1.0, 502.0), ("b", "M1", "baseline", 0.0, 1.0, 1.0),
            ("a", "M1", "baseline", 0.0, 2.0, 2.0))
    report = model.NodesNearZonesReport(9, 2, 1, 4, rows)
    assert native.select(report, ["b"]) == ["b"]
    assert native.select(report, []) == []
    assert native.select(report) == ["a", "b"]
    assert seen == [(["b"], 9), ([], 9), (["a", "b"], 9)]


def test_table_when_shown_then_hint_and_numeric_columns_right_aligned(mods, monkeypatch):
    model, native, ui = mods
    monkeypatch.setattr(native, "capture", lambda tolerance, whole_font=False: model.NodesNearZonesReport(7, 3, 2, tolerance, scanned(model, tolerance)))
    shell = ui.show()
    tab = shell.snapshot_tabs[0]
    assert tab.hint.text() == "Double-click a row to select its glyph."
    align = [bool(tab.table.item(0, c).textAlignment() & 0x2) for c in range(7)]  # Qt.AlignRight
    assert align == [False, False, False, True, True, True, True]
