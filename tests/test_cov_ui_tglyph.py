# this_file: tests/test_cov_ui_tglyph.py
# SPDX-License-Identifier: Apache-2.0
"""TGlyph window built offscreen: controls, loading, follow, input, painting and close."""

import sys
from types import SimpleNamespace
from typing import Any

import pytest
from _tglyph_fakes import editable_font, layered_font

import _cov_qt as fq

OWN_MODULES = (
    "fontlabapp.fontui.tglyph",
    "fontlabapp.fontui.tglyph_model",
    "fontlabapp.fontui.tglyph_edit",
    "fontlabapp.fontui.tmetrics",
    "fontlabapp.fontui.tmetrics_model",
    "fontlabapp.fontui.livesync",
)
MODIFIERS = {
    "ShiftModifier": 0x02000000,
    "ControlModifier": 0x04000000,
    "AltModifier": 0x08000000,
    "MetaModifier": 0x10000000,
}
EXTRA_METHODS = {
    "cubicTo",
    "drawEllipse",
    "drawLine",
    "drawRect",
    "drawText",
    "quadTo",
    "raise_",
    "setCaseSensitivity",
    "setCompleter",
    "setWindowTitle",
}


class Painter(fq.FakeWidget):
    """Fake QPainter remembering every instance."""

    log: list = []

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        Painter.log.append(self)


@pytest.fixture
def tg_mod(monkeypatch):
    handle = fq.install(monkeypatch)
    for name in OWN_MODULES:
        monkeypatch.delitem(sys.modules, name, raising=False)
        fq._forget_on_parent(name, monkeypatch)
    handle.qt.QtGui.QPainter = Painter
    monkeypatch.setattr(fq, "SIGNALS", fq.SIGNALS | {"returnPressed"})
    monkeypatch.setattr(fq, "RECORDED_METHODS", fq.RECORDED_METHODS | EXTRA_METHODS)
    for name, flag in MODIFIERS.items():
        monkeypatch.setattr(fq.FakeWidget, name, flag, raising=False)
    Painter.log = []
    module = handle.load("fontlabapp.fontui.tglyph")
    # Painter doubles use the light scheme; the real Qt suite checks resolution.
    monkeypatch.setattr(module, "_canvas_colors", lambda canvas, colors: {
        **colors, "selection_background": colors["selected"], "selection_foreground": "#303030",
    })
    monkeypatch.setattr(fq, "RECORDED_METHODS", fq.RECORDED_METHODS | {
        "setContentsMargins", "setSpacing", "setFrameShape",
    })
    module.handle = handle
    yield module
    for name in OWN_MODULES:
        sys.modules.pop(name, None)
        fq._forget_on_parent(name)
    fq.release()


def make(module: Any, name: str | None = "a", layer: str | None = None, font: Any = None):
    window = module.TGlyph(layered_font() if font is None else font, name, layer)
    window.canvas.width, window.canvas.height = 400, 400
    window.fit()
    return window


def test_toggle_key_when_selected_then_write_and_follow_external_change(tg_mod):
    font = editable_font()
    window = make(tg_mod, font=font)
    window.model.selection = {(0, 5)}
    assert window.key_press("Key_O") is True
    assert window.model.data.contours[0].points[5].type is None
    assert len(font.edits) == 1
    font["a"].width = 777
    window.follow()
    assert window.model.data.width == 777
    window.model.selection = {(1, 0)}
    assert window.key_press("Key_O") is False
    assert "endpoint" in window.diagnostic.text
    assert len(font.edits) == 1
    window.close()


@pytest.mark.parametrize("modifier", ["ControlModifier", "MetaModifier", "AltModifier"])
def test_toggle_key_when_command_modifier_then_no_write(tg_mod, modifier):
    font = editable_font()
    window = make(tg_mod, font=font)
    window.model.selection = {(0, 5)}
    assert window.key_press("Key_O", MODIFIERS[modifier]) is False
    assert font.edits == []
    assert window.model.data.contours[0].points[5].on_curve
    window.close()


