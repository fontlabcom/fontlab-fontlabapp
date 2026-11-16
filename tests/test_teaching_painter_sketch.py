# this_file: tests/test_teaching_painter_sketch.py
"""Glyph Sketch Pad: SVG, outline capture, canvas events and panel, on real offscreen Qt with a fake host."""

import sys
import types

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import dialog_base, with_properties
from fontlabapp.fontui.teaching_painter import sketch as mod


def test_sketch_svg_when_strokes_then_polylines_in_font_units():
    text = mod.sketch_svg("A / Regular", [[(0, 0), (10, 5.5)], []], (-100, -100, 1200, 1200))
    assert text.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-100 -1100 1200 1200">')
    assert "<title>Sketch for A / Regular</title>" in text
    assert text.count("<polyline") == 1 and 'points="0,0 10,5.5"' in text


@pytest.mark.parametrize(
    ("label", "strokes", "box", "message"),
    [
        ("A", [], (0, 0, 1, 1), "Draw a stroke before preparing SVG text."),
        ("A", [[]], (0, 0, 1, 1), "Draw a stroke before preparing SVG text."),
        ("A", [[(0, float("nan"))]], (0, 0, 1, 1), "Sketch coordinates and a positive view box must be finite."),
        ("A", [[(0, 0)]], (0, 0, 0, 1), "Sketch coordinates and a positive view box must be finite."),
        ("A", [[(0, 0)] * (mod.MAX_POINTS + 1)], (0, 0, 1, 1), "Sketch point limit exceeded; clear or undo a stroke."),
        ("A\x01", [[(0, 0)]], (0, 0, 1, 1), "The glyph label cannot be represented as XML text."),
        ("A\ud800", [[(0, 0)]], (0, 0, 1, 1), "The glyph label cannot be represented as XML text."),
    ],
)
def test_sketch_svg_when_invalid_then_refused(label, strokes, box, message):
    with pytest.raises(ValueError) as error:
        mod.sketch_svg(label, strokes, box)
    assert str(error.value) == message


def test_sketch_svg_when_label_has_markup_then_escaped():
    assert "<title>Sketch for a&lt;b&amp;c</title>" in mod.sketch_svg("a<b&c", [[(0, 0)]], (0, 0, 1, 1))


class Layer:
    isNull = False


class Glyph:
    def __init__(self, name="A"):
        self.name, self.layer = name, Layer()

    def findLayer(self, master):
        return self.layer


class Pkg:
    def __init__(self):
        self.id, self.master, self.upm, self.glyph = 1, "Regular", 1000, Glyph()

    def findName(self, name):
        return self.glyph if name == self.glyph.name else None


@pytest.fixture
def world(studio_qt, monkeypatch):  # noqa: F811
    import fontlabapp
    import fontlabapp.contours.nodes.coordinates as coordinates
    import fontlabapp.core.scripting as scripting
    import fontlabapp.proof.inspectors.model as inspectors

    qt = sys.modules["PythonQt"]
    with_properties(qt.QtGui)
    state = types.SimpleNamespace(package=Pkg(), shown=[], current=None, clock=None)
    path = qt.QtGui.QPainterPath()
    path.addRect(0, 0, 500, 700)
    fl = types.SimpleNamespace(CurrentGlyph=lambda: state.current or state.package.glyph)
    natives = {"fontlab": fl, "PythonQt": qt}
    monkeypatch.setattr(fontlabapp, "_native", lambda name: natives[name], raising=False)
    monkeypatch.setattr(coordinates, "_native", lambda name: natives[name], raising=False)
    monkeypatch.setattr(scripting, "current_package", lambda *ident: state.package)
    monkeypatch.setattr(scripting, "names_dialog_type", lambda: dialog_base(qt.QtGui))
    monkeypatch.setattr(scripting, "show_script_dialog", lambda cls, key: state.shown.append(key) or cls(None))
    monkeypatch.setattr(inspectors, "outline", lambda layer: path)
    state.path = path
    return state


