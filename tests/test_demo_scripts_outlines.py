# this_file: tests/test_demo_scripts_outlines.py
"""Offline runs of the Scripts/Anchors, Components, Contours and Guides demos (Issue 208, Task 5).

Each demo runs through runpy as ``__main__`` (entry points and arguments are
asserted) and as an imported name (nothing may run). The real host-free
``fontlabapp`` modules stay in use, so the sample plans are computed by the real
planners. ``PythonQt`` and ``fontlab`` are stubbed, and so are the few modules
that load native classes when imported (the report dialogs). Fake fonts answer
exactly the reads the real inspectors make. Offline results are not native
FontLab acceptance.
"""

from types import SimpleNamespace

import pytest
from _demo_support import Recorder, qt_namespace, run_script, script_path, stub_module

OK = 1
PACKAGE = SimpleNamespace(isNull=False, id=3, master="Regular", masters=["Regular", "Bold"])

PLANS = script_path("Anchors", "Anchor Plans Demo")
RINGS = script_path("Anchors", "Anchor Rings Demo")
CLEANUP = script_path("Anchors", "Anchor Cleanup Demo")
ANCHORS_INSPECT = script_path("Anchors", "Anchors Inspect Demo")
WRITERS = script_path("Components", "Component Writers Demo")
COMPONENTS_INSPECT = script_path("Components", "Components Inspect Demo")
RECIPES = script_path("Components", "Component Recipes Demo")
GRAPH = script_path("Components", "Component Graph Demo")
REPORTS = script_path("Contours", "Contour Reports Demo")
SAMPLES = script_path("Contours", "Contour Samples Demo")
MATH = script_path("Contours", "Contour Math Demo")
PANELS = script_path("Contours", "Contour Panels Demo")
CONTOUR_PLANS = script_path("Contours", "Contour Plans Demo")
GUIDE_PLANS = script_path("Guides", "Guide Plans Demo")
HINTS = script_path("Guides", "Postscript Hints Demo")

EXPLAINED = [PLANS, RINGS, CLEANUP, WRITERS, SAMPLES, MATH, PANELS, CONTOUR_PLANS, GUIDE_PLANS]


# --- Host stubs and fake fonts --------------------------------------------------


def install_host(monkeypatch, package=PACKAGE, glyphs=(), current_glyph=None):
    """Stub the natives; the fake current font lists ``glyphs`` in font order.

    Returns (QtGui, asked): ``asked`` collects one tuple per question box in the
    order (parent, title, text, icon, buttons, default) of
    ``run_standard_message_box``, which is replaced by a recorder.
    """
    import fontlabapp.qt.dialogs as dialogs

    qt = qt_namespace()
    qt.QtGui.QMessageBox.Ok = OK
    stub_module(monkeypatch, "PythonQt", QtGui=qt.QtGui, QtCore=qt.QtCore)
    font = SimpleNamespace(glyphs=[SimpleNamespace(name=name, unicodes=[]) for name in glyphs])
    stub_module(
        monkeypatch,
        "fontlab",
        MainWindow=lambda: "main-window",
        CurrentFont=lambda: font,
        CurrentGlyph=lambda: current_glyph,
        flWorkspace=SimpleNamespace(instance=lambda: SimpleNamespace(currentPackage=package)),
    )
    asked = []

    def ask(_qt, parent, title, text, icon, buttons, default=None):
        asked.append((parent, title, text, icon, buttons, default))
        return OK

    monkeypatch.setattr(dialogs, "run_standard_message_box", ask)
    return qt.QtGui, asked


def shown(gui) -> tuple[str, str, str]:
    """(title, text, details) of the one modal message box the demo ran."""
    assert gui.QMessageBox.call_count == 1, "exactly one message box expected"
    assert gui.QMessageBox.call_args[0] == ("main-window",), "box parents to the main window"
    box = gui.QMessageBox.return_value
    box.exec.assert_called_once_with()
    details = box.setDetailedText.call_args[0][0] if box.setDetailedText.called else ""
    return box.setText.call_args[0][0], box.setInformativeText.call_args[0][0], details


def explained(monkeypatch, path) -> tuple[str, str, str]:
    """Run an explain-only demo with no font open and return its one message box."""
    gui, asked = install_host(monkeypatch, package=None)
    run_script(path)
    assert asked == [], "an explain-only demo asks nothing"
    return shown(gui)


