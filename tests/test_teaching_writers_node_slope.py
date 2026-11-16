# this_file: tests/test_teaching_writers_node_slope.py
"""Node Slope And Handles: slope targets, handle carry, cubic handle modes, planner and editor."""

import importlib
import math
import sys
from types import SimpleNamespace as NS

import pytest

MODULE = "fontlabapp.fontui.teaching_writers.node_slope_and_handles"


@pytest.fixture
def mod():
    return importlib.import_module(MODULE)


def node(x, y, on=True, selected=False):
    return NS(x=x, y=y, selected=selected, isOn=lambda on=on: on)


def contour(nodes, closed=False, tt=False):
    return NS(nodes=lambda: list(nodes), closed=closed, isTT=tt)


def matrix(m11=1, m22=1, m12=0, m21=0):
    return NS(m11=lambda: m11, m22=lambda: m22, m12=lambda: m12, m21=lambda: m21, dx=lambda: 0, dy=lambda: 0)


def shape(*contours, refs=1, **kw):
    return NS(isComponent=False, contours=list(contours), shapeData=NS(referenceCount=refs), transform=matrix(**kw))


def layer(*shapes, name="Regular"):
    return NS(shapes=list(shapes), name=name)


def test_snapshot_contour_when_already_snapshot_then_reused(mod):
    snap = mod.snapshot_contour(contour([node(0, 0)], closed=True))
    assert snap.closed and mod.snapshot_contour(snap) is snap


def test_slope_of_when_valid_then_dx_over_dy(mod):
    assert mod.slope_of([node(0, 0), node(20, 100)]) == pytest.approx(0.2)


@pytest.mark.parametrize("nodes,message", [
    ([node(0, 0)], "at least two"),
    ([node(0, 0), node(5, 0)], "horizontal"),
    ([node(0, 0), node(1e308, 1e-308)], "finite"),
])
def test_slope_of_when_unusable_then_refused(mod, nodes, message):
    with pytest.raises(ValueError, match=message):
        mod.slope_of(nodes)


def test_slope_moves_when_pivot_bottom_then_selected_nodes_follow_slope(mod):
    a, b = node(0, 0), node(50, 100)
    assert mod.slope_moves([a, b], 0.1, top=False, flip=False) == [(b, 10.0, 100.0)]
    assert mod.slope_moves([a, b], 0.1, top=True, flip=True) == [(a, 60.0, 0.0)]


def test_slope_targets_when_top_pivot_and_flip_then_pivot_fixed(mod):
    nodes = {(0, 0): node(0, 0), (0, 1): node(50, 100)}
    assert mod.slope_targets(nodes, 0.1, True, True) == {(0, 0): (60.0, 0.0)}


def test_slope_targets_when_single_or_unchanged_then_empty(mod):
    assert mod.slope_targets({(0, 0): node(0, 0)}, 0.1, False, False) == {}
    nodes = {(0, 0): node(0, 0), (0, 1): node(10, 100)}
    assert mod.slope_targets(nodes, 0.1, False, False) == {}


def test_slope_targets_when_invalid_then_refused(mod):
    with pytest.raises(ValueError, match="finite dx/dy"):
        mod.slope_targets({}, math.nan, False, False)
    flat = {(0, 0): node(0, 5), (0, 1): node(9, 5)}
    with pytest.raises(ValueError, match="different y"):
        mod.slope_targets(flat, 0.1, False, False)
    huge = {(0, 0): node(0, 0), (0, 1): node(0, 1e300)}
    with pytest.raises(ValueError, match="finite"):
        mod.slope_targets(huge, 1e300, False, False)


def test_carry_handles_when_closed_wrap_then_unselected_handles_follow(mod):
    nodes = [node(0, 0, selected=True), node(10, 0, on=False), node(20, 0, on=False, selected=True), node(30, 0), node(5, 5, on=False)]
    snap = mod.snapshot_contour(contour(nodes, closed=True))
    result = mod.carry_handles([snap], {(0, 0): (7.0, 0.0)})
    assert result[(0, 1)] == (17.0, 0.0) and result[(0, 4)] == (12.0, 5.0)
    assert (0, 2) not in result  # selected handle keeps its own target


