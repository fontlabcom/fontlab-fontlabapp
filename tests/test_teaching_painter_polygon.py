# this_file: tests/test_teaching_painter_polygon.py
"""Em Star Polygon: geometry, SVG, drawing fences and panel, on real offscreen Qt with a fake host."""

import sys
import types

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import dialog_base, with_properties
from fontlabapp.fontui.teaching_painter import polygon as mod


def test_polygon_points_when_valid_then_alternating_radii_ccw():
    points = mod.polygon_points(1000, 3, 0.4, 0.2, 0)
    assert len(points) == 6
    assert points[0] == pytest.approx((400, 0))
    assert points[1][0] ** 2 + points[1][1] ** 2 == pytest.approx(200**2)
    assert points[1][1] > 0


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((float("nan"), 5, 0.4, 0.2, 0), "Use finite numeric UPM, radii and rotation values."),
        ((True, 5, 0.4, 0.2, 0), "Use finite numeric UPM, radii and rotation values."),
        (("1000", 5, 0.4, 0.2, 0), "Use finite numeric UPM, radii and rotation values."),
        ((8, 5, 0.4, 0.2, 0), "Use a font UPM between 16 and 16384."),
        ((1000, 2, 0.4, 0.2, 0), "Use an integer tip count between 3 and 128."),
        ((1000, 5.0, 0.4, 0.2, 0), "Use an integer tip count between 3 and 128."),
        ((1000, 5, 0.2, 0.4, 0), "Use 0.001 <= inner <= outer <= 0.5 em and 0..360 degrees."),
        ((1000, 5, 0.4, 0.2, 361), "Use 0.001 <= inner <= outer <= 0.5 em and 0..360 degrees."),
    ],
)
def test_polygon_points_when_invalid_then_refused(args, message):
    with pytest.raises(ValueError) as error:
        mod.polygon_points(*args)
    assert str(error.value) == message


def test_polygon_svg_when_generated_then_y_down_em_square():
    text = mod.polygon_svg(1000, 3, 0.4, 0.2, 0)
    assert text.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" width="1000" height="1000">')
    assert 'points="900.000000,500.000000 ' in text
    assert text.endswith("</svg>\n")


def test_round_unit_when_tie_then_away_from_zero():
    assert mod.round_unit(2.5) == 3.0
    assert mod.round_unit(-2.5) == -3.0
    assert mod.round_unit(2.4) == 2.0


def test_save_svg_when_new_absolute_path_then_written_and_never_replaced(tmp_path):
    target = tmp_path / "a.svg"
    mod.save_svg(str(target), "<svg/>")
    assert target.read_text() == "<svg/>"
    with pytest.raises(FileExistsError):
        mod.save_svg(str(target), "other")
    assert target.read_text() == "<svg/>"


@pytest.mark.parametrize("name", ["relative.svg", "/tmp/x.txt"])
def test_save_svg_when_relative_or_wrong_suffix_then_refused(name):
    with pytest.raises(ValueError) as error:
        mod.save_svg(name, "x")
    assert str(error.value) == "Enter an absolute destination path ending in .svg."


class Pkg:
    def __init__(self, upm=1000, ident=1):
        self.id, self.upm, self.masters, self.master = ident, upm, ("Regular",), "Regular"


class Node:
    def __init__(self, point, nodeType="on"):
        self.x, self.y, self.kind = point.x(), point.y(), nodeType

    def isOn(self):
        return self.kind == "on"


class Contour:
    def __init__(self, nodes, closed=False):
        self._nodes, self.closed = list(nodes), closed

    def nodes(self):
        return self._nodes


class Transform:
    def map(self, point):
        return point


class Shape:
    def __init__(self):
        self.contours, self.transform = [], Transform()

    def addContour(self, contour):
        self.contours.append(contour)


class Layer:
    def __init__(self, name="Regular", width=600.0):
        self.id, self.name, self.advanceWidth, self.isNull, self.shapes = 7, name, width, False, []

    def addShape(self, shape):
        self.shapes.append(shape)