def forbid_windows(monkeypatch) -> Recorder:
    """Replace ``show_script_dialog`` with a recorder the test asserts was never called."""
    import fontlabapp.core.scripting as scripting

    recorder = Recorder("window")
    monkeypatch.setattr(scripting, "show_script_dialog", recorder)
    return recorder


class Pin:
    """A native-like anchor pin: ``name`` and a ``point`` with callable x and y."""

    def __init__(self, name, x, y):
        self.name, self.point = name, SimpleNamespace(x=lambda: x, y=lambda: y)


class Guide:
    """A native-like guide object; ``isHint`` and the role predicates are callables."""

    def __init__(self, hint, horizontal=False, vertical=False, error=None):
        self.isHint, self.horizontal, self.vertical, self.error = hint, horizontal, vertical, error

    def isHorizontal(self):
        if self.error:
            raise self.error
        return self.horizontal

    def isVertical(self):
        return self.vertical


class Shape:
    """A native-like component shape with a translation."""

    def __init__(self, base, dx=0, dy=0):
        self.isComponent = True
        self.shapeData = SimpleNamespace(componentGlyph=base)
        self.transform = SimpleNamespace(dx=lambda: dx, dy=lambda: dy)


class Layer:
    """A native-like layer; absent attributes are the ones the demos never read."""

    def __init__(self, anchors=(), shapes=(), guidelines=(), auto=False):
        self.isNull, self.autoLayer = False, auto
        self.anchors, self.shapes, self.guidelines = list(anchors), list(shapes), list(guidelines)


class Glyph:
    """A glyph with one layer per master name."""

    def __init__(self, name, **layers):
        self.name, self.layers = name, layers

    def findLayer(self, master):
        return self.layers.get(master)


class Font:
    """A font whose ``findName`` answers from a dict, like the native package."""

    def __init__(self, *glyphs, masters=("Regular", "Bold")):
        self.glyphs = {glyph.name: glyph for glyph in glyphs}
        self.masters, self.master, self.isNull, self.id = list(masters), masters[0], False, 3

    def findName(self, name):
        return self.glyphs.get(name)


def anchor_font() -> Font:
    """A has top and bottom; acutecomb has _top; e loses its top on Bold."""
    both = lambda *pins: {"Regular": Layer(pins), "Bold": Layer(pins)}  # noqa: E731
    return Font(
        Glyph("A", **both(Pin("top", 250, 700), Pin("bottom", 250, 0))),
        Glyph("acutecomb", **both(Pin("_top", 0, 500))),
        Glyph("e", Regular=Layer([Pin("top", 240, 520)]), Bold=Layer([])),
    )


def component_font() -> Font:
    """aacute is the same on both masters; eacute names a base that does not exist on Bold."""
    plain = lambda *shapes: {"Regular": Layer(shapes=shapes), "Bold": Layer(shapes=shapes)}  # noqa: E731
    return Font(
        Glyph("a", **plain()),
        Glyph("e", **plain()),
        Glyph("acute", **plain()),
        Glyph("aacute", **plain(Shape("a"), Shape("acute", 120, 600))),
        Glyph("eacute", Regular=Layer(shapes=[Shape("e"), Shape("acute")]), Bold=Layer(shapes=[Shape("e"), Shape("acutex")])),
    )


# --- Explain-only demos ----------------------------------------------------------


def test_plans_demo_when_run_then_real_planners_print_centering_rounding_and_copy_rows(monkeypatch) -> None:
    title, text, details = explained(monkeypatch, PLANS)
    assert title == "Anchor Plans Demo" and text == "Sample anchor plans. Nothing was written."
    assert "a · Regular: top 183, 704 -> 250, 704" in details
    assert "bottom 262, -3 -> 250, -3" in details
    assert "Apply would write 2 anchors on 1 layer as one Undo step." in details
    assert "top: (183, 704) -> (180, 700)" in details and "bottom: (262, -3) -> (260, 0)" in details
    assert "snap(15, 10) = 20, snap(-15, 10) = -10" in details
    assert "top: (100, 650) -> (220, 704)" in details and "bottom: None -> (314, -3)" in details
    assert "writer.on_origin((0, 0)) is True" in details
    assert "fontlabapp.anchors.panel.model" in details and "fontlabapp.anchors.edit" in details