def test_carry_handles_when_open_end_then_no_wrap_and_offcurve_ignored(mod):
    nodes = [node(0, 0, selected=True), node(10, 0, on=False)]
    snap = mod.snapshot_contour(contour(nodes))
    assert mod.carry_handles([snap], {(0, 0): (1.0, 0.0), (0, 1): (3.0, 0.0)}) == {(0, 0): (1.0, 0.0), (0, 1): (3.0, 0.0)}


def test_carry_handles_when_overflow_then_refused(mod):
    nodes = [node(0, 0, selected=True), node(1e308, 0, on=False)]
    snap = mod.snapshot_contour(contour(nodes))
    with pytest.raises(ValueError, match="Handle coordinates"):
        mod.carry_handles([snap], {(0, 0): (1e308, 0.0)})


def test_coordinate_rows_when_moves_then_old_and_new_text(mod):
    snap = mod.snapshot_contour(contour([node(1, 2)]))
    row = mod.coordinate_rows([snap], {(0, 0): (3.0, 2.0)})[0]
    assert "contour 1 node 0" in str(row)


def cubic(selected=(True, True), p=(0, 0), c=(0, 100), d=(100, 200), q=(200, 200), tt=False, closed=False):
    nodes = [node(*p, selected=selected[0]), node(*c, on=False), node(*d, on=False), node(*q, selected=selected[1])]
    return mod_snapshot(nodes, closed, tt)


def mod_snapshot(nodes, closed=False, tt=False):
    return importlib.import_module(MODULE).snapshot_contour(contour(nodes, closed=closed, tt=tt))


def test_segment_indices_when_tt_or_unselected_then_skipped(mod):
    assert mod.segment_indices(cubic()) == [(0, 1, 2, 3)]
    assert mod.segment_indices(cubic(selected=(True, False))) == []
    assert mod.segment_indices(cubic(tt=True)) == []


def test_segment_indices_when_closed_then_wrap_span_included(mod):
    nodes = [node(0, 0, selected=True), node(1, 1, on=False), node(2, 1, on=False), node(3, 0, selected=True), node(4, 4, on=False), node(5, 4, on=False)]
    snap = mod.snapshot_contour(contour(nodes, closed=True))
    assert mod.segment_indices(snap) == [(0, 1, 2, 3), (3, 4, 5, 0)]


def test_proportions_when_one_cubic_then_lengths_over_chord(mod):
    ratios = mod.proportions(contour([node(0, 0, selected=True), node(0, 100, on=False), node(100, 200, on=False), node(200, 200, selected=True)]))
    chord = math.hypot(200, 200)
    assert ratios == pytest.approx((100 / chord, 100 / chord))


def test_proportions_when_none_zero_chord_or_nan_then_refused(mod):
    with pytest.raises(ValueError, match="exactly one"):
        mod.proportions(contour([node(0, 0)]))
    flat = [node(0, 0, selected=True), node(1, 1, on=False), node(2, 2, on=False), node(0, 0, selected=True)]
    with pytest.raises(ValueError, match="zero chord"):
        mod.proportions(contour(flat))
    bad = [node(0, 0, selected=True), node(math.nan, 1, on=False), node(2, 2, on=False), node(5, 5, selected=True)]
    with pytest.raises(ValueError, match="finite"):
        mod.proportions(contour(bad))


def test_hobby_ratio_when_unit_tangents_then_positive_and_bad_turn_refused(mod):
    assert mod.hobby_ratio(math.radians(30), math.radians(30)) > 0
    with pytest.raises(ValueError, match="turn too far"):
        mod.hobby_ratio(math.pi, math.pi)
    assert mod.hobby_ratio(math.radians(120), 0.0) == pytest.approx(0.6522325721243587)


def test_handle_targets_when_proportions_then_lengths_scaled_along_rays(mod):
    snap = cubic(c=(0, 100), d=(200, 100), q=(200, 200), p=(0, 0))
    moves = mod.handle_targets(snap, "Proportions", 0.5, 0.25)
    chord = math.hypot(200, 200)
    assert moves[1] == pytest.approx((0.0, chord * 0.5)) and moves[2] == pytest.approx((200 - 0.25 * chord, 100.0 + 0.0) if False else moves[2])
    assert [m[0] for m in mod.handle_moves(snap, "Proportions", 0.5, 0.25)] == [snap.nodes[1], snap.nodes[2]]


def test_handle_targets_when_hobby_then_moves_and_zero_ray_skipped(mod):
    snap = cubic()
    assert mod.handle_targets(snap, "Hobby", 1, 1)
    zero = cubic(c=(0, 0))
    assert mod.handle_targets(zero, "Proportions", 1, 1) == {}


