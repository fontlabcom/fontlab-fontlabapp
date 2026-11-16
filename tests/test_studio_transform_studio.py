# this_file: tests/test_studio_transform_studio.py
"""Transform Studio (Phase D A6): geometry, planners, session writes and the three tabs on offscreen Qt.

Writes are checked for the explicit layers they target and their
``Transform Studio: <action> <subject>`` Undo label (§1.3/§1.4); preview and
read-only paths are checked never to call ``history`` or touch native layers,
while drawing the planned ghost through ``set_overlay``. Hinted layers are
refused until the user ticks "Edit hinted layers anyway" or removes hints.
"""

import importlib
import math
import sys
from types import SimpleNamespace

import pytest
from _contour_fakes import Metrics, NShape, Package, Shell, curve, hint_counts, square
from _studio_qt import studio_qt  # noqa: F401 - fixture

PKG = "fontlabapp.studios.transform_studio"
TABS = f"{PKG}.tabs"
SESSION = f"{PKG}.session"
APP_LABEL = "Transform Studio"


@pytest.fixture(autouse=True)
def qt_transform(studio_qt, monkeypatch):  # noqa: F811
    """Session and tabs import PythonQt and fontlab lazily; load them on offscreen Qt, then drop them."""
    for name in (TABS, SESSION, f"{PKG}.native"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setitem(sys.modules, "fontlab", SimpleNamespace(FontMetrics=Metrics))
    monkeypatch.setattr("fontlabapp.hints.postscript.hint_counts", hint_counts)
    yield studio_qt
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)


def _geo():
    return importlib.import_module(f"{PKG}.geometry")


def _model():
    return importlib.import_module(f"{PKG}.model")


def _session():
    return importlib.import_module(SESSION)


def package(**kwargs):
    pkg = Package(angles={"Regular": -12.0, "Bold": -10.0}, **kwargs)
    pkg.add(
        "A",
        lambda log: (
            [NShape([square(log, selected=(0, 1))], log=log)],
            [("top", 50, 100)],
        ),
    )
    pkg.add("O", lambda log: [NShape([curve(log)], log=log)])
    pkg.add("H", lambda log: [NShape([square(log)], log=log)], hinted=True)
    pkg.add("Z", lambda log: [])
    return pkg


def studio(pkg=None, **kwargs):
    made = _session().Studio(
        Shell(pkg if pkg is not None else package()), metrics=Metrics, **kwargs
    )
    made.reload()
    return made


def layer_of(pkg, name, master="Regular"):
    native = importlib.import_module(f"{PKG}.native")
    return native.snapshot(pkg.layer(name, master))


# Geometry -----------------------------------------------------------------
def test_geometry_when_affine_helpers_then_compose_and_invert():
    g = _geo()
    m = g.concat(g.rotation(90), g.translate(10, 0))
    x, y = g.apply(m, 1, 0)
    assert (round(x, 9), round(y, 9)) == (10, 1)
    back = g.apply(g.invert(m), x, y)
    assert (round(back[0], 9), round(back[1], 9)) == (1, 0)
    assert (
        g.is_identity(g.IDENTITY)
        and g.is_translation(g.translate(3, 4))
        and not g.is_translation(m)
    )
    assert g.finite(1, 2) and not g.finite(1, math.inf)
    assert g.apply(g.about((2, 0, 0, 2, 0, 0), 10, 10), 10, 10) == (10, 10)
    assert g.subject(["A", "A"]) == "A" and g.subject(["A", "B"]) == "2 glyphs"
    assert g.plural(1, "node") == "1 node" and g.plural(2, "node") == "2 nodes"
    with pytest.raises(ValueError):
        g.invert((0, 0, 0, 0, 0, 0))


def test_geometry_when_curves_then_ink_box_uses_extrema():
    g = _geo()
    N = g.Node
    cubic = g.Contour((N(0, 0), N(0, 100, False), N(100, 100, False), N(100, 0)))
    quad = g.Contour((N(0, 0), N(50, 100, False), N(100, 0)), tt=True)
    for contour in (cubic, quad):
        x, y, w, h = g.layer_ink(g.Layer(shapes=(g.Shape(contours=(contour,)),)))
        assert (x, y, w) == (0, 0, 100) and 49 < h < 76
    component = g.Shape(matrix=g.translate(10, 0), component=True, box=(0, 0, 10, 10))
    assert g.corners(component)[0] == (10, 0) and g.corners(g.Shape()) == []
    assert (
        g.layer_ink(g.Layer()) is None
        and g.layer_ink(g.Layer(shapes=(component,))) is None
    )