def test_toggle_key_when_repeated_then_no_write_but_shift_is_allowed(tg_mod):
    font = editable_font()
    window = make(tg_mod, font=font)
    window.model.selection = {(0, 5)}
    assert window.key_press("Key_O", auto_repeat=True) is False
    assert font.edits == []
    assert window.key_press("Key_O", MODIFIERS["ShiftModifier"]) is True
    assert len(font.edits) == 1
    window.close()


def test_injected_host_when_external_edit_then_refresh_and_ui_write_returns_to_font(tg_mod):
    callbacks = []
    font = editable_font()
    host = SimpleNamespace(subscribe=lambda owner, callback, fonts: callbacks.append((owner, callback, fonts)))
    window = tg_mod.TGlyph(font, "a", host=host)
    owner, callback, fonts = callbacks[0]
    assert owner is window and fonts() == [font]
    font["a"].width = 818
    callback()
    assert window.model.data.width == 818
    window.model.selection = {(0, 5)}
    window.key_press("Key_O")
    assert font["a"].contours[0].points[5].type == "offcurve"
    window.close()


def calls(widget: Any, name: str) -> list:
    return [args for call, args in widget.calls if call == name]


def event(**values: Any) -> SimpleNamespace:
    """A Qt event exposing PythonQt-style accessor methods for ``values``."""
    accessors = {key: (lambda value=value: value) for key, value in values.items()}
    accepted = []
    return SimpleNamespace(accept=lambda: accepted.append(True), accepted=accepted, **accessors)


def pos(x: float, y: float) -> SimpleNamespace:
    return SimpleNamespace(x=lambda: x, y=lambda: y)


def test_init_when_layered_font_then_layers_completion_and_readout(tg_mod):
    window = make(tg_mod)
    assert [item.text() for item in window.layer_control.items] == ["public.default", "Bold"], "the selector lists layers"
    assert window.completer.args[0] == ["a", "b", "hole", "space"], "completion offers the glyph order"
    assert window.name_control.text == "a"
    assert window.readout.text.startswith("a on public.default: width 500, 3 contours, 13 points")
    assert window.diagnostic.text == ""
    window.close()
    assert window.closed


def test_init_when_no_name_then_first_glyph(tg_mod):
    window = make(tg_mod, None)
    assert window.model.name == "a"
    empty = tg_mod.TGlyph(SimpleNamespace(keys=lambda: [], info=None), None)
    assert empty.model.status == "Type a glyph name." and empty.readout.text == ""


def test_init_when_unknown_layer_then_listed_and_reported(tg_mod):
    window = make(tg_mod, "a", "Ghost")
    assert [item.text() for item in window.layer_control.items] == ["public.default", "Bold", "Ghost"]
    assert window.diagnostic.text == "Layer Ghost is not in this font."


def test_choose_layer_when_bold_selected_then_same_glyph_on_bold(tg_mod):
    window = make(tg_mod)
    window.layer_control.setCurrentIndex(1)
    assert window.model.layer == "Bold" and window.model.data.width == 700.0
    window.choose_layer()  # unchanged layer: nothing to do
    assert window.model.layer == "Bold"


def test_choose_name_when_typed_then_loads_and_unknown_reports(tg_mod):
    window = make(tg_mod)
    window.name_control.text = " b "
    window.name_control.returnPressed.emit()
    assert window.model.name == "b" and window.readout.text.endswith("1 components, 0 anchors")
    window.name_control.text = "zz"
    window.choose_name()
    assert window.model.data is None and "zz is not on layer" in window.diagnostic.text


def test_step_when_prev_next_clicked_then_glyph_order_wraps(tg_mod):
    window = make(tg_mod)
    window.next_control.clicked.emit()
    assert window.model.name == "b"
    window.step(-1)
    window.prev_control.clicked.emit()
    assert window.model.name == "space"


def test_follow_when_points_move_then_view_and_selection_kept(tg_mod):
    window = make(tg_mod)
    view = window.model.view
    window.zoom(2.0, 100, 100)
    state = (view.scale, view.dx, view.dy)
    window.press(*view.to_screen(100.0, 0.0), "LeftButton")
    assert window.model.selection == {(0, 1)} and window.readout.text.endswith("1 selected")
    window.font["a"].moveBy((5, 5))
    window.follow()
    assert window.model.selection == {(0, 1)}, "same structure keeps the selection"
    assert (view.scale, view.dx, view.dy) == state, "zoom and pan survive the refresh"
    window.font["a"].contours[1].appendPoint((95, 310), "line")
    window.follow()
    assert window.model.selection == set(), "a new point resets the selection"


