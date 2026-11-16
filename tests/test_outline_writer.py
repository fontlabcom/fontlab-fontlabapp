# this_file: tests/test_outline_writer.py
"""Outline plan kernel and transform writer of the Contours scripts (issue 122, T14g).

The outline doubles extend the FontLab doubles of ``test_component_writer``
with nodes, contours, shape matrices, shared outline data and anchors. Every
native call goes into one log, so the tests pin the per-glyph refusals, the
master-compatibility hold, the one-Undo notification and the bake-versus-
compose rule of FontLab's layer transform (``fllayer.cpp:6957-6978``). They
do not prove native FontLab behaviour.
"""

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import test_component_writer as fld

import fontlabapp.contours.affine as affine  # noqa: PLR0402 - from-import hits the package __getattr__
import fontlabapp.anchors.writer as aw
import fontlabapp.contours.transform.model as ot
import fontlabapp.contours.writer as ow

LOG = fld.LOG
NO_FACTS = fld.facts()


# ---------------------------------------------------------------- outline doubles
class Matrix:
    """A QTransform double: six getters, as PythonQt exposes them."""

    def __init__(self, *values):
        self.values = tuple(float(v) for v in (values or (1, 0, 0, 1, 0, 0)))

    def m11(self):
        return self.values[0]

    def m12(self):
        return self.values[1]

    def m21(self):
        return self.values[2]

    def m22(self):
        return self.values[3]

    def dx(self):
        return self.values[4]

    def dy(self):
        return self.values[5]


class Node:
    def __init__(self, x, y, on=True):
        self.x, self.y, self.on = float(x), float(y), on

    def isOn(self):
        return self.on


class Contour:
    def __init__(self, points):
        self._nodes = [Node(*p) for p in points]

    @property
    def nodesCount(self):
        return len(self._nodes)

    def nodes(self):
        return self._nodes


class Shape:
    """An own contour shape, or a component of glyph ``base``."""

    def __init__(self, *contours, matrix=(1, 0, 0, 1, 0, 0), refs=1, base="", includes=()):
        self.id = next(fld.IDS)
        self.name = f"shape{self.id}"
        self.isComponent = bool(base)
        self.contours = [Contour(points) for points in contours]
        self.transform = Matrix(*matrix)
        self.shapeData = NS(referenceCount=refs, componentGlyph=base)
        self.includesList = list(includes)

    def applyTransform(self):
        LOG.append(("bake", self.name))
        m = self.transform.values
        for contour in self.contours:
            for node in contour.nodes():
                node.x, node.y = affine.apply(m, node.x, node.y)
        self.transform = Matrix()

    def changed(self):
        LOG.append(("shape-changed", self.name))


class Pin:
    def __init__(self, name, x, y):
        self.name, self._xy = name, (float(x), float(y))

    @property
    def point(self):
        x, y = self._xy
        return NS(x=lambda: x, y=lambda: y)

    @point.setter
    def point(self, value):
        LOG.append(("move", self.name))
        self._xy = (value.x(), value.y())


def glyph(name, shapes_by_master, anchors=(), auto=()):
    """A glyph with masters L and B; the same anchors on every master."""
    found = fld.Glyph(name, **{m: list(s) for m, s in shapes_by_master.items()})
    for master, layer in found.by_master.items():
        layer.anchors = [Pin(*a) for a in anchors]
        layer.autoLayer = master in auto
    return found


SQUARE = [(0, 0), (100, 0), (100, 100), (0, 100)]


@pytest.fixture
def native(monkeypatch):
    """The FontLab double plus a PythonQt double with QPointF and QTransform."""
    LOG.clear()
    fake = fld.Native()
    qt = NS(
        QtCore=NS(QDateTime=NS(currentDateTimeUtc=lambda: fld.STAMP), QPointF=lambda x, y: NS(x=lambda: x, y=lambda: y)),
        QtGui=NS(QTransform=Matrix, QPainterPath=Path2),
    )  # fmt: skip
    monkeypatch.setitem(sys.modules, "fontlab", fake)
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    return fake