class Glyph:
    def __init__(self, package, layer):
        self.isNull, self.package, self.id = False, package, 3
        self.activeLayer, self.layers = layer, [layer]


class Result(dict):
    mismatches = ()


@pytest.fixture
def world(studio_qt, monkeypatch):  # noqa: F811
    import fontlabapp
    import fontlabapp.core.history.glyphs as history
    import fontlabapp.core.scripting as scripting

    qt = sys.modules["PythonQt"]
    with_properties(qt.QtGui)
    package = Pkg()
    layer = Layer()
    state = types.SimpleNamespace(package=package, layer=layer, glyph=Glyph(package, layer), cap=700.0,
                                  commits=[], mismatches=(), shown=[], pending=("a",), note="")
    qt.QtGui.QGraphicsScene.addPolygon = lambda self, *args: None
    fl = types.SimpleNamespace(
        CurrentGlyph=lambda: state.glyph, FontMetrics=lambda p, m: types.SimpleNamespace(capsHeight=state.cap),
        flNode=Node, flContour=Contour, flShape=Shape)
    natives = {"fontlab": fl, "PythonQt": qt}
    monkeypatch.setattr(fontlabapp, "_native", lambda name: natives[name], raising=False)
    monkeypatch.setattr(scripting, "current_package", lambda *ident: state.package)
    monkeypatch.setattr(scripting, "names_dialog_type", lambda: dialog_base(qt.QtGui))
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: {"facts": 1})

    def commit(title, layers, glyphs, mutate, operation, facts, read_back):
        mutate()
        result = Result(pending_updates=state.pending, pending_note=state.note)
        result.mismatches = tuple(read_back()) or state.mismatches
        state.commits.append((title, operation, facts))
        return result

    monkeypatch.setattr(history, "commit", commit)
    monkeypatch.setattr(scripting, "show_script_dialog", lambda cls, key: state.shown.append(key) or cls(None))
    return state


def test_current_svg_when_font_open_then_uses_package_upm(world):
    world.package.upm = 2000
    assert 'viewBox="0 0 2000 2000"' in mod.current_svg(5, 0.4, 0.2, 0)


def test_current_svg_when_no_font_then_refused(world):
    world.package = None
    with pytest.raises(ValueError, match="Open a font before generating artwork."):
        mod.current_svg(5, 0.4, 0.2, 0)


def test_current_svg_when_upm_changes_during_generation_then_refused(world, monkeypatch):
    import fontlabapp.core.scripting as scripting

    packages = iter([Pkg(1000), Pkg(2000)])
    monkeypatch.setattr(scripting, "current_package", lambda *ident: next(packages))
    with pytest.raises(ValueError, match="Font or UPM changed; generate again."):
        mod.current_svg(5, 0.4, 0.2, 0)


def test_draw_current_when_valid_then_one_closed_rounded_contour_added(world):
    disclosure = {}
    mod.draw_current(3, 0.4, 0.2, 0, disclosure=disclosure)
    assert world.commits == [("Draw Em Star Polygon", "geometry", {"facts": 1})]
    (shape,) = world.layer.shapes
    (contour,) = shape.contours
    assert contour.closed and len(contour.nodes()) == 6
    assert (contour.nodes()[0].x, contour.nodes()[0].y) == (700.0, 350.0)
    assert disclosure == {"pending_updates": ("a",), "pending_note": ""}


def test_draw_current_when_note_pending_and_no_target_then_printed(world, capsys):
    world.note = "queued"
    mod.draw_current(3, 0.4, 0.2, 0)
    assert capsys.readouterr().out == "Queued glyph ids: ('a',) · queued\n"


