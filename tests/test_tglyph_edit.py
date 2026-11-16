# this_file: tests/test_tglyph_edit.py
# SPDX-License-Identifier: Apache-2.0
"""Qt-free TGlyph edits: structure rules, gestures, pen tool and the staged write."""

import pytest
from _tglyph_fakes import editable_font, layered_font

from fontlabapp.fontui.tglyph_edit import (
    Edit,
    Editor,
    delete_points,
    draw_contours,
    handles,
    move_points,
    normalise,
    points_in_rect,
    toggle_points,
    write_contours,
)
from fontlabapp.fontui.tglyph_model import (
    Contour,
    GlyphData,
    Point,
    TGlyphModel,
    read_glyph,
)


def P(x, y, kind=None, smooth=False):
    return Point(float(x), float(y), kind, smooth)


def model(font=None, name="a", layer=None):
    m = TGlyphModel(editable_font() if font is None else font, layer=layer)
    m.load(name)
    m.fit(400, 400)
    return m


def screen(m, c, p):
    point = m.data.contours[c].points[p]
    return m.view.to_screen(point.x, point.y)


def own(font, name="a", layer="public.default"):
    return [[(pt.x, pt.y, pt.type) for pt in c.points] for c in read_glyph(font, name, layer).contours]


def test_toggle_points_when_line_point_then_control_and_valid_quadratic():
    data = read_glyph(layered_font(), "a", "public.default")
    result = toggle_points(data, {(0, 5)})
    points = result.contours[0].points
    assert points[5].type is None and points[0].type == "qcurve"
    assert [(p.x, p.y) for p in points] == [(p.x, p.y) for p in data.contours[0].points]
    assert result.contours[1:] == data.contours[1:]
    assert (result.components, result.anchors, result.width) == (data.components, data.anchors, data.width)


def test_toggle_points_when_control_then_on_curve_without_dropping_other_controls():
    data = read_glyph(layered_font(), "a", "public.default")
    result = toggle_points(data, {(0, 2)})
    assert [p.type for p in result.contours[0].points] == ["line", "line", "line", None, "qcurve", "line"]
    assert len(result.contours[0].points) == len(data.contours[0].points)


@pytest.mark.parametrize("selection", [{(1, 0)}, {(1, 1)}, {(0, 0), (0, 1), (0, 4), (0, 5)}])
def test_toggle_points_when_endpoint_or_no_on_curve_then_refused(selection):
    data = read_glyph(layered_font(), "a", "public.default")
    with pytest.raises(ValueError, match="endpoint|on-curve"):
        toggle_points(data, selection)


def test_toggle_points_when_two_or_many_controls_then_valid_segment_types():
    data = read_glyph(layered_font(), "a", "public.default")
    result = toggle_points(data, {(0, 1)})
    assert result.contours[0].points[4].type == "qcurve"
    restored = toggle_points(result, {(0, 1)})
    assert restored.contours[0].points[4].type == "qcurve"
    result = toggle_points(data, {(0, 0), (0, 5)})
    assert result.contours[0].points[1].type == "curve"
    assert toggle_points(data, set()) == data


def test_editor_toggle_when_selected_then_single_layer_write_and_refresh():
    font = editable_font()
    m = model(font)
    editor = Editor(m)
    assert editor.toggle() is None
    m.selection = {(0, 5)}
    edit = editor.toggle()
    editor.commit(edit)
    assert font.edits == [("a", "public.default", "TGlyph: Toggle on/off-curve a")]
    assert m.refresh() is False
    assert m.data.contours[0].points[5].type is None
    editor.drag = (0, 0)
    assert editor.toggle() is None
    editor.drag = None
    m.data = None
    assert editor.toggle() is None


# --- structure ------------------------------------------------------------------
def test_handles_when_closed_then_wraps_and_open_does_not():
    closed = Contour((P(0, 0, "curve"), P(10, 0, "line"), P(20, 0), P(30, 0)))
    assert handles(closed, 0) == [3], "a closed contour's point 0 owns the trailing handle"
    assert handles(closed, 2) == [], "an off-curve point owns no handles"
    opened = Contour((P(0, 0, "move"), P(5, 5), P(9, 9), P(10, 0, "curve")))
    assert handles(opened, 0) == [1] and handles(opened, 3) == [2], "open ends do not wrap"