@pytest.mark.parametrize("selection", [{(0, 0)}, {(2, 4)}, {(0, 0), (0, 4), (2, 4)}], ids=["first", "last", "multiple"])
def test_follow_when_only_smooth_changes_then_redraw_and_selection_survive(tg_mod, selection, monkeypatch):
    font = editable_font()
    window = make(tg_mod, font=font)
    window.zoom(1.7, 120, 80)
    window.model.view.pan(23, -41)
    for c, p in sorted(selection):
        window.press(*at(window, c, p), "LeftButton", MODIFIERS["ShiftModifier"])
        window.release()
    assert window.model.selection == selection and not window.editor.busy
    view, readout = vars(window.model.view).copy(), window.readout.text
    updates, readouts = len(calls(window.canvas, "update")), []
    set_text = window.readout.setText

    def record_readout(text):
        readouts.append(text)
        set_text(text)

    monkeypatch.setattr(window.readout, "setText", record_readout)
    visual = window.model.fingerprint()
    point = font["a"].contours[0].points[1]
    point.smooth = not point.smooth
    assert window.model.fingerprint() != visual and window.echo.token is None
    window.follow()
    assert window.model.data.contours[0].points[1].smooth == point.smooth
    assert len(calls(window.canvas, "update")) == updates + 1
    assert len(readouts) == 1
    assert window.model.selection == selection, "smooth-only follow keeps exact indices"
    assert window.readout.text == readout and window.readout.text.endswith(f"{len(selection)} selected")
    assert vars(window.model.view) == view and font.edits == []


def test_follow_when_echo_matches_then_no_refresh(tg_mod):
    window = make(tg_mod)
    window.press(*window.model.view.to_screen(100.0, 0.0), "LeftButton")
    window.font["a"].contours[1].appendPoint((95, 310), "line")
    window.echo.record(window.model.fingerprint())
    window.follow()
    assert window.model.selection == {(0, 1)}, "our own write is not re-read"


def test_refresh_when_view_not_adjusted_then_refits(tg_mod):
    window = make(tg_mod)
    window.canvas.width = 800
    window.refresh()
    assert window.model.view.dx > 200, "an unadjusted view refits to the new size"


def test_set_follow_when_on_then_timer_and_current_glyph(tg_mod, monkeypatch):
    window = make(tg_mod)
    monkeypatch.setattr(tg_mod, "current_glyph_name", lambda font: "b")
    window.follow_control.checked = True
    window.follow_control.toggled.emit(True)
    assert window.follow_timer.started == 1 and window.model.name == "b"
    monkeypatch.setattr(tg_mod, "current_glyph_name", lambda font: None)
    window.follow_timer.timeout.emit()
    assert window.model.name == "b", "a glyph outside this font is ignored"
    window.follow_control.checked = False
    window.set_follow(False)
    assert ("stop", ()) in window.follow_timer.calls
    monkeypatch.setattr(tg_mod, "current_glyph_name", lambda font: "a")
    window.follow_current()
    assert window.model.name == "b", "an unticked box does not follow"


def test_current_glyph_name_when_native_present_or_missing(tg_mod, monkeypatch):
    font = layered_font()
    assert tg_mod.current_glyph_name(font) is None, "no FontLab: None"
    native = SimpleNamespace(CurrentGlyph=lambda: SimpleNamespace(name="b"))
    monkeypatch.setitem(sys.modules, "fontlab", native)
    assert tg_mod.current_glyph_name(font) == "b"
    native.CurrentGlyph = lambda: SimpleNamespace(name="Q")
    assert tg_mod.current_glyph_name(font) is None, "other font's glyph is ignored"
    native.CurrentGlyph = lambda: None
    assert tg_mod.current_glyph_name(font) is None


