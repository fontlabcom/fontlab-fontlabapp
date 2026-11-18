# this_file: tests/test_cov_ui_transform.py
"""TransformEditor and its view built offscreen against a behavioural PythonQt fake."""

import json
from typing import Any

import pytest
from _light_canvas import light_canvas

import _cov_qt as fq


@pytest.fixture
def tmod(monkeypatch):
    handle = fq.install(monkeypatch)
    editor = handle.load("fontlabapp.fontui.transform")
    view = handle.load("fontlabapp.fontui.transform_view")
    light_canvas(monkeypatch, view)
    yield type("Mods", (), {"editor": editor, "view": view})
    fq.release()


def make(tmod: Any, name: str | None = "V", font: Any = "default", on_change: Any = None):
    ufo = fq.ufo_font() if font == "default" else font
    return tmod.editor.TransformEditor(ufo, name, None, on_change), ufo


def test_exact_text_when_integral_or_fractional_then_round_trips(tmod):
    assert tmod.view.exact_text(2.0) == "2", "whole floats lose the decimal tail"
    assert tmod.view.exact_text(0.1) == "0.1", "short fractions stay short"
    assert tmod.view.exact_text(1e300) == repr(1e300), "huge floats keep repr form"
    assert float(tmod.view.exact_text(1 / 3)) == 1 / 3, "long fractions round-trip exactly"


def test_record_when_glyph_has_contour_then_outline_has_bounds_and_width(tmod):
    ufo = fq.ufo_font()
    outline = tmod.view.record(ufo, ufo["A"])
    assert outline.bounds == (0, 0, 600, 700), "bounds cover the triangle"
    assert outline.width == 600.0, "the advance width is carried"
    assert outline.recording, "the contour is recorded for drawing"


def test_init_when_name_given_then_glyph_selected_and_identity_preview_shown(tmod):
    seen = []
    editor, _ = make(tmod, "V", on_change=lambda r, g: seen.append((r, g)))
    assert [i.text() for i in editor.glyph_control.items] == ["A", "V"], (
        "the glyph chooser lists the font's glyphs"
    )
    assert editor.glyph_control.currentText == "V", "the requested glyph is selected"
    assert editor.diagnostic.text == "V: affine preview at 100%; the source font is unchanged.", (
        "the status describes the identity preview"
    )
    assert seen, "on_change follows the first preview"
    assert seen[0][0].intensity == 100, "the first preview is at full intensity"
    assert editor.matrix["xx"].text == "1", "xx starts at identity"
    assert editor.matrix["dx"].text == "0", "dx starts at identity"
    assert editor.enabled_control.checked, "the transform starts enabled"
    assert editor.compare_control.checked, "comparison with the original starts on"


def test_init_when_name_unknown_then_first_glyph_used(tmod):
    editor, _ = make(tmod, "nope")
    assert editor.glyph_control.currentText == "A", "an unknown name falls back to the first glyph"


def test_update_when_font_none_then_error_shown_and_result_cleared(tmod):
    editor, _ = make(tmod, font=None)
    assert editor.diagnostic.text == "No font supplied", "the missing font is reported"
    assert editor.result is None, "no result without a font"
    assert editor.update() is False, "update fails without a font"


def test_update_when_font_has_no_glyphs_then_error_shown(tmod):
    from ufoLib2 import Font

    editor, _ = make(tmod, font=Font())
    assert editor.diagnostic.text == "The font has no glyphs", "an empty font is reported"


def test_update_when_field_edited_then_preview_follows_and_callback_runs(tmod):
    seen = []
    editor, _ = make(tmod, "A", on_change=lambda r, g: seen.append(r))
    editor.matrix["xx"].setText("2")
    assert seen[-1].matrix[0] == 2.0, "typing in a matrix field re-previews"
    assert editor.result.bounds == (0, 0, 1200, 700), editor.result.bounds
    assert editor.original.bounds == (0, 0, 600, 700), "the original stays untouched"


