# this_file: tests/test_studio_interpolation_doctor.py
"""Interpolation Doctor (Phase D A5): literal findings, read-only tabs, the blend ghost and Make Compatible.

Check, Node counts and Preview must never call ``history`` nor touch a native
object (the fakes log every native write). Make Compatible writes only the
planned explicit layers inside one ``Interpolation Doctor: Make compatible
<subject>`` step. Findings are pinned on exact (glyph, master) layers with
the originals' literal text.
"""

import importlib
import sys
from types import SimpleNamespace

import pytest
from _contour_fakes import Metrics, Shell, hint_counts
from _interp_fakes import IPackage, extra_layer
from _outline_fakes import T, OContour, OShape, box
from _studio_qt import studio_qt  # noqa: F401 - fixture

PKG = "fontlabapp.studios.interpolation_doctor"
APP_LABEL = "Interpolation Doctor"


@pytest.fixture(autouse=True)
def qt_doctor(studio_qt, monkeypatch):  # noqa: F811
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setitem(sys.modules, "fontlab", SimpleNamespace(FontMetrics=Metrics))
    monkeypatch.setattr("fontlabapp.hints.postscript.hint_counts", hint_counts)
    yield studio_qt
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)


def mod(name):
    return importlib.import_module(f"{PKG}.{name}")


# Fixture font: A compatible, B 4 vs 3 nodes, C components swapped, D anchors differ, E line vs cubic.
def square(log, master=None):
    return [OShape([box(0, 0, 100, log)], log=log)]


def tri(log):
    return OContour([(0, 0, True), (100, 0, True), (50, 90, True)], log=log)


def curvy(log):
    spec = [(0, 0, True), (100, 0, True), (130, 30, False), (130, 70, False), (100, 100, True), (0, 100, True)]
    return OContour(spec, log=log)


def build_a(log, master):
    size = 100 if master == "Regular" else 200
    return [OShape([box(0, 0, size, log)], log=log)], [("top", 50, 100)]


def build_b(log, master):
    return [OShape([box(0, 0, 100, log) if master == "Regular" else tri(log)], log=log)]


def build_c(log, master):
    order = ("A", "B") if master == "Regular" else ("B", "A")
    return [OShape(component=name, log=log) for name in order]


def build_d(log, master):
    anchors = [("top", 1, 1), ("bottom", 1, 1)] if master == "Regular" else [("top", 1, 1)]
    return square(log), anchors


def build_e(log, master):
    return [OShape([box(0, 0, 100, log) if master == "Regular" else curvy(log)], log=log)]


def font(**extra):
    pkg = IPackage()
    for name, build in (("A", build_a), ("B", build_b), ("C", build_c), ("D", build_d), ("E", build_e)):
        pkg.add(name, build)
    for name, (build, kwargs) in extra.items():
        pkg.add(name, build, **kwargs)
    return pkg


def doctor(pkg, **kwargs):
    d = mod("session").Doctor(Shell(pkg), metrics=Metrics, select=kwargs.pop("select", lambda p, n: list(n)),
                              **kwargs)  # fmt: skip
    d.reload()
    return d


def untouched(d, pkg):
    return d.shell.calls == [] and pkg.writes() == []


# Check: Masters, Anchors, Components ----------------------------------------------------
def test_check_masters_when_selection_then_literal_rows_marks_and_no_history():
    pkg = font()
    d = doctor(pkg)
    found = d.check("masters", ["A", "B", "C", "D", "E", "missing"])
    assert untouched(d, pkg)
    assert found.flagged == ["B", "C", "D", "E"]
    assert found.status == "4 of 5 glyphs incompatible" and d.status == f"{APP_LABEL}: 4 of 5 glyphs incompatible"
    rows = {(g, m): v for g, m, v in found.records}
    assert rows[("A", None)] == ("", "", "", "", "", "✓")
    assert rows[("B", None)] == ("", "", "", "", "", "✗ contours")
    assert rows[("B", "Regular")] == ("Regular", "1", "4 ≠", "0", "0", "")
    assert rows[("B", "Bold")] == ("Bold", "1", "3 ≠", "0", "0", "")
    assert rows[("C", None)][-1] == "✗ components" and rows[("D", None)][-1] == "✗ anchors"
    assert rows[("D", "Regular")] == ("Regular", "1", "4", "2 ≠", "0", "")
    assert found.marks[("B", "Bold")] == ((0, 0), (0, 1), (0, 2))
    assert found.marks[("A", "Regular")] == ()


