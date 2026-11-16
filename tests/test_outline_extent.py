# this_file: tests/test_outline_extent.py
"""outline_extent: vertical extents from outline nodes, never from boundingBox (fl#8575)."""

from importlib import import_module
from math import sqrt
from types import SimpleNamespace as NS

import pytest

outline_extent = import_module("fontlabapp.contours.extent")


class Transform:
    """QTransform double: m11() … m33(); y' = m12 x + m22 y + m32 (QTransform.map)."""

    def __init__(self, sx=1.0, sy=1.0, dx=0.0, dy=0.0, m12=0.0, m21=0.0, m13=0.0):
        values = {"m11": sx, "m12": m12, "m13": m13, "m21": m21, "m22": sy, "m23": 0.0, "m31": dx, "m32": dy, "m33": 1.0}
        for name, value in values.items():
            setattr(self, name, lambda value=value: value)


class Layer:
    """flLayer double whose boundingBox read and update() fail the test."""

    def __init__(self, *shapes):
        self.shapes = list(shapes)

    @property
    def boundingBox(self):
        raise AssertionError("boundingBox must not be read (fl#8575)")

    def update(self):
        raise AssertionError("update() must not be called")


def node(x, y, kind):
    """flNode double: kind "on", "curve" (flNode::Curve) or "off" (flNode::Off)."""
    return NS(x=x, y=y, isOn=lambda: kind == "on", isCurve=lambda: kind == "curve", isOff=lambda: kind == "off")


def contour(points, closed=True, tt=False):
    """Contour double from ``(x, y, kind)`` triples; ``isTT`` is never read."""
    nodes = [node(*point) for point in points]
    return NS(nodes=lambda: nodes, closed=closed, isTT=tt)


def shape(*contours, transform=None):
    return NS(contours=list(contours), transform=transform or Transform())


def extent(*contours, transform=None):
    return outline_extent.vertical_extent(Layer(shape(*contours, transform=transform)))


ARC = [(0, 0, "on"), (0, 100, "curve"), (100, 100, "curve"), (100, 0, "on")]


def test_vertical_extent_when_line_contour_then_node_range():
    square = contour([(0, 0, "on"), (100, 0, "on"), (100, 700, "on"), (0, 700, "on")])
    assert extent(square) == (0.0, 700.0), "lines: node range"


def test_vertical_extent_when_cubic_extreme_between_nodes_then_exact_extreme():
    # on (0,0), cubic controls (0,100) (100,100), on (100,0): the top at t=0.5 is 75.
    assert extent(contour(ARC)) == (0.0, pytest.approx(75.0)), "cubic: the extreme lies between nodes"


def test_vertical_extent_when_quadratic_arc_then_single_extreme():
    arc = contour([(0, 0, "on"), (50, 100, "off"), (100, 0, "on")], tt=True)
    assert extent(arc) == (0.0, pytest.approx(50.0)), "quadratic: one extreme"


def test_vertical_extent_when_quadratic_offs_in_a_row_then_implied_midpoints():
    # Two Off nodes in a row: the curve passes the implied on-curve point (50, 100).
    offs = [(0, 0, "on"), (0, 100, "off"), (100, 100, "off"), (100, 0, "on")]
    assert extent(contour(offs, tt=True)) == (0.0, pytest.approx(100.0)), "quadratic: implied midpoint"
    assert extent(contour(offs, closed=False, tt=True)) == (0.0, pytest.approx(100.0)), "quadratic open contour"
    ring = [(0, 0, "off"), (100, 0, "off"), (100, 100, "off"), (0, 100, "off")]
    assert extent(contour(ring, tt=True)) == (0.0, 100.0), "all-Off ring: implied midpoints at the edges"


def test_vertical_extent_when_contour_mixes_cubic_and_quadratic_then_each_by_node_kind():
    # FontLab marks this contour isTT (one Off node), yet its Curve pair is a cubic:
    # no implied midpoint between Curve nodes. Cubic top 75; quadratic closing bottom -25.
    mixed = contour([*ARC, (50, -50, "off")], tt=True)
    assert extent(mixed) == (pytest.approx(-25.0), pytest.approx(75.0)), "mixed contour: segment kind by node kind"


def test_vertical_extent_when_curve_pair_in_a_non_tt_contour_then_cubic_not_quadratic():
    # isTT is never read: the same Curve pair gives the cubic extreme in either contour.
    assert extent(contour(ARC, tt=True)) == extent(contour(ARC, tt=False)) == (0.0, pytest.approx(75.0)), "isTT ignored"


def test_vertical_extent_when_closing_segment_wraps_then_its_extreme_counts():
    # The cubic is the closing segment: from (100, 0) back to (0, 0) through controls below.
    wrap = contour([(0, 0, "on"), (100, 0, "on"), (100, -100, "curve"), (0, -100, "curve")])
    assert extent(wrap) == (pytest.approx(-75.0), 0.0), "closing segment"


