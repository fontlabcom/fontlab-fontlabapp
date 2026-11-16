# this_file: tests/test_cov_views.py
"""Coverage for ``fontlabapp.qt.views``: Panel, Preview and GlyphWindow over fake native objects."""

from __future__ import annotations

import importlib
import math
from types import SimpleNamespace
from typing import Any

import pytest

from fontlabapp.qt.views import GlyphWindow, Panel, Preview

views = importlib.import_module("fontlabapp.qt.views")


class Recorder:
    """Records every call as ``(name, args)`` and returns canned values."""

    def __init__(self, **returns: Any) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self._returns = returns

    def __getattr__(self, name: str) -> Any:
        def call(*args: Any) -> Any:
            self.calls.append((name, args))
            return self._returns.get(name)

        return call


class FakeDrawing:
    """Replaces ``fontlabapp.qt.painting.drawing.Drawing``; remembers its constructor arguments."""

    def __init__(self, parent: Any, callback: Any, *, canvas: Any = None) -> None:
        self.parent, self.callback, self.canvas = parent, callback, canvas


class Owner:
    """Takes ownership of drawings, as a controller would."""

    def __init__(self) -> None:
        self.owned: list[Any] = []

    def _own(self, drawing: Any) -> str:
        self.owned.append(drawing)
        return "owned"