def test_update_when_text_not_a_number_then_message_names_the_field(tmod):
    editor, _ = make(tmod)
    editor.matrix["yy"].setText("x")
    assert editor.diagnostic.text == "yy: not a number: 'x'", (
        "the diagnostic names the field and the bad text"
    )
    assert editor.result is None, "no result for invalid input"


def test_update_when_singular_matrix_then_determinant_refusal(tmod):
    editor, _ = make(tmod)
    editor.matrix["xx"].setText("0")
    editor.matrix["yy"].setText("0")
    assert "determinant" in editor.diagnostic.text, editor.diagnostic.text


def test_update_when_disabled_then_status_says_identity(tmod):
    editor, _ = make(tmod)
    editor.enabled_control.setChecked(False)
    assert editor.diagnostic.text.endswith(
        "(disabled: identity); the source font is unchanged."
    ), editor.diagnostic.text


def test_update_when_callback_raises_then_status_reports_failure(tmod):
    def boom(recipe, glyph):
        raise RuntimeError("consumer bug")

    editor, _ = make(tmod, on_change=boom)
    assert editor.diagnostic.text == "Callback failed: consumer bug", (
        "the callback failure is surfaced"
    )


def test_update_when_transform_fails_then_error_shown(tmod, monkeypatch):
    editor, _ = make(tmod)

    def fail(glyph, recipe):
        raise ValueError("boom")

    monkeypatch.setattr(tmod.editor, "transform_glyph", fail)
    assert editor.update() is False, "a failing transform fails the update"
    assert editor.diagnostic.text == "boom", "the transform error is shown"


def test_update_when_closed_then_returns_false(tmod):
    editor, _ = make(tmod)
    editor.close()
    assert editor.update() is False, "a closed editor refuses updates"
    assert editor.on_change is None, "the callback is dropped on close"


def test_glyph_change_when_other_glyph_chosen_then_name_in_status(tmod):
    editor, _ = make(tmod, "A")
    editor.glyph_control.setCurrentIndex(1)
    assert editor.diagnostic.text.startswith("V:"), editor.diagnostic.text


def test_slider_when_moved_then_field_gets_whole_percent(tmod):
    editor, _ = make(tmod)
    editor.intensity_slider.setValue(30)
    assert editor.intensity_field.text == "30", "the field mirrors the slider as a whole percent"
    assert "affine preview at 30%" in editor.diagnostic.text, "the preview follows the slider"


def test_field_when_fractional_then_slider_rounds_and_recipe_stays_exact(tmod):
    editor, _ = make(tmod)
    editor.intensity_field.setText("40.5")
    assert editor.intensity_slider.value == 40, "the slider rounds to a whole percent"
    assert editor.recipe().intensity == 40.5, "the text field keeps the exact value"


def test_field_when_invalid_then_slider_ignores_it_and_error_shown(tmod):
    editor, _ = make(tmod)
    editor.intensity_slider.setValue(20)
    editor.intensity_field.setText("abc")
    assert editor.intensity_slider.value == 20, "invalid text leaves the slider alone"
    assert editor.diagnostic.text == "intensity: not a number: 'abc'", (
        "the diagnostic names the intensity field"
    )


def test_field_when_nan_or_inf_then_slider_ignores_it(tmod):
    editor, _ = make(tmod)
    editor.intensity_slider.setValue(20)
    editor.intensity_field.setText("inf")
    assert editor.intensity_slider.value == 20, "OverflowError from round() is swallowed"


def test_compare_toggle_when_changed_then_canvas_repaints(tmod):
    editor, _ = make(tmod)
    before = len([c for c in editor.canvas.calls if c[0] == "update"])
    editor.compare_control.setChecked(False)
    after = len([c for c in editor.canvas.calls if c[0] == "update"])
    assert after == before + 1, "toggling comparison repaints the canvas once"