class Path2:
    """A QPainterPath double that records its calls."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *args: self.calls.append((name, *args))


# ---------------------------------------------------------------- outline helpers
def test_translation_when_plain_move_then_offset_else_none():
    assert ow.translation(Shape(SQUARE, matrix=(1, 0, 0, 1, 3, -4))) == (3.0, -4.0)
    assert ow.translation(Shape(SQUARE, matrix=(2, 0, 0, 1, 0, 0))) is None
    assert ow.translation(Shape(SQUARE, matrix=(1, 0, 0.2, 1, 0, 0))) is None


def test_node_points_when_read_then_stored_order_and_on_flags():
    contour = Contour([(0, 0), (5, 9, False), (10, 0)])
    assert ow.node_points(contour) == [(0.0, 0.0, True), (5.0, 9.0, False), (10.0, 0.0, True)]


def test_outline_shapes_when_shared_scaled_or_component_then_kept_with_notes():
    plain, moved = Shape(SQUARE), Shape(SQUARE, matrix=(1, 0, 0, 1, 7, 0))
    shared, scaled = Shape(SQUARE, refs=2), Shape(SQUARE, matrix=(2, 0, 0, 2, 0, 0))
    layer = fld.Layer("A", "L", [plain, shared, Shape(base="acute"), scaled, Shape(), moved])
    editable, notes = ow.outline_shapes(layer)
    assert editable == [plain, moved]
    assert notes == ["shared outline, kept", "scaled or rotated shape, kept"]
    assert ow.note_rows(notes + ["shared outline, kept"]) == [
        ow.Change("2 shapes", "", "shared outline, kept"),
        ow.Change("1 shape", "", "scaled or rotated shape, kept"),
    ]


def test_held_back_when_keys_differ_or_master_out_of_scope_then_reason():
    row = lambda key: ow.Change("c", "", "", "edit", key=key)
    same = {"L": (None, [row(1)]), "B": (None, [row(1)])}
    assert ow.held_back(same, ["L", "B"]) == ""
    differ = {"L": (None, [row(1)]), "B": (None, [row(2)])}
    assert ow.held_back(differ, ["L", "B"]) == "masters would differ, kept"
    assert ow.held_back(same, ["L"]) == "other masters need it too; choose All masters"
    plain = {"L": (None, [ow.Change("n", "", "", "edit")]), "B": (None, [])}
    assert ow.held_back(plain, ["L"]) == "", "edits without keys never hold"


# ---------------------------------------------------------------- collect
def planner_with(key=None, problem=""):
    def plan(g, master, layer):
        LOG.append(("plan", g.name, master))
        return [ow.Change("nodes", "1", "2", f"edit-{g.name}-{master}", problem, key)]

    return plan


def test_collect_when_glyph_refused_then_row_skipped_and_others_planned():
    a = glyph("A", {"L": [Shape(SQUARE)], "B": [Shape(SQUARE)]})
    b = glyph("B", {"L": [Shape(SQUARE)], "B": [Shape(SQUARE)]})
    facts = fld.facts(("B", True, ()))
    LOG.clear()
    plan = ow.collect([a, b], ["L"], planner_with(), facts)
    assert plan.refused == ["B"] and plan.work == [(a, a.by_master["L"], ["edit-A-L"])]
    assert ("B", ow.Change("glyph", "", "skipped: has auto layers")) in plan.rows
    assert ("plan", "B", "L") not in LOG, "a refused glyph is never planned"


def test_collect_when_base_of_auto_composite_then_skipped_unless_allow_bases():
    a = glyph("A", {"L": [Shape(SQUARE)]})
    facts = fld.facts(("Aacute", True, ("A",)))
    plan = ow.collect([a], ["L"], planner_with(), facts)
    assert plan.refused == ["A"] and plan.rows == [("A", ow.Change("glyph", "", "skipped: base of auto Aacute"))]
    plan = ow.collect([a], ["L"], planner_with(), facts, allow_bases=True)
    assert plan.refused == [] and plan.edits == 1


def test_collect_when_layer_is_auto_then_listed_only_in_scope_and_never_planned():
    a = glyph("A", {"L": [Shape(SQUARE)], "B": [Shape(SQUARE)]}, auto=("B",))
    LOG.clear()
    plan = ow.collect([a], ["L", "B"], planner_with(), NO_FACTS)
    assert plan.skipped == ["A/B"] and ("A · B", ow.Change("layer", "", "auto layer, skipped")) in plan.rows
    assert ("plan", "A", "B") not in LOG
    plan = ow.collect([a], ["L"], planner_with(), NO_FACTS, compatible=True, all_masters=["L", "B"])
    assert plan.skipped == [], "an auto layer out of scope is not listed"


def test_collect_when_compatible_and_masters_differ_then_held_with_reason_text():
    a = glyph("A", {"L": [Shape(SQUARE)], "B": [Shape(SQUARE)]})

    def plan_keys(g, master, layer):
        return [ow.Change("contour 1", "", "delete", "edit", key=master)]

    plan = ow.collect([a], ["L", "B"], plan_keys, NO_FACTS, compatible=True, all_masters=["L", "B"])
    assert plan.held == ["A"] and plan.work == []
    assert [c.new for _, c in plan.rows] == ["masters would differ, kept"] * 2
    assert [c.edit for _, c in plan.rows] == [None, None]
    plan = ow.collect([a], ["L"], planner_with(key=1), NO_FACTS, compatible=True, all_masters=["L", "B"])
    assert plan.held == ["A"] and plan.rows[0][1].new == "other masters need it too; choose All masters"
    plan = ow.collect([a], ["L"], planner_with(key=1), NO_FACTS)
    assert plan.held == [] and plan.edits == 1, "without the tick nothing is held"


def test_collect_when_row_blocked_then_problem_and_layer_not_in_work():
    a = glyph("A", {"L": [Shape(SQUARE)]})
    plan = ow.collect([a], ["L"], planner_with(problem="bad"), NO_FACTS)
    assert plan.problems == ["A · L: bad"] and plan.work == []


def test_apply_work_when_updates_queued_then_writes_and_discloses(native, capsys):
    native.pending.append(41)
    owner = glyph("A", {"L": [Shape(SQUARE)]})
    layer = owner.by_master["L"]
    node = layer.shapes[0].contours[0].nodes()[0]
    result = ow.apply_work([(owner, layer, [(node, 1.0, 0.0)])], "Move", NO_FACTS, NodeMover())
    assert node.x == 1.0 and native.pending == [41]
    assert result["pending_updates"] == (41,) and "8537" in result["pending_note"]
    import fontlabapp.core.edit_guards as guards
    guards.disclose(result)
    output = capsys.readouterr().out
    assert "(41,)" in output and result["pending_note"] in output


class NodeMover(ow.Editor):
    def write(self, layer, steps):
        for node, x, y in steps:
            node.x, node.y = x, y

    def check(self, prepared):
        return [layer.name for layer, steps in prepared for node, x, y in steps if (node.x, node.y) != (x, y)]


def test_apply_work_when_outline_edit_then_one_notify_of_layers_and_glyph(native):
    a = glyph("A", {"L": [Shape(SQUARE)], "B": [Shape(SQUARE)]})
    plan = ow.collect([a], ["L", "B"], lambda g, m, layer: [
        ow.Change("node", "0, 0", "1, 0", (layer.shapes[0].contours[0].nodes()[0], 1.0, 0.0))
    ], NO_FACTS)  # fmt: skip
    LOG.clear()
    assert ow.apply_work(plan.work, "Round", NO_FACTS, NodeMover()) == {"pending_note": "", "edits": 2, "layers": 2, "pending_updates": ()}
    assert fld.history_events() == [
        ("init", "A/L"), ("init", "A/B"), ("init", "A"), ("stamp", "A", fld.STAMP),
        ("notify", "Round", ["A/L", "A/B", "A"], ()), ("stamp", "A", fld.STAMP),
    ]  # fmt: skip


# ---------------------------------------------------------------- transform writer
@pytest.mark.parametrize(
    ("shape", "expected"),
    [
        (Shape(SQUARE), True),
        (Shape(SQUARE, matrix=(1, 0, 0, 1, 5, 5)), True),
        (Shape(base="acute"), False),
        (Shape(SQUARE, refs=2), False),
        (Shape(SQUARE, matrix=(2, 0, 0, 1, 0, 0)), False),
        (Shape(SQUARE, includes=("inner",)), False),
        (Shape(), False),
    ],
    ids=["plain", "moved", "component", "shared", "scaled", "includes", "empty"],
)
def test_bakes_when_shape_kind_then_fontlab_layer_transform_rule(shape, expected):
    """FontLab's layer transform bakes only these shapes (fllayer.cpp:6957-6978)."""
    assert ot.bakes(shape) is expected