def test_rings_demo_when_run_then_rings_follow_handle_size_and_zoom(monkeypatch) -> None:
    title, text, details = explained(monkeypatch, RINGS)
    assert title == "Anchor Rings Demo" and text == "Sample duplicate-anchor rings. Nothing was drawn."
    assert "Handle size 8, zoom 1: 4 rings" in details
    assert "anchors (0, 1) at (0.0, 0.0): diameter 16.0, outer stroke 6.0, inner stroke 2.0" in details
    assert "Handle size 12, zoom 0.25: 4 rings" in details and "diameter 83.6, outer stroke 24.0" in details
    assert details.count("anchors (2, 4) at (250.0, 700.0)") == 4, "three coincident anchors give a ring for every pair"
    assert details.endswith("not opened here: fontlabapp.anchors.canvas_rings.ui.CanvasAnchorRingsDialog")


def test_cleanup_demo_when_run_then_findings_and_copy_edits_come_from_the_real_models(monkeypatch) -> None:
    title, text, details = explained(monkeypatch, CLEANUP)
    assert title == "Anchor Cleanup Demo" and text == "Sample anchor cleanup and copy results. Nothing was changed."
    assert "duplicate name: top, top.1 -> remove anchor ids [2]" in details
    assert "coincident: bottom, ogonek -> remove anchor ids [4]" in details
    assert "All masters to All masters: [('Regular', 'Regular')]" in details
    assert "2 copied" in details
    assert details.index("rename top.bak at x 10") < details.index("add top at x 240") < details.index("add bottom at x 300")
    assert details.endswith("not opened here: fontlabapp.anchors.duplicates.ui, fontlabapp.anchors.crossfont.ui")


def test_writers_demo_when_run_then_plain_component_moves_and_blocked_scaled_row(monkeypatch) -> None:
    title, text, details = explained(monkeypatch, WRITERS)
    assert title == "Component Writers Demo" and text == "Sample component plan. Nothing was written."
    assert "aacute · Regular: acute 120, 600 -> 130, 600" in details
    assert "aacute · Regular: dotaccent -40, 0 -> -30, 0" in details
    assert "ccedilla · Regular: cedilla 30, -10 -> 40, -10  [blocked: scaled or turned, not a plain move]" in details
    assert "Layers to write: 1." in details and "ccedilla · Regular: scaled or turned" in details
    assert "3 contours + 1 component and 1 contour." in details
    assert "NewComponent(base='acute', layer='Regular', x=120, y=600)" in details
    assert "fontlabapp.components.panel.model" in details


def test_samples_demo_when_run_then_all_four_reports_show_their_findings(monkeypatch) -> None:
    title, text, details = explained(monkeypatch, SAMPLES)
    assert title == "Contour Samples Demo" and text == "Sample contour reports. Nothing was read or written."
    assert "H / Regular / Regular — path 1, segment 2: angle: 0.9548412538721887 → 0?" in details
    assert "node x height: 501 → 500?" in details and "2 near misses." in details
    assert "? 31 points - 4 lines, 9 curves, 18 offcurves, 2 paths - Light" in details
    assert "28 points - 4 lines, 8 curves, 16 offcurves, 2 paths - Regular" in details
    assert "M 0 0\nL 100 0\nC 100 50 50 100 0 100\nZ" in details
    assert "o -- Regular" in details


def test_samples_demo_when_fonttools_missing_then_only_that_section_is_unavailable(monkeypatch) -> None:
    import fontlabapp.contours.dangerous_offcurves.model as dangerous

    def missing(*_args, **_kwargs):
        raise ImportError("No module named 'fontTools'")

    monkeypatch.setattr(dangerous, "_intersections", missing)
    _, _, details = explained(monkeypatch, SAMPLES)
    assert "Dangerous Offcurves:\nUnavailable: No module named 'fontTools'" in details
    assert "2 near misses." in details and "M 0 0" in details