def test_reset_button_when_clicked_then_identity_restored(tmod):
    editor, _ = make(tmod)
    editor.matrix["xx"].setText("3")
    editor.buttons["reset"].clicked.emit()
    assert editor.matrix["xx"].text == "1", "the matrix field returns to identity"
    assert editor.recipe().matrix == (1, 0, 0, 1, 0, 0), "the recipe is the identity matrix"


def test_zoom_when_button_pressed_then_scale_grows_and_view_resets(tmod):
    editor, _ = make(tmod)
    editor.buttons["zoom"].clicked.emit()
    assert editor.zoom == 1.25, "Zoom in grows the scale by a quarter"
    editor.buttons["view"].clicked.emit()
    assert editor.zoom == 1.0, "Reset view returns to unit scale"


@pytest.mark.parametrize("asked,expected", [(1e9, 64.0), (0.0, 1 / 64), (2.0, 2.0)])
def test_set_zoom_when_out_of_range_then_clamped(tmod, asked, expected):
    editor, _ = make(tmod)
    editor.set_zoom(asked)
    assert editor.zoom == expected, f"zoom {asked} clamps to {expected}"


def test_show_script_when_called_then_script_shown_and_returned(tmod):
    editor, _ = make(tmod)
    editor.matrix["dx"].setText("5")
    editor.buttons["script"].clicked.emit()
    text = editor.script_view.plain_text
    assert text == editor.show_script(), "the button shows the returned script"
    assert "5" in text, text
    assert editor.script_view.shown, "the read-only script view is revealed"


def test_view_when_outlines_present_then_scale_positive(tmod):
    editor, _ = make(tmod, "A")
    scale, x, y = editor.view(400, 300)
    assert scale > 0, (scale, x, y)
    editor.zoom = 2.0
    assert editor.view(400, 300)[0] == pytest.approx(scale * 2), "zoom multiplies the scale"


def test_view_when_glyph_empty_and_metrics_missing_then_defaults_used(tmod):
    ufo = fq.ufo_font()
    ufo.newGlyph("space").width = 250
    ufo.info.ascender = ufo.info.descender = ufo.info.unitsPerEm = None
    editor, _ = make(tmod, "space", font=ufo)
    scale, _, _ = editor.view(400, 300)
    assert editor.original.bounds is None, "an empty glyph has no bounds"
    assert scale > 0, "default metrics still give a positive scale"


def test_save_settings_when_path_given_then_json_written_and_status_shown(tmod, tmp_path):
    editor, _ = make(tmod)
    editor.matrix["dy"].setText("7")
    path = tmp_path / "recipe.json"
    editor.save_settings(str(path))
    assert json.loads(path.read_text())["matrix"][5] == 7, "the saved recipe carries dy"
    assert editor.diagnostic.text == f"Saved settings to {path}", "the save is reported"


def test_load_settings_when_file_valid_then_controls_show_it(tmod, tmp_path):
    editor, _ = make(tmod)
    editor.matrix["dx"].setText("9")
    path = tmp_path / "recipe.json"
    editor.save_settings(str(path))
    editor.reset_transform()
    editor.load_settings(str(path))
    assert editor.matrix["dx"].text == "9", "the loaded recipe fills the matrix field"
    assert "affine preview" in editor.diagnostic.text, "the preview is refreshed after loading"


def test_dialog_buttons_when_path_chosen_then_save_and_load_run(tmod, tmp_path, monkeypatch):
    editor, _ = make(tmod)
    path = tmp_path / "chosen.json"
    monkeypatch.setattr(fq.FakeFileDialog, "path", str(path))
    editor.matrix["dx"].setText("4")
    editor.buttons["save"].clicked.emit()
    assert path.exists(), "Save settings writes the chosen path"
    editor.reset_transform()
    editor.buttons["load"].clicked.emit()
    assert editor.matrix["dx"].text == "4", "Load settings reads it back"


def test_dialog_when_cancelled_then_nothing_happens(tmod, tmp_path, monkeypatch):
    editor, _ = make(tmod)
    monkeypatch.setattr(fq.FakeFileDialog, "path", "")
    before = editor.diagnostic.text
    editor.buttons["save"].clicked.emit()
    assert editor.diagnostic.text == before, "cancelling the dialog leaves the status alone"