def test_zoom_keys_and_wheel_when_used_then_scale_changes(tg_mod):
    window = make(tg_mod)
    view = window.model.view
    start = view.scale
    assert window.key_press("Key_Plus") and view.scale == pytest.approx(start * 1.25)
    assert window.key_press("Key_Minus") and view.scale == pytest.approx(start)
    assert window.key_press("Key_0") and not view.adjusted
    assert window.key_press("Key_A") is False
    window.wheel(240.0, 10, 10)
    assert view.scale == pytest.approx(start * 1.25**2)
    window.wheel(0.0, 10, 10)
    assert view.scale == pytest.approx(start * 1.25**2)
    window.fit_control.clicked.emit()
    assert view.scale == pytest.approx(start)


def test_pan_when_space_or_middle_drag_then_offsets_move(tg_mod):
    window = make(tg_mod)
    view = window.model.view
    assert window.key_press("Key_Space") and window.space
    window.press(10, 10, "LeftButton")
    window.move(30, 50)
    assert window.panning == (30, 50) and view.adjusted
    window.release()
    assert window.key_release("Key_Space", True) is False, "auto-repeat release keeps space armed"
    assert window.key_release("Key_Space") and not window.space
    dx = view.dx
    window.press(0, 0, "MiddleButton")
    window.move(5, 0)
    assert view.dx == dx + 5
    window.release()
    window.move(50, 0)
    assert view.dx == dx + 5, "moves without a drag do nothing"
    assert window.key_release("Key_A") is False


def test_press_when_shift_then_extends_selection(tg_mod):
    window = make(tg_mod)
    view = window.model.view
    window.press(*view.to_screen(0.0, 0.0), "LeftButton")
    window.press(*view.to_screen(100.0, 0.0), "LeftButton", MODIFIERS["ShiftModifier"])
    assert window.model.selection == {(0, 0), (0, 1)}
    window.press(0, 0, "RightButton")
    assert window.model.selection == {(0, 0), (0, 1)}, "other buttons do nothing"
    assert tg_mod._has(object(), "ShiftModifier") is False


def test_callbacks_when_they_fail_then_diagnostic_not_raise(tg_mod, monkeypatch):
    window = make(tg_mod)

    def boom(*args):
        raise RuntimeError("boom")

    for target, method, args in (
        (window.model, "load", ()),
        (window.model, "refresh", ()),
        (window.model, "fingerprint", ()),
        (window.model, "fit", ()),
        (window.model, "select_at", ()),
        (window.model.view, "zoom", ()),
        (window.model.view, "pan", ()),
    ):
        monkeypatch.setattr(target, method, boom)
    window.load("b")
    window.refresh()
    window.follow()
    window.fit()
    window.press(0, 0, "LeftButton")
    window.zoom(2.0)
    window.panning = (0, 0)
    window.move(1, 1)
    window.key_press("Key_Plus")
    window.name_control.text = "b"
    window.choose_name()
    window.step(1)
    window.layer_control.currentIndex = 1
    window.choose_layer()
    monkeypatch.setattr(tg_mod, "current_glyph_name", boom)
    window.follow_control.checked = True
    window.follow_current()
    monkeypatch.setattr(window.follow_timer, "start", boom)
    window.set_follow(True)
    assert window.diagnostic.text == "Error: boom"


def test_key_press_when_lookup_fails_then_false(tg_mod, monkeypatch):
    window = make(tg_mod)

    class Bad:
        def __eq__(self, other):
            raise RuntimeError("bad key")

    assert window.key_press(Bad()) is False and window.diagnostic.text == "Error: bad key"


def test_closed_window_when_called_then_everything_is_inert(tg_mod):
    window = make(tg_mod)
    window.close()
    window.close()
    for call in (
        lambda: window.load("b"),
        window.refresh,
        window.follow,
        window.choose_layer,
        window.choose_name,
        lambda: window.step(1),
        window.fit,
        lambda: window.set_follow(True),
        window.follow_current,
        lambda: window.zoom(2.0),
        lambda: window.press(0, 0, "LeftButton"),
        lambda: window.move(1, 1),
    ):
        call()
    window.fail(RuntimeError("late"))
    assert window.key_press("Key_Plus") is False and window.key_release("Key_Space") is False
    assert window.model.name == "a"


def _painted(window: Any) -> Any:
    Painter.log = []
    window.canvas.paintEvent(None)
    (painter,) = Painter.log
    return painter


