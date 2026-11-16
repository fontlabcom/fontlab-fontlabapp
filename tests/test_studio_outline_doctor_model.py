# this_file: tests/test_studio_outline_doctor_model.py
"""Outline Doctor model helpers: translations, editable shapes, segments and exact area."""

from types import SimpleNamespace as NS

import pytest

from fontlabapp.studios.outline_doctor import model as m


def matrix(m11=1.0, m22=1.0, m12=0.0, m21=0.0, dx=0.0, dy=0.0):
    return NS(
        m11=lambda: m11,
        m22=lambda: m22,
        m12=lambda: m12,
        m21=lambda: m21,
        dx=lambda: dx,
        dy=lambda: dy,
    )


def shape(transform=None, *, component=False, contours=("c",), refs=1):
    return NS(
        transform=transform,
        isComponent=component,
        contours=list(contours),
        shapeData=NS(referenceCount=refs),
    )


def test_translation_when_no_transform_then_zero_offset():
    assert m.translation(shape()) == (0.0, 0.0)


def test_translation_when_only_moves_then_returns_offset():
    assert m.translation(shape(matrix(dx=12, dy=-3))) == (12.0, -3.0)


@pytest.mark.parametrize(
    "bad", [{"m11": 2.0}, {"m22": 0.5}, {"m12": 0.2}, {"m21": -0.1}]
)
def test_translation_when_scaled_or_turned_then_none(bad):
    assert m.translation(shape(matrix(dx=5, **bad))) is None


def test_outline_shapes_when_mixed_then_splits_editable_from_notes():
    layer = NS(
        shapes=[
            shape(component=True),
            shape(contours=()),
            shape(refs=2),
            shape(matrix(m11=2.0)),
            shape(matrix(dx=1)),
        ]
    )
    found, notes = m.outline_shapes(layer)
    assert [position for position, _ in found] == [4], (
        "only the plain own outline is editable"
    )
    assert notes == ["shared outline, kept", "scaled or rotated shape, kept"]


SQUARE = [(0.0, 0.0, True), (0.0, 10.0, True), (10.0, 10.0, True), (10.0, 0.0, True)]


def test_segments_of_when_no_on_curve_then_empty():
    assert m.segments_of([(0.0, 0.0, False), (1.0, 1.0, False)], truetype=False) == ()


def test_segments_of_when_lines_only_then_closed_line_ring():
    segments = m.segments_of(SQUARE, truetype=False)
    assert len(segments) == 4 and all(len(s) == 2 for s in segments)
    assert segments[-1][1] == (0.0, 0.0), "the ring closes on the start node"


def test_segments_of_when_two_off_curves_then_cubic():
    points = [
        (0.0, 0.0, True),
        (0.0, 5.0, False),
        (5.0, 10.0, False),
        (10.0, 10.0, True),
    ]
    segments = m.segments_of(points, truetype=False)
    assert segments[0] == ((0.0, 0.0), (0.0, 5.0), (5.0, 10.0), (10.0, 10.0))


def test_segments_of_when_truetype_off_curves_then_implied_on_curve_quadratics():
    points = [
        (0.0, 0.0, True),
        (0.0, 10.0, False),
        (10.0, 10.0, False),
        (10.0, 0.0, True),
    ]
    first, second, *_ = m.segments_of(points, truetype=True)
    assert first == ((0.0, 0.0), (0.0, 10.0), (5.0, 10.0))
    assert second == ((5.0, 10.0), (10.0, 10.0), (10.0, 0.0))


def test_unsigned_area_when_square_lines_then_exact_area():
    assert m.unsigned_area(m.segments_of(SQUARE, truetype=False)) == 100


def test_unsigned_area_when_quadratic_bulge_then_adds_curve_area():
    segments = (((0.0, 0.0), (5.0, 10.0), (10.0, 0.0)), ((10.0, 0.0), (0.0, 0.0)))
    assert m.unsigned_area(segments) == pytest.approx(33.3333333, rel=1e-6)


def test_unsigned_area_when_cubic_arc_then_matches_bezier_integral():
    segments = (
        ((0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)),
        ((10.0, 0.0), (0.0, 0.0)),
    )
    assert m.unsigned_area(segments) == pytest.approx(
        60.0
    )  # 1800 * integral of t^2 (1-t)^2 dt


def test_unsigned_area_when_non_finite_then_raises():
    with pytest.raises(ValueError, match="finite"):
        m.unsigned_area((((0.0, 0.0), (float("nan"), 1.0)),))


def test_unsigned_area_when_segment_has_five_points_then_raises():
    with pytest.raises(ValueError, match="continuous"):
        m.unsigned_area((((0.0, 0.0),) * 5,))
