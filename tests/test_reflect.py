# this_file: tests/test_reflect.py
"""Both complete original coordinate/scale actions over detached selections."""

import math
from dataclasses import replace

import pytest
from fontlabapp.contours.reflect import Element, plan


def element(kind="node", position=(10.0, 20.0), **kwargs):
    return Element(kind, position, **kwargs)


@pytest.mark.parametrize("axis", ["horizontal", "vertical"])
@pytest.mark.parametrize("kind", ["node", "anchor", "guide", "annotation"])
def test_every_selected_position_kind_uses_same_original_axis_rule(axis, kind):
    raw = ("cubic", "control", 0xA523, "named point", "note", ("hint", 7))
    old = element(kind, retained=raw)
    result = plan((old,), (-20.0, -50.0, 100.0, 200.0), axis)
    assert result.elements == (
        replace(old, position=(50.0, 20.0) if axis == "horizontal" else (10.0, 80.0)),
    )
    assert result.elements[0].retained is raw
    assert result.update_metrics


@pytest.mark.parametrize(
    "axis,scale", [("horizontal", (-2.0, -3.0)), ("vertical", (2.0, 3.0))]
)
def test_rotated_component_negates_only_scale_axis_retaining_rotation(axis, scale):
    old = element(
        "component",
        scale=(2.0, -3.0),
        rotation=37.0,
        retained=("base", "Regular", "component note", "alignment"),
    )
    new = plan((old,), (0.0, 0.0, 100.0, 100.0), axis).elements[0]
    assert new.scale == scale and new.rotation == 37.0
    assert new.position == ((90.0, 20.0) if axis == "horizontal" else (10.0, 80.0))
    assert new.retained == old.retained


@pytest.mark.parametrize("axis", ["horizontal", "vertical"])
def test_full_bounds_include_component_extent_and_anchor_not_just_origins(axis):
    rows = (
        element(),
        element("component", (100.0, 200.0), scale=(1.0, 1.0)),
        element("anchor", (-50.0, 400.0)),
    )
    result = plan(rows, (-50.0, 20.0, 450.0, 480.0), axis)
    assert [row.position for row in result.elements] == (
        [(340.0, 20.0), (250.0, 200.0), (400.0, 400.0)]
        if axis == "horizontal"
        else [(10.0, 500.0), (100.0, 320.0), (-50.0, 120.0)]
    )


def test_unselected_geometry_and_metadata_remain_the_exact_original_objects():
    outside = element(position=(1000.0, 1000.0), selected=False)
    result = plan((element(), outside), (0.0, 0.0, 100.0, 100.0), "horizontal")
    assert result.elements[1] is outside


def test_no_selection_still_requests_original_metrics_update():
    assert plan((), (0.0, 0.0, 0.0, 0.0), "vertical").update_metrics


def test_original_arithmetic_order_is_not_algebraically_reassociated():
    old = element(position=(-1e16, 0.0))
    expected = 1.0 - -1e16 + 1.0
    assert expected != 2.0 * 1.0 - -1e16
    assert (
        plan((old,), (1.0, 0.0, 0.0, 0.0), "horizontal").elements[0].position[0]
        == expected
    )


def test_zero_scale_and_reflected_component_signs_are_not_normalized():
    old = element("component", scale=(-0.0, -2.0), rotation=-190.0)
    new = plan((old,), (0.0, 0.0, 0.0, 0.0), "horizontal").elements[0]
    assert math.copysign(1, new.scale[0]) == 1 and new.scale[1] == -2
    assert new.rotation == -190


@pytest.mark.parametrize("axis", ["x", "both", "", None])
def test_unknown_mode_refused_before_any_plan(axis):
    with pytest.raises(ValueError, match="horizontal or vertical"):
        plan((element(),), (0, 0, 1, 1), axis)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_bounds_refused_before_any_plan(bad):
    with pytest.raises(ValueError, match="finite"):
        plan((element(),), (bad, 0, 1, 1), "horizontal")


def test_overflow_and_malformed_component_state_refused_wholly():
    with pytest.raises(ValueError, match="finite"):
        plan((element(position=(-1e308, 0)),), (1e308, 0, 0, 0), "horizontal")
    with pytest.raises(ValueError, match="scale"):
        plan((element("component"),), (0, 0, 0, 0), "vertical")