def test_draw_current_when_readback_mismatch_then_runtime_error_with_undo_hint(world):
    import fontlabapp.core.history.glyphs as history

    world.mismatches = ("Bad.",)
    with pytest.raises(RuntimeError) as error:
        mod.draw_current(3, 0.4, 0.2, 0)
    assert str(error.value) == "Bad. " + history.UNDO_HINT


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda w: setattr(w, "package", None), "Open a font before drawing."),
        (lambda w: setattr(w, "glyph", None), "Open a glyph before drawing."),
        (lambda w: setattr(w.glyph, "isNull", True), "Open a glyph before drawing."),
        (lambda w: setattr(w.glyph, "package", Pkg(ident=99)), "The active glyph belongs to another font."),
        (lambda w: setattr(w.glyph, "activeLayer", None), "The glyph has no owned active layer."),
        (lambda w: setattr(w.glyph, "layers", []), "The glyph has no owned active layer."),
        (lambda w: setattr(w.layer, "name", "mask.Regular"),
         "The active layer has no associated master; choose a master layer or its named backup."),
        (lambda w: setattr(w.layer, "advanceWidth", float("inf")), "The current layer advance must be finite."),
        (lambda w: setattr(w, "cap", 0.0), "The current layer cap height must be finite and positive."),
    ],
)
def test_draw_current_when_context_invalid_then_refused(world, edit, message):
    edit(world)
    with pytest.raises(ValueError) as error:
        mod.draw_current(3, 0.4, 0.2, 0)
    assert str(error.value) == message
    assert world.layer.shapes == []


def test_draw_current_when_context_changes_during_scan_then_refused(world, monkeypatch):
    import fontlabapp.core.history.glyphs as history

    monkeypatch.setattr(history, "scan_auto_facts", lambda package: setattr(world, "cap", 650.0) or {})
    with pytest.raises(ValueError, match="Font, glyph, layer or metrics changed; draw again."):
        mod.draw_current(3, 0.4, 0.2, 0)


def test_draw_current_when_geometry_changes_before_attach_then_refused(world, monkeypatch):
    import fontlabapp.core.history.glyphs as history

    def commit(title, layers, glyphs, mutate, **kw):
        world.layer.shapes.append(Shape())
        mutate()

    monkeypatch.setattr(history, "commit", commit)
    with pytest.raises(ValueError, match="Font, glyph, layer or geometry changed; draw again."):
        mod.draw_current(3, 0.4, 0.2, 0)


@pytest.mark.parametrize(
    ("tamper", "message"),
    [
        (lambda w, s: None, "Current context or shape count differs from the plan."),
        (lambda w, s: s.contours[0].nodes()[0].__setattr__("x", 0.0),
         "Attached polygon node coordinates or types differ from the plan."),
        (lambda w, s: s.contours.append(Contour([])), "The attached shape must hold one closed contour."),
        (lambda w, s: setattr(s.contours[0], "closed", False), "The attached shape must hold one closed contour."),
    ],
)
def test_read_back_when_attached_geometry_differs_then_mismatch_reported(world, monkeypatch, tamper, message):
    import fontlabapp.core.history.glyphs as history

    def commit(title, layers, glyphs, mutate, read_back, **kw):
        mutate()
        if message.startswith("Current"):
            world.layer.shapes.clear()
        else:
            tamper(world, world.layer.shapes[-1])
        result = Result(pending_updates=(), pending_note="")
        result.mismatches = tuple(read_back())
        return result

    monkeypatch.setattr(history, "commit", commit)
    with pytest.raises(RuntimeError) as error:
        mod.draw_current(3, 0.4, 0.2, 0)
    assert str(error.value).startswith(message)


def test_read_back_when_pre_existing_shape_moved_then_mismatch_reported(world, monkeypatch):
    import fontlabapp.core.history.glyphs as history

    old = Shape()
    old.addContour(Contour([Node(types.SimpleNamespace(x=lambda: 1.0, y=lambda: 2.0))], True))
    world.layer.shapes.append(old)

    def commit(title, layers, glyphs, mutate, read_back, **kw):
        mutate()
        old.contours[0].nodes()[0].x = 50.0
        result = Result(pending_updates=(), pending_note="")
        result.mismatches = tuple(read_back())
        return result

    monkeypatch.setattr(history, "commit", commit)
    with pytest.raises(RuntimeError) as error:
        mod.draw_current(3, 0.4, 0.2, 0)
    assert str(error.value).startswith("Pre-existing shape geometry changed.")