def test_paint_when_glyph_then_metrics_outline_points_anchors(tg_mod):
    window = make(tg_mod, "b")
    window.load("a")
    window.press(*window.model.view.to_screen(0.0, 0.0), "LeftButton")
    painter = _painted(window)
    labels = [args[1] for args in calls(painter, "drawText")]
    assert {"baseline", "ascender", "x-height", "cap height", "descender", "top"} <= set(labels)
    paths = [args[0] for args in calls(painter, "drawPath")]
    assert len(paths) == 2, "closed contours filled, open contour stroked"
    filled = [name for name, _ in paths[0].calls]
    assert "cubicTo" in filled and "quadTo" in filled and "closeSubpath" in filled
    assert calls(painter, "drawEllipse") and calls(painter, "drawRect"), "smooth/off-curve circles, corner squares"
    assert ("end", ()) in painter.calls


def test_paint_when_composite_then_component_path(tg_mod):
    window = make(tg_mod, "b")
    painter = _painted(window)
    assert len(calls(painter, "drawPath")) == 2, "the component's closed and open contours are drawn"
    assert window.readout.text.endswith("1 components, 0 anchors")


def test_paint_when_no_glyph_then_status_text(tg_mod):
    window = make(tg_mod, "zz")
    painter = _painted(window)
    assert any("zz is not on layer" in str(args) for args in calls(painter, "drawText"))
    assert ("end", ()) in painter.calls


def test_paint_when_drawing_fails_then_diagnostic_and_painter_ended(tg_mod, monkeypatch):
    window = make(tg_mod)
    monkeypatch.setattr(tg_mod, "_paint_points", lambda *a: (_ for _ in ()).throw(RuntimeError("paint")))
    painter = _painted(window)
    assert window.diagnostic.text == "Error: paint" and ("end", ()) in painter.calls
    Painter.log = []
    monkeypatch.setattr(tg_mod.QtGui, "QPainter", lambda *a: (_ for _ in ()).throw(RuntimeError("no painter")))
    tg_mod.paint(window, window.canvas)
    assert window.diagnostic.text == "Error: no painter"


def test_contour_path_when_unusual_runs_then_drawn(tg_mod):
    m = sys.modules["fontlabapp.fontui.tglyph_model"]
    view = m.View(scale=1.0)
    path = tg_mod.QtGui.QPainterPath()
    tg_mod._contour_path(path, view, m.Contour(()))
    tg_mod._contour_path(path, view, m.Contour((m.Point(0, 0, None), m.Point(5, 5, None))))
    assert path.calls == [], "empty and all off-curve closed contours draw nothing"
    odd = m.Contour((m.Point(0, 0, "line"), m.Point(1, 1, None), m.Point(2, 2, "curve")))
    tg_mod._contour_path(path, view, odd)
    assert [name for name, _ in path.calls] == ["moveTo", "lineTo", "lineTo", "closeSubpath"], (
        "a one-handle cubic run falls back to its straight span"
    )


def test_canvas_events_when_dispatched_then_forwarded(tg_mod):
    window = make(tg_mod)
    canvas = window.canvas
    view = window.model.view
    press = event(pos=pos(*view.to_screen(100.0, 0.0)), button="LeftButton", modifiers=0)
    canvas.mousePressEvent(press)
    assert window.model.selection == {(0, 1)} and press.accepted
    canvas.keyPressEvent(event(key="Key_Space", modifiers=0, isAutoRepeat=False))
    canvas.mousePressEvent(event(pos=pos(0, 0), button="LeftButton", modifiers=0))
    canvas.mouseMoveEvent(event(pos=pos(4, 0)))
    canvas.mouseReleaseEvent(event(pos=pos(4, 0)))
    assert window.panning is None
    release = event(key="Key_Space", isAutoRepeat=False)
    canvas.keyReleaseEvent(release)
    assert release.accepted and not window.space
    scale = view.scale
    canvas.wheelEvent(event(pos=pos(0, 0), angleDelta=SimpleNamespace(y=lambda: 120)))
    assert view.scale == pytest.approx(scale * 1.25)
    view.adjusted = False
    canvas.width = 900
    canvas.resizeEvent(None)
    assert view.dx > 300
    broken = SimpleNamespace(accept=lambda: None)
    for handler in (canvas.mousePressEvent, canvas.mouseMoveEvent, canvas.wheelEvent):
        handler(broken)
    canvas.keyReleaseEvent(SimpleNamespace(key=lambda: (_ for _ in ()).throw(RuntimeError("key"))))
    assert window.diagnostic.text == "Error: key"
    canvas.keyReleaseEvent(event(key="Key_A", isAutoRepeat=False))
    assert window.diagnostic.text.startswith("Error:"), "a missing base handler is reported, not raised"