def test_math_demo_when_run_then_transforms_extent_reflect_and_node_distances(monkeypatch) -> None:
    title, text, details = explained(monkeypatch, MATH)
    assert title == "Contour Math Demo" and text == "Sample outline math. Nothing was read or written."
    assert "point (0, 100) moves to (20.0, 100.0); the inverse brings it back to (0.0, 100.0)." in details
    assert "(1.0, 0.0087)" in details and "the identity leaves (7.0, 9.0)" in details
    assert "only reaches y 75 (extent.contour_ys); its turning point is [75.0]." in details
    assert "point: (10, 20) -> (90.0, 20)" in details
    assert "component: (60, 0) -> (40.0, 0), scale (-1.0, 1.0)" in details
    assert "anchor: (500, 700) -> (500, 700) (not selected)" in details
    assert "1:0 → 1:1: dx 30, dy 40, length 50, angle 53.1 degrees" in details


def test_panels_demo_when_run_then_selection_area_and_slant_plans(monkeypatch) -> None:
    title, text, details = explained(monkeypatch, PANELS)
    assert title == "Contour Panels Demo" and text == "Sample contour panel plans. Nothing was applied."
    assert "Selected nodes now, per contour (x is selected): .x.; ..; x.." in details
    assert "contours: xxx; ..; xxx (2 contours chosen)" in details
    assert "partial: .xx; xx; x.. (3 contours chosen)" in details
    assert "other selection cleared: True" in details
    assert "Area of the 100 x 100 square: 10000" in details
    assert "Bad input is refused: Enter a finite numeric area in square font units." in details
    assert "(0, 0), (100, 0), (120, 100), (20, 100)" in details
    assert "Preview scale in a 120 x 120 widget: 0.72, offset 24, 96" in details
    assert "Needs FontLab, so not run here: fontlabapp.contours.panel.model, fontlabapp.contours.selection.panel.model, fontlabapp.contours.selection.native, fontlabapp.contours.copy" in details


def test_panels_demo_when_fonttools_missing_then_area_line_says_so_and_plans_still_show(monkeypatch) -> None:
    import fontlabapp.contours.selection.model as selection

    def missing(_segments):
        raise RuntimeError("Select Small Contours requires fontlab-fontlabapp[fontui].")

    monkeypatch.setattr(selection, "unsigned_area", missing)
    _, _, details = explained(monkeypatch, PANELS)
    assert "Area unavailable: Select Small Contours requires fontlab-fontlabapp[fontui]." in details
    assert "partial: .xx; xx; x.. (3 contours chosen)" in details and "Preview scale" in details


def test_contour_plans_demo_when_run_then_three_planners_print_their_steps(monkeypatch) -> None:
    title, text, details = explained(monkeypatch, CONTOUR_PLANS)
    assert title == "Contour Plans Demo" and text == "Sample contour tool plans. Nothing was edited."
    assert "Path length 359.2: 18 samples with detail, 11 without; 17 straight nodes would be drawn." in details
    assert "Step 1: 2 nodes move, y values [700, 520, 400] -> [720.0, 540.0, 400.0]" in details
    assert "Step 2: 2 nodes move, y values [720.0, 540.0, 400.0] -> [740.0, 560.0, 400.0]" in details
    assert "current: 1 insertions [(2, 'line')]" in details
    assert "handles: 3 insertions [(2, 'off'), (3, 'off'), (4, 'curve')]" in details
    assert "all: 1 insertions [(2, 'line')]" in details


def test_guide_plans_demo_when_run_then_grid_filters_scaling_rows_and_perpendicular_guides(monkeypatch) -> None:
    title, text, details = explained(monkeypatch, GUIDE_PLANS)
    assert title == "Guide Plans Demo" and text == "Sample guide plans. Nothing was written."
    assert "(250.0, 0.0, 90.0, 'Grid V 2')" in details
    assert "Filter 'Horizontal' with name text '2' keeps: ['Grid H 2']" in details
    assert "Filter 'Vertical' keeps: ['Grid V 1', 'Grid V 2']" in details
    assert "(300.0, 0.0, 90.0, 'Grid V 2') and (60.0, 0.0, 39.81, 'Slant') (Angled)" in details
    assert "(180 degrees becomes 0 and x is zeroed): ('Regular', (0.0, 7.0, 0.0, 'top'))" in details
    assert "A bad row is refused before any write: row 3: X, Y and angle must be finite numbers" in details
    assert "guide through (50, 26.6667) at 148.0 degrees" in details
    assert "guide through (250, 100) at 0.0 degrees" in details and "guide through (250, 100) at 90.0 degrees" in details
    assert "with one node only: ('Please select at least two points.',)" in details
    assert "fontlabapp.guides.rewrite.model, fontlabapp.guides.rewrite.ui" in details