@pytest.fixture
def panel(world):
    qt = sys.modules["PythonQt"]
    dialog = mod.panel_type(qt)(None)
    return dialog, world, qt


def click(dialog, qt, text):
    (found,) = [b for b in dialog.findChildren(qt.QtGui.QPushButton) if b.text() == text]
    found.click()


def test_panel_when_generated_then_svg_shown_and_status_ready(panel):
    dialog, world, qt = panel
    click(dialog, qt, "Generate Preview and SVG")
    assert dialog.output.toPlainText().startswith("<svg ")
    assert dialog.status.text() == "Preview ready. Draw in Current Layer, or save SVG for an external vector editor."


def test_panel_when_no_font_then_status_shows_refusal_and_output_empty(panel):
    dialog, world, qt = panel
    world.package = None
    click(dialog, qt, "Generate Preview and SVG")
    assert dialog.output.toPlainText() == ""
    assert dialog.status.text() == "Open a font before generating artwork."


def test_panel_when_saved_then_new_file_written(panel, tmp_path):
    dialog, world, qt = panel
    dialog.destination.setText(str(tmp_path / "star.svg"))
    click(dialog, qt, "Save New SVG")
    assert dialog.status.text() == "Saved new SVG for an external vector editor."
    assert (tmp_path / "star.svg").read_text() == dialog.output.toPlainText()


def test_panel_when_save_fails_then_output_retained_with_error(panel):
    dialog, world, qt = panel
    dialog.destination.setText("relative.svg")
    click(dialog, qt, "Save New SVG")
    assert dialog.status.text() == "Enter an absolute destination path ending in .svg."
    assert dialog.output.toPlainText().startswith("<svg ")


def test_panel_when_drawn_then_status_confirms_and_hooks_run(panel):
    dialog, world, qt = panel
    seen = []
    dialog.lab_check_target = lambda: seen.append("check")
    dialog.lab_applied = lambda: seen.append("applied")
    dialog.lab_refresh_preview = lambda: seen.append("refresh")
    dialog.lab_accept_preview = lambda parameters: seen.append(parameters)
    click(dialog, qt, "Generate Preview and SVG")
    click(dialog, qt, "Draw in Current Layer")
    assert dialog.status.text() == "Drawn one closed contour. Edit > Undo removes this action."
    assert seen == ["refresh", (5, 0.45, 0.2, 90.0), "check", "applied"]
    assert len(world.layer.shapes) == 1


def test_panel_when_draw_refused_then_status_shows_message_with_note(panel):
    dialog, world, qt = panel
    world.glyph = None
    click(dialog, qt, "Draw in Current Layer")
    assert dialog.status.text() == "Open a glyph before drawing."


def test_panel_when_close_clicked_then_hook_or_close(panel):
    dialog, world, qt = panel
    closed = []
    dialog.lab_close = lambda: closed.append(1)
    click(dialog, qt, "Close")
    assert closed == [1]
    del dialog.lab_close
    dialog.show()
    click(dialog, qt, "Close")
    assert not dialog.isVisible()


def test_main_when_called_then_shows_designer_em_star_dialog(world):
    dialog = mod.main()
    assert world.shown == ["designer_em_star"]
    assert dialog.windowTitle() == "Em Star Polygon"


@pytest.mark.parametrize("upm", [16, 16384])
def test_polygon_points_when_upm_at_inclusive_bounds_then_accepted(upm):
    assert mod.polygon_points(upm, 5, 0.4, 0.2, 0)


@pytest.mark.parametrize("upm", [15, 16385])
def test_polygon_points_when_upm_just_outside_bounds_then_refused(upm):
    with pytest.raises(ValueError, match="between 16 and 16384"):
        mod.polygon_points(upm, 5, 0.4, 0.2, 0)