def test_canvas_resize_when_fit_fails_then_diagnostic(tg_mod, monkeypatch):
    window = make(tg_mod)
    monkeypatch.setattr(window, "fit", lambda: (_ for _ in ()).throw(RuntimeError("resize")))
    window.canvas.resizeEvent(None)
    assert window.diagnostic.text == "Error: resize"


def test_show_tglyph_when_font_given_then_window_shown(tg_mod, monkeypatch):
    monkeypatch.setattr(tg_mod, "current_glyph_name", lambda font: "b")
    window = tg_mod.show_tglyph(layered_font())
    assert window.model.name == "b"
    assert ("setWindowTitle", ("TGlyph",)) in window.widget.calls and window.widget.shown
    named = tg_mod.show_tglyph(layered_font(), "space", "public.default")
    assert named.model.name == "space"
    monkeypatch.setattr(tg_mod, "current_glyph_name", lambda font: (_ for _ in ()).throw(RuntimeError("x")))
    assert tg_mod.show_tglyph(layered_font()).model.name == "a"


def test_show_tglyph_when_no_font_then_message_and_none(tg_mod, monkeypatch):
    notes = []
    monkeypatch.setattr(tg_mod, "_notify", notes.append)
    monkeypatch.setattr(tg_mod, "_current_font", lambda: None)
    assert tg_mod.show_tglyph() is None
    monkeypatch.setattr(tg_mod, "_current_font", lambda: (_ for _ in ()).throw(RuntimeError("no fontport")))
    assert tg_mod.show_tglyph() is None
    assert notes == [tg_mod.NO_FONT_MESSAGE, f"{tg_mod.NO_FONT_MESSAGE} (no fontport)"]


def test_show_tglyph_when_show_fails_then_closed_and_raised(tg_mod, monkeypatch):
    monkeypatch.setattr(fq.FakeWidget, "show", lambda self: (_ for _ in ()).throw(RuntimeError("show")), raising=False)
    with pytest.raises(RuntimeError, match="show"):
        tg_mod.show_tglyph(layered_font(), "a")


def test_notify_when_offline_then_prints(tg_mod, capsys):
    tg_mod._notify("hello")
    assert "TGlyph: hello" in capsys.readouterr().out


def test_current_font_when_called_then_delegates_to_tmetrics(tg_mod, monkeypatch):
    tmetrics = tg_mod.handle.load("fontlabapp.fontui.tmetrics")
    monkeypatch.setattr(tmetrics, "_current_font", lambda: "font")
    assert tg_mod._current_font() == "font"


def test_tmetrics_double_click_when_default_then_opens_and_reuses_tglyph(tg_mod, monkeypatch):
    from test_cov_ui_tmetrics import _bar

    monkeypatch.setattr(fq.FakeWidget, "horizontalScrollBar", _bar("_hbar"), raising=False)
    monkeypatch.setattr(fq.FakeWidget, "verticalScrollBar", _bar("_vbar"), raising=False)
    tmetrics = tg_mod.handle.load("fontlabapp.fontui.tmetrics")
    font = layered_font()
    metrics = tmetrics.show_tmetrics(font, "ab")
    metrics.on_open_glyph("b")
    viewer = metrics.tglyph
    assert viewer.font is font and viewer.model.name == "b", "TGlyph opens on the double-clicked glyph"
    metrics.on_open_glyph("a")
    assert metrics.tglyph is viewer and viewer.model.name == "a", "the open TGlyph is reused"
    assert ("raise_", ()) in viewer.widget.calls
    viewer.close()
    metrics.on_open_glyph("space")
    assert metrics.tglyph is not viewer and metrics.tglyph.model.name == "space", "a closed TGlyph is replaced"
    custom = []
    assert tmetrics.show_tmetrics(font, "a", on_open_glyph=custom.append).on_open_glyph == custom.append