def test_capture_outline_when_ready_then_label_path_and_padded_box(world):
    label, path, box = mod.capture_outline()
    assert label == "A / Regular" and path is world.path
    assert box == (-100.0, -100.0, 1200.0, 1200.0)


def test_capture_outline_when_outline_exceeds_em_then_box_grows(world):
    world.path.addRect(0, 0, 2000, 3000)
    assert mod.capture_outline()[2] == (-100.0, -100.0, 2200.0, 3200.0)


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda w: setattr(w, "package", None), "Open a font and a glyph before capturing an outline."),
        (lambda w: setattr(w, "current", types.SimpleNamespace(name="missing")), "Open a glyph before capturing an outline."),
        (lambda w: setattr(w.package.glyph.layer, "isNull", True), "The current glyph has no layer in the current master."),
        (lambda w: setattr(w.package, "upm", float("inf")), "The current font has an invalid UPM."),
    ],
)
def test_capture_outline_when_context_invalid_then_refused(world, edit, message):
    edit(world)
    with pytest.raises(ValueError) as error:
        mod.capture_outline()
    assert str(error.value) == message


def test_capture_outline_when_package_changes_then_refused(world, monkeypatch):
    import fontlabapp.core.scripting as scripting
    import fontlabapp.proof.inspectors.model as inspectors

    def outline(layer):
        world.package.master = "Bold"
        return world.path

    monkeypatch.setattr(inspectors, "outline", outline)
    with pytest.raises(ValueError, match="Glyph, font or master changed; capture again."):
        mod.capture_outline()
    monkeypatch.setattr(scripting, "current_package", lambda *ident: None if ident else world.package)
    world.package.master = "Regular"
    monkeypatch.setattr(inspectors, "outline", lambda layer: world.path)
    with pytest.raises(ValueError, match="Glyph, font or master changed; capture again."):
        mod.capture_outline()


def test_capture_outline_when_deadline_passes_then_timeout(world, monkeypatch):
    ticks = iter([0.0, 5.0])
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError, match="Outline capture expired; no partial result."):
        mod.capture_outline()


class Event:
    def __init__(self, x=0, y=0, left=True):
        self._x, self._y, self._left = x, y, left

    def x(self):
        return self._x

    def y(self):
        return self._y

    def button(self):
        return sys.modules["PythonQt"].QtCore.Qt.LeftButton if self._left else 0


@pytest.fixture
def panel(world):
    qt = sys.modules["PythonQt"]
    dialog = mod.panel_type(qt)(None)
    dialog.canvas.resize(500, 500)
    return dialog, world, qt


def click(dialog, qt, text):
    (found,) = [b for b in dialog.findChildren(qt.QtGui.QPushButton) if b.text() == text]
    found.click()


def captured(panel_):
    dialog, world, qt = panel_
    click(dialog, qt, "Capture")
    return dialog


def test_canvas_mapping_when_resized_then_scale_fits_box_centered(panel):
    dialog, *_ = panel
    dialog.canvas.view_box = (0, 0, 1000, 500)
    scale, left, top = dialog.canvas.mapping()
    assert scale == pytest.approx(0.5) and left == 0 and top == pytest.approx(125)
    assert dialog.canvas.point(Event(0, 125)) == pytest.approx((0, 500))
    assert dialog.canvas.point(Event(500, 375)) == pytest.approx((1000, 0))


def test_panel_when_captured_then_status_and_reference_set(panel):
    dialog = captured(panel)
    assert dialog.status.text() == "Captured A / Regular. Draw over this detached outline."
    assert dialog.canvas.reference_path is not None and dialog.glyph_label == "A / Regular"


def test_panel_when_capture_refused_then_reference_cleared_and_status_shows_error(panel):
    dialog, world, qt = panel
    world.package = None
    click(dialog, qt, "Capture")
    assert dialog.canvas.reference_path is None
    assert dialog.status.text() == "Open a font and a glyph before capturing an outline."