def test_move_points_when_on_curve_moved_then_handles_follow_as_floats():
    data = read_glyph(layered_font(), "a", "public.default")
    moved = move_points(data, {(0, 4)}, 3, -2)
    before, after = data.contours[0].points, moved.contours[0].points
    for i in (3, 4, 5):
        if i == 5:
            assert after[i] == before[i], "the line neighbour stays"
        else:
            assert (after[i].x, after[i].y) == (before[i].x + 3, before[i].y - 2)
    assert after[2] == before[2], "the other cubic's handle stays"
    assert all(isinstance(p.x, float) for p in after)
    assert moved.contours[1:] == data.contours[1:] and moved.components == data.components


def test_move_points_when_stale_keys_then_ignored():
    data = read_glyph(layered_font(), "a", "public.default")
    assert move_points(data, {(9, 0), (0, 99)}, 5, 5) == data


def test_normalise_when_only_off_curves_then_none():
    assert normalise((P(1, 1), P(2, 2)), True) is None
    assert normalise((), False) is None


def test_normalise_when_closed_starts_with_handles_then_rotated_to_on_curve():
    points = (P(5, 5), P(0, 0, "line"), P(1, 1), P(2, 2), P(3, 3, "curve"))
    out = normalise(points, True)
    assert out[0] == P(0, 0, "line"), "a closed contour starts on-curve"
    assert [p.type for p in out] == ["line", None, None, "curve"], "a handle leading into a line point drops"
    curved = normalise((P(5, 5), P(4, 4), P(0, 0, "curve"), P(1, 1, "line")), True)
    assert curved == (P(0, 0, "curve"), P(1, 1, "line"), P(5, 5), P(4, 4)), "handles leading into a curve wrap to the end"


def test_normalise_when_open_with_dangling_handles_then_trimmed_and_move_first():
    points = (P(9, 9), P(0, 0, "line", True), P(1, 1), P(1, 2), P(2, 2, "curve"), P(3, 3))
    assert normalise(points, False) == (P(0, 0, "move"), P(1, 1), P(1, 2), P(2, 2, "curve"))


def test_normalise_when_curve_loses_handles_or_line_has_some_then_fixed():
    out = normalise((P(0, 0, "line"), P(10, 0, "qcurve"), P(5, 5), P(20, 0, "line")), True)
    assert out == (P(0, 0, "line"), P(10, 0, "line"), P(20, 0, "line")), "handles before a line drop; a bare curve is a line"


def test_normalise_when_cubic_curve_keeps_one_handle_then_line():
    out = normalise((P(0, 0, "line"), P(5, 5), P(10, 0, "curve"), P(20, 0, "line")), True)
    assert out == (P(0, 0, "line"), P(10, 0, "line"), P(20, 0, "line")), "a lone cubic handle is dropped"


def test_normalise_when_cubic_curve_keeps_two_handles_or_qcurve_one_then_kept():
    cubic = (P(0, 0, "line"), P(3, 5), P(7, 5), P(10, 0, "curve"))
    assert normalise(cubic, True) == cubic
    quad = (P(0, 0, "line"), P(5, 5), P(10, 0, "qcurve"))
    assert normalise(quad, True) == quad, "one handle is a valid quadratic segment"


def test_delete_points_when_one_cubic_handle_removed_then_segment_becomes_line():
    contour = Contour((P(0, 0, "line"), P(3, 5), P(7, 5), P(10, 0, "curve")))
    data = GlyphData("a", "public.default", 500.0, (contour,), (), ())
    out = delete_points(data, {(0, 1)})
    assert out.contours[0].points == (P(0, 0, "line"), P(10, 0, "line"))


def test_delete_points_when_on_curve_then_its_handles_go_too():
    data = read_glyph(layered_font(), "a", "public.default")
    out = delete_points(data, {(0, 4)})
    assert [p.type for p in out.contours[0].points] == ["line", "line", "line"]
    assert out.contours[1:] == data.contours[1:]