def test_check_masters_when_auto_or_missing_layer_then_noted():
    pkg = font(F=(build_a, {"auto": ("Bold",)}), G=(build_a, {"masters": ("Regular",)}))
    d = doctor(pkg)
    found = d.check("masters", ["F", "G"])
    rows = {(g, m): v for g, m, v in found.records}
    assert rows[("F", "Bold")] == ("Bold", "auto layer · not compared", "", "", "", "")
    assert rows[("F", None)][-1] == "✓"
    assert rows[("G", None)][-1] == "✗ missing layer" and found.flagged == ["G"]


def test_check_anchors_when_whole_font_then_mismatch_first_and_only_bad_filter():
    pkg = font()
    d = doctor(pkg)
    found = d.check("anchors", whole_font=True)
    assert untouched(d, pkg) and found.flagged == ["D"]
    assert found.records == [
        ("D", None, ("", "", "", "", "", "✗")),
        ("D", "Regular", ("Regular", "", "", "2: bottom, top", "", "")),
        ("D", "Bold", ("Bold", "", "", "1: top", "", "missing: bottom")),
        ("A", None, ("", "", "", "", "", "✓")),
        ("A", "Regular", ("Regular", "", "", "1: top", "", "")),
        ("A", "Bold", ("Bold", "", "", "1: top", "", "")),
    ]
    assert found.status == "1 glyph with different anchors across masters"
    assert [r[0] for r in d.check("anchors", whole_font=True, only_bad=True).records] == ["D"] * 3
    assert d.check("anchors", ["A"]).status == "All masters carry the same anchor names"


def test_check_anchors_when_auto_layer_then_auto_cell():
    pkg = font(F=(build_a, {"auto": ("Bold",)}))
    found = doctor(pkg).check("anchors", ["F"])
    assert ("F", "Bold", ("Bold", "", "", "auto", "", "")) in found.records


def test_check_components_when_order_differs_then_red_master():
    pkg = font()
    d = doctor(pkg)
    found = d.check("components", whole_font=True)
    assert untouched(d, pkg) and found.flagged == ["C"]
    assert found.records == [
        ("C", None, ("", "", "", "", "", "✗")),
        ("C", "Regular", ("Regular", "", "", "", "A + B", "")),
        ("C", "Bold", ("Bold", "", "", "", "B + A", "differs from the first master")),
    ]
    assert found.status == "1 glyph with incompatible components"
    assert d.check("components", ["C"], only_bad=True).records[0][0] == "C"
    pkg2 = IPackage()
    pkg2.add("C", lambda log, m: [OShape(component="A", log=log)])
    assert doctor(pkg2).check("components", ["C"], only_bad=True).records == []
    assert doctor(pkg2).check("components", ["C"]).status == "All composites have the same components on every master"


def test_check_when_unknown_kind_or_no_font_then_value_error():
    d = doctor(font())
    with pytest.raises(ValueError, match="Unknown check"):
        d.check("kerning", ["A"])
    with pytest.raises(ValueError, match="Choose glyphs"):
        d.check("masters", [])
    empty = mod("session").Doctor(Shell(None))
    empty.reload()
    with pytest.raises(ValueError, match="Open a font"):
        empty.check("masters", ["A"])
    with pytest.raises(ValueError, match="Open a font"):
        empty.node_counts(["A"])


def test_component_name_when_no_base_then_shape_name():
    model = mod("model")
    assert model.component_name(SimpleNamespace(name="x", shapeData=SimpleNamespace(componentGlyph=None))) == "x"
    assert model.component_name(SimpleNamespace(name="x", shapeData=SimpleNamespace(componentGlyph="A"))) == "A"


# Node counts --------------------------------------------------------------------------
def test_node_counts_when_whole_font_then_literal_cells_and_no_history():
    pkg = font()
    d = doctor(pkg)
    found = d.node_counts(whole_font=True)
    assert untouched(d, pkg)
    assert found.flagged == ["B", "E"]  # A differs in size only, not in counts
    rows = {(g, m): v for g, m, v in found.records}
    assert rows[("B", "Regular")] == ("Regular", "1 / 4", "✗ differ")
    assert rows[("B", "Bold")] == ("Bold", "1 / 3 ≠", "✗ differ")
    assert rows[("E", "Bold")] == ("Bold", "1 / 6 ≠", "✗ differ")
    assert rows[("C", "Regular")] == ("Regular", "0 / 0", "✓")
    assert found.status == "2 of 5 glyphs have masters that differ"
    only = d.node_counts(["A", "B"], only_flagged=True)
    assert {g for g, _, _ in only.records} == {"B"}


def test_node_counts_when_auto_layer_then_auto_never_odd():
    pkg = font(F=(build_a, {"auto": ("Bold",)}))
    found = doctor(pkg).node_counts(["F"])
    assert ("F", "Bold", ("Bold", "auto", "✓")) in found.records
    model = mod("model")
    assert model.odd_cells({"a": (1, 4), "b": (1, 4), "c": (1, 3), "d": None}) == ["c"]
    assert model.odd_cells({"a": (1, 4)}) == []