def test_geometry_when_simulated_then_ghost_and_verify_report_differences():
    g = _geo()
    N = g.Node
    layer = g.Layer(shapes=(g.Shape(contours=(g.Contour((N(0, 0), N(10, 0), N(10, 10), N(0, 10))),)),),
                    anchors=(("top", 5, 10),), advance=20)  # fmt: skip
    steps = [("node", 0, 0, 0, 1, 1, True), ("remove", 0, 0, (3,), 3), ("anchor", 0, 6, 11), ("advance", 30),
             ("shape", 0, g.translate(5, 0), True)]  # fmt: skip
    after = g.simulate(layer, steps)
    assert [(n.x, n.y) for n in after.shapes[0].contours[0].nodes] == [
        (6, 1),
        (15, 0),
        (15, 10),
    ]
    assert after.anchors == (("top", 6, 11),) and after.advance == 30
    overlay = g.ghost(after)
    assert len(overlay.contours) == 1 and len(overlay.contours[0].points) == 3
    assert g.verify("A", after, after, steps) == []
    problems = g.verify("A", after, layer, steps)
    assert any("node count" in p for p in problems) and any(
        "anchor top" in p for p in problems
    )
    assert any("advance" in p for p in problems)


def test_anchor_steps_when_moved_near_origin_then_problem():
    g = _geo()
    layer = g.Layer(anchors=(("top", 1, 1),))
    steps, problem = g.anchor_steps(layer, g.translate(-1, -1))
    assert steps and problem
    assert g.anchor_steps(layer, g.translate(10, 0)) == ([("anchor", 0, 11, 1)], "")


# Model --------------------------------------------------------------------
def test_linear_when_flat_or_infinite_then_errors():
    m = _model()
    assert m.linear(100, 100, 0, 0)[:4] == (1, 0, 0, 1)
    with pytest.raises(ValueError, match="flatten"):
        m.linear(0, 100, 0, 0)
    with pytest.raises(ValueError):
        m.linear(math.nan, 100, 0, 0)
    with pytest.raises(ValueError, match="finite"):
        m.rotation_linear(math.inf)
    assert m.rotation_linear(0)[:4] == (1, 0, 0, 1)


def test_transform_planner_when_each_origin_then_shape_matrix_about_origin():
    g, m = _geo(), _model()
    N = g.Node
    shape = g.Shape(contours=(g.Contour((N(0, 0), N(100, 0), N(100, 100), N(0, 100))),))
    layer = g.Layer(shapes=(shape,), anchors=(("top", 50, 100),), advance=300)
    assert m.origin_of(layer, 0) == (50, 50) and m.origin_of(layer, 1) == (0, 0)
    assert m.origin_of(layer, 2) == (0, 0) and m.origin_of(layer, 3) == (150, 0)
    assert m.origin_of(g.Layer(), 0) is None
    rows = m.transform_planner_changes(layer, m.linear(200, 200, 0, 0), 0, (0, 0), True)
    shape_step = next(s for s in rows[0].edit if s[0] == "shape")
    assert g.apply(shape_step[2], 50, 50) == (50, 50) and shape_step[3] is True
    assert ("anchor", 0, 50.0, 150.0) in rows[0].edit
    moved = m.transform_planner_changes(
        layer, m.linear(100, 100, 0, 0), 2, (10, 0), False
    )
    assert [s for s in moved[0].edit if s[0] == "anchor"] == []
    assert (
        m.transform_planner_changes(layer, m.linear(100, 100, 0, 0), 2, (0, 0), True)
        == []
    )
    assert (
        m.transform_planner_changes(
            g.Layer(), m.linear(200, 100, 0, 0), 0, (0, 0), True
        )
        == m.EMPTY_NOTE
    )


