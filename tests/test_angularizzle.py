# this_file: tests/test_angularizzle.py
"""Owned analytic controls for the licensed Angularizzle numerical port."""

import math
from itertools import pairwise

import pytest

from fontlabapp.contours.angularizzle.model import Path, Segment, angularize, line_nodes


def square(size=160):
    corners = ((0, 0), (size, 0), (size, size), (0, size), (0, 0))
    return Path(tuple(Segment((a, b)) for a, b in pairwise(corners)))


def test_square_keeps_source_order_duplicate_terminal_and_fractional_steps():
    (result,) = angularize((square(),), 80)
    expected = (
        (0, 0),
        (80, 0),
        (160, 0),
        (160, 80),
        (160, 160),
        (80, 160),
        (0, 160),
        (0, 80),
    )
    assert result.length == 640, "Four original straight lengths must survive"
    assert result.points == (*expected, expected[-1]), (
        "Source appends its last point twice"
    )
    assert line_nodes(result) == expected
    (fractional,) = angularize((Path((Segment(((0, 0), (10, 0))),)),), 6)
    assert fractional.points == ((0, 0), (5, 0), (5, 0))
    assert line_nodes(fractional) == (), (
        "Source collapses a closed path with only two unique nodes"
    )


def test_open_empty_and_move_only_paths_produce_no_output():
    assert angularize((), 80) == ()
    assert (
        angularize(
            (Path((), closed=False), Path(()), Path((Segment(((1, 2),), move=True),))),
            80,
        )
        == ()
    )


def test_keep_detail_false_preserves_strict_threshold_and_collapsed_counter():
    (result,) = angularize((square(),), 80, keep_detail=False)
    assert result.points == ((0, 0), (160, 0), (160, 160)), (
        "Equal distances do not qualify"
    )
    assert line_nodes(result) == (), (
        "Do not replace source counter collapse by a generic simplifier"
    )


def test_short_cubic_uses_endpoints_and_exact_boundary_still_uses_short_route():
    path = Path((Segment(((0, 0), (1, 0), (2, 0), (3, 0))),))
    (result,) = angularize((path,), 80)
    assert result.points == ((0, 0), (3, 0), (3, 0))
    assert 2.9 < result.length <= 3, "Original lookup estimates cubic length"


def test_long_straight_cubic_has_analytic_points_and_source_lookup_length():
    path = Path((Segment(((0, 0), (100, 0), (200, 0), (300, 0))),))
    (result,) = angularize((path,), 80)
    assert len(result.points) == 5, (
        "Floor(lookup length / 80) plus endpoints and duplicate tail"
    )
    assert result.points[0] == (0, 0) and result.points[-1] == (300, 0)
    assert result.points[-2] == (300, 0)
    assert result.points[1][0] == pytest.approx(result.length / 3)
    assert result.points[2][0] == pytest.approx(2 * result.length / 3)
    assert all(p[1] == 0 for p in result.points)


def test_nonconsecutive_duplicate_is_removed_without_sorting():
    path = Path(
        tuple(
            Segment(pair)
            for pair in (((0, 0), (10, 0)), ((10, 0), (0, 0)), ((0, 0), (0, 10)))
        )
    )
    (result,) = angularize((path,), 80)
    assert result.points == ((0, 0), (10, 0), (0, 0)), (
        "Source repeats original last even after global deduplication"
    )


@pytest.mark.parametrize("plane", [0, -1, 4, math.nan, math.inf])
def test_invalid_plane_is_refused_before_output(plane):
    with pytest.raises(ValueError, match="plane"):
        angularize((square(),), plane)


@pytest.mark.parametrize(
    "points",
    [
        (),
        ((0, 0),),
        ((0, 0), (1, 1), (2, 2)),
        ((0, 0), (math.nan, 0)),
        ((0, 0), (math.inf, 0)),
    ],
)
def test_unsupported_or_nonfinite_segments_are_refused(points):
    with pytest.raises(ValueError):
        angularize((Path((Segment(points),)),), 80)


def test_coincident_line_is_diagnosed_instead_of_source_division_by_zero():
    with pytest.raises(ValueError, match="coincident"):
        angularize((Path((Segment(((1, 2), (1, 2))),)),), 80)


def test_excessive_output_is_refused_without_partial_result():
    with pytest.raises(ValueError, match="budget"):
        angularize((Path((Segment(((0, 0), (1e12, 0))),)),), 5)


def test_symmetric_cubic_retains_analytic_midpoint_and_original_endpoints():
    (result,) = angularize(
        (Path((Segment(((0, 0), (0, 100), (100, 100), (100, 0))),)),), 80
    )
    assert result.points[0] == (0, 0) and result.points[-1] == (100, 0)
    assert result.points[1] == pytest.approx((50, 75), abs=0.02)
    assert 199.9 < result.length < 200, (
        "Lookup polygon approaches the analytic length200 from below"
    )


def test_first_lookup_interval_intentionally_maps_to_zero_and_missing_distance_refuses():
    from fontlabapp.contours.angularizzle.model import STEP, _parameter

    assert _parameter([0, 10, 20], 5) == 0, "Keep the source's first-interval quirk"
    assert _parameter([0, 10, 20], 15) == pytest.approx(1.5 * STEP)
    with pytest.raises(ValueError, match="lookup"):
        _parameter([0, 10, 20], 21)


def test_bad_coordinate_dimension_and_overflowing_distance_are_refused():
    for points in (((0, 0, 1), (1, 1)), ((-1e308, 0), (1e308, 0))):
        with pytest.raises(ValueError, match="finite"):
            angularize((Path((Segment(points),)),), 80)


def test_budget_spans_multiple_paths_before_duplicate_removal(monkeypatch):
    import fontlabapp.contours.angularizzle.model as api

    monkeypatch.setattr(api, "MAX_POINTS", 9)
    with pytest.raises(ValueError, match="budget"):
        angularize((square(), square()), 80)


def test_flat_cubic_and_one_point_result_keep_source_empty_counter():
    (result,) = angularize((Path((Segment(((1, 2),) * 4),)),), 80)
    assert result.length == 0 and result.points == ((1, 2), (1, 2))
    assert line_nodes(result) == ()