def test_transform_changes_when_identity_then_no_rows():
    layer = glyph("A", {"L": [Shape(SQUARE)]}, anchors=[("top", 50, 100)]).by_master["L"]
    assert ot.transform_changes(layer, affine.IDENTITY, True, "0, 0") == []


def test_transform_changes_when_planned_then_outline_row_and_anchor_row():
    plain, mark = Shape(SQUARE), Shape(base="acute", matrix=(1, 0, 0, 1, 10, 0))
    layer = glyph("A", {"L": [plain, mark]}, anchors=[("top", 50, 100)]).by_master["L"]
    double = (2.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    rows = ot.transform_changes(layer, double, True, "origin")
    assert [(c.name, c.old, c.new, c.problem) for c in rows] == [
        ("outline", "4 nodes", "origin", ""),
        ("anchors", "1 anchor", "move", ""),
    ]
    kind, steps = rows[0].edit
    assert kind == "shapes" and [(s, new, bake) for s, new, bake, _ in steps] == [
        (plain, double, True),
        (mark, (2.0, 0.0, 0.0, 1.0, 20.0, 0.0), False),
    ]
    assert steps[0][3] == (plain.contours[0].nodes()[0], (0.0, 0.0)), "probe: first node and its target"
    assert ot.transform_changes(layer, double, False, "origin")[-1].name == "outline"


def test_transform_changes_when_anchor_lands_on_origin_then_blocked_by_anchor_writer_rule(monkeypatch):
    layer = glyph("A", {"L": [Shape(SQUARE)]}, anchors=[("bottom", 10, 0), ("home", 0.2, 0)]).by_master["L"]
    calls = []
    real = aw.on_origin

    def spy(point, near=0.0):
        calls.append((tuple(point), near))
        return real(point, near)

    monkeypatch.setattr(aw, "on_origin", spy)
    rows = ot.transform_changes(layer, (1.0, 0.0, 0.0, 1.0, -10.0, 0.0), True, "")
    assert rows[1].problem == (
        "bottom would move to 0, 0; FontLab cannot redo that (fl#8527). "
        "Untick the anchors or change the values."
    )
    assert ((0.0, 0.0), ot.ORIGIN_NEAR) in calls, "the new point uses the rounding tolerance"
    assert ((10.0, 0.0), 0.0) in calls, "the old point counts as on the origin only when exact"
    home = glyph("A", {"L": [Shape(SQUARE)]}, anchors=[("home", 0.0, 0.0)]).by_master["L"]
    rows = ot.transform_changes(home, (1.0, 0.0, 0.0, 1.0, 0.0, 0.1), True, "")
    assert rows[1].problem == "", "an anchor exactly on the origin does not count"


def test_transform_changes_when_anchor_near_origin_moves_to_origin_then_blocked():
    """T14g review M1: an anchor at (0.3, 0) moved to exactly (0, 0) is refused (fl#8527)."""
    layer = glyph("A", {"L": [Shape(SQUARE)]}, anchors=[("near", 0.3, 0.0)]).by_master["L"]
    rows = ot.transform_changes(layer, (1.0, 0.0, 0.0, 1.0, -0.3, 0.0), True, "")
    kind, moves = rows[1].edit
    assert kind == "anchors" and moves[0][1:] == (0.0, 0.0)
    assert rows[1].problem.startswith("near would move to 0, 0"), rows[1].problem


def test_on_origin_when_exact_or_near_then_anchor_writer_redo_rule():
    assert aw.on_origin((0, 0)) and aw.on_origin((0.0, -0.0))
    assert not aw.on_origin((0.0, 0.5)) and not aw.on_origin((0.4, 0))
    assert aw.on_origin((0.4, -0.49), 0.5) and not aw.on_origin((0.5, 0), 0.5)


def test_anchor_writer_require_safe_when_existing_anchor_moves_to_origin_then_uses_on_origin(monkeypatch, native):
    calls = []
    monkeypatch.setattr(aw, "on_origin", lambda point, near=0.0: calls.append(tuple(point)) or True)
    layer = glyph("a", {"L": []}, anchors=[("top", 5, 5)]).by_master["L"]
    with pytest.raises(ValueError, match="Redo"):
        aw.require_safe([(glyph("a", {"L": []}), layer, [("set", "top", (0, 1))])], NO_FACTS)
    assert calls == [(0, 1)]


def test_transform_editor_when_written_then_composes_bakes_and_moves_anchors(native):
    plain, mark = Shape(SQUARE), Shape(base="acute", matrix=(1, 0, 0, 1, 10, 0))
    layer = glyph("A", {"L": [plain, mark]}, anchors=[("top", 50, 100)]).by_master["L"]
    rows = ot.transform_changes(layer, (2.0, 0.0, 0.0, 1.0, 0.0, 0.0), True, "")
    prepared = [(layer, [row.edit for row in rows])]
    editor = ot.TransformEditor()
    LOG.clear()
    editor.write(layer, prepared[0][1])
    assert LOG == [("bake", plain.name), ("shape-changed", plain.name), ("shape-changed", mark.name), ("move", "top")]
    assert plain.contours[0].nodes()[1].x == 200 and plain.transform.values == (1, 0, 0, 1, 0, 0)
    assert mark.transform.values == (2, 0, 0, 1, 20, 0)
    assert editor.check(prepared) == []
    mark.transform = Matrix()
    layer.anchors[0]._xy = (0.0, 0.0)
    assert editor.check(prepared) == ["A/L: a shape", "A/L/top"]


def test_transform_editor_when_baked_node_rounded_within_half_unit_then_no_alarm(native):
    plain = Shape([(0.3, 0), (100, 0), (100, 100)])
    layer = glyph("A", {"L": [plain]}).by_master["L"]
    rows = ot.transform_changes(layer, (1.0, 0.0, 0.0, 1.0, 10.0, 0.0), False, "")
    editor = ot.TransformEditor()
    editor.write(layer, [rows[0].edit])
    plain.contours[0].nodes()[0].x = 10.0  # FontLab rounds 10.3
    assert editor.check([(layer, [rows[0].edit])]) == []
    plain.contours[0].nodes()[0].x = 11.0
    assert editor.check([(layer, [rows[0].edit])]) == ["A/L: a shape"]


def test_preview_geometry_when_mapped_and_fitted_then_exact_points(native):
    layer = glyph("A", {"L": [Shape([(0, 0), (10, 0, False), (20, 0, False), (30, 0)], matrix=(1, 0, 0, 1, 5, 0))]}).by_master["L"]
    before = ot.layer_outline(layer)
    assert before == [[(5.0, 0.0, True), (15.0, 0.0, False), (25.0, 0.0, False), (35.0, 0.0, True)]]
    assert ot.mapped(before, (1.0, 0.0, 0.0, 1.0, 0.0, 7.0))[0][0] == (5.0, 7.0, True)
    path = ot.outline_path(before + [[(0, 0, False)]])
    assert path.calls == [("moveTo", 5.0, 0.0), ("cubicTo", 15.0, 0.0, 25.0, 0.0, 35.0, 0.0),
                          ("lineTo", 5.0, 0.0), ("closeSubpath",)]  # fmt: skip
    box = NS(x=lambda: 0.0, y=lambda: 0.0, width=lambda: 100.0, height=lambda: 50.0)
    assert ot.fit(box, 248, 148) == (2.0, 0.0, 0.0, -2.0, 24.0, 124.0)
    flat = NS(x=lambda: 0.0, y=lambda: 0.0, width=lambda: 0.0, height=lambda: 50.0)
    assert ot.fit(flat, 248, 148) == affine.IDENTITY


# ---------------------------------------------------------------- cold import
@pytest.mark.parametrize(
    "module",
    ["fontlabapp.masters.layers.writer", "fontlabapp.contours.writer", "fontlabapp.contours.panel.model", "fontlabapp.contours.transform.model"],
)
def test_module_when_cold_imported_then_only_stdlib_and_no_qt(module):
    import fontlabapp

    package_root = str(Path(fontlabapp.__file__).resolve().parent.parent)
    script = f"""
import importlib.abc
import sys

class StdlibOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split('.')[0]
        if root not in ('fontlabapp', 'org') and root not in sys.stdlib_module_names:
            raise AssertionError('Non-stdlib import: ' + fullname)

sys.meta_path.insert(0, StdlibOnly())
sys.path.insert(0, sys.argv[1])
import {module}
lazy = {{'fontlabapp.contours.panel.ui', 'fontlabapp.contours.transform.ui', 'fontlabapp.components.panel.ui',
        'fontlabapp.core.scripting', 'PythonQt', 'fontlab'}}
assert not lazy & set(sys.modules), lazy & set(sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, package_root],
        capture_output=True, text=True, timeout=20, check=False,
    )  # fmt: skip
    assert result.returncode == 0, result.stdout + result.stderr