# Literal reports ---------------------------------------------------------------------
def test_report_node_when_b_and_e_then_literal_text():
    pkg = font()
    d = doctor(pkg)
    text = d.report("node", ["B", "E", "B"])
    assert untouched(d, pkg)
    assert text == (
        "🔠 Glyph: B\n\n    ⭕️ Master: Regular\n     • Paths: 1\n     • Nodes: 4 (Lines: 4 · Curves: 0)\n"
        "     • Handles: 0\n     • Total Points: 4\n\n    ⭕️ Master: Bold\n     • Paths: 1\n"
        "     • Nodes: 3 (Lines: 3 · Curves: 0)\n     • Handles: 0\n     • Total Points: 3\n"
        "  ⚠️ Incompatibility in master 'Bold':\n     • Path #1 mismatch → Expected (4, 0), Found (3, 0)\n"
        "     • First difference at node #4: Expected LINE, Found —\n\n" + "-" * 100 + "\n"
        "  ⚠️ Masters are not compatible with the reference master.\n"
        "🔠 Glyph: E\n\n    ⭕️ Master: Regular\n     • Paths: 1\n     • Nodes: 4 (Lines: 4 · Curves: 0)\n"
        "     • Handles: 0\n     • Total Points: 4\n\n    ⭕️ Master: Bold\n     • Paths: 1\n"
        "     • Nodes: 4 (Lines: 3 · Curves: 1)\n     • Handles: 2\n     • Total Points: 6\n"
        "  ⚠️ Incompatibility in master 'Bold':\n     • Path #1 mismatch → Expected (4, 0), Found (4, 2)\n"
        "     • First difference at node #2: Expected LINE, Found OFFCURVE\n\n" + "-" * 100 + "\n"
        "  ⚠️ Masters are not compatible with the reference master."
    )
    assert d.report("node", ["A"]).endswith("  ✅ All masters are fully compatible with the reference master.")


def test_report_node_when_path_missing_or_master_missing_then_text_or_refusal():
    pkg = font(F=(lambda log, m: [OShape([box(0, 0, 10, log)] * (2 if m == "Bold" else 1), log=log)], {}),
               G=(build_a, {"masters": ("Regular",)}))  # fmt: skip
    d = doctor(pkg)
    assert "  ⚠️ Incompatibility in master 'Bold': Path #2 → Path missing in reference master." in d.report("node", ["F"])
    with pytest.raises(ValueError, match="missing a valid master layer"):
        d.report("node", ["G"])
    model = mod("model")
    with pytest.raises(ValueError, match="No glyph selected"):
        model.node_report([])
    with pytest.raises(ValueError, match="no master layers"):
        model.node_report([("A", [])])


def test_report_why_when_foreground_layers_then_adjacent_pairs_literal():
    pkg = font()
    glyph = pkg.findName("D")
    extra_layer(glyph, "mask.Regular", mask=True)
    extra_layer(glyph, "Sketch", [OShape([tri([])])])
    d = doctor(pkg)
    text = d.report("why", ["D", "C", "A"])
    assert untouched(d, pkg)
    assert text == (
        "D is not compatible\n"
        "anchors differ:\n  Regular has bottom, top\n  Bold has top\n"
        "path 1, node count differ:\n  Bold has 4\n  Sketch has 3\n"
        "anchors differ:\n  Bold has top\n  Sketch has \n\n\n"
        "C is compatible\n\n\n"  # the original compares component name sets, not order
        "A is compatible\n\n\n"
    )


def test_report_why_literal_lines_are_pinned():
    model = mod("model")
    L = model.Layer
    text = model.why_report([("D", [L("Regular", (("line",) * 4,), frozenset({"top", "bottom"}), frozenset()),
                                    L("Bold", (("line",) * 4,), frozenset({"top"}), frozenset()),
                                    L("Sketch", (("line",) * 3,), frozenset(), frozenset({"A"})),
                                    L("Alt", (("line", "curve", "line"),), frozenset(), frozenset({"A"})),
                                    L("None", (), frozenset(), frozenset({"A"}))])])  # fmt: skip
    assert text == (
        "D is not compatible\n"
        "anchors differ:\n  Regular has bottom, top\n  Bold has top\n"
        "path 1, node count differ:\n  Bold has 4\n  Sketch has 3\n"
        "anchors differ:\n  Bold has top\n  Sketch has \n"
        "components differ:\n  Bold has \n  Sketch has A\n"
        "path 1, node 2 node types differ:\n  Sketch has line\n  Alt has curve\n"
        "path counts differ:\n  Alt has 1\n  None has 0\n\n\n"
    )
    with pytest.raises(ValueError, match="no reportable foreground layer"):
        model.why_report([("A", [])])