# --- Task 5 editing -------------------------------------------------------------
def at(window, c, p):
    point = window.model.data.contours[c].points[p]
    return window.model.view.to_screen(point.x, point.y)


def test_drag_when_released_then_one_write_echo_and_selection_kept(tg_mod):
    window = make(tg_mod, font=editable_font())
    zoom = window.model.view
    x, y = at(window, 0, 4)
    window.press(x, y, "LeftButton", 0)
    window.move(x + 30, y)
    assert window.model.font.edits == [], "no write during the drag"
    window.follow()
    assert window.editor.busy, "an unchanged font does not cancel the drag"
    window.release(x + 30, y)
    assert window.model.font.edits == [("a", "public.default", "TGlyph: Move a")]
    assert window.diagnostic.text.startswith("Move: a on public.default.")
    assert window.echo.token == window.model.fingerprint(), "the own write is the recorded echo"
    window.follow()
    assert window.model.selection == {(0, 4)} and window.model.view == zoom, "the echo keeps selection and view"
    assert "1 selected" in window.readout.text


def test_drag_when_font_changes_mid_gesture_then_cancelled(tg_mod):
    window = make(tg_mod, font=editable_font())
    x, y = at(window, 0, 0)
    window.press(x, y, "LeftButton", 0)
    window.move(x + 30, y)
    window.model.font["a"].width = 999
    window.follow()
    assert not window.editor.busy and window.model.data.width == 999
    window.release(x + 30, y)
    assert window.model.font.edits == [], "a cancelled drag never writes"


@pytest.mark.parametrize("state", ["drag", "band", "pending", "pen"])
def test_follow_when_structure_changes_then_editor_resets_and_release_cannot_write(tg_mod, state):
    font = editable_font()
    window = make(tg_mod, font=font)
    window.zoom(1.7, 120, 80)
    view = vars(window.model.view).copy()
    if state == "drag":
        x, y = at(window, 0, 0)
        window.press(x, y, "LeftButton", 0)
        window.move(x + 30, y)
        assert window.editor.busy and window.editor.before is not None
    elif state == "band":
        window.press(-500, -500, "LeftButton", 0)
        window.move(-450, -450)
        assert window.editor.busy and window.editor.band is not None
    else:
        window.set_tool("pen")
        window.press(100, 300, "LeftButton", 0)
        assert window.editor.pending is not None
        if state == "pen":
            window.press(200, 300, "LeftButton", 0)
            assert window.editor.pen is not None
    writes = list(font.edits)
    font["a"].contours[1].appendPoint((95, 310), "line")
    window.follow()
    assert not window.editor.busy and window.editor.before is None
    assert window.editor.pending is None and window.editor.pen is None
    assert window.editor.base == set() and window.model.selection == set()
    assert len(window.model.data.contours[1].points) == 3
    assert vars(window.model.view) == view
    window.release(230, 300)
    assert font.edits == writes, "later release cannot commit a stale gesture"


def test_release_when_write_fails_then_diagnostic_and_preview_reverted(tg_mod):
    font = editable_font()
    font.fail = RuntimeError("History scope refused")
    window = make(tg_mod, font=font)
    before = window.model.data
    x, y = at(window, 0, 0)
    window.press(x, y, "LeftButton", 0)
    window.move(x, y - 30)
    window.release(x, y - 30)
    assert window.diagnostic.text == "Error: History scope refused"
    assert window.model.data == before and window.echo.token is None


def test_release_when_editor_raises_then_cancelled_and_diagnostic(tg_mod, monkeypatch):
    window = make(tg_mod, font=editable_font())
    window.press(*at(window, 0, 0), "LeftButton", 0)
    monkeypatch.setattr(window.editor, "release", lambda *a: (_ for _ in ()).throw(ValueError("bad")))
    window.release(1, 1)
    assert window.diagnostic.text == "Error: bad" and not window.editor.busy