def test_delete_points_when_contour_emptied_then_dropped():
    data = read_glyph(layered_font(), "a", "public.default")
    out = delete_points(data, {(1, 0), (1, 1)})
    assert len(out.contours) == 2 and out.contours[1] == data.contours[2]


def test_delete_points_when_open_start_removed_then_next_point_moves():
    data = read_glyph(layered_font(), "a", "public.default")
    out = delete_points(data, {(1, 0)})
    assert out.contours[1].points == (P(90, 300, "move"),)


def test_delete_points_when_closed_start_removed_then_contour_starts_on_curve():
    data = read_glyph(layered_font(), "a", "public.default")
    out = delete_points(data, {(2, 0)})  # quadratic contour: first qcurve goes with its handle
    points = out.contours[2].points
    assert points[0].on_curve and all(p.on_curve or i for i, p in enumerate(points))
    assert out.contours[2].closed


def test_points_in_rect_when_band_then_screen_hits_and_none_data():
    m = model(layered_font())
    x0, y0 = screen(m, 1, 0)
    x1, y1 = screen(m, 1, 1)
    assert points_in_rect(m.data, m.view, (x1 + 1, y1 + 1, x0 - 1, y0 - 1)) == {(1, 0), (1, 1)}, "corners in any order"
    assert points_in_rect(None, m.view, (0, 0, 9, 9)) == set()


def test_draw_contours_when_replayed_then_pen_receives_paths():
    log = []

    class Pen:
        def beginPath(self):
            log.append("begin")

        def addPoint(self, pt, segmentType=None, smooth=False):
            log.append((pt, segmentType, smooth))

        def endPath(self):
            log.append("end")

    draw_contours((Contour((P(1, 2, "move", True),)),), Pen())
    assert log == ["begin", ((1.0, 2.0), "move", True), "end"]


# --- write ----------------------------------------------------------------------
def test_write_contours_when_font_read_only_then_type_error():
    with pytest.raises(TypeError, match="Read-only"):
        write_contours(layered_font(), "a", "public.default", (), "TGlyph: Move a")


def test_write_contours_when_bold_then_default_untouched_and_anchors_kept():
    font = editable_font()
    default = own(font)
    write_contours(font, "a", "Bold", (Contour((P(1, 1, "move"), P(2, 2, "line"))),), "TGlyph: Move a")
    assert own(font, layer="Bold") == [[(1, 1, "move"), (2, 2, "line")]]
    assert own(font) == default, "Issue 235: only the explicit layer is written"
    assert font.edits == [("a", "Bold", "TGlyph: Move a")]
    assert [a.name for a in font["a"].anchors] == ["top"]


def test_write_contours_when_composite_then_components_kept():
    font = editable_font()
    write_contours(font, "b", "public.default", (Contour((P(0, 0, "move"), P(5, 0, "line"))),), "TGlyph: Add point b")
    data = read_glyph(font, "b", "public.default")
    assert [c.base for c in data.components] == ["a"] and len(data.contours) == 1


# --- editor: select tool --------------------------------------------------------
def test_editor_when_click_without_move_then_selects_and_no_write():
    m = model()
    editor = Editor(m)
    editor.press(*screen(m, 0, 1))
    assert m.selection == {(0, 1)} and editor.drag is not None
    assert editor.release(*screen(m, 0, 1)) is None and m.font.edits == []
    assert editor.release() is None, "a second release is harmless"


def test_editor_when_drag_then_preview_only_until_release_writes_once():
    m = model()
    editor = Editor(m)
    x, y = screen(m, 0, 4)
    before = m.data
    editor.press(x, y)
    editor.move(x + 20, y)
    assert m.data != before and m.font.edits == [], "the drag only previews"
    edit = editor.release(x + 20, y)
    assert m.data == before, "release reverts the preview until the commit"
    assert edit.action == "Move" and edit.selection == {(0, 4)}
    dx = edit.data.contours[0].points[4].x - before.contours[0].points[4].x
    assert dx == round(20 / m.view.scale) and edit.data.contours[0].points[3].x - before.contours[0].points[3].x == dx
    token = editor.commit(edit)
    assert m.font.edits == [("a", "public.default", "TGlyph: Move a")]
    assert token == m.fingerprint(), "the recorded fingerprint matches a fresh read"
    assert m.selection == {(0, 4)}


