# this_file: tests/test_painting_view.py
"""View pixels per glyph unit through composed glyph, block and viewport maps."""

import math

import pytest

from fontlabapp.qt.painting.view import px_per_unit


class Point:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


def test_px_per_unit_when_translation_only_then_one():
    to_view = lambda p: Point(p.x() + 30, p.y() - 7)
    assert px_per_unit(to_view, Point) == 1.0


def test_px_per_unit_when_glyph_and_view_scale_then_product():
    glyph = lambda p: Point(p.x() * 0.5, p.y() * 0.5)
    view = lambda p: Point(p.x() * 4 + 10, p.y() * -4 + 3)
    assert px_per_unit(lambda p: view(glyph(p)), Point) == 2.0


def test_px_per_unit_when_rotated_then_length_is_kept():
    turn = math.radians(30)
    rotate = lambda p: Point(
        3 * (p.x() * math.cos(turn) - p.y() * math.sin(turn)),
        3 * (p.x() * math.sin(turn) + p.y() * math.cos(turn)),
    )
    assert px_per_unit(rotate, Point) == pytest.approx(3.0)


def test_px_per_unit_when_map_is_not_finite_then_value_error():
    with pytest.raises(ValueError, match="Non-finite"):
        px_per_unit(lambda p: Point(p.x() * math.inf, 0), Point)