@pytest.fixture
def fake_native(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Fake ``PythonQt`` whose QColor/QPointF are tagged tuples; patches ``Drawing``."""
    qt = SimpleNamespace(
        QtGui=SimpleNamespace(QWidget="QWidget", QColor=lambda c: ("color", c)),
        QtCore=SimpleNamespace(QPointF=lambda x, y: ("point", x, y)),
    )
    monkeypatch.setattr(views, "_native", lambda name: qt)
    monkeypatch.setattr("fontlabapp.qt.painting.drawing.Drawing", FakeDrawing)
    return qt


# ---------------------------------------------------------------- Panel


def test_panel_visible_when_widget_visible_then_reflects_widget() -> None:
    """``visible`` reads straight from the wrapped widget."""
    assert Panel(SimpleNamespace(isVisible=lambda: True)).visible is True, "visible widget reads True"
    assert Panel(SimpleNamespace(isVisible=lambda: False)).visible is False, "hidden widget reads False"


@pytest.mark.parametrize("bad", [1, 0, "yes", None])
def test_panel_set_visible_when_not_bool_then_type_error(bad: Any) -> None:
    """Only real booleans are accepted, and nothing is touched on refusal."""
    widget = Recorder()
    with pytest.raises(TypeError, match="must be bool"):
        Panel(widget).set_visible(bad)
    assert widget.calls == [], "a refused call must not reach the widget"


def test_panel_set_visible_when_main_and_id_then_uses_native_show_panel() -> None:
    """With a main window and PanelId, visibility goes through ``showPanel``."""
    widget, main = Recorder(), Recorder()
    panel = Panel(widget, main, 21)
    assert panel.set_visible(True) is panel, "set_visible returns the panel for chaining"
    assert main.calls == [("showPanel", (21, True))], "visibility goes through showPanel with the id"
    assert widget.calls == [], "the widget itself must not be toggled"


@pytest.mark.parametrize("main,panel_id", [(None, 21), (Recorder(), None), (None, None)])
def test_panel_set_visible_when_no_native_route_then_toggles_widget(main: Any, panel_id: Any) -> None:
    """Without both a main window and an id, the widget is shown or hidden directly."""
    widget = Recorder()
    Panel(widget, main, panel_id).set_visible(False)
    assert widget.calls == [("setVisible", (False,))], "the widget is hidden directly"
    assert main is None or main.calls == [], "main must stay untouched without a PanelId"


def test_panel_show_and_hide_when_called_then_set_visibility_and_chain() -> None:
    """``show`` and ``hide`` are set_visible(True/False)."""
    widget = Recorder()
    panel = Panel(widget)
    assert panel.show() is panel, "show chains"
    assert panel.hide() is panel, "hide chains"
    assert widget.calls == [("setVisible", (True,)), ("setVisible", (False,))], "show then hide"


def test_panel_focus_when_called_then_shows_raises_and_focuses() -> None:
    """``focus`` shows the panel, raises it and gives it keyboard focus, in that order."""
    widget = Recorder()
    panel = Panel(widget)
    assert panel.focus() is panel, "focus chains"
    assert [name for name, _ in widget.calls] == [
        "setVisible",
        "raise_",
        "setFocus",
    ], "focus shows, raises, then focuses"


def test_panel_ids_when_listed_then_are_unique_ints() -> None:
    """Native PanelId values are distinct integers."""
    values = list(views._PANEL_IDS.values())
    assert all(isinstance(v, int) for v in values), "every PanelId is an int"
    assert len(set(values)) == len(values), "no two panels share an id"


# -------------------------------------------------------------- Preview


def _preview_widget(class_name: str = "FontPreviewWidget", object_name: str = "widgetPreview") -> Any:
    widget = Recorder()
    widget.className = lambda: class_name
    widget.objectName = object_name
    return widget


def _panel_widget(children: list[Any]) -> Any:
    return SimpleNamespace(findChildren=lambda kind: children)


def test_preview_init_when_one_matching_child_then_binds_it(fake_native: Any) -> None:
    """The unique FontPreviewWidget named widgetPreview is bound; others are ignored."""
    target = _preview_widget()
    decoys = [_preview_widget("QLabel"), _preview_widget("FontPreviewWidget", "other")]
    owner = Owner()
    preview = Preview(_panel_widget([decoys[0], target, decoys[1]]), owner)
    assert preview.widget is target, "the unique matching child is bound"
    assert isinstance(preview.panel, Panel), "the raw widget is wrapped in a Panel"
    assert preview._owner is owner, "the owner is kept"


def test_preview_init_when_given_panel_object_then_reuses_it(fake_native: Any) -> None:
    """An existing Panel descriptor is used as is, not wrapped again."""
    target = _preview_widget()
    panel = Panel(_panel_widget([target]))
    assert Preview(panel).panel is panel, "an existing Panel is reused"


@pytest.mark.parametrize("count", [0, 2])
def test_preview_init_when_not_exactly_one_match_then_lookup_error(fake_native: Any, count: int) -> None:
    """Zero or several candidate widgets are refused."""
    children = [_preview_widget() for _ in range(count)]
    with pytest.raises(LookupError, match="unique FontPreviewWidget"):
        Preview(_panel_widget(children))


@pytest.fixture
def preview(fake_native: Any) -> Preview:
    """A preview bound to a recording widget and an owner."""
    return Preview(_panel_widget([_preview_widget()]), Owner())


def test_preview_set_text_when_called_then_forwards_text_and_process_flag(preview: Preview) -> None:
    """``process`` defaults to True and can be switched off."""
    assert preview.set_text("abc") is preview, "set_text chains"
    preview.set_text("xyz", process=False)
    assert preview.widget.calls == [
        ("setText", ("abc", True)),
        ("setText", ("xyz", False)),
    ], "process defaults to True and can be disabled"


def test_preview_set_font_size_when_valid_then_forwards_float(preview: Preview) -> None:
    """Valid sizes are converted to float."""
    assert preview.set_font_size(24) is preview, "set_font_size chains"
    assert preview.widget.calls == [("setFontSize", (24.0,))], "the size reaches the widget as a float"


@pytest.mark.parametrize("bad", [0, -1, math.inf, -math.inf, math.nan])
def test_preview_set_font_size_when_not_positive_finite_then_value_error(preview: Preview, bad: float) -> None:
    """Zero, negative, infinite and NaN sizes are refused before reaching the widget."""
    with pytest.raises(ValueError, match="positive and finite"):
        preview.set_font_size(bad)
    assert preview.widget.calls == [], "a refused size must not reach the widget"


def test_preview_set_color_when_called_then_wraps_in_qcolor(preview: Preview) -> None:
    """The colour name is converted by the native QColor."""
    assert preview.set_color("#ff0000") is preview, "set_color chains"
    assert preview.widget.calls == [
        ("setTextColor", (("color", "#ff0000"),))
    ], "the colour is wrapped in a native QColor"


def test_preview_set_auto_size_when_called_then_forwards_flag(preview: Preview) -> None:
    """The auto-size flag is passed through."""
    assert preview.set_auto_size(True) is preview, "set_auto_size chains"
    assert preview.widget.calls == [("setAutoSize", (True,))], "the flag is forwarded"


def test_preview_set_waterfall_when_valid_then_forwards_sizes(preview: Preview) -> None:
    """A valid size list reaches the widget unchanged."""
    assert preview.set_waterfall([12, 18.5]) is preview, "set_waterfall chains"
    assert preview.widget.calls == [("setTextWaterfall", ([12, 18.5],))], "sizes are forwarded unchanged"


@pytest.mark.parametrize("bad", [[12, 0], [-3], [math.nan], [10, math.inf]])
def test_preview_set_waterfall_when_any_size_invalid_then_value_error(preview: Preview, bad: list[float]) -> None:
    """One bad size refuses the whole waterfall."""
    with pytest.raises(ValueError, match="Waterfall sizes"):
        preview.set_waterfall(bad)
    assert preview.widget.calls == [], "a refused waterfall must not reach the widget"


def test_preview_draw_when_pixels_with_owner_then_drawing_is_owned(preview: Preview) -> None:
    """The overlay is built on the preview widget and handed to the owner."""
    callback = lambda painter: None
    result = preview.draw(callback)
    assert result == "owned", "the owner's return value is passed back"
    drawing = preview._owner.owned[0]
    assert drawing.parent is preview.widget, "the drawing is attached to the preview widget"
    assert drawing.callback is callback, "the callback is handed to the drawing"


def test_preview_draw_when_no_owner_then_returns_the_drawing(fake_native: Any) -> None:
    """Without an owner the bare Drawing is returned."""
    preview = Preview(_panel_widget([_preview_widget()]))
    drawing = preview.draw(lambda painter: None, coordinates="pixels")
    assert isinstance(drawing, FakeDrawing), "without an owner the bare Drawing is returned"
    assert drawing.parent is preview.widget, "the drawing is attached to the preview widget"


def test_preview_draw_when_coordinates_not_pixels_then_value_error(preview: Preview) -> None:
    """Preview drawing supports pixels only."""
    with pytest.raises(ValueError, match="pixels only"):
        preview.draw(lambda painter: None, coordinates="canvas")
    assert preview._owner.owned == [], "nothing may be created on refusal"


# ---------------------------------------------------------- GlyphWindow


class Canvas:
    """Fake flCanvas with a scale, view point and mapping calls."""

    def __init__(self) -> None:
        self.viewPoint, self.viewPort = ("view", 0), "viewport-widget"
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def scale(self) -> float:
        return 2.5

    def zoomTo(self, centre: Any, scale: float) -> None:
        self.calls.append(("zoomTo", (centre, scale)))

    def mapToViewportF(self, point: Any) -> Any:
        return ("to", point)

    def mapFromViewport(self, point: Any) -> Any:
        return ("from", point)


def _glyph_window(canvas: Canvas | None, owner: Any = None, children: list[Any] | None = None) -> GlyphWindow:
    inner = SimpleNamespace(name="inner")
    viewport = SimpleNamespace(findChildren=lambda kind: children if children is not None else [inner])
    widget = SimpleNamespace(widgetViewport=viewport)
    workspace = SimpleNamespace(
        getCanvasForViewport=lambda w: canvas if (w is inner and canvas is not None) else None
    )
    return GlyphWindow(widget, workspace, owner)


def test_glyph_window_init_when_built_then_exposes_widget_and_viewport() -> None:
    """The viewport is taken from the widget's ``widgetViewport``."""
    window = _glyph_window(Canvas())
    assert window.viewport is window.widget.widgetViewport, "viewport comes from widgetViewport"


class _NoViewportAttr:
    """FontLab 9's GlyphWindow: widgetViewport is a named child, not an attribute."""

    def __init__(self, children: list[Any]) -> None:
        self._children = children

    def findChildren(self, kind: Any) -> list[Any]:
        return self._children

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(f"GlyphWindow has no attribute named '{name}'")


def test_glyph_window_init_when_viewport_is_only_a_named_child_then_found(fake_native: Any) -> None:
    viewport = SimpleNamespace(objectName="widgetViewport")
    widget = _NoViewportAttr([SimpleNamespace(objectName="other"), viewport])
    assert GlyphWindow(widget, SimpleNamespace()).viewport is viewport, "falls back to the named child"


def test_glyph_window_init_when_no_viewport_child_then_lookup_error(fake_native: Any) -> None:
    with pytest.raises(LookupError, match="no widgetViewport child"):
        GlyphWindow(_NoViewportAttr([SimpleNamespace(objectName="other")]), SimpleNamespace())


def test_glyph_window_canvas_when_inner_widget_has_canvas_then_returns_it(fake_native: Any) -> None:
    """The container is tried first, then its children, until a canvas is found."""
    canvas = Canvas()
    assert _glyph_window(canvas).canvas is canvas, "the canvas of the inner widget is found"


def test_glyph_window_canvas_when_viewport_itself_has_canvas_then_returns_it(fake_native: Any) -> None:
    """The container widget is checked before the inner widgets."""
    canvas = Canvas()
    viewport = SimpleNamespace(findChildren=lambda kind: [])
    window = GlyphWindow(SimpleNamespace(widgetViewport=viewport), SimpleNamespace(getCanvasForViewport=lambda w: canvas))
    assert window.canvas is canvas, "the container's own canvas is found first"


def test_glyph_window_canvas_when_none_found_then_lookup_error(fake_native: Any) -> None:
    """No canvas anywhere raises a LookupError."""
    with pytest.raises(LookupError, match="no native canvas"):
        _glyph_window(None).canvas


def test_glyph_window_zoom_when_read_then_returns_canvas_scale(fake_native: Any) -> None:
    """``zoom`` is the canvas scale."""
    assert _glyph_window(Canvas()).zoom == 2.5, "zoom is the canvas scale"


def test_glyph_window_zoom_to_when_no_centre_then_keeps_view_point(fake_native: Any) -> None:
    """Without a centre the canvas view point is kept."""
    canvas = Canvas()
    window = _glyph_window(canvas)
    assert window.zoom_to(3) is window, "zoom_to chains"
    assert canvas.calls == [("zoomTo", (canvas.viewPoint, 3.0))], "the view point is kept as centre"


def test_glyph_window_zoom_to_when_centre_given_then_uses_it(fake_native: Any) -> None:
    """An explicit centre wins over the view point."""
    canvas = Canvas()
    _glyph_window(canvas).zoom_to(1, center="centre")
    assert canvas.calls == [("zoomTo", ("centre", 1.0))], "the explicit centre is used"


@pytest.mark.parametrize("bad", [0, -2, math.inf, math.nan])
def test_glyph_window_zoom_to_when_scale_invalid_then_value_error(fake_native: Any, bad: float) -> None:
    """Non-positive and non-finite zooms are refused before touching the canvas."""
    canvas = Canvas()
    with pytest.raises(ValueError, match="Zoom must be positive"):
        _glyph_window(canvas).zoom_to(bad)
    assert canvas.calls == [], "a refused zoom must not touch the canvas"


def test_glyph_window_pan_to_when_finite_then_zooms_at_current_scale_to_point(fake_native: Any) -> None:
    """Panning re-centres at the present zoom."""
    canvas = Canvas()
    window = _glyph_window(canvas)
    assert window.pan_to(10, 20) is window, "pan_to chains"
    assert canvas.calls == [("zoomTo", (("point", 10, 20), 2.5))], "pan re-centres at the current scale"


@pytest.mark.parametrize("x,y", [(math.nan, 0), (0, math.inf)])
def test_glyph_window_pan_to_when_not_finite_then_value_error(fake_native: Any, x: float, y: float) -> None:
    """A non-finite centre is refused."""
    canvas = Canvas()
    with pytest.raises(ValueError, match="Canvas center must be finite"):
        _glyph_window(canvas).pan_to(x, y)
    assert canvas.calls == [], "a refused centre must not touch the canvas"


def test_glyph_window_pixel_mapping_when_called_then_delegates_to_canvas(fake_native: Any) -> None:
    """Both conversions go through the canvas with native points."""
    window = _glyph_window(Canvas())
    assert window.to_pixels(1, 2) == ("to", ("point", 1, 2)), "to_pixels maps via the canvas"
    assert window.from_pixels(3, 4) == ("from", ("point", 3, 4)), "from_pixels maps via the canvas"


def test_glyph_window_draw_when_pixels_then_overlay_has_no_canvas(fake_native: Any) -> None:
    """Pixel drawing is attached to the canvas viewport without a canvas map."""
    canvas, callback = Canvas(), lambda painter: None
    drawing = _glyph_window(canvas).draw(callback)
    assert isinstance(drawing, FakeDrawing), "a Drawing is created"
    assert (drawing.parent, drawing.callback, drawing.canvas) == (
        "viewport-widget",
        callback,
        None,
    ), "pixel drawings attach to the canvas viewport without a canvas map"


def test_glyph_window_draw_when_canvas_units_and_owner_then_passes_canvas_and_is_owned(fake_native: Any) -> None:
    """Canvas-unit drawing receives the canvas; an owner takes the result."""
    canvas, owner = Canvas(), Owner()
    result = _glyph_window(canvas, owner).draw(lambda painter: None, coordinates="canvas")
    assert result == "owned", "the owner takes the drawing"
    assert owner.owned[0].canvas is canvas, "canvas-unit drawings receive the canvas"


def test_glyph_window_draw_when_unknown_coordinates_then_value_error(fake_native: Any) -> None:
    """Glyph-local coordinates are not offered."""
    with pytest.raises(ValueError, match="pixels or canvas"):
        _glyph_window(Canvas()).draw(lambda painter: None, coordinates="font")