def test_report_points_when_extra_layers_then_stored_foreground_literal():
    pkg = font()
    glyph = pkg.findName("E")
    extra_layer(glyph, "mask.Regular", [OShape([tri([])])], mask=True)
    extra_layer(glyph, "#service", service=True)
    extra_layer(glyph, "Sketch", [OShape([tri([])])])
    d = doctor(pkg)
    text = d.report("points", ["E", "E"])
    assert untouched(d, pkg)
    block = ("---------- E ----------\n"
             "4 points - 4 lines, 0 curves, 0 offcurves, 1 paths - Regular\n"
             "? 6 points - 3 lines, 1 curves, 2 offcurves, 1 paths - Bold\n"
             "? 3 points - 3 lines, 0 curves, 0 offcurves, 1 paths - Sketch\n\n")  # fmt: skip
    assert text == block * 2


def test_report_master_points_when_extra_layers_then_master_layers_only():
    pkg = font()
    glyph = pkg.findName("E")
    extra_layer(glyph, "Sketch", [OShape([tri([])])])
    extra_layer(glyph, "Light", [OShape([tri([])])], master=True)
    d = doctor(pkg)
    assert d.report("master points", ["E"]) == (
        "Layer: Regular\nTotal: 4 Points - 0 Handles, 4 Nodes, 1 Paths\n\n"
        "Layer: Bold\nTotal: 6 Points - 2 Handles, 4 Nodes, 1 Paths\n\n"
        "Layer: Light\nTotal: 3 Points - 0 Handles, 3 Nodes, 1 Paths\n"
    )
    assert untouched(d, pkg)
    with pytest.raises(ValueError, match="Unknown report"):
        d.report("kerning", ["E"])


def test_node_kinds_when_quadratic_or_open_then_original_types():
    model = mod("model")
    tt = OContour([(0, 0, True), (50, 80, False), (100, 0, True)], tt=True)
    assert model.node_kinds(tt) == ["offcurve", "qcurve", "line"]
    opened = OContour([(0, 0, True), (30, 30, False), (60, 30, False), (90, 0, True)], closed=False)
    assert model.node_kinds(opened) == ["line", "offcurve", "offcurve", "curve"]
    counts = model.counts(SimpleNamespace(shapes=[OShape([tt, opened])]))
    assert counts == model.Counts(lines=2, curves=2, handles=3, paths=2) and counts.points == 7


# Select (Font window selection; no history) ---------------------------------------------
def test_select_when_flagged_then_selector_called_with_package():
    seen = []
    pkg = font()
    d = doctor(pkg, select=lambda package, names: seen.append((package, names)) or names)
    assert d.select(["B", "E"], "incompatible") == ["B", "E"]
    assert seen == [(pkg, ["B", "E"])] and d.status == f"{APP_LABEL}: Selected 2 incompatible glyphs in the Font window"
    with pytest.raises(ValueError, match="No flagged glyphs"):
        d.select([], "flagged")
    assert untouched(d, pkg)


def test_select_default_uses_core_scripting(monkeypatch):
    import fontlabapp.core.scripting as scripting

    seen = []
    monkeypatch.setattr(scripting, "select_glyphs", lambda names, package_id: seen.append((names, package_id)) or names)
    assert mod("session")._select(SimpleNamespace(id=7), ["A"]) == ["A"] and seen == [(["A"], 7)]


# Preview: blend ghost ---------------------------------------------------------------
class Preview:
    def __init__(self):
        self.calls = []

    def load(self, *args):
        self.calls.append(("load", *args))

    def set_overlay(self, overlay):
        self.calls.append(("set_overlay", overlay))

    def refresh(self):
        self.calls.append(("refresh",))

    def highlight(self, **kwargs):
        self.calls.append(("highlight", kwargs))


def test_blend_when_compatible_then_interpolated_ghost_and_no_writes():
    pkg = font()
    d = doctor(pkg)
    d.preview = Preview()
    overlay = d.blend("A", "Regular", "Bold", 25)
    assert untouched(d, pkg)
    points = [(p.x, p.y, p.type) for p in overlay.contours[0].points]
    assert points == [(0.0, 0.0, "line"), (125.0, 0.0, "line"), (125.0, 125.0, "line"), (0.0, 125.0, "line")]
    assert overlay.contours[0].closed and d.preview.calls == [("load", "A", "Regular"), ("set_overlay", overlay)]
    assert d.status == "A: 25 % from Regular to Bold · 4 nodes"
    second = d.blend("A", "Regular", "Bold", 25, ghost_second=True)
    assert [(p.x, p.y) for p in second.contours[0].points][2] == (200.0, 200.0)