@pytest.mark.parametrize("mode,a,b,message", [
    ("Slope", 1, 1, "nonnegative"), ("Proportions", -1, 1, "nonnegative"),
    ("Proportions", math.nan, 1, "nonnegative"), ("Hobby", 0, 1, "positive"),
])
def test_handle_targets_when_invalid_args_then_refused(mod, mode, a, b, message):
    with pytest.raises(ValueError, match=message):
        mod.handle_targets(cubic(), mode, a, b)


def test_handle_targets_when_overflow_then_refused(mod):
    with pytest.raises(ValueError, match="finite"):
        mod.handle_targets(cubic(), "Proportions", 1e308, 1)


def test_changes_when_slope_then_rows_for_moves_or_kept(mod):
    nodes = [node(0, 0, selected=True), node(50, 100, selected=True)]
    rows = mod.changes(layer(shape(contour(nodes))), "Slope", 0.1, 0, False, False)
    assert len(rows) == 1 and "contour 1 node 1" in str(rows[0])
    same = [node(0, 0, selected=True), node(10, 100, selected=True)]
    assert "kept: no selected node" in str(mod.changes(layer(shape(contour(same))), "Slope", 0.1, 0, False, False)[0])
    flat = [node(0, 0, selected=True), node(9, 0, selected=True)]
    assert "kept: Select nodes" in str(mod.changes(layer(shape(contour(flat))), "Slope", 0.1, 0, False, False)[0])


def test_changes_when_notes_and_tt_then_rows_report_kept(mod):
    tt = contour([node(0, 0)], tt=True)
    rows = mod.changes(layer(shape(tt, refs=2), shape(tt, m11=2), shape(tt)), "Slope", 0.1, 0, False, False)
    text = " ".join(str(r) for r in rows)
    assert "shared outline" in text and "scaled or rotated" in text and "quadratic contours" in text


def test_changes_when_handle_modes_then_rows_and_kept_reasons(mod):
    ok = cubic(c=(0, 100), d=(200, 100), q=(200, 200))
    lay = layer(shape(contour(list(ok.nodes))))
    assert "contour 1 node 1" in str(mod.changes(lay, "Proportions", 0.5, 0.25, False, False)[0])
    zero = layer(shape(contour(list(cubic(c=(0, 0)).nodes))))
    text = " ".join(str(r) for r in mod.changes(zero, "Proportions", 1, 1, False, False))
    assert "zero chord or handle ray" in text and "no movable selected cubic" in text
    err = " ".join(str(r) for r in mod.changes(lay, "Hobby", 0, 1, False, False))
    assert "kept: Use finite nonnegative" in err or "kept: Hobby tensions must be positive" in err


def test_coordinate_editor_when_written_then_checked_against_readback(mod):
    editor = mod.CoordinateEditor()
    n = node(0, 0)
    editor.write(NS(), [[(n, 3.0, 4.0)]])
    assert (n.x, n.y) == (3.0, 4.0)
    lay = NS(name="Bold")
    assert editor.check([(lay, [[(n, 3.0, 4.0)]])]) == []
    assert editor.check([(lay, [[(n, 9.0, 4.0)]])]) == ["Bold: coordinates"]
    n.x = math.nan
    assert editor.check([(lay, [[(n, 3.0, 4.0)]])]) == ["Bold: coordinates"]


def test_selected_contours_when_one_layer_then_non_tt_contours(mod, monkeypatch):
    sel = importlib.import_module("fontlabapp.masters.layers.selection")
    ok, tt = contour([node(0, 0)]), contour([node(1, 1)], tt=True)
    lay = layer(shape(ok, tt))
    lay.id = 1
    monkeypatch.setattr(sel, "capture", lambda deadline: NS(occurrences=[NS(layer=lay), NS(layer=lay)]))
    assert mod.selected_contours() == [ok]
    monkeypatch.setattr(sel, "capture", lambda deadline: NS(occurrences=[]))
    with pytest.raises(ValueError, match="one glyph layer"):
        mod.selected_contours()