def test_vertical_extent_when_contour_starts_with_control_then_rotated():
    start_off = contour([(100, 100, "curve"), (100, 0, "on"), (0, 0, "on"), (0, 100, "curve")])
    assert extent(start_off) == (0.0, pytest.approx(75.0)), "rotate to an on node"


def test_vertical_extent_when_component_transformed_then_placed():
    square = contour([(0, 0, "on"), (10, 0, "on"), (10, 100, "on"), (0, 100, "on")])
    assert extent(square, transform=Transform(sy=2.0, dy=-50.0)) == (-50.0, 150.0), "component: scale and offset"


def test_vertical_extent_when_component_skewed_then_m12_moves_y_and_m21_only_x():
    # QTransform: y' = m12 x + m22 y + dy. A swapped m12/m21 gives (0, 310) instead.
    bar = contour([(0, 0, "on"), (100, 0, "on"), (100, 10, "on"), (0, 10, "on")])
    assert extent(bar, transform=Transform(m12=0.5, m21=3.0)) == (0.0, 60.0), "skew: m12 shears y by x"


def test_vertical_extent_when_empty_layer_or_sticker_then_none():
    assert outline_extent.vertical_extent(Layer()) is None, "empty layer"
    assert outline_extent.vertical_extent(Layer(shape(), shape(contour([])))) is None, "no contours, no nodes"


def test_vertical_extent_when_open_contour_then_no_closing_segment():
    assert extent(contour(ARC, closed=False)) == (0.0, pytest.approx(75.0)), "open cubic"
    assert extent(contour([(5, 9, "on")], closed=False)) == (9.0, 9.0), "open single node"


@pytest.mark.parametrize(
    ("points", "closed", "message"),
    [
        ([(0, 0, "curve"), (10, 10, "on")], False, "start at an on-curve"),
        ([(0, 0, "curve"), (10, 10, "curve")], True, "start at an on-curve"),
        ([(0, 0, "on"), (1, 1, "off")], False, "end at an on-curve"),
        ([(0, 0, "on"), (1, 1, "curve"), (2, 2, "on")], False, "one quadratic or two cubic"),
        ([(0, 0, "on"), (1, 1, "curve"), (2, 2, "off"), (3, 3, "on")], False, "one quadratic or two cubic"),
        ([(0, 0, "on"), (1, 1, "curve"), (2, 2, "curve"), (3, 3, "curve"), (4, 4, "on")], True, "one quadratic or two cubic"),
    ],
)
def test_vertical_extent_when_topology_invalid_then_refused(points, closed, message):
    with pytest.raises(ValueError, match=message):
        extent(contour(points, closed=closed))


def test_vertical_extent_when_projective_transform_then_refused():
    square = contour([(0, 0, "on"), (10, 0, "on")])
    with pytest.raises(ValueError, match="Projective"):
        extent(square, transform=Transform(m13=0.1))


@pytest.mark.parametrize(
    ("values", "expected"),
    [((0, 0, 0, 0), []), ((0, 3, 3, 0), [2.25]), ((0, 1, 2, 3), []), ((0, 0, 3, 3), []), ((0, 0, 1, 3), [])],
)
def test_cubic_extremes_when_degenerate_or_monotonic_then_only_interior_turns(values, expected):
    assert outline_extent.cubic_extremes(*values) == pytest.approx(expected), f"cubic extremes of {values}"


def test_cubic_extremes_when_quadratic_like_derivative_then_one_root():
    # a == 0 (p3 = p0 - 3p1 + 3p2): derivative is linear.
    assert outline_extent.cubic_extremes(0, 2, 2, 0) == pytest.approx([1.5]), "linear derivative root"


def test_cubic_extremes_when_no_real_turn_or_s_curve_then_closed_form():
    # a = 1, b = 0, c = 1: the derivative has no real root.
    assert outline_extent.cubic_extremes(0, 1, 2, 4) == [], "negative discriminant: no turn"
    # 30 t(1-t)(1-2t) turns at t = (1 -+ 1/sqrt 3)/2, where it is -+5/sqrt 3.
    expected = [-5 / sqrt(3), 5 / sqrt(3)]
    assert outline_extent.cubic_extremes(0, 10, -10, 0) == pytest.approx(expected), "S curve: both closed-form turns"


def test_quadratic_extremes_when_straight_or_outside_then_empty():
    assert outline_extent.quadratic_extremes(0, 5, 10) == [], "straight: no turn"
    assert outline_extent.quadratic_extremes(0, 10, 0) == pytest.approx([5.0]), "turn at t=0.5"
    assert outline_extent.quadratic_extremes(0, 0, 10) == [], "turn at t=0 is not interior"
