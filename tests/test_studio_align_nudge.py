# this_file: tests/test_studio_align_nudge.py
"""Align & Nudge (Phase D A24): planners, session writes and the four tabs on offscreen Qt.

Writes are checked for their explicit layers and their ``Align & Nudge: <action>
<subject>`` Undo label (§1.3/§1.4); previews are checked never to call
``history`` or write native layers while drawing the ghost via ``set_overlay``.
"""

import importlib
import math
import sys
from types import SimpleNamespace

import pytest
from _contour_fakes import (
    Metrics,
    NContour,
    NNode,
    NShape,
    Package,
    Shell,
    hint_counts,
    square,
)
from _studio_qt import studio_qt  # noqa: F401 - fixture

PKG = "fontlabapp.studios.align_nudge"
TABS = f"{PKG}.tabs"
APP_LABEL = "Align & Nudge"


@pytest.fixture(autouse=True)
def qt_align(studio_qt, monkeypatch):  # noqa: F811
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setitem(sys.modules, "fontlab", SimpleNamespace(FontMetrics=Metrics))
    monkeypatch.setattr("fontlabapp.hints.postscript.hint_counts", hint_counts)
    yield studio_qt
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)


def _g():
    return importlib.import_module("fontlabapp.studios.transform_studio.geometry")


def _m():
    return importlib.import_module(f"{PKG}.model")


def poly(points, selected=(), closed=True, **kwargs):
    g = _g()
    return g.Contour(tuple(g.Node(x, y, on, selected=i in selected) for i, (x, y, on) in enumerate(points)),
                     closed=closed, **kwargs)  # fmt: skip


def box(x0=0, y0=0, size=100, selected=(0, 1, 2, 3), **kwargs):
    pts = (
        (x0, y0, True),
        (x0 + size, y0, True),
        (x0 + size, y0 + size, True),
        (x0, y0 + size, True),
    )
    return poly(pts, selected, **kwargs)


def layer(*contours, shapes=None, **kwargs):
    g = _g()
    built = (
        shapes
        if shapes is not None
        else tuple(g.Shape(contours=(c,)) for c in contours)
    )
    return g.Layer(shapes=tuple(built), **kwargs)


def tip(selected=(0,)):
    """Tip (0,0), corner (10,0), handle (20,50), handle (0,80), end (0,100): a closed cubic."""
    return poly(
        ((0, 0, True), (10, 0, True), (20, 50, False), (0, 80, False), (0, 100, True)),
        selected,
    )


def steps(rows):
    return [s for r in rows for s in (r.edit or ())]


# Align & distribute -------------------------------------------------------
def test_align_when_whole_contours_then_move_as_units_to_bounds():
    m = _m()
    lay = layer(box(0), box(200, 50, 50))
    rows = m.align_changes(lay, "left")
    assert {s[3]: s[4] for s in steps(rows) if s[2] == 0 and s[1] == 1} == {
        0: 0,
        1: 50,
        2: 50,
        3: 0,
    }
    assert all(s[1] == 1 for s in steps(rows))
    assert m.align_changes(lay, "top") == []
    bottom = steps(m.align_changes(lay, "bottom"))
    assert {s[5] for s in bottom if s[3] in (0, 1)} == {0}
    centre = m.align_changes(lay, "vertical")
    assert steps(centre) and m.align_changes(lay, "right", coordinate=500)[
        0
    ].new.startswith("500")
    assert m.align_changes(lay, "horizontal", all_nodes=True)


def test_align_when_partial_contour_then_handles_follow_and_distribute():
    m = _m()
    curve = poly(
        ((0, 0, True), (0, 40, False), (60, 100, False), (100, 100, True)),
        selected=(3,),
        closed=False,
    )
    lay = layer(curve, box(200, 0, 10, selected=(0,)), box(500, 0, 10, selected=(0,)))
    moved = steps(m.align_changes(lay, "right"))
    assert ("node", 0, 0, 3, 500.0, 100.0, None) in moved and (
        "node",
        0,
        0,
        2,
        460.0,
        100.0,
        None,
    ) in moved
    spread = steps(m.align_changes(lay, "distribute_x"))
    assert spread == [("node", 1, 0, 0, 300.0, 0.0, None)]
    few = m.align_changes(
        layer(box(selected=(0,)), box(9, selected=(0,))), "distribute_y"
    )
    assert few[-1].new == "select at least three nodes to distribute, kept"