@pytest.mark.parametrize("path", EXPLAINED, ids=[path.stem for path in EXPLAINED])
def test_explained_demo_when_main_then_no_window_opens_and_no_font_is_needed(monkeypatch, path) -> None:
    opened = forbid_windows(monkeypatch)
    gui, asked = install_host(monkeypatch, package=None)
    run_script(path)
    assert opened.calls == [] and asked == []
    assert shown(gui)[2], "the details text is not empty"


@pytest.mark.parametrize("path", [*EXPLAINED, ANCHORS_INSPECT, COMPONENTS_INSPECT, RECIPES, GRAPH, REPORTS, HINTS], ids=lambda path: path.stem)
def test_demo_when_imported_then_nothing_runs(monkeypatch, path) -> None:
    opened = forbid_windows(monkeypatch)
    gui, asked = install_host(monkeypatch)
    run_script(path, "imported")
    assert gui.QMessageBox.call_count == 0 and opened.calls == [] and asked == []


# --- Font-reading demos ----------------------------------------------------------


def inspect_with(monkeypatch, path, font):
    """Run an inspect demo against ``font``; the font order is the dict order."""
    gui, asked = install_host(monkeypatch, package=font, glyphs=list(font.glyphs))
    run_script(path)
    assert asked == []
    return shown(gui)


def test_anchors_inspect_demo_when_font_open_then_names_classes_differences_and_attachment(monkeypatch) -> None:
    title, text, details = inspect_with(monkeypatch, ANCHORS_INSPECT, anchor_font())
    assert title == "Anchors Inspect Demo" and text == "Anchor summary of the open font. Nothing was changed."
    assert details.startswith("3 glyphs read, masters: Regular, Bold")
    assert "Common anchor names:\n  top, _top, bottom" in details
    assert "2 base glyphs, 1 mark glyphs on Regular" in details
    assert "1 glyphs differ between masters: e" in details
    assert "acutecomb attaches to A through 'top' by moving 250, 200" in details
    assert "fontlabapp.anchors.inspect.ui, fontlabapp.anchors.inspect.views" in details


def test_anchors_inspect_demo_when_no_marks_then_attachment_says_what_is_needed(monkeypatch) -> None:
    font = Font(Glyph("A", Regular=Layer([Pin("top", 1, 2)]), Bold=Layer([Pin("top", 1, 2)])))
    _, _, details = inspect_with(monkeypatch, ANCHORS_INSPECT, font)
    assert "Needs a glyph with plain anchors and a glyph with _anchors." in details


def test_anchors_inspect_demo_when_mark_shares_no_family_then_attachment_names_the_pair(monkeypatch) -> None:
    font = Font(
        Glyph("A", Regular=Layer([Pin("top", 1, 2)]), Bold=Layer([Pin("top", 1, 2)])),
        Glyph("ogonekcomb", Regular=Layer([Pin("_ogonek", 0, 0)]), Bold=Layer([Pin("_ogonek", 0, 0)])),
    )
    _, _, details = inspect_with(monkeypatch, ANCHORS_INSPECT, font)
    assert "ogonekcomb shares no anchor family with A." in details


def test_anchors_inspect_demo_when_a_read_fails_then_other_sections_still_show(monkeypatch) -> None:
    import fontlabapp.anchors.inspect.model as model

    def fail(*_args):
        raise RuntimeError("native read failed")

    monkeypatch.setattr(model, "anchor_sets", fail)
    _, _, details = inspect_with(monkeypatch, ANCHORS_INSPECT, anchor_font())
    assert "Master differences:\n  Unavailable: native read failed" in details
    assert "Common anchor names:\n  top, _top, bottom" in details and "attaches to A" in details


def test_anchors_inspect_demo_when_no_anchors_then_names_say_so(monkeypatch) -> None:
    font = Font(Glyph("space", Regular=Layer(), Bold=Layer()))
    _, _, details = inspect_with(monkeypatch, ANCHORS_INSPECT, font)
    assert "Common anchor names:\n  No anchors" in details and "0 glyphs differ between masters: none" in details