def test_transform_changes_when_component_shared_or_scaled_then_all_composed():
    """I2: shared and scaled/rotated own outlines move with the glyph (composed, not kept)."""
    g = _geo()
    N = g.Node
    outline = g.Contour((N(0, 0), N(10, 0), N(10, 10)))
    layer = g.Layer(shapes=(g.Shape(component=True, box=(0, 0, 10, 10)),
                            g.Shape(contours=(outline,), shared=True),
                            g.Shape(matrix=(2, 0, 0, 2, 0, 0), contours=(outline,)),
                            g.Shape(contours=(outline,), locked=True)))  # fmt: skip
    move = g.translate(5, 0)
    rows = g.transform_changes(layer, move, False, "move")
    assert not any("kept" in r.new for r in rows), "no shape may be left untransformed"
    shapes = {s[1]: s for r in rows for s in (r.edit or ()) if s[0] == "shape"}
    assert set(shapes) == {0, 1, 2, 3}
    assert shapes[1] == ("shape", 1, g.concat(g.IDENTITY, move), False)
    assert shapes[2] == ("shape", 2, g.concat((2, 0, 0, 2, 0, 0), move), False)
    assert shapes[3][3] is True and shapes[0][3] is False
    after = g.simulate(layer, [s for r in rows for s in (r.edit or ())])
    before_pts = [g.glyph_points(sh) for sh in layer.shapes[1:]]
    after_pts = [g.glyph_points(sh) for sh in after.shapes[1:]]
    for old, new in zip(before_pts, after_pts):
        assert [(x + 5, y) for x, y, *_ in old] == [(x, y) for x, y, *_ in new]
    assert g.verify("t", after, after, [s for r in rows for s in (r.edit or ())]) == []


def test_origin_when_pure_composite_then_component_box_used():
    """I3: the origin box includes components, like layer.boundingBox."""
    g, m = _geo(), _model()
    layer = g.Layer(shapes=(g.Shape(component=True, box=(100, 0, 300, 200)),))
    assert m.origin_of(layer, 0) == (200.0, 100.0)
    assert m.origin_of(layer, 1) == (100.0, 0.0)
    rows = m.transform_planner_changes(layer, m.linear(200, 200, 0, 0), 0, (0, 0), False)
    steps = [s for r in rows for s in (r.edit or ())]
    assert steps and steps[0][0] == "shape" and steps[0][3] is False
    assert g.apply(steps[0][2], 200, 100) == (200, 100), "box centre stays fixed"
    mixed = g.Layer(shapes=(g.Shape(component=True, box=(100, 0, 300, 200)),
                            g.Shape(contours=(g.Contour((g.Node(0, 0), g.Node(10, 0), g.Node(10, 400))),))))  # fmt: skip
    assert m.layer_box(mixed) == (0, 0, 300, 400)
    assert m.layer_box(g.Layer()) is None


def test_smart_slant_when_scaled_own_shape_then_composed_without_type_error():
    """I4: a scaled own shape used to raise TypeError (None + tuple) at model.py:161."""
    g, m = _geo(), _model()
    N = g.Node
    square = g.Contour((N(0, 0), N(50, 0), N(50, 100), N(0, 100)))
    layer = g.Layer(shapes=(g.Shape(matrix=(2, 0, 0, 2, 0, 0), contours=(square,)),), advance=200)
    rows = m.smart_changes(layer, 10, True, False)
    assert isinstance(rows, list)
    steps = [s for r in rows for s in (r.edit or ())]
    assert any(s[0] == "shape" and s[3] is False for s in steps)
    assert any(s[0] == "advance" for s in steps)
    assert [r.name for r in rows] == ["outline", "advance"]


def test_slant_when_pivot_and_angle_then_shear_about_pivot():
    g, m = _geo(), _model()
    N = g.Node
    layer = g.Layer(shapes=(g.Shape(contours=(g.Contour((N(0, 0), N(100, 0), N(100, 200), N(0, 200))),)),),
                    anchors=(("top", 50, 200),), advance=200)  # fmt: skip
    matrix = m.slant_matrix(10, 100)
    assert g.apply(matrix, 0, 100) == (0, 100)
    rows = m.slant_changes(layer, 10, 100, True)
    assert rows and any(s[0] == "anchor" for s in rows[0].edit)
    with pytest.raises(ValueError):
        m.slant_matrix(89, 0)
    assert m.slant_changes(layer, 0, 0, True) == []