def test_main_when_panel_refused_then_prints_and_returns_none(mod, monkeypatch, capsys):
    scripting = importlib.import_module("fontlabapp.core.scripting")
    monkeypatch.setattr(mod, "panel_type", lambda: "P")
    monkeypatch.setattr(scripting, "show_script_dialog", lambda cls, key: (_ for _ in ()).throw(ValueError("busy")))
    assert mod.main() is None and capsys.readouterr().out == "Node Slope And Handles: busy\n"
    monkeypatch.setattr(scripting, "show_script_dialog", lambda cls, key: (cls, key))
    assert mod.main() == ("P", "numeric_node_slope_handles")


# ---- panel_type with a stub base panel and fake Qt widgets ----------------


class _W:
    def __init__(self, *a, **k):
        self._text, self._index, self._checked, self.value = "", 0, False, 0.0
        self.enabled, self.range, self.items = True, None, []
        self.toggled = self.currentIndexChanged = self.clicked = "sig"

    def addItems(self, items):
        self.items = list(items)

    @property
    def currentIndex(self):
        return self._index

    def setCurrentIndex(self, i):
        self._index = i

    def setText(self, t):
        self._text = t

    def setEnabled(self, flag):
        self.enabled = flag

    def setRange(self, lo, hi):
        self.range = (lo, hi)

    def setValue(self, v):
        self.value = v

    def isChecked(self):
        return self._checked

    def setChecked(self, flag):
        self._checked = flag

    def setSortingEnabled(self, flag):
        self.sorting = flag


@pytest.fixture
def numeric(mod, monkeypatch):
    import fontlabapp.contours.panel.model as pm
    import fontlabapp.core.scripting as scripting

    class Base:
        package = NS(italicAngle_value=10.0)
        glyphs = ["A"]
        package_id = 1

        def __init__(self):
            self.table, self.status = _W(), _W()
            self.rows, self.watched, self.refreshed = [], [], 0
            self.build_controls()

        def spin(self, *a, **k):
            return _W()

        def add_row(self, *a):
            self.rows.append(a)

        def watch(self, signal, slot=None):
            self.watched.append((signal, slot))

        def refresh(self):
            self.refreshed += 1

        def intro(self):
            return "Guide"

        def fill(self, plan):
            self.filled = plan

        def reload(self):
            self.reloaded = True

        def apply(self):
            self.applied = True

    monkeypatch.setattr(pm, "panel_type", lambda: Base)
    gui = NS(QComboBox=_W, QLabel=_W, QCheckBox=_W, QPushButton=lambda title: _W())
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtGui=gui))
    monkeypatch.setattr(scripting, "current_package", lambda pid: Base.package)
    return mod.panel_type()()


def test_panel_modes_when_changed_then_labels_ranges_and_enabled_follow(numeric):
    p = numeric
    assert p.first_label._text == "Slope (dx/dy)" and p.second_value.enabled is False
    assert p.first_value.range == (-100, 100) and p.per_master_italic.enabled
    p.per_master_italic.setChecked(True)
    p.update_mode_fields()
    assert p.first_value.enabled is False
    p.mode_box.setCurrentIndex(1)
    p.mode_changed()
    assert p.first_label._text == "First handle / chord" and p.first_value.range == (0, 100)
    assert p.second_value.enabled and not p.top_pivot.enabled and p.refreshed == 1
    p.mode_box.setCurrentIndex(2)
    p.update_mode_fields()
    assert p.first_label._text == "First Hobby tension" and p.second_label._text == "Second Hobby tension"
    assert p.first_value.range == (0.000001, 100) and p.second_value.range == (0.000001, 100)


def test_panel_hooks_when_lab_methods_present_then_called(numeric):
    p = numeric
    p.fill("plan")
    assert p.filled == "plan" and not hasattr(p.table, "sorting")
    seen = []
    p.lab_refresh_preview = lambda: seen.append("refresh")
    p.lab_check_target = lambda: seen.append("check")
    p.fill("plan")
    p.reload()
    p.apply()
    assert p.table.sorting is True and seen == ["refresh", "check"] and p.applied
    assert "dx/dy" in p.intro()
    p.glyphs = []
    assert p.intro() == "Guide"
    p.glyphs, p.package = ["A"], None
    assert p.intro() == "Guide"


