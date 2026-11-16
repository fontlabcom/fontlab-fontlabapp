# this_file: tests/test_contour_selection.py
"""Pedro selection contracts, including cross-contour state and analytic area."""

import math

import pytest

from fontlabapp.contours.selection.model import Path, plan, unsigned_area, threshold


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("contours", ((False, False), (True, True, True), ())),
        ("partial", ((False, False), (True, True, True), ())),
    ],
)
def test_selected_control_qualifies_and_empty_paths_keep_order(mode, expected):
    paths = (Path((False, False)), Path((True, False, False)), Path(()))
    assert plan(paths, mode).nodes == expected


def test_partial_state_crosses_contours_without_wrapping():
    paths = (Path((False, True, False)), Path(()), Path((False, False, True, False)))
    assert plan(paths, "partial").nodes == (
        (False, True, True),
        (),
        (True, True, True, False),
    )


@pytest.mark.parametrize(
    "limit,expected,count",
    [
        (-1, ((False,), (False,), ()), 0),
        (0, ((False,), (False,), ()), 0),
        (10, ((True,), (False,), ()), 2),
        (math.nextafter(10, math.inf), ((True,), (True,), ()), 3),
    ],
)
def test_small_strict_unsigned_threshold_and_path_count(limit, expected, count):
    result = plan((Path((False,), 0), Path((True,), 10), Path((), 0)), "small", limit)
    assert result.nodes == expected
    assert result.paths == count
    assert result.clear_other


@pytest.mark.parametrize("value", ["bad", "nan", "inf", "-inf", None, object()])
def test_invalid_threshold_refuses(value):
    with pytest.raises(ValueError):
        threshold(value)


def test_valid_threshold_does_not_clamp_or_round():
    assert threshold(" -1.125 ") == -1.125
    with pytest.raises(ValueError):
        plan((), "unknown")
    with pytest.raises(ValueError):
        plan((Path((True,)),), "small", 3)


@pytest.mark.parametrize(
    "segments,expected",
    [
        ((), 0),
        ((((0, 0), (10, 0)), ((10, 0), (10, 10))), 50),
        ((((10, 10), (10, 0)), ((10, 0), (0, 0))), 50),
        ((((0, 0), (0, 10), (10, 10), (10, 0)),), 60),
        ((((0, 0), (5, 10), (10, 0)),), 100 / 3),
    ],
)
def test_analytic_area_closes_open_paths_and_uses_cubic_quadratic_geometry(
    segments, expected
):
    assert unsigned_area(segments) == pytest.approx(expected)


def test_discontinuous_or_malformed_segments_refuse():
    for segments in [(((0, 0),),), (((0, 0), (1, 0)), ((3, 0), (3, 1)))]:
        with pytest.raises(ValueError):
            unsigned_area(segments)


@pytest.mark.parametrize(
    "segment",
    [
        ((0, 0), (0, 10), (10, 10), (10, 0)),
        ((0, 0), (5, 10), (10, 0)),
    ],
)
def test_curved_reverse_winding_keeps_unsigned_area(segment):
    assert unsigned_area((segment,)) == pytest.approx(
        unsigned_area((tuple(reversed(segment)),))
    )


def test_nonfinite_geometry_and_negative_unsigned_area_refuse():
    with pytest.raises(ValueError, match="finite"):
        unsigned_area((((0, 0), (float("inf"), 1)),))
    for value in (-1, float("inf"), float("nan")):
        with pytest.raises(ValueError, match="unsigned area"):
            plan((Path((True,), value),), "small", 10)
