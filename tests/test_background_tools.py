# this_file: tests/test_background_tools.py
"""Independent source-domain and geometry oracle for three background tools."""

import math

import pytest
from fontlabapp.masters.background.model import Transform, numeric, selected_paths


@pytest.mark.parametrize(
    "value,expected", [("12.5", 12.5), ("-4", -4), ("0", 0), (" 1e2 ", 100)]
)
def test_finite_original_numeric_values(value, expected):
    assert numeric(value) == expected


@pytest.mark.parametrize("value", ["", "bad", "NaN", "inf", None, True])
def test_invalid_and_nonfinite_values_fail_before_any_writer(value):
    with pytest.raises(ValueError):
        numeric(value)


def test_path_only_scalar_about_origin_and_signed_shift_components():
    matrix = (2, 3, 0, 4, 5, 0, 10, 20, 1)
    scale = Transform("scale", -50)
    assert scale.point((10, -20)) == (-5, 10)
    assert scale.component(matrix) == matrix
    shift = Transform("shift", -17.5)
    assert shift.point((10, 20)) == (-7.5, 20)
    assert shift.component(matrix) == (2, 3, 0, 4, 5, 0, -7.5, 20, 1)


def test_scale_preserves_original_percentage_multiplication_order():
    assert Transform("scale", 110).point((0.1, 0.2)) == (
        0.1 * (110 * 0.01),
        0.2 * (110 * 0.01),
    )


def test_repeated_occurrences_apply_repeated_operations_in_order():
    op = Transform("scale", 110)
    expected = (0.1, 0.2)
    for _ in range(3):
        expected = op.point(expected)
    assert op.points(((0.1, 0.2),), repeat=3) == (expected,)
    assert Transform("shift", 0).points(((1, 2),), repeat=0) == ((1, 2),)


def test_replacement_uses_all_nodes_selected_and_keeps_empty_paths():
    assert selected_paths(((True, True), (True, False), (), (False,))) == (0, 2)
    assert selected_paths(()) == ()


@pytest.mark.parametrize(
    "mode,value", [("other", 1), ("scale", math.inf), ("shift", math.nan)]
)
def test_invalid_transform_refuses(mode, value):
    with pytest.raises(ValueError):
        Transform(mode, value)


def test_nonfinite_coordinates_and_nonaffine_component_transform_refuse():
    with pytest.raises(ValueError):
        Transform("shift", 1).point((math.inf, 0))
    with pytest.raises(ValueError):
        Transform("shift", 1).component((1, 0, 1, 0, 1, 0, 0, 0, 1))