def test_blend_when_incompatible_then_message_and_overlay_cleared():
    pkg = font()
    d = doctor(pkg)
    d.preview = Preview()
    assert d.blend("B", "Regular", "Bold", 50) is None
    assert d.status == "B cannot interpolate between these masters: contour 1: 4 vs 3 nodes or different node types"
    assert d.preview.calls == [("load", "B", "Regular"), ("set_overlay", None)]
    model = mod("model")
    assert model.problem([[(0, 0, True)]], []) == "1 vs 0 contours"
    assert untouched(d, pkg)


def test_outline_when_component_transformed_then_layer_coordinates():
    model = mod("model")
    shape = OShape([OContour([(10, 0, True), (20, 0, True), (20, 5, True)])], transform=T(dx=100, dy=50))
    assert model.outline(SimpleNamespace(shapes=[shape]))[0][0] == (110.0, 50.0, True)


def test_overlay_closer_when_shell_closes_then_ghost_cleared():
    session = mod("session")
    d = doctor(font())
    d.preview = Preview()
    session.OverlayCloser(d).close()
    assert d.preview.calls == [("set_overlay", None)]
    d.preview = SimpleNamespace(set_overlay=lambda o: (_ for _ in ()).throw(RuntimeError("closed")))
    session.OverlayCloser(d).close()


# Make Compatible -----------------------------------------------------------------------
def test_make_compatible_when_line_vs_cubic_then_one_labelled_step_on_explicit_layer():
    pkg = font()
    d = doctor(pkg)
    d.preview = Preview()
    fixes = d.plan_compatible(["E", "B"])
    assert untouched(d, pkg)
    rows = mod("tabs").fix_records(fixes)
    assert rows == [
        ("E", "Regular", ("Regular", "contour 1", "1", "line to cubic", "")),
        ("E", "Bold", ("Bold", "", "", "", "no change")),
        ("B", "Regular", ("Regular", "glyph", "", "Master segment counts differ, kept", "")),
        ("B", "Bold", ("Bold", "glyph", "", "Master segment counts differ, kept", "")),
    ]
    assert d.make_compatible(["E", "B"])
    assert d.shell.calls == [("Interpolation Doctor: make compatible E", ["E"], [("E", "Regular")])]
    assert d.shell.allowed == [False]
    assert pkg.writes() == [("curve",)]
    assert pkg.layer("E", "Regular").shapes[0].contours[0].nodesCount == 6
    assert d.status == "Interpolation Doctor: make compatible E."
    assert ("set_overlay", None) in d.preview.calls and ("refresh",) in d.preview.calls


def test_make_compatible_when_current_master_only_and_bases_opt_in_then_passed():
    pkg = font()
    d = doctor(pkg)
    d.master = "Bold"
    assert not d.make_compatible(["E"], all_masters=False, allow_bases=True)
    assert d.status == "Interpolation Doctor: no change." and d.shell.calls == []
    d.master = "Regular"
    assert d.make_compatible(["E"], all_masters=False, allow_bases=True)
    assert d.shell.calls[0][2] == [("E", "Regular")] and d.shell.allowed == [True]


def test_make_compatible_when_hinted_then_refused_until_opt_in():
    pkg = font(H=(build_e, {"hinted": True}))
    d = doctor(pkg)
    assert not d.make_compatible(["H"])
    assert d.shell.calls == [] and pkg.writes() == []
    assert d.status.startswith("Interpolation Doctor: no change. Skipped: H (Regular): ")
    assert "Tick Edit hinted layers anyway" in d.status
    assert d.make_compatible(["H"], allow_hinted=True)
    assert d.shell.calls == [("Interpolation Doctor: make compatible H", ["H"], [("H", "Regular")])]


def test_plan_compatible_when_auto_missing_or_shared_then_noted():
    pkg = font(F=(build_e, {"auto": ("Bold",)}), G=(build_e, {"masters": ("Regular",)}),
               S=(lambda log, m: [OShape([box(0, 0, 10, log)], refs=2, log=log)], {}),
               R=(lambda log, m: [OShape([box(0, 0, 10, log)], transform=T(m11=2.0), log=log)], {}))  # fmt: skip
    d = doctor(pkg)
    notes = {(f.glyph, f.master): (f.note, [c.after for c in f.changes]) for f in d.plan_compatible(["F", "G", "S", "R"])}
    assert notes[("F", "Bold")] == ("auto layer, skipped", [])
    assert notes[("G", "Bold")] == ("no layer in this master", [])
    assert notes[("G", "Regular")] == ("", ["Every declared master must have a layer, kept"])
    assert notes[("S", "Regular")] == ("", ["Use own, unscaled outline shapes, kept"])
    assert notes[("R", "Bold")] == ("", ["Use own, unscaled outline shapes, kept"])
    model = mod("model")
    assert model.shape_notes(pkg.layer("S")) == ["shared outline, kept"]
    assert model.shape_notes(pkg.layer("R")) == ["scaled or rotated shape, kept"]
    assert untouched(d, pkg)