def test_smart_slant_when_sidebearings_then_advance_adjusts():
    g, m = _geo(), _model()
    N = g.Node
    layer = g.Layer(shapes=(g.Shape(contours=(g.Contour((N(50, 0), N(150, 0), N(150, 200), N(50, 200))),)),),
                    advance=200)  # fmt: skip
    rows = m.smart_changes(layer, 10, True, False)
    steps = [s for r in rows for s in (r.edit or ())]
    assert any(s[0] == "advance" for s in steps)
    plain = [
        s for r in m.smart_changes(layer, 10, False, False) for s in (r.edit or ())
    ]
    assert not any(s[0] == "advance" for s in plain)
    with pytest.raises(ValueError):
        m.smart_check(85)
    assert isinstance(m.smart_changes(g.Layer(), 10, True, False), (str, list))


def test_selection_changes_when_nodes_selected_then_rotate_about_their_centre():
    g, m = _geo(), _model()
    N = g.Node
    contour = g.Contour(
        (N(0, 0, selected=True), N(100, 0, selected=True), N(100, 100), N(0, 100))
    )
    layer = g.Layer(shapes=(g.Shape(contours=(contour,)),))
    rows = m.selection_changes(layer, m.REFLECTIONS["horizontal"])
    moved = {s[3]: (s[4], s[5]) for r in rows for s in (r.edit or ()) if s[0] == "node"}
    assert moved == {0: (100, 0), 1: (0, 0)}
    assert m.selection_changes(g.Layer(shapes=(g.Shape(contours=(contour._replace(nodes=(N(0, 0),)),)),)),
                               m.rotation_linear(10)) == []  # fmt: skip
    component = g.Shape(component=True, selected=True, box=(0, 0, 10, 10))
    rotated = m.selection_changes(g.Layer(shapes=(component,)), m.rotation_linear(90))
    assert any(s[0] == "shape" for r in rotated for s in (r.edit or ()))


# Native -------------------------------------------------------------------
def test_native_when_snapshot_and_write_then_round_trip():
    native = importlib.import_module(f"{PKG}.native")
    g = _geo()
    pkg = package()
    layer = pkg.layer("A")
    snap = native.snapshot(layer)
    assert (
        snap.anchors == (("top", 50.0, 100.0),)
        and snap.shapes[0].contours[0].nodes[0].selected
    )
    native.write(layer, (("node", 0, 0, 0, 5, 6, True), ("anchor", 0, 1, 2), ("advance", 600),
                         ("remove", 0, 0, (3,), 3), ("shape", 0, g.translate(10, 0), True)))  # fmt: skip
    after = native.snapshot(layer)
    assert [(n.x, n.y) for n in after.shapes[0].contours[0].nodes][:2] == [
        (15, 6),
        (110, 0),
    ]
    assert after.anchors == (("top", 1.0, 2.0),) and after.advance == 600
    assert ("changed",) in pkg.log and ("bake",) in pkg.log
    assert native.matrix_of(None) == g.IDENTITY


# Session ------------------------------------------------------------------
def scale(m, sx=200):
    return lambda name, master, snap: m.transform_planner_changes(
        snap, m.linear(sx, 100, 0, 0), 2, (0, 0), True
    )


def test_apply_when_scaled_then_one_labelled_step_on_explicit_layer():
    m, s = _model(), studio()
    assert s.apply("transform", scale(m), ["A"])
    assert s.shell.calls == [
        ("Transform Studio: transform A", ["A"], [("A", "Regular")])
    ]
    after = layer_of(s.shell.pkg, "A")
    assert after.shapes[0].contours[0].nodes[1].x == 200 and after.anchors == (
        ("top", 100.0, 100.0),
    )
    assert layer_of(s.shell.pkg, "A", "Bold").shapes[0].contours[0].nodes[1].x == 100
    assert s.apply("transform", scale(m), ["A", "O"], all_masters=True)
    assert s.shell.calls[-1] == ("Transform Studio: transform 2 glyphs", ["A", "O"],
                                 [("A", "Regular"), ("A", "Bold"), ("O", "Regular"), ("O", "Bold")])  # fmt: skip