def test_anchors_inspect_demo_when_more_names_than_shown_then_list_ends_with_dots(monkeypatch) -> None:
    pins = [Pin(f"anchor{number:02d}", 1, 2) for number in range(12)]
    font = Font(Glyph("A", Regular=Layer(pins), Bold=Layer(pins)))
    _, _, details = inspect_with(monkeypatch, ANCHORS_INSPECT, font)
    assert "anchor00, anchor01, anchor02, anchor03, anchor04, anchor05, anchor06, anchor07, anchor08, anchor09 ..." in details


def test_anchors_inspect_demo_when_no_font_then_says_so_and_reads_nothing(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch, package=None)
    run_script(ANCHORS_INSPECT)
    assert shown(gui)[:2] == ("Anchors Inspect Demo", "Open a font first. This demo reads its anchors.")
    assert gui.QMessageBox.return_value.setDetailedText.called is False


def test_components_inspect_demo_when_font_open_then_layers_bases_gaps_and_differences(monkeypatch) -> None:
    title, text, details = inspect_with(monkeypatch, COMPONENTS_INSPECT, component_font())
    assert title == "Components Inspect Demo" and text == "Component summary of the open font. Nothing was changed."
    assert details.startswith("5 glyphs read, masters: Regular, Bold")
    assert "4 layers carry components" in details
    assert "Glyph,Master,Components,Offsets,Layer" in details
    assert 'aacute,Regular,a + acute,"acute 120,600",components' in details
    assert "acute: used by 2 glyphs" in details
    assert details.index("a: used by 1 glyphs") < details.index("acutex: used by 1 glyphs") < details.index("e: used by 1 glyphs")
    assert "acutex: 1 layers (first: eacute, Bold, glyph missing)" in details
    assert "1 glyphs differ between masters: eacute" in details
    assert "fontlabapp.components.inspect.ui, fontlabapp.components.inspect.views" in details


def test_components_inspect_demo_when_no_components_then_sections_say_none(monkeypatch) -> None:
    font = Font(Glyph("a", Regular=Layer(), Bold=Layer()))
    _, _, details = inspect_with(monkeypatch, COMPONENTS_INSPECT, font)
    assert "0 layers carry components" in details
    assert "No component bases" in details and "No missing bases" in details
    assert "0 glyphs differ between masters: none" in details


def test_components_inspect_demo_when_a_read_fails_then_other_sections_still_show(monkeypatch) -> None:
    import fontlabapp.components.inspect.model as model

    def fail(*_args):
        raise RuntimeError("native read failed")

    monkeypatch.setattr(model, "report", fail)
    _, _, details = inspect_with(monkeypatch, COMPONENTS_INSPECT, component_font())
    assert "Layers with components:\n  Unavailable: native read failed" in details
    assert "acute: used by 2 glyphs" in details and "1 glyphs differ between masters: eacute" in details


def test_components_inspect_demo_when_no_font_then_says_so_and_reads_nothing(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch, package=None)
    run_script(COMPONENTS_INSPECT)
    assert shown(gui)[:2] == ("Components Inspect Demo", "Open a font first. This demo reads its components.")


# --- Hint counts -----------------------------------------------------------------


def hint_font(*glyphs) -> Font:
    return Font(*glyphs)


def run_hints(monkeypatch, font, selected):
    """Run the hints demo with ``selected`` as the Font window selection."""
    import fontlabapp.components.inspect.model as model

    gui, asked = install_host(monkeypatch, package=font)
    monkeypatch.setattr(model, "selected_names", lambda: list(selected))
    run_script(HINTS)
    assert asked == []
    return gui


def test_hints_demo_when_glyphs_selected_then_counts_hints_by_role_per_master(monkeypatch) -> None:
    guides = [Guide(True, horizontal=True), Guide(True, horizontal=True), Guide(True, vertical=True), Guide(True), Guide(False)]
    font = hint_font(Glyph("H", Regular=Layer(guidelines=guides), Bold=Layer(guidelines=[Guide(True, vertical=True)])))
    title, text, details = shown(run_hints(monkeypatch, font, ["H"]))
    assert title == "Postscript Hints Demo" and text == "Hint counts of 1 glyphs. Nothing was changed."
    assert details.splitlines() == ["H / Regular: 2 horizontal, 1 vertical", "H / Bold: 0 horizontal, 1 vertical"]