def test_plan_compatible_when_contour_counts_or_open_then_glyph_kept():
    pkg = font(K=(lambda log, m: [OShape([box(0, 0, 10, log)] * (1 if m == "Regular" else 2), log=log)], {}),
               O=(lambda log, m: [OShape([OContour([(0, 0, True), (5, 5, True)], closed=False, log=log)],
                                         log=log)], {}))  # fmt: skip
    d = doctor(pkg)
    after = {(f.glyph, f.master): f.changes[0].after for f in d.plan_compatible(["K", "O"])}
    assert after[("K", "Regular")] == "Master contour counts differ, kept"
    assert after[("O", "Bold")] == "Use closed PostScript contours, kept"


def test_make_compatible_when_shell_refuses_or_mismatch_or_error_then_false():
    pkg = font()
    d = doctor(pkg)
    d.shell.refuse = True
    assert not d.make_compatible(["E"])
    d.shell.refuse = False
    original = mod("model").write_compatible
    session = mod("session")
    session.m.write_compatible = lambda edits: None
    try:
        assert not d.make_compatible(["E"])
        assert d.status.startswith("Partly applied: Interpolation Doctor: make compatible E. Regular. Native changes")
    finally:
        session.m.write_compatible = original
    d.shell.history = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("FontLab refused cubic conversion."))
    assert not d.make_compatible(["E"])
    assert d.status == "Interpolation Doctor: FontLab refused cubic conversion. Native changes may remain; use Edit > Undo."
    assert not d.make_compatible([])
    assert d.status.startswith("Interpolation Doctor: Choose glyphs first")


def test_write_compatible_when_native_refuses_then_runtime_error():
    endpoint = SimpleNamespace(convertToCurve=lambda smooth: False)
    with pytest.raises(RuntimeError, match="refused cubic"):
        mod("model").write_compatible([(None, (endpoint,), 0)])


def test_make_compatible_with_skipped_layer_then_status_lists_it():
    pkg = font(H=(build_e, {"hinted": True}))
    d = doctor(pkg)
    assert d.make_compatible(["E", "H"])
    assert d.shell.calls[0][0] == "Interpolation Doctor: make compatible E"
    assert "Skipped: H (Regular):" in d.status


def test_first_mismatch_when_no_other_or_equal_then_empty():
    session = mod("session")
    assert session.first_mismatch({"a": (("oooo",), (), ())}, "a") == ()
    assert session.first_mismatch({"a": (("oooo",), (), ()), "b": (("oooo",), (), ())}, "a") == ()
    assert session.first_mismatch({"a": (("ooo", "oo"), (), ()), "b": (("ooo",), (), ())}, "a") == ((1, 0), (1, 1))


# Qt tabs ------------------------------------------------------------------------
@pytest.fixture
def ss(studio_qt, monkeypatch):  # noqa: F811
    from PySide6.QtWidgets import QWidget

    import fontlabapp.core.edit_guards as guards
    import fontlabapp.core.history.glyphs as history

    studios = importlib.import_module(PKG)
    commits = []

    def commit(title, layers, glyphs, mutate, **kwargs):
        commits.append((title, [(lay.glyph, lay.master) for lay in layers], [g.name for g in glyphs],
                        kwargs.get("allow_bases")))  # fmt: skip
        mutate()
        problems = tuple(kwargs["read_back"]()) if kwargs.get("read_back") else ()
        return SimpleNamespace(pending_note="", mismatches=problems)

    monkeypatch.setattr(guards, "require_history_scope", lambda glyphs, **k: None)
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: SimpleNamespace(users={}))
    monkeypatch.setattr(history, "commit", commit)

    class QtPreview(QWidget, Preview):
        def __init__(self):
            QWidget.__init__(self)
            Preview.__init__(self)

    pkg, preview = font(), QtPreview()
    shell = studios.show(package=lambda: pkg, font=lambda: object(), preview=lambda shell, studio: preview)
    studio_qt.owned.append(shell)
    selected = []
    shell.interpolation_doctor._select_names = lambda package, names: selected.append(list(names)) or list(names)
    yield SimpleNamespace(shell=shell, studio=shell.interpolation_doctor, pkg=pkg, preview=preview, commits=commits,
                          selected=selected, tabs=sys.modules[f"{PKG}.tabs"])  # fmt: skip