def test_dialog_when_file_unreadable_then_error_shown(tmod, tmp_path, monkeypatch):
    editor, _ = make(tmod)
    monkeypatch.setattr(fq.FakeFileDialog, "path", str(tmp_path / "missing.json"))
    editor.buttons["load"].clicked.emit()
    assert "missing.json" in editor.diagnostic.text, editor.diagnostic.text


class Painter(fq.FakeWidget):
    """Records every painter created by the canvas."""

    made: list = []

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        Painter.made.append(self)


def test_paint_when_result_present_then_both_outlines_drawn_and_painter_ended(
    tmod, monkeypatch
):
    editor, _ = make(tmod, "A")
    Painter.made = []
    monkeypatch.setattr(tmod.view.QtGui, "QPainter", Painter)
    editor.canvas.paintEvent(None)
    painter = Painter.made[0]
    draws = [c for c in painter.calls if c[0] == "drawPath"]
    assert len(draws) == 4, "closed and open path groups for result plus original"
    assert painter.calls[-1][0] == "end", "the painter always ends"


def test_paint_when_compare_off_then_only_result_drawn(tmod, monkeypatch):
    editor, _ = make(tmod, "A")
    editor.compare_control.setChecked(False)
    Painter.made = []
    monkeypatch.setattr(tmod.view.QtGui, "QPainter", Painter)
    editor.canvas.paintEvent(None)
    names = [c[0] for c in Painter.made[0].calls]
    assert names.count("drawPath") == 2, "only the result's two path groups are drawn"
    assert names[-1] == "end", "the painter always ends"


def test_paint_when_no_result_or_closed_then_only_background_painted(tmod, monkeypatch):
    editor, _ = make(tmod, "A")
    editor.result = None
    Painter.made = []
    monkeypatch.setattr(tmod.view.QtGui, "QPainter", Painter)
    editor.canvas.paintEvent(None)
    names = [c[0] for c in Painter.made[0].calls]
    assert "drawPath" not in names, "nothing is drawn without a result"
    assert names[-1] == "end", "the painter always ends"


def test_paint_when_drawing_raises_then_error_in_status_and_painter_ended(
    tmod, monkeypatch
):
    editor, _ = make(tmod, "A")
    Painter.made = []
    monkeypatch.setattr(tmod.view.QtGui, "QPainter", Painter)

    def explode(width, height):
        raise RuntimeError("paint failure")

    monkeypatch.setattr(editor, "view", explode)
    editor.canvas.paintEvent(None)
    assert editor.diagnostic.text == "paint failure", "the paint error is shown in the status"
    assert Painter.made[0].calls[-1][0] == "end", "an exception must not leave it active"


def test_draw_when_open_path_present_then_outline_only(tmod, monkeypatch):
    from fontTools.pens.recordingPen import RecordingPen

    pen = RecordingPen()
    pen.moveTo((0, 0))
    pen.lineTo((10, 10))
    pen.endPath()
    painter = Painter()
    tmod.view._draw(painter, pen.value, "#000000", True)
    brushes = [c for c in painter.calls if c[0] == "setBrush"]
    draws = [c for c in painter.calls if c[0] == "drawPath"]
    assert len(brushes) == 2, "the brush is set for the closed and the open group"
    assert len(draws) == 2, "both path groups are drawn"


def test_close_when_called_then_callback_dropped_and_widget_deleted(tmod):
    editor, _ = make(tmod, on_change=lambda *a: None)
    editor.close()
    assert editor.on_change is None, "the callback is dropped"
    assert editor.widget.deleted, "the root widget is scheduled for deletion"


def test_window_when_created_then_compact_panel_metrics(tmod):
    window = make(tmod)[0]
    assert [a for c, a in window.layout.calls if c == "setContentsMargins"] == [(6, 6, 6, 6)]
    assert [a for c, a in window.layout.calls if c == "setSpacing"] == [(4,)]