def test_editor_when_drag_without_coordinates_or_tiny_then_no_write():
    m = model()
    editor = Editor(m)
    x, y = screen(m, 0, 0)
    editor.press(x, y)
    editor.move(x + 0.01, y)
    assert editor.release(x + 0.01, y) is None, "a sub-unit drag rounds to zero"
    editor.press(x, y)
    assert editor.release() is None


def test_editor_when_selected_point_pressed_then_whole_selection_drags():
    m = model()
    editor = Editor(m)
    m.selection = {(0, 0), (1, 0)}
    x, y = screen(m, 1, 0)
    editor.press(x, y)
    assert m.selection == {(0, 0), (1, 0)}
    edit = editor.release(x, y - 10)
    assert edit.data.contours[0].points[0].y == m.data.contours[0].points[0].y + round(10 / m.view.scale)


def test_editor_when_shift_click_then_toggles_and_deselected_point_does_not_drag():
    m = model()
    editor = Editor(m)
    m.selection = {(0, 0)}
    editor.press(*screen(m, 1, 0), extend=True)
    assert m.selection == {(0, 0), (1, 0)} and editor.drag is not None
    editor.release()
    editor.press(*screen(m, 1, 0), extend=True)
    assert m.selection == {(0, 0)} and editor.drag is None


def test_editor_when_rubber_band_then_selects_and_shift_adds():
    m = model()
    editor = Editor(m)
    x0, y0 = screen(m, 1, 0)
    x1, y1 = screen(m, 1, 1)
    editor.press(x0 - 3, y0 - 8)
    assert editor.band is not None and editor.busy
    editor.move(x1 + 3, y1 + 8)
    assert m.selection == {(1, 0), (1, 1)}
    assert editor.release(x1 + 3, y1 + 8) is None and editor.band is None
    m.selection = {(0, 0)}
    editor.press(x0 - 3, y0 - 8, extend=True)
    editor.move(x1 + 3, y1 + 8)
    assert m.selection == {(0, 0), (1, 0), (1, 1)}
    editor.press(5, 395)
    assert m.selection == set(), "a plain miss clears"


def test_editor_when_no_data_then_every_gesture_is_refused():
    m = model(name="zz")
    editor = Editor(m)
    m.selection = {(0, 0)}
    editor.press(10, 10)
    assert not editor.busy
    assert editor.nudge(1, 0) is None and editor.delete() is None and editor.pen_click(10, 10) is None


def test_editor_when_cancelled_mid_drag_then_preview_reverts():
    m = model()
    editor = Editor(m)
    before = m.data
    x, y = screen(m, 0, 0)
    editor.press(x, y)
    editor.move(x + 40, y)
    assert editor.escape() is True and m.data == before
    assert editor.escape() is False


# --- editor: keys ---------------------------------------------------------------
def test_editor_when_nudged_then_edit_and_guards():
    m = model()
    editor = Editor(m)
    assert editor.nudge(1, 0) is None, "no selection"
    m.selection = {(1, 1)}
    assert editor.nudge(0, 0) is None
    edit = editor.nudge(-10, 1)
    assert edit.action == "Nudge" and edit.data.contours[1].points[1] == P(80, 301, "line")
    editor.press(*screen(m, 1, 1))
    assert editor.nudge(1, 0) is None and editor.delete() is None, "not during a drag"


def test_editor_when_delete_then_selection_clears_after_commit():
    m = model()
    editor = Editor(m)
    assert editor.delete() is None
    m.selection = {(1, 0), (1, 1)}
    edit = editor.delete()
    assert edit.action == "Delete" and len(edit.data.contours) == 2
    editor.commit(edit)
    assert m.selection == set() and len(read_glyph(m.font, "a", "public.default").contours) == 2
    assert m.font.edits[-1][2] == "TGlyph: Delete a"