def test_apply_when_shared_and_scaled_outlines_then_whole_glyph_composed():
    """I2 regression: shared and scaled own outlines get the composed transform; read-back passes."""
    from PySide6.QtGui import QTransform

    m, g, native = _model(), _geo(), importlib.import_module(f"{PKG}.native")
    pkg = package()
    pkg.add("S", lambda log: [NShape([square(log)], log=log),
                              NShape([square(log)], refs=2, log=log),
                              NShape([square(log)], transform=QTransform(2, 0, 0, 2, 0, 0), log=log)])  # fmt: skip
    s = studio(pkg)
    move = lambda name, master, snap: m.transform_planner_changes(  # noqa: E731
        snap, m.linear(100, 100, 0, 0), 2, (30, 0), False
    )
    assert s.apply("transform", move, ["S"])
    assert s.shell.calls[-1] == ("Transform Studio: transform S", ["S"], [("S", "Regular")])
    after = native.snapshot(pkg.layer("S"))
    assert after.shapes[0].matrix == g.IDENTITY and after.shapes[0].contours[0].nodes[0].x == 30
    assert after.shapes[1].matrix == g.translate(30, 0), "shared outline composed, nodes untouched"
    assert after.shapes[1].contours[0].nodes[0].x == 0
    assert after.shapes[2].matrix == (2, 0, 0, 2, 30, 0), "scaled outline composed"
    assert "Partly" not in s.shell.status.text()


def test_plan_when_previewed_then_no_history_and_no_native_write():
    m, s = _model(), studio()
    seen = []
    s.preview = SimpleNamespace(
        set_overlay=seen.append, load=lambda *a: None, refresh=lambda: None
    )
    s.set_glyphs(["A"])
    rows = s.plan(scale(m), all_masters=True)
    assert len(rows) == 2 and s.shell.calls == [] and s.shell.pkg.writes() == []
    overlay = s.ghost(rows)
    assert seen == [overlay] and overlay.contours[0].points[1].x == 200
    s.set_glyphs(["Z"])
    assert s.ghost(s.plan(scale(m))) is None and seen[-1] is None


def test_apply_when_hinted_then_refused_until_opt_in_or_hints_removed():
    m, s = _model(), studio()
    assert not s.apply("transform", scale(m), ["H"])
    assert "Edit hinted layers anyway" in s.status and s.shell.calls == []
    assert s.apply("transform", scale(m), ["H"], allow_hinted=True)
    assert s.shell.calls[-1][0] == "Transform Studio: transform H"
    s2 = studio()
    s2._commit = lambda label, layers, glyphs, mutate, read_back: (
        s2.shell.calls.append((label,)),
        mutate(),
    )
    assert s2.remove_hints(["H"], all_masters=True) == 2
    assert (
        s2.remove_hints(["A"]) == 0
        and s2.status == f"{APP_LABEL}: no PostScript hints removed."
    )


def test_apply_when_missing_auto_empty_or_errors_then_notes_and_no_write():
    m, s = _model(), studio()
    pkg = s.shell.pkg
    pkg.add("Q", lambda log: [NShape([square(log)], log=log)], masters=["Regular"])
    pkg.add("U", lambda log: [NShape([square(log)], log=log)], auto=True)
    rows = s.plan(scale(m), ["Q", "U", "Z"], all_masters=True)
    notes = {(r.glyph, r.master): r.note for r in rows}
    assert (
        notes[("Q", "Bold")] == _session().MISSING_NOTE
        and notes[("U", "Regular")] == _session().AUTO_NOTE
    )
    centre = lambda name, master, snap: m.transform_planner_changes(  # noqa: E731
        snap, m.linear(200, 100, 0, 0), 0, (0, 0), True
    )
    assert s.plan(centre, ["Z"])[0].note == m.EMPTY_NOTE
    assert (
        not s.apply("transform", scale(m), ["Z"])
        and s.status == f"{APP_LABEL}: no change."
    )
    assert (
        not s.apply("transform", scale(m), ["Nope"])
        and s.status == f"{APP_LABEL}: Glyph Nope is not in the font."
    )
    problem = lambda name, master, snap: [  # noqa: E731
        _geo().Change("x", "", "", (("advance", 1),), problem="bad")
    ]
    assert (
        not s.apply("transform", problem, ["A"])
        and s.status == f"{APP_LABEL}: refused. A (Regular): bad"
    )
    s.shell.refuse = True
    assert (
        not s.apply("transform", scale(m), ["A"])
        and s.shell.calls[-1][0] == "Transform Studio: transform A"
    )
    with pytest.raises(ValueError, match="glyph"):
        s.plan(scale(m), [])