def test_draw_when_no_capture_then_mouse_press_ignored(panel):
    dialog, *_ = panel
    dialog.canvas.mousePressEvent(Event(10, 10))
    assert dialog.canvas.strokes == [] and not dialog.canvas.drawing


def test_draw_when_dragged_then_stroke_recorded_and_svg_prepared(panel):
    dialog = captured(panel)
    canvas = dialog.canvas
    canvas.mousePressEvent(Event(100, 100))
    canvas.mouseMoveEvent(Event(100, 100))
    canvas.mouseMoveEvent(Event(200, 150))
    canvas.mouseReleaseEvent(Event(300, 150))
    assert len(canvas.strokes[0]) == 3 and canvas.point_count == 3 and not canvas.drawing
    assert dialog.status.text() == "Scratch sketch. Copy SVG Text before closing to retain it."
    click(dialog, sys.modules["PythonQt"], "SVG Text")
    assert dialog.output.toPlainText().startswith("<svg ")
    assert dialog.status.text() == "Select and copy SVG text. The grey reference outline is not included."


def test_draw_when_click_without_move_then_short_mark_added(panel):
    dialog = captured(panel)
    dialog.canvas.mousePressEvent(Event(50, 50))
    dialog.canvas.mouseReleaseEvent(Event(50, 50))
    (stroke,) = dialog.canvas.strokes
    assert len(stroke) == 2 and stroke[1][0] == pytest.approx(stroke[0][0] + 0.1)


def test_draw_when_right_button_or_move_without_press_then_ignored(panel):
    dialog = captured(panel)
    dialog.canvas.mousePressEvent(Event(1, 1, left=False))
    dialog.canvas.mouseMoveEvent(Event(2, 2))
    dialog.canvas.mouseReleaseEvent(Event(2, 2))
    assert dialog.canvas.strokes == []


def test_draw_when_point_limit_reached_then_refused_with_status(panel):
    dialog = captured(panel)
    canvas = dialog.canvas
    canvas.point_count = mod.MAX_POINTS
    canvas.mousePressEvent(Event(5, 5))
    assert dialog.status.text() == "Sketch point limit reached; Clear or Undo Stroke."
    assert canvas.strokes == []
    canvas.strokes, canvas.drawing = [[(0.0, 0.0)]], True
    canvas.mouseMoveEvent(Event(9, 9))
    assert not canvas.drawing and dialog.status.text() == "Sketch point limit reached; Clear or Undo Stroke."


def test_release_when_move_fails_then_status_set_and_drawing_stopped(panel):
    dialog = captured(panel)
    canvas = dialog.canvas
    canvas.drawing = True
    canvas.strokes = []
    canvas.mouseReleaseEvent(Event(1, 1))
    assert not canvas.drawing and dialog.status.text() == "list index out of range"


def test_capture_when_strokes_exist_then_refused(panel):
    dialog = captured(panel)
    dialog.canvas.mousePressEvent(Event(5, 5))
    click(dialog, panel[2], "Capture")
    assert dialog.status.text() == "Clear or Undo Stroke before capturing another glyph."


def test_undo_and_clear_when_strokes_then_points_and_output_reset(panel):
    dialog = captured(panel)
    qt = panel[2]
    for x in (10, 20):
        dialog.canvas.mousePressEvent(Event(x, x))
        dialog.canvas.mouseReleaseEvent(Event(x + 5, x))
    assert len(dialog.canvas.strokes) == 2
    click(dialog, qt, "Undo Stroke")
    assert len(dialog.canvas.strokes) == 1 and dialog.canvas.point_count == len(dialog.canvas.strokes[0])
    click(dialog, qt, "Clear")
    assert dialog.canvas.strokes == [] and dialog.canvas.point_count == 0
    click(dialog, qt, "Undo Stroke")
    assert dialog.canvas.point_count == 0