def test_align_when_errors_components_and_skips_then_notes():
    g, m = _g(), _m()
    with pytest.raises(ValueError):
        m.align_changes(layer(box()), "sideways")
    with pytest.raises(ValueError):
        m.align_changes(layer(box()), "left", coordinate=math.inf)
    with pytest.raises(ValueError, match="Distribution"):
        m.align_changes(layer(box()), "distribute_x", all_nodes=True)
    assert m.align_changes(layer(box(selected=())), "left") == []
    assert (
        m.align_changes(layer(box(), locked=True), "left")[0].new
        == "locked or non-body layer, kept"
    )
    comp = g.Shape(
        matrix=g.translate(50, 0), component=True, selected=True, box=(0, 0, 10, 10)
    )
    lay = layer(shapes=(comp, g.Shape(contours=(box(),)), g.Shape(component=True, selected=True),
                        g.Shape(contours=(box(),), locked=True), g.Shape(contours=(box(),), shared=True),
                        g.Shape(contours=(box(matrix=(2, 0, 0, 2, 0, 0)),))))  # fmt: skip
    rows = m.align_changes(lay, "left")
    texts = " | ".join(f"{r.name}: {r.new}" for r in rows)
    assert "no bounding box, kept" in texts and "locked shape, kept" in texts
    assert (
        "shared outline data, kept" in texts
        and "contour has its own transform, kept" in texts
    )
    assert ("shape", 0, g.translate(0, 0), False) in steps(rows)
    owners = poly(
        ((0, 0, True), (5, 5, False), (10, 0, True)), selected=(0, 2), closed=True
    )
    assert (
        "two selected owners"
        in m.align_changes(layer(owners, box(50, selected=(0,))), "left")[0].new
    )
    with pytest.raises(ValueError):
        m.position([(0, math.inf)], 1, 0.5)
    with pytest.raises(ValueError):
        m.group_steps(lay, ("node", 1, [], []), math.nan, 0)


# Interpolated nudge -------------------------------------------------------
def test_nudge_when_one_end_moves_then_handles_scale():
    m = _m()
    points = [(0, 0, True), (0, 40, False), (60, 100, False), (100, 100, True)]
    result = m.nudged(points + [(100, 0, True)], {3}, 0, 10)
    assert result[3] == (100, 110) and result[2] == (60, 110) and result[1] == (0, 44)
    with pytest.raises(ValueError):
        m.nudged(points, {1}, 0, 1)
    with pytest.raises(ValueError):
        m.nudged(points, {0}, math.inf, 1)
    with pytest.raises(ValueError, match="cubic"):
        m.nudged([(0, 0, True), (1, 1, False), (2, 2, True)], {0}, 1, 1)


def test_nudge_changes_when_selected_then_rows_and_skips():
    g, m = _g(), _m()
    lay = layer(shapes=(g.Shape(contours=(tip(),)), g.Shape(contours=(box(),), shared=True),
                        g.Shape(contours=(box(closed=False),))))  # fmt: skip
    rows = m.nudge_changes(lay, 0, 10)
    assert ("node", 0, 0, 0, 0, 10, None) in steps(rows)
    assert any(r.new == "open or quadratic contour, kept" for r in rows)
    assert m.nudge_changes(layer(box(selected=())), 0, 10)[-1].new == m.NUDGE_EMPTY
    with pytest.raises(ValueError):
        m.nudge_changes(lay, math.nan, 0)


# Overlap nodes ------------------------------------------------------------
def test_overlap_when_tip_selected_then_corner_and_handle_follow_italic():
    g, m = _g(), _m()
    rows = m.overlap_changes(layer(tip()), 0)
    assert steps(rows) == [
        ("node", 0, 0, 1, 0, 0, False),
        ("node", 0, 0, 2, 0, 50, None),
    ]
    slanted = steps(m.overlap_changes(layer(tip()), -10))
    assert slanted[1][4] == math.trunc(math.tan(math.radians(10)) * 50)
    assert m.overlap_changes(layer(box(selected=())), 0) == []
    assert m.overlap_changes(layer(tip(selected=(1,))), 0) == []
    kept = m.overlap_changes(layer(poly(((0, 0, True),), (0,), tt=True)), 0)
    assert kept and all(not r.edit for r in kept)
    with pytest.raises(ValueError, match="italic"):
        m.overlap_changes(layer(tip()), 89)
    for bad, text in ((layer(tip(), locked=True), "Unlock"),
                      (layer(shapes=(g.Shape(contours=(tip(),), shared=True),)), "shared"),
                      (layer(poly(tip().nodes and ((0, 0, True), (1, 0, True), (2, 2, False)), (0,),
                                  matrix=g.translate(1, 0))), "Bake"),
                      (layer(poly(((math.inf, 0, True), (1, 0, True), (2, 2, False)), (0,))), "non-finite"),
                      (layer(shapes=(g.Shape(matrix=(2, 0, 0, 2, 0, 0), contours=(tip(),)),)), "unscaled")):  # fmt: skip
        with pytest.raises(ValueError, match=text):
            m.overlap_changes(bad, 0)