def test_apply_when_native_drops_a_write_then_partly_applied(monkeypatch):
    pkg = Package()
    pkg.add(
        "R", lambda log: [NShape([square(log, rounding=True, selected=(0,))], log=log)]
    )
    s = studio(pkg)
    planner = lambda name, master, snap: [  # noqa: E731
        _geo().Change("n", "", "", (("node", 0, 0, 0, 0.3, 0.0, None),))
    ]
    assert s.apply(
        "nudge", planner, ["R"]
    )  # sub-unit rounding stays inside the 0.5-unit read-back tolerance
    moved = lambda name, master, snap: [  # noqa: E731
        _geo().Change("n", "", "", (("node", 0, 0, 1, 7.0, 0.0, None),))
    ]
    monkeypatch.setattr(
        importlib.import_module(f"{PKG}.native"), "write", lambda layer, steps: None
    )
    assert not s.apply("nudge", moved, ["R"])
    assert (
        s.status.startswith("Partly applied: Transform Studio: nudge R.")
        and "Undo" in s.status
    )


def test_studio_when_no_font_then_says_so():
    s = _session().Studio(Shell(None))
    s.reload()
    assert s.shell.statuses[-1] == _session().NO_FONT
    with pytest.raises(ValueError):
        s.targets(False)
    assert not s.apply("transform", lambda *a: [], ["A"])


def test_studio_reads_when_masters_switch_then_restored():
    s = studio()
    assert s.italic_angle() == -12.0 and s.x_height("Bold") == 500.0
    assert s.italic_angles(["Bold", "Regular"]) == {"Bold": -10.0, "Regular": -12.0}
    assert s.shell.pkg.master == "Regular"
    s.shell.pkg.master = "Bold"
    assert (
        s.italic_angles(["Regular"]) == {"Regular": -12.0}
        and s.shell.pkg.master == "Bold"
    )
    s2 = _session().Studio(Shell(package()), selection=lambda: ["A", "A", "O"])
    assert s2.use_selection() == ["A", "O"]


def test_default_readers_when_called_then_use_scripting_and_metrics(monkeypatch):
    session = _session()
    monkeypatch.setattr(
        "fontlabapp.core.scripting.names_selected_names", lambda: ["B"], raising=False
    )
    assert session._selection() == ["B"]
    assert session._metrics(None, "Bold").xHeight == 500