def test_hints_demo_when_a_layer_is_missing_then_it_is_skipped(monkeypatch) -> None:
    font = hint_font(Glyph("H", Regular=Layer(guidelines=[Guide(True, horizontal=True)])))
    _, _, details = shown(run_hints(monkeypatch, font, ["H"]))
    assert details == "H / Regular: 1 horizontal, 0 vertical"


def test_hints_demo_when_a_read_fails_then_that_layer_is_marked_unreadable(monkeypatch) -> None:
    broken = Guide(True, error=RuntimeError("native read failed"))
    font = hint_font(Glyph("H", Regular=Layer(guidelines=[broken]), Bold=Layer(guidelines=[Guide(True, vertical=True)])))
    _, _, details = shown(run_hints(monkeypatch, font, ["H"]))
    assert details.splitlines() == ["H / Regular: unreadable (native read failed)", "H / Bold: 0 horizontal, 1 vertical"]


def test_hints_demo_when_more_than_twenty_selected_then_lists_twenty(monkeypatch) -> None:
    names = [f"g{number:02d}" for number in range(25)]
    font = hint_font(*(Glyph(name, Regular=Layer()) for name in names))
    title, text, details = shown(run_hints(monkeypatch, font, names))
    assert text == "Hint counts of 20 glyphs. Nothing was changed."
    assert len(details.splitlines()) == 20 and details.splitlines()[-1].startswith("g19 / Regular")


def test_hints_demo_when_nothing_selected_then_asks_for_a_selection(monkeypatch) -> None:
    import fontlabapp.components.inspect.model as model

    gui, _ = install_host(monkeypatch, package=hint_font(Glyph("H", Regular=Layer())), current_glyph=None)
    monkeypatch.setattr(model, "selected_names", lambda: [])
    run_script(HINTS)
    assert shown(gui)[:2] == ("Postscript Hints Demo", "Select glyphs in a Font window first. This demo reads their hints.")


def test_hints_demo_when_selection_read_fails_then_message_names_the_error(monkeypatch) -> None:
    import fontlabapp.components.inspect.model as model

    def fail():
        raise ValueError("Font-window carrier is missing or unreadable.")

    gui, _ = install_host(monkeypatch, package=hint_font(Glyph("H", Regular=Layer())))
    monkeypatch.setattr(model, "selected_names", fail)
    run_script(HINTS)
    assert shown(gui)[1] == "The selection could not be read: Font-window carrier is missing or unreadable."


def test_hints_demo_when_no_font_then_says_so(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch, package=None)
    run_script(HINTS)
    assert shown(gui)[:2] == ("Postscript Hints Demo", "Open a font and select glyphs first. This demo reads their hints.")


# --- Windows ---------------------------------------------------------------------


class FakeDialog:
    """A dialog class stand-in with the KEY the real one carries."""

    KEY = "fake_dialog_key"


def test_recipes_demo_when_font_open_then_shows_the_report_dialog_under_its_key(monkeypatch) -> None:
    stub_module(monkeypatch, "fontlabapp.components.recipes.ui", ComponentRecipesDialog=FakeDialog)
    opened = forbid_windows(monkeypatch)
    _, asked = install_host(monkeypatch)
    run_script(RECIPES)
    assert opened.calls == [((FakeDialog, "fake_dialog_key"), {})] and asked == []


def test_recipes_demo_when_no_font_then_says_so_and_opens_nothing(monkeypatch) -> None:
    stub_module(monkeypatch, "fontlabapp.components.recipes.ui", ComponentRecipesDialog=FakeDialog)
    opened = forbid_windows(monkeypatch)
    _, asked = install_host(monkeypatch, package=None)
    run_script(RECIPES)
    assert opened.calls == [] and len(asked) == 1
    assert asked[0][1:4] == ("Component Recipes Demo", "Open a font and select glyphs first. The report reads their components.", "Information")


