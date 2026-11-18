# this_file: tests/test_issue253_sequence_preview.py
"""Sequence preview in Kerning and Groups: compact margin and theme-following canvas."""
import importlib
import sys
from types import SimpleNamespace as NS

import _cov_qt as fq
import pytest
from fontlabapp.fontui.model import Outline
from PySide6 import QtCore, QtGui, QtWidgets
from test_renderer_palettes_qt import palette
from test_renderer_palettes_qt import renderers  # noqa: F401  (fixture)

MODULES = ("sequence_canvas", "preview")
DARK, LIGHT = (0x20, 0x21, 0x24), (255, 255, 255)


def rgb(image, x, y):
    c = image.pixelColor(x, y)
    return c.red(), c.green(), c.blue()


def canvas_with(dark):
    widget = type("W", (QtWidgets.QWidget,), {n: property(getattr(QtWidgets.QWidget, n)) for n in ("width", "height", "rect", "palette")})()
    widget.setPalette(palette(dark))
    widget.resize(120, 90)
    return widget


def grab(widget, paint):
    image = QtGui.QImage(120, 90, QtGui.QImage.Format_RGB32)
    painter_target = image
    original = QtGui.QPainter

    class P(original):
        def __init__(self, _):
            super().__init__(painter_target)

    sys.modules["PythonQt"].QtGui.QPainter = P
    try:
        paint(widget)
    finally:
        sys.modules["PythonQt"].QtGui.QPainter = original
    return image


def load(name):
    sys.modules.pop("fontlabapp.fontui." + name, None)
    return importlib.import_module("fontlabapp.fontui." + name)


@pytest.mark.parametrize("dark", [True, False])
def test_preview_when_palette_is_dark_or_light_then_canvas_background_follows(renderers, dark):  # noqa: F811
    module = load("preview")
    owner = NS(closed=False, data=None)
    image = grab(canvas_with(dark), lambda w: module.Preview.paint(owner, w))
    assert rgb(image, 60, 45) == (DARK if dark else LIGHT), "empty preview canvas uses palette Base"


@pytest.mark.parametrize("dark", [True, False])
def test_sequence_canvas_when_palette_is_dark_or_light_then_background_and_ink_follow(renderers, dark):  # noqa: F811
    module = load("sequence_canvas")
    recording = [("moveTo", ((10, 10),)), ("lineTo", ((10, 60),)), ("lineTo", ((100, 60),)), ("lineTo", ((100, 10),)), ("closePath", ())]
    glyph = NS(index=0, name="A", x=0, advance=110, label="A")
    owner = NS(
        font=type("F", (dict,), {"keys": lambda s: list(s)})({"A": 1}), run=NS(glyphs=[glyph], direction="ltr"), outlines={"A": Outline(recording, (0, 0, 110, 70), 110, ())},
        positions=[(0, 0)], scale=1.0, origin_x=0, baseline=70, line_height=70, selected_index=-1, closed=False, fail=lambda e: pytest.fail(str(e)),
    )
    image = grab(canvas_with(dark), lambda w: module.paint(owner, w))
    assert rgb(image, 2, 2) == (DARK if dark else LIGHT), "canvas background follows the palette"
    ink = rgb(image, 50, 35)
    assert (ink[0] > 0x80) == dark and ink != (DARK if dark else LIGHT), "glyph ink contrasts with the canvas"


def test_sequence_when_embedded_then_layout_margin_is_zero_and_standalone_is_compact(monkeypatch):
    handle = fq.install(monkeypatch)
    try:
        module = handle.load("fontlabapp.fontui.sequence")
        model = fq.FontModel(fq.ufo_font())

        def margins(parent):
            seq = module.Sequence(model, parent, None)
            return [a for c, a in seq.layout.calls if c == "setContentsMargins"]

        assert margins(None) == [(6, 6, 6, 6)], "standalone keeps the compact panel margin"
        assert margins(module.Sequence(model, None, None).widget) == [(0, 0, 0, 0)], "embedded in a compact host: no second margin"
    finally:
        fq.release()