# Qt tabs ------------------------------------------------------------------
@pytest.fixture
def ss(studio_qt, monkeypatch):  # noqa: F811
    from PySide6.QtWidgets import QWidget

    import fontlabapp.core.edit_guards as guards
    import fontlabapp.core.history.glyphs as history

    studios = importlib.import_module(PKG)
    commits = []

    def commit(title, layers, glyphs, mutate, **kwargs):
        commits.append(
            (
                title,
                [(layer.glyph, layer.master) for layer in layers],
                [g.name for g in glyphs],
            )
        )
        mutate()
        problems = tuple(kwargs["read_back"]()) if kwargs.get("read_back") else ()
        return SimpleNamespace(pending_note="", mismatches=problems)

    monkeypatch.setattr(guards, "require_history_scope", lambda glyphs, **k: None)
    monkeypatch.setattr(
        history, "scan_auto_facts", lambda package: SimpleNamespace(users={})
    )
    monkeypatch.setattr(history, "commit", commit)

    class QtPreview(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def load(self, *args):
            self.calls.append(("load", *args))

        def refresh(self):
            self.calls.append(("refresh",))

        def set_overlay(self, overlay):
            self.calls.append(("set_overlay", overlay))

        def highlight(self, **kwargs):
            self.calls.append(("highlight", kwargs))

    pkg, preview = package(), QtPreview()
    shell = studios.show(
        package=lambda: pkg,
        font=lambda: object(),
        preview=lambda shell, studio: preview,
    )
    studio_qt.owned.append(shell)
    shell.transform_studio._metrics = Metrics
    yield SimpleNamespace(shell=shell, studio=shell.transform_studio, pkg=pkg, preview=preview, commits=commits,
                          tabs=sys.modules[TABS], studios=studios)  # fmt: skip


def tab(ss, index):
    return next(
        view.__self__
        for view in ss.studio.views
        if isinstance(view.__self__, ss.tabs.TAB_CLASSES[index][1])
    )


def click(t, text):
    from PySide6.QtWidgets import QPushButton

    button = next(b for b in t.widget.findChildren(QPushButton) if b.text() == text)
    button.click()


def overlays(ss):
    return [c[1] for c in ss.preview.calls if c[0] == "set_overlay"]


def test_show_when_built_then_three_tabs(ss):
    assert ss.studios.TAB_TITLES == ("Transform", "Slant", "Rotate & reflect")
    assert len(ss.studio.views) == 3 and ss.shell.preview is ss.preview
    assert (
        tab(ss, 0).write_note.text() == "Writes go to Regular unless All masters is on."
    )
    assert ss.studios.studio_for(ss.shell) is ss.studio


def test_transform_tab_when_preview_then_ghost_and_apply_labelled(ss):
    t = tab(ss, 0)
    t.glyphs_field.setText("A")
    t.scale_x.setValue(150)
    t.origin.setCurrentIndex(2)
    click(t, "Preview transform")
    assert ss.commits == [] and ss.pkg.writes() == []
    assert (
        ss.shell.status.text()
        == f"{APP_LABEL}: 1 change(s) planned on 1 layer(s); nothing written."
    )
    assert (
        overlays(ss)[-1] is not None and overlays(ss)[-1].contours[0].points[1].x == 150
    )
    click(t, "Transform")
    assert ss.commits == [("Transform Studio: transform A", [("A", "Regular")], ["A"])]
    assert overlays(ss)[-1] is None and ("refresh",) in ss.preview.calls
    t.scale_x.setValue(0)
    assert (
        t.scale_x.value() == 1
    )  # the 1% floor keeps the original's flatten refusal unreachable from the UI


def test_transform_tab_when_hinted_then_refused_then_opt_in(ss):
    t = tab(ss, 0)
    t.glyphs_field.setText("H")
    t.move_x.setValue(10)
    t.origin.setCurrentIndex(2)
    click(t, "Transform")
    assert ss.commits == [] and "Edit hinted layers anyway" in ss.shell.status.text()
    t.allow_hinted.setChecked(True)
    click(t, "Transform")
    assert ss.commits[-1][0] == "Transform Studio: transform H"


def test_slant_tab_when_italic_and_smart_then_labelled_steps(ss):
    t = tab(ss, 1)
    t.glyphs_field.setText("A")
    t.refresh()
    assert (
        t.italic.text() == "Current master’s italic angle (-12°)"
        and t.italic.isEnabled()
    )
    t.italic.click()
    assert t.angle.value() == 12
    click(t, "Preview slant")
    assert ss.commits == [] and overlays(ss)[-1] is not None
    t.all_masters.setChecked(True)
    click(t, "Slant")
    assert ss.commits[-1] == (
        "Transform Studio: slant A",
        [("A", "Regular"), ("A", "Bold")],
        ["A"],
    )
    t.sidebearings.setChecked(True)
    click(t, "Preview smart slant")
    click(t, "Smart slant")
    assert ss.commits[-1][0] == "Transform Studio: smart slant A"
    ss.pkg.angles["Regular"] = 0.0
    t.refresh()
    assert not t.italic.isEnabled()


def test_rotate_tab_when_presets_and_reflections_then_selection_moves(ss):
    t = tab(ss, 2)
    t.glyphs_field.setText("A")
    click(t, "Preview rotation")
    assert ss.commits == [] and overlays(ss)[-1] is not None
    click(t, "Rotate")
    assert ss.commits[-1] == ("Transform Studio: rotate A", [("A", "Regular")], ["A"])
    click(t, "45° CW")
    assert ss.commits[-1][0] == "Transform Studio: rotate A"
    click(t, "Preview horizontal reflection")
    click(t, "Reflect horizontal")
    assert ss.commits[-1][0] == "Transform Studio: reflect horizontal A"
    click(t, "Reflect vertical")
    assert ss.commits[-1][0] == "Transform Studio: reflect vertical A"
    assert not t.allow_bases.isVisibleTo(t.widget)


def test_tabs_when_master_row_selection_and_hints_then_follow(ss):
    t = tab(ss, 0)
    t.glyphs_field.setText("A")
    t.master_box.setCurrentIndex(1)
    assert ss.studio.master == "Bold" and ("load", "A", "Bold") in ss.preview.calls
    t.row_chosen("O", "Regular")
    assert ss.studio.master == "Regular"
    t.row_chosen("")
    ss.studio._selection = list
    assert t.use_selection() == []
    ss.studio._selection = lambda: ["H"]
    click(t, "Use font selection")
    assert t.glyphs_field.text() == "H"
    ss.studio._commit = lambda label, layers, glyphs, mutate, read_back: mutate()
    click(t, "Remove PostScript hints")
    assert "removed PostScript hints from 1 layer(s)" in ss.shell.status.text()
    t.glyphs_field.setText("")
    click(t, "Preview transform")
    assert ss.shell.status.text().startswith(f"{APP_LABEL}: ")


def test_records_when_no_change_then_note_row():
    session, tabs = _session(), importlib.import_module(TABS)
    rows = [
        session.Row("A", "Regular", None, (), ""),
        session.Row("O", "Bold", None, (), "auto layer, skipped"),
    ]
    assert tabs.records(rows) == [("A", "Regular", ("Regular", "", "", "", "no change")),
                                  ("O", "Bold", ("Bold", "", "", "", "auto layer, skipped"))]  # fmt: skip


def test_show_when_build_fails_then_shell_closed(studio_qt, monkeypatch):  # noqa: F811
    import fontlabapp.fontui as fontui

    closed = []
    real = fontui.app_shell

    def failing(*args, **kwargs):
        shell = real(*args, **kwargs)
        studio_qt.owned.append(shell)
        shell.add_tab = lambda spec: (_ for _ in ()).throw(RuntimeError("boom"))
        original = shell.close
        shell.close = lambda: (closed.append(True), original())
        return shell

    monkeypatch.setattr(fontui, "app_shell", failing)
    studios = importlib.import_module(PKG)
    with pytest.raises(RuntimeError, match="boom"):
        studios.show(
            package=lambda: None, font=lambda: None, preview=lambda shell, studio: None
        )
    assert closed == [True]


def test_glyph_preview_when_font_then_control_less_tglyph(monkeypatch):
    import fontlabapp.fontui as fontui

    app = importlib.import_module(f"{PKG}.app")
    seen = []
    monkeypatch.setattr(
        fontui, "glyph_view", lambda *a, **k: seen.append((a, k)) or "view"
    )
    shell = SimpleNamespace(widget="w", hint_check="hc")
    assert (
        app._glyph_preview(shell, SimpleNamespace(font=lambda: None, current="Regular"))
        is None
    )
    assert (
        app._glyph_preview(
            shell, SimpleNamespace(font=lambda: "font", current="Regular")
        )
        == "view"
    )
    assert seen == [(("font", "w"), {"layer": "Regular", "controls": False, "label_prefix": APP_LABEL,
                                     "hint_check": "hc"})]  # fmt: skip


def test_registry_when_imported_then_three_tabs_registered_once():
    studios = importlib.import_module("fontlabapp.studios")
    importlib.import_module(PKG)
    assert [spec.title for spec in studios.tabs(APP_LABEL)] == [
        "Transform",
        "Slant",
        "Rotate & reflect",
    ]
    importlib.reload(sys.modules[PKG])
    assert len(studios.tabs(APP_LABEL)) == 3


def test_shell_status_when_status_text_is_property_or_method_then_string(studio_qt):  # noqa: F811
    from types import SimpleNamespace as NS

    from fontlabapp.studios.transform_studio.session import Studio

    own = NS(status="own", shell=NS())
    prop = NS(status="own", shell=NS(status=NS(text="Shell text")))  # PythonQt: str property
    call = NS(status="own", shell=NS(status=NS(text=lambda: "Shell text")))  # PySide: method
    bare = NS(status="own", shell=NS(status=None))
    assert Studio.shell_status(prop) == Studio.shell_status(call) == "Shell text"
    assert Studio.shell_status(bare) == Studio.shell_status(own) == "own"