def test_recipes_demo_when_show_fails_then_warning_names_the_error(monkeypatch) -> None:
    import fontlabapp.core.scripting as scripting

    stub_module(monkeypatch, "fontlabapp.components.recipes.ui", ComponentRecipesDialog=FakeDialog)
    _, asked = install_host(monkeypatch)
    monkeypatch.setattr(scripting, "show_script_dialog", lambda *_args: (_ for _ in ()).throw(RuntimeError("busy")))
    run_script(RECIPES)
    assert len(asked) == 1 and asked[0][1:4] == ("Component Recipes Demo", "The report did not open: busy", "Warning")


def patch_graphs(monkeypatch, first=None, second=None):
    """Replace the two graph entry points on the real module with recorders."""
    import fontlabapp.components.graph.model as graph

    calls = []
    monkeypatch.setattr(graph, "show", first or (lambda: calls.append("show")))
    monkeypatch.setattr(graph, "show_official", second or (lambda: calls.append("show_official")))
    return calls


def test_graph_demo_when_font_open_then_opens_both_graphs_in_order(monkeypatch) -> None:
    calls = patch_graphs(monkeypatch)
    _, asked = install_host(monkeypatch)
    run_script(GRAPH)
    assert calls == ["show", "show_official"] and asked == []


def test_graph_demo_when_no_font_then_says_so_and_opens_nothing(monkeypatch) -> None:
    calls = patch_graphs(monkeypatch)
    _, asked = install_host(monkeypatch, package=None)
    run_script(GRAPH)
    assert calls == [] and len(asked) == 1
    assert asked[0][1:4] == ("Component Graph Demo", "Open a font first. The graphs read its components.", "Information")


def test_graph_demo_when_first_fails_then_second_still_opens_and_warning_lists_the_first(monkeypatch) -> None:
    def fail():
        raise RuntimeError("Open component graphs on the main UI thread.")

    calls = patch_graphs(monkeypatch, first=fail)
    _, asked = install_host(monkeypatch)
    run_script(GRAPH)
    assert calls == ["show_official"] and len(asked) == 1
    assert asked[0][2] == "Some graphs did not open:\nclipped-force graph: Open component graphs on the main UI thread."
    assert asked[0][3] == "Warning"


def patch_reports(monkeypatch, near=None, svg=None):
    """Stub the point-counts dialog module and record all three entry points."""
    import fontlabapp.contours.near_miss.model as near_miss
    import fontlabapp.contours.svg_path.model as svg_path
    import fontlabapp.core.scripting as scripting

    calls = []
    stub_module(monkeypatch, "fontlabapp.contours.point_counts.ui", PointCountsDialog=FakeDialog)
    monkeypatch.setattr(near_miss, "show", near or (lambda: calls.append("near_miss")))
    monkeypatch.setattr(svg_path, "show", svg or (lambda: calls.append("svg_path")))
    monkeypatch.setattr(scripting, "show_script_dialog", lambda kind, key: calls.append((kind, key)))
    return calls


def test_reports_demo_when_font_open_then_opens_point_counter_near_miss_and_svg_in_order(monkeypatch) -> None:
    calls = patch_reports(monkeypatch)
    _, asked = install_host(monkeypatch)
    run_script(REPORTS)
    assert calls == [(FakeDialog, "fake_dialog_key"), "near_miss", "svg_path"] and asked == []


def test_reports_demo_when_no_font_then_says_so_and_opens_nothing(monkeypatch) -> None:
    calls = patch_reports(monkeypatch)
    _, asked = install_host(monkeypatch, package=None)
    run_script(REPORTS)
    assert calls == [] and len(asked) == 1
    assert asked[0][1:4] == ("Contour Reports Demo", "Open a font and select glyphs first. These reports read their contours.", "Information")


def test_reports_demo_when_two_fail_then_third_still_opens_and_warning_lists_both(monkeypatch) -> None:
    def refuse():
        raise ValueError("Select glyphs before running Close But No Cigar.")

    def expire():
        raise TimeoutError("Selection scan exceeded its deadline; no partial report.")

    calls = patch_reports(monkeypatch, near=refuse, svg=expire)
    _, asked = install_host(monkeypatch)
    run_script(REPORTS)
    assert calls == [(FakeDialog, "fake_dialog_key")] and len(asked) == 1
    assert asked[0][2] == (
        "Some reports did not open:\n"
        "close but no cigar: Select glyphs before running Close But No Cigar.\n"
        "SVG path commands: Selection scan exceeded its deadline; no partial report."
    )
    assert asked[0][3] == "Warning"