# Simplify -----------------------------------------------------------------
def test_simplify_when_alternate_selected_then_removed_and_structure_checked():
    g, m = _g(), _m()
    rows = m.simplify_changes(layer(box()))
    assert steps(rows) == [("remove", 0, 0, (1,), 3)]
    assert m.removals(box(closed=False)) == [1]
    assert m.removals(tip()) == []
    other = layer(box(selected=()))
    assert steps(m.simplify_changes(other, layer(box()))) == [("remove", 0, 0, (1,), 3)]
    assert m.simplify_changes(layer(box(), box()), layer(box()))[0].problem == m.COUNTS
    assert (
        m.simplify_changes(layer(box(closed=False)), layer(box()))[0].problem
        == m.STRUCTURE
    )
    kept = m.simplify_changes(layer(shapes=(g.Shape(contours=(box(),), shared=True),)))
    assert kept[0].new == "shared outline, kept"


# Session ------------------------------------------------------------------
def package():
    pkg = Package(angles={"Regular": -12.0, "Bold": 0.0})
    pkg.add("A", lambda log: [NShape([square(log, selected=(0, 1, 2, 3)), square(log, 200, 0, 50, (0, 1, 2, 3))],
                                     log=log)])  # fmt: skip

    def tipped(log):
        pts = (
            (0, 0, True),
            (10, 0, True),
            (20, 50, False),
            (0, 80, False),
            (0, 100, True),
        )
        return [NShape([NContour([NNode(x, y, on, selected=i == 0, log=log) for i, (x, y, on) in enumerate(pts)],
                                 log=log)], log=log)]  # fmt: skip

    pkg.add("T", tipped)
    pkg.add(
        "H",
        lambda log: [NShape([square(log, selected=(0, 1, 2, 3))], log=log)],
        hinted=True,
    )
    return pkg


def test_session_when_applied_then_label_names_align_and_nudge():
    session = importlib.import_module(f"{PKG}.session")
    model = _m()
    s = session.Studio(Shell(package()), metrics=Metrics)
    s.reload()
    assert s.APP == APP_LABEL
    assert s.apply(
        "align", lambda n, ma, snap: model.align_changes(snap, "left"), ["A"]
    )
    assert s.shell.calls == [("Align & Nudge: align A", ["A"], [("A", "Regular")])]
    assert not s.apply(
        "simplify", lambda n, ma, snap: model.simplify_changes(snap), ["H"]
    )
    assert "Edit hinted layers anyway" in s.status


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
    yield SimpleNamespace(shell=shell, studio=shell.align_nudge, pkg=pkg, preview=preview, commits=commits,
                          tabs=sys.modules[TABS], studios=studios)  # fmt: skip


def tab(ss, index):
    return next(
        view.__self__
        for view in ss.studio.views
        if isinstance(view.__self__, ss.tabs.TAB_CLASSES[index][1])
    )


def click(t, text):
    from PySide6.QtWidgets import QPushButton

    next(b for b in t.widget.findChildren(QPushButton) if b.text() == text).click()


def overlays(ss):
    return [c[1] for c in ss.preview.calls if c[0] == "set_overlay"]


def test_show_when_built_then_four_tabs(ss):
    assert ss.studios.TAB_TITLES == (
        "Align & distribute",
        "Interpolated nudge",
        "Overlap nodes",
        "Simplify",
    )
    assert len(ss.studio.views) == 4 and ss.studios.studio_for(ss.shell) is ss.studio
    assert not tab(ss, 0).allow_bases.isVisibleTo(tab(ss, 0).widget)
    assert not tab(ss, 2).allow_bases.isVisibleTo(tab(ss, 2).widget)
    assert tab(ss, 1).allow_bases.isVisibleTo(tab(ss, 1).widget)


def test_align_tab_when_preview_then_ghost_then_apply_labelled(ss):
    t = tab(ss, 0)
    t.glyphs_field.setText("A")
    click(t, "Preview alignment")
    assert ss.commits == [] and ss.pkg.writes() == [] and overlays(ss)[-1] is not None
    click(t, "Align")
    assert ss.commits == [("Align & Nudge: align A", [("A", "Regular")], ["A"])]
    assert overlays(ss)[-1] is None
    t.operation.setCurrentIndex(6)
    assert not t.reference.isEnabled() and not t.coordinate.isEnabled()
    t.geometry.setCurrentIndex(1)
    click(t, "Preview alignment")
    assert ss.shell.status.text() == f"{APP_LABEL}: {_m().DISTRIBUTE_ALL}"
    t.operation.setCurrentIndex(4)
    t.geometry.setCurrentIndex(0)
    t.reference.setCurrentIndex(1)
    assert t.coordinate.isEnabled()
    t.coordinate.setValue(300)
    t.all_masters.setChecked(True)
    click(t, "Align")
    assert ss.commits[-1] == (
        "Align & Nudge: align A",
        [("A", "Regular"), ("A", "Bold")],
        ["A"],
    )