def tab(ss, index):
    return next(v.__self__ for v in ss.studio.views if isinstance(v.__self__, ss.tabs.TAB_CLASSES[index][1]))


def click(t, text):
    from PySide6.QtWidgets import QPushButton

    next(b for b in t.widget.findChildren(QPushButton) if b.text() == text).click()


def test_show_when_built_then_four_tabs(ss):
    assert [title for title, _ in ss.tabs.TAB_CLASSES] == list(importlib.import_module(PKG).TAB_TITLES)
    assert list(importlib.import_module(PKG).TAB_TITLES) == ["Check", "Fix", "Node counts", "Preview"]
    assert len(ss.studio.views) == 4
    assert mod("app").studio_for(ss.shell) is ss.studio
    assert importlib.import_module(PKG).studio_for(ss.shell) is ss.studio
    for index in (0, 2, 3):
        t = tab(ss, index)
        assert t.all_masters.isHidden() and t.allow_hinted.isHidden() and t.allow_bases.isHidden()
        assert t.write_note.text() == ss.tabs.READ_ONLY_NOTE


def test_check_tab_when_kind_changes_then_original_default_scope(ss):
    t = tab(ss, 0)
    assert t.kind() == "masters" and not t.whole_font.isChecked() and t.only_bad.isHidden()
    t.check_box.setCurrentIndex(1)
    assert t.kind() == "anchors" and t.whole_font.isChecked() and not t.only_bad.isHidden()
    t.check_box.setCurrentIndex(2)
    assert t.kind() == "components" and t.whole_font.isChecked()
    click(t, "Check")
    assert [r[0] for r in t.records] == ["C"] * 3
    click(t, "Select mismatches")
    assert ss.selected == [["C"]] and "Selected 1 mismatching glyphs" in ss.studio.status
    assert ss.commits == [] and ss.pkg.writes() == []


def test_check_tab_when_masters_row_chosen_then_loaded_and_highlighted(ss):
    t = tab(ss, 0)
    t.glyphs_field.setText("A B")
    click(t, "Check")
    assert ss.studio.status == f"{APP_LABEL}: 1 of 2 glyphs incompatible"
    ss.preview.calls.clear()
    t.row_chosen("B", "Bold")
    assert ("load", "B", "Bold") in ss.preview.calls
    assert ("highlight", {"points": ((0, 0), (0, 1), (0, 2))}) in ss.preview.calls
    t.row_chosen("")
    click(t, "Why You Not Compatible")
    assert t.report_box.toPlainText().startswith("A is compatible")
    click(t, "Master Node Compatibility Report")
    assert t.report_box.toPlainText().startswith("🔠 Glyph: A")
    assert ss.commits == [] and ss.pkg.writes() == []
    t.glyphs_field.setText("")
    t.found = None
    click(t, "Select mismatches")
    assert "Choose glyphs first" in ss.studio.status


def test_node_tab_when_count_then_rows_reports_and_select(ss):
    t = tab(ss, 2)
    t.whole_font.setChecked(True)
    t.only_flagged.setChecked(True)
    click(t, "Count")
    assert {r[0] for r in t.records} == {"B", "E"}
    click(t, "Select flagged")
    assert ss.selected == [["B", "E"]]
    t.whole_font.setChecked(False)
    t.glyphs_field.setText("E")
    click(t, "Point Counter")
    assert t.report_box.toPlainText().startswith("---------- E ----------")
    click(t, "Point Counter (Master Layers)")
    assert t.report_box.toPlainText().startswith("Layer: Regular\nTotal: 4 Points")
    assert ss.commits == [] and ss.pkg.writes() == []
    t.found = None
    t.glyphs_field.setText("A")
    click(t, "Select flagged")
    assert "No flagged glyphs to select" in ss.studio.status


def test_fix_tab_when_preview_then_apply_one_labelled_commit(ss):
    t = tab(ss, 1)
    assert t.all_masters.isChecked() and t.allow_bases.isVisibleTo(t.widget) and not t.allow_bases.isChecked()
    t.glyphs_field.setText("E B")
    click(t, "Preview")
    assert ss.commits == [] and ss.pkg.writes() == []
    assert ss.studio.status == f"{APP_LABEL}: 1 change(s) planned on 4 layer(s); nothing written."
    assert t.records[0] == ("E", "Regular", ("Regular", "contour 1", "1", "line to cubic", ""))
    click(t, "Make compatible on chosen glyphs")
    assert ss.commits == [("Interpolation Doctor: make compatible E", [("E", "Regular")], ["E"], False)]
    assert ss.pkg.layer("E", "Regular").shapes[0].contours[0].nodesCount == 6