# --- editor: pen tool -----------------------------------------------------------
def test_editor_when_pen_clicks_then_adds_closes_and_escape_ends():
    m = model(name="space")
    editor = Editor(m)
    editor.set_tool("pen")
    assert editor.pen_click(100, 300) is None, "the first click is pending only"
    assert editor.pending is not None and editor.pending.type == "move" and m.font.edits == []
    assert editor.pen_click(100, 300) is None, "a second click on the pending point adds nothing"
    second = editor.pen_click(200, 300)
    assert second.action == "Add point" and editor.pending is None
    editor.commit(second)
    assert [p.type for p in m.data.contours[0].points] == ["move", "line"]
    assert m.selection == {(0, 1)}
    third = editor.pen_click(150, 200)
    editor.commit(third)
    close = editor.pen_click(101, 301)
    assert close.action == "Close contour" and close.data.contours[0].closed
    token = editor.commit(close)
    assert editor.pen is None and token == m.fingerprint()
    assert own(m.font, "space")[0][0][2] == "line"
    assert editor.pen_click(50, 50) is None
    assert len(m.data.contours) == 1 and editor.escape() is True and editor.pending is None
    assert editor.escape() is False
    assert [e[2] for e in m.font.edits] == ["TGlyph: Add point space"] * 2 + ["TGlyph: Close contour space"]


def test_editor_when_pen_pending_and_tool_switched_then_discarded_without_write():
    m = model(name="space")
    editor = Editor(m)
    editor.set_tool("pen")
    assert editor.pen_click(100, 300) is None and editor.pending is not None
    editor.set_tool("select")
    assert editor.pending is None and m.font.edits == [] and m.data.contours == ()
    editor.set_tool("pen")
    assert editor.pen_click(10, 10) is None, "a fresh first click after the switch is pending again"


def test_editor_when_pen_pending_and_points_deleted_then_discarded():
    m = model()
    editor = Editor(m)
    editor.pen_click(100, 300)
    m.selection = {(0, 0)}
    editor.commit(editor.delete())
    assert editor.pending is None


def test_editor_when_pen_index_stale_then_new_contour():
    m = model(name="space")
    editor = Editor(m)
    editor.pen = 7
    assert editor.pen_click(10, 10) is None and editor.pen is None
    edit = editor.pen_click(60, 60)
    assert editor.pen == 0 and len(edit.data.contours) == 1 and len(edit.data.contours[0].points) == 2


def test_editor_when_unknown_tool_then_value_error():
    with pytest.raises(ValueError):
        Editor(model()).set_tool("knife")


# --- editor: commit failure -----------------------------------------------------
def test_editor_when_write_fails_then_reverts_and_raises():
    m = model()
    m.font.fail = RuntimeError("Undo history is not available")
    editor = Editor(m)
    editor.pen = 1
    before, selection = m.data, {(1, 1)}
    m.selection = set(selection)
    with pytest.raises(RuntimeError):
        editor.commit(editor.nudge(5, 0))
    assert m.data == before and m.selection == selection and editor.pen is None
    assert own(m.font) == own(layered_font()), "nothing reached the font"


def test_edit_when_built_then_frozen():
    edit = Edit("Move", GlyphData("a", "public.default", 0.0, (), (), ()), frozenset())
    with pytest.raises(AttributeError):
        edit.action = "x"


def test_read_only_editor_when_direct_routes_then_no_write_or_preview():
    m = model()
    editor = Editor(m, read_only=True)
    before = m.data
    m.selection = {(0, 5)}
    assert editor.nudge(10, 0) is None
    assert editor.delete() is None
    assert editor.toggle() is None
    assert editor.pen_click(10, 10) is None
    editor.set_tool("pen")
    assert editor.tool == "select"
    x, y = screen(m, 0, 5)
    editor.press(x, y)
    editor.move(x + 30, y)
    assert editor.release(x + 30, y) is None
    assert m.data == before
    with pytest.raises(ValueError, match="read-only"):
        editor.commit(Edit("Nudge", move_points(before, {(0, 5)}, 10, 0), frozenset({(0, 5)})))
    assert m.data == before and m.font.edits == []
    editor.press(-100, -100)
    editor.move(1000, 1000)
    editor.release()
    assert m.selection