def test_svg_text_when_nothing_drawn_then_status_shows_refusal(panel):
    dialog, world, qt = panel
    click(dialog, qt, "SVG Text")
    assert dialog.status.text() == "Draw a stroke before preparing SVG text."


def test_paint_when_reference_and_strokes_then_renders_without_failure(panel):
    dialog = captured(panel)
    dialog.canvas.mousePressEvent(Event(10, 10))
    dialog.canvas.mouseReleaseEvent(Event(60, 60))
    status = dialog.status.text()
    image = dialog.canvas.grab()
    assert not image.isNull() and dialog.status.text() == status


def test_paint_when_path_breaks_then_status_reports_and_painter_ended(panel):
    dialog = captured(panel)
    dialog.canvas.reference_path = object()
    dialog.canvas.grab()
    assert dialog.status.text().startswith("Sketch paint failed: ")


def test_close_when_hook_or_default_then_hook_runs_else_closes(panel):
    dialog, world, qt = panel
    closed = []
    dialog.lab_close = lambda: closed.append(1)
    click(dialog, qt, "Close")
    assert closed == [1]
    del dialog.lab_close
    dialog.show()
    dialog.canvas.drawing = True
    click(dialog, qt, "Close")
    assert not dialog.isVisible() and not dialog.canvas.drawing


def test_main_when_called_then_shows_sketch_pad(world):
    dialog = mod.main()
    assert world.shown == ["widgets_glyph_sketch_pad"]
    assert dialog.windowTitle() == "Glyph Sketch Pad"


def test_capture_outline_when_clock_reaches_deadline_exactly_then_timeout(world, monkeypatch):
    ticks = iter([0.0, 2.0])  # `>=` refuses, `>` would accept
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError, match="Outline capture expired; no partial result."):
        mod.capture_outline()


def test_sketch_svg_when_points_exactly_at_limit_then_accepted_and_one_more_refused():
    assert mod.sketch_svg("A", [[(0, 0)] * mod.MAX_POINTS], (0, 0, 1, 1))
    with pytest.raises(ValueError, match="point limit"):
        mod.sketch_svg("A", [[(0, 0)] * (mod.MAX_POINTS - 1), [(0, 0)] * 2], (0, 0, 1, 1))


@pytest.mark.parametrize("label,refused", [("A\x1f", True), ("A\x20", False), ("A\ud7ff", False), ("A\udfff", True), ("A\ue000", False)])
def test_sketch_svg_when_label_char_at_control_or_surrogate_edge_then_only_unrepresentable_refused(label, refused):
    if refused:
        with pytest.raises(ValueError, match="cannot be represented"):
            mod.sketch_svg(label, [[(0, 0)]], (0, 0, 1, 1))
    else:
        assert mod.sketch_svg(label, [[(0, 0)]], (0, 0, 1, 1))


def test_capture_outline_when_glyph_disappears_during_capture_then_refused(world, monkeypatch):
    import fontlabapp.contours.nodes.coordinates as coordinates

    real = coordinates.current_glyph
    calls = []
    monkeypatch.setattr(coordinates, "current_glyph", lambda package: real(package) if not calls.append(1) and len(calls) == 1 else None)
    with pytest.raises(ValueError, match="Glyph, font or master changed; capture again."):
        mod.capture_outline()


def test_paint_when_painter_cannot_be_created_then_failure_kept_and_no_cleanup_error(panel, monkeypatch):
    dialog = captured(panel)
    qt = panel[2]

    def broken(*args):
        raise RuntimeError("no painter")

    monkeypatch.setattr(qt.QtGui, "QPainter", broken)
    dialog.canvas.update()
    dialog.canvas.paintEvent(None)
    assert dialog.status.text() == "Sketch paint failed: no painter"  # `painter.end()` on None must not run