def test_fix_tab_when_bases_ticked_then_allow_bases_passed(ss):
    t = tab(ss, 1)
    t.allow_bases.setChecked(True)
    t.glyphs_field.setText("E")
    click(t, "Make compatible on chosen glyphs")
    assert ss.commits[0][3] is True


def test_preview_tab_when_slider_moves_then_ghost_updates_without_writes(ss):
    t = tab(ss, 3)
    assert t.first.currentText() == "Regular" and t.second.currentText() == "Bold" and t.slider.value() == 50
    t.glyphs_field.setText("A")
    click(t, "Show blend")
    overlays = [c[1] for c in ss.preview.calls if c[0] == "set_overlay" and c[1] is not None]
    assert [(p.x, p.y) for p in overlays[-1].contours[0].points][2] == (150.0, 150.0)
    t.slider.setValue(100)
    assert t.percent.text() == "100 %" and ss.studio.status == "A: 100 % from Regular to Bold · 4 nodes"
    t.ghost_second.setChecked(True)
    t.row_chosen("B")
    assert ss.studio.status.startswith("B cannot interpolate")
    t.row_chosen("")
    assert ss.commits == [] and ss.pkg.writes() == []
    t.glyphs_field.setText("")
    click(t, "Show blend")
    assert "Type glyph names" in ss.studio.status
    t.current = ""
    assert t.update() is None


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
    with pytest.raises(RuntimeError, match="boom"):
        importlib.import_module(PKG).show(package=lambda: None, font=lambda: None,
                                          preview=lambda shell, studio: None)  # fmt: skip
    assert closed == [True]


def test_glyph_preview_when_font_then_control_less_tglyph(monkeypatch):
    import fontlabapp.fontui as fontui

    app = mod("app")
    seen = []
    monkeypatch.setattr(fontui, "glyph_view", lambda *a, **k: seen.append((a, k)) or "view")
    shell = SimpleNamespace(widget="w", hint_check="hc")
    assert app._glyph_preview(shell, SimpleNamespace(font=lambda: None, current="Regular")) is None
    assert app._glyph_preview(shell, SimpleNamespace(font=lambda: "font", current="Regular")) == "view"
    assert seen == [(("font", "w"), {"layer": "Regular", "controls": False, "label_prefix": APP_LABEL,
                                     "hint_check": "hc"})]  # fmt: skip


def test_studio_for_when_new_shell_then_created_once():
    app = mod("app")
    shell = SimpleNamespace(package=lambda: None, set_status=lambda text: None)
    first = app.studio_for(shell)
    assert app.studio_for(shell) is first and shell.interpolation_doctor is first


def test_check_tab_when_kind_switched_after_check_then_select_uses_new_kind(ss):
    t = tab(ss, 0)
    t.glyphs_field.setText("A B C D E")
    click(t, "Check")
    assert {r[0] for r in t.records if r[1] is None and r[2][-1] != "✓"} == {"B", "C", "D", "E"}
    t.check_box.setCurrentIndex(2)
    click(t, "Select mismatches")
    assert ss.selected == [["C"]]
    assert ss.commits == [] and ss.pkg.writes() == []


def test_glyph_fake_when_glyph_attribute_written_then_logged():
    pkg = font()
    pkg.findName("A").mark = 3
    assert pkg.writes() == [("glyph set", "A", "mark")]


def test_blend_when_drawn_master_has_no_layer_then_empty_ghost_without_error():
    pkg = font(N=(lambda log, m: [], {"masters": ("Bold",)}))
    d = doctor(pkg)
    d.preview = Preview()
    overlay = d.blend("N", "Regular", "Bold", 50)
    assert overlay.contours == () and d.preview.calls == [("set_overlay", overlay)]
    assert d.blend("N", "Bold", "Regular", 50, ghost_second=True).contours == ()
    assert untouched(d, pkg)


def test_preview_tab_when_blend_from_other_master_then_write_master_unchanged(ss):
    fix, t = tab(ss, 1), tab(ss, 3)
    assert ss.studio.master == "Regular"
    note = fix.write_note.text()
    t.first.setCurrentIndex(1)
    t.second.setCurrentIndex(0)
    t.glyphs_field.setText("E")
    click(t, "Show blend")
    assert ("load", "E", "Bold") in ss.preview.calls
    assert ss.studio.master == "Regular" and fix.write_note.text() == note
    fix.all_masters.setChecked(False)
    fix.glyphs_field.setText("E")
    click(fix, "Make compatible on chosen glyphs")
    assert ss.commits == [("Interpolation Doctor: make compatible E", [("E", "Regular")], ["E"], False)]