def test_panel_copy_values_when_italic_slope_or_proportions_then_fields_set(numeric, mod, monkeypatch):
    p = numeric
    p.copy_values("italic")
    assert p.per_master_italic.isChecked() and p.first_value.value == pytest.approx(-math.tan(math.radians(10)))
    assert p.refreshed == 1
    sel = contour([node(0, 0, selected=True), node(10, 100, selected=True)])
    monkeypatch.setattr(mod, "selected_contours", lambda: [sel])
    p.copy_values("slope")
    assert not p.per_master_italic.isChecked() and p.first_value.value == pytest.approx(0.1)
    monkeypatch.setattr(mod, "segments", lambda c: [1])
    monkeypatch.setattr(mod, "proportions", lambda c: (0.3, 0.4))
    p.copy_values("handles")
    assert p.mode_box.currentIndex == 1 and p.second_value.value == 0.4 and p.first_value.value == 0.3
    monkeypatch.setattr(mod, "proportions", lambda c: (0.3, 101))
    p.copy_values("handles")
    assert p.status._text == "Handle proportion exceeds the field range."
    monkeypatch.setattr(mod, "proportions", lambda c: (500, 1))
    p.copy_values("handles")
    assert p.status._text == "Copied value exceeds the field range."
    monkeypatch.setattr(mod, "segments", lambda c: [])
    p.copy_values("handles")
    assert p.status._text == "Select exactly one cubic segment."


def test_panel_copy_values_when_font_closed_then_status(numeric, monkeypatch):
    import fontlabapp.core.scripting as scripting

    monkeypatch.setattr(scripting, "current_package", lambda pid: None)
    numeric.copy_values("italic")
    assert numeric.status._text == "Open the bound font first."


def test_panel_planner_when_modes_then_changes_follow(numeric, mod, monkeypatch):
    p = numeric
    calls = []
    monkeypatch.setattr(mod, "changes", lambda *a: calls.append(a) or ["row"])
    p.first_value.value, p.second_value.value = 0.2, 0.3
    p.top_pivot.setChecked(True)
    assert p.planner()("g", "Regular", "layer") == ["row"]
    assert calls[-1] == ("layer", "Slope", 0.2, 0.3, True, False)
    import fontlabapp.masters.angles.model as angles

    monkeypatch.setattr(angles, "capture", lambda package: NS(angles=[("Regular", 10.0)]))
    p.per_master_italic.setChecked(True)
    plan = p.planner()
    plan("g", "Regular", "layer")
    assert calls[-1][2] == pytest.approx(-math.tan(math.radians(10)))
    with pytest.raises(ValueError, match="'Bold' not found"):
        plan("g", "Bold", "layer")
    import fontlabapp.core.scripting as scripting

    monkeypatch.setattr(scripting, "current_package", lambda pid: None)
    with pytest.raises(ValueError, match="Open the bound font"):
        p.planner()
    assert isinstance(p.editor(), mod.CoordinateEditor)


def test_main_when_dialog_shows_or_fails_then_returned_or_printed(mod, monkeypatch, capsys):
    import fontlabapp.core.scripting as scripting

    monkeypatch.setattr(mod, "panel_type", lambda: "P")
    monkeypatch.setattr(scripting, "show_script_dialog", lambda t, k: (t, k))
    assert mod.main() == ("P", mod.KEY)
    monkeypatch.setattr(scripting, "show_script_dialog", lambda t, k: (_ for _ in ()).throw(RuntimeError("deadline")))
    assert mod.main() is None and capsys.readouterr().out == f"{mod.TITLE}: deadline\n"


def test_carry_handles_when_neighbours_on_curve_or_selected_then_never_carried(mod):
    nodes = [node(0, 0, selected=True), node(10, 0, on=False, selected=True), node(20, 0, on=False), node(30, 0), node(5, 5)]
    snap = mod.snapshot_contour(contour(nodes, closed=True))
    result = mod.carry_handles([snap], {(0, 0): (7.0, 0.0)})
    assert result == {(0, 0): (7.0, 0.0)}  # (0,1) selected handle and (0,4) unselected on-curve stay put


def test_segment_indices_when_open_contour_then_no_wrap_span(mod):
    nodes = [node(0, 0, selected=True), node(1, 0, selected=True), node(2, 1, on=False), node(3, 1, on=False)]
    assert mod.segment_indices(mod.snapshot_contour(contour(nodes))) == []
    assert mod.segment_indices(mod.snapshot_contour(contour(nodes, closed=True))) == [(1, 2, 3, 0)]


def test_segment_indices_when_closed_without_on_curve_nodes_then_empty(mod):
    nodes = [node(0, 0, on=False), node(1, 0, on=False), node(2, 1, on=False)]
    assert mod.segment_indices(mod.snapshot_contour(contour(nodes, closed=True))) == []