def test_nudge_tab_when_defaults_then_y_ten(ss):
    t = tab(ss, 1)
    assert (t.dx.value(), t.dy.value()) == (0, 10)
    t.glyphs_field.setText("T")
    click(t, "Preview nudge")
    assert ss.commits == [] and overlays(ss)[-1] is not None
    click(t, "Nudge")
    assert ss.commits[-1][0] == "Align & Nudge: nudge T"


def test_overlap_tab_when_masters_then_each_italic_angle(ss):
    t = tab(ss, 2)
    t.glyphs_field.setText("T")
    t.all_masters.setChecked(True)
    click(t, "Preview overlap")
    assert ss.commits == []
    assert ss.pkg.master == "Regular" and overlays(ss)[-1] is not None
    click(t, "Overlap")
    assert ss.commits[-1] == (
        "Align & Nudge: overlap T",
        [("T", "Regular"), ("T", "Bold")],
        ["T"],
    )
    t.glyphs_field.setText("A")
    click(t, "Overlap")
    assert "no change" in ss.shell.status.text()


def test_simplify_tab_when_all_masters_then_preview_master_selection_drives(ss):
    t = tab(ss, 3)
    t.glyphs_field.setText("A")
    t.all_masters.setChecked(True)
    click(t, "Preview simplification")
    assert ss.commits == []
    click(t, "Simplify")
    assert ss.commits[-1] == (
        "Align & Nudge: simplify A",
        [("A", "Regular"), ("A", "Bold")],
        ["A"],
    )
    t.glyphs_field.setText("Nope")
    click(t, "Simplify")
    assert "Nope" in ss.shell.status.text()


def test_simplify_tab_when_opened_then_all_masters_and_compatible_by_default(ss):
    """I1: Simplify is structural; like the original it defaults to All masters + Keep masters compatible."""
    tabs = ss.tabs
    t = tab(ss, 3)
    assert t.all_masters.isChecked() and t.compatible.isChecked()
    assert t.compatible.text() == tabs.COMPATIBLE_LABEL
    assert not tab(ss, 0).all_masters.isChecked(), "other tabs keep the current-master default"
    t.glyphs_field.setText("A")
    click(t, "Simplify")
    assert ss.commits[-1] == ("Align & Nudge: simplify A", [("A", "Regular"), ("A", "Bold")], ["A"])
    for master in ("Regular", "Bold"):
        nodes = ss.pkg.layer("A", master).shapes[0].contours[0].nodes()
        assert len(nodes) == 3, f"{master} keeps the same structure"


def test_simplify_tab_when_compatible_then_holds_back_incompatible_or_partial_scope(ss):
    tabs = ss.tabs
    missing = importlib.import_module("fontlabapp.studios.transform_studio.session").MISSING_NOTE
    ss.pkg.add("R", lambda log: [NShape([square(log, selected=(0, 1))], log=log)], masters=["Regular"])
    t = tab(ss, 3)
    t.glyphs_field.setText("R")
    before = len(ss.commits)
    click(t, "Simplify")
    assert len(ss.commits) == before, "R only exists in one master: held back"
    assert [(r.master, r.note) for r in ss.studio.rows] == [("Regular", tabs.DIFFER_NOTE), ("Bold", missing)]
    t.glyphs_field.setText("A")
    t.all_masters.setChecked(False)
    click(t, "Simplify")
    assert len(ss.commits) == before and [r.note for r in ss.studio.rows] == [tabs.SCOPE_NOTE]
    t.compatible.setChecked(False)
    click(t, "Simplify")
    assert ss.commits[-1] == ("Align & Nudge: simplify A", [("A", "Regular")], ["A"])
    assert len(ss.pkg.layer("A", "Bold").shapes[0].contours[0].nodes()) == 4


def test_safe_when_planner_raises_then_problem_row(ss):
    planner = ss.tabs._safe(
        lambda name, master, snap: (_ for _ in ()).throw(ValueError("bad tip"))
    )
    assert planner("A", "Regular", None)[0].problem == "bad tip"
    ss.pkg.add("Q", lambda log: [NShape([square(log)], log=log)], masters=["Bold"])
    simplify = tab(ss, 3).planner()
    ss.studio.master = "Regular"
    assert simplify("Q", "Bold", None)[0].problem == _m().COUNTS


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
    assert seen[0][1]["label_prefix"] == APP_LABEL and seen[0][1]["controls"] is False


def test_registry_when_imported_then_four_tabs_registered_once():
    studios = importlib.import_module("fontlabapp.studios")
    importlib.import_module(PKG)
    titles = ["Align & distribute", "Interpolated nudge", "Overlap nodes", "Simplify"]
    assert [spec.title for spec in studios.tabs(APP_LABEL)] == titles
    importlib.reload(sys.modules[PKG])
    assert len(studios.tabs(APP_LABEL)) == 4