def test_keys_when_nudge_delete_tools_and_escape_then_written(tg_mod):
    window = make(tg_mod, font=editable_font())
    window.press(*at(window, 1, 1), "LeftButton", 0)
    window.release()
    shift = MODIFIERS["ShiftModifier"]
    assert window.key_press("Key_Right", shift) is True
    assert window.key_press("Key_Up", 0) is True
    point = window.model.data.contours[1].points[1]
    assert (point.x, point.y) == (100.0, 301.0)
    assert [e[2] for e in window.model.font.edits] == ["TGlyph: Nudge a"] * 2
    assert window.key_press("Key_Delete", 0) is True
    assert window.model.font.edits[-1][2] == "TGlyph: Delete a" and window.model.selection == set()
    assert window.key_press("Key_Backspace", 0) is True, "an empty selection is accepted without a write"
    assert len(window.model.font.edits) == 3
    assert window.key_press("Key_P", 0) is True and window.editor.tool == "pen"
    assert window.readout.text.endswith("pen tool")
    assert window.key_press("Key_V", 0) is True and window.editor.tool == "select"
    assert window.key_press("Key_Escape", 0) is False, "Escape with nothing to end is not consumed"
    assert window.key_press("Key_X", 0) is False


def test_pen_when_clicked_then_contour_built_and_closed(tg_mod):
    window = make(tg_mod, name="space", font=editable_font())
    window.set_tool("pen")
    window.press(100, 300, "LeftButton", 0)
    window.release(100, 300)
    assert window.editor.pending is not None and window.model.font.edits == [], "first click is preview only"
    assert window.model.data.contours == ()
    ellipses = len(calls(_painted(window), "drawEllipse"))
    assert ellipses == 1, "the pending point is painted"
    for x, y in ((200, 300), (150, 200), (101, 301)):
        window.press(x, y, "LeftButton", 0)
        window.release(x, y)
    contour = window.model.data.contours[0]
    assert contour.closed and len(contour.points) == 3
    assert window.diagnostic.text.startswith("Close contour: space on public.default.")
    window.press(50, 50, "LeftButton", 0)
    assert window.editor.pending is not None
    assert window.key_press("Key_Escape", 0) is True and window.editor.pending is None
    assert len(window.model.font.edits) == 3, "two-point contour, one added point, close"


def test_pen_when_pending_and_tool_switched_then_discarded(tg_mod):
    window = make(tg_mod, name="space", font=editable_font())
    window.set_tool("pen")
    window.press(100, 300, "LeftButton", 0)
    window.set_tool("select")
    assert window.editor.pending is None and window.model.font.edits == []


def test_pen_when_read_only_font_then_diagnostic(tg_mod):
    window = make(tg_mod, name="space")
    window.set_tool("pen")
    window.press(100, 100, "LeftButton", 0)
    window.press(200, 100, "LeftButton", 0)
    assert window.diagnostic.text == "Error: Read-only: font has no edit_glyph"
    assert window.model.data.contours == ()


def test_band_when_dragged_then_painted_and_selects(tg_mod):
    window = make(tg_mod, font=editable_font())
    x0, y0 = at(window, 1, 0)
    x1, y1 = at(window, 1, 1)
    window.press(x0 - 3, y0 - 8, "LeftButton", 0)
    window.move(x1 + 3, y1 + 8)
    tg_mod.paint(window, window.canvas)
    assert calls(Painter.log[-1], "drawRect"), "the rubber band is drawn"
    window.release(x1 + 3, y1 + 8)
    assert window.model.selection == {(1, 0), (1, 1)} and window.model.font.edits == []


def test_press_when_right_button_then_ignored(tg_mod):
    window = make(tg_mod, font=editable_font())
    window.press(*at(window, 0, 0), "RightButton", 0)
    assert window.model.selection == set() and not window.editor.busy


def test_embed_when_controls_hidden_then_no_outer_margins_or_spacing(tg_mod):
    window = tg_mod.TGlyph(layered_font(), "a", controls=False)
    assert calls(window.layout, "setContentsMargins") == [(0, 0, 0, 0)]
    assert calls(window.layout, "setSpacing") == [(0,)]
    assert window.diagnostic.shown and window.readout.shown
    window.close()
