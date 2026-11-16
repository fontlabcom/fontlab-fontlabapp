# this_file: tests/test_crossfont_anchors.py
"""Literal original arithmetic/collision alternatives; no source body executed."""

import math
from itertools import product

import pytest
from fontlabapp.anchors.crossfont.model import Options, Pin, copy_layer, layer_pairs

META = (5, True, False, True, 2, "x+1", "y+2")


def pin(key, name="top", x=25.125, y=100.5):
    return Pin(key, name, x, y, META)


@pytest.mark.parametrize(
    "relative,italic,collision,rename_destination,specific",
    list(product((False, True), repeat=5)),
)
def test_all_original_mode_combinations_keep_exact_metadata_order_and_rounding(
    relative, italic, collision, rename_destination, specific
):
    source = (pin(1), pin(2, "bottom", -7.25, -22.5))
    destination = (pin(3), pin(4, "keep"))
    o = Options(
        relative,
        italic,
        10,
        collision,
        rename_destination,
        ".bak",
        " top " if specific else None,
    )
    result = copy_layer(source, destination, 100, 200, o)
    incoming = result.pins[-1] if specific else result.pins[-2]
    assert incoming.name == (
        "top.bak" if collision and not rename_destination else "top"
    )
    assert incoming.x == ((25.125 / 100) * 200 if relative else 25.125) + (
        round(100.5 * math.tan(math.radians(10))) if italic else 0
    )
    assert incoming.y == 100.5 and incoming.metadata == META
    assert result.pins[0].name == (
        "top.bak"
        if collision and rename_destination
        else "top"
        if collision
        else "keep"
    )
    assert result.copied == (1 if specific else 2)
    assert source[0] == pin(1) and destination[0] == pin(3)


@pytest.mark.parametrize(
    "collision,rename", [(False, False), (True, False), (True, True)]
)
def test_duplicate_names_empty_suffix_and_first_only_collision_are_not_deduplicated(
    collision, rename
):
    result = copy_layer(
        (pin(1), pin(2)),
        (pin(3), pin(4)),
        1,
        1,
        Options(False, False, 0, collision, rename, "", None),
    )
    assert result.copied == 2 and len(result.pins) == (4 if collision else 2)
    assert [p.name for p in result.pins] == ["top"] * len(result.pins)
    if not collision:
        assert [e.identity for e in result.edits if e.action == "remove"] == [3, 4]


def test_zero_source_advance_falls_back_absolute_before_italic():
    result = copy_layer(
        (pin(1),), (), 0, 200, Options(True, True, 20, False, False, ".x", None)
    )
    assert result.pins[0].x == 25.125 + round(100.5 * math.tan(math.radians(20)))
    assert result.zero_advance == ("top",)


def test_empty_specific_request_can_copy_an_empty_named_anchor():
    result = copy_layer(
        (pin(1), pin(2, "")), (), 1, 1, Options(False, False, 0, False, False, "", "  ")
    )
    assert [p.name for p in result.pins] == [""]


def test_same_layer_destination_rename_changes_later_original_source_handles():
    source = (pin(1), pin(2))
    result = copy_layer(
        source, source, 1, 1, Options(False, False, 0, True, True, ".bak", None)
    )
    assert [p.name for p in result.pins] == ["top.bak", "top.bak", "top", "top"]


def test_original_master_mapping_equal_counts_common_names_and_single_different_names():
    assert layer_pairs(
        ("Light", "Bold"), ("Bold", "Other"), "*All masters*", "*All masters*"
    ) == (("Bold", "Bold"),)
    assert layer_pairs(("Light",), ("Other",), "*All masters*", "*All masters*") == (
        ("Light", "Other"),
    )
    assert layer_pairs(("Light", "Bold"), ("Other",), "Bold", "Other") == (
        ("Bold", "Other"),
    )
    with pytest.raises(ValueError, match="Unequal"):
        layer_pairs(("Light", "Bold"), ("Other",), "*All masters*", "*All masters*")


@pytest.mark.parametrize("value", [-1, 21, 1.5])
def test_invalid_angle_refuses_the_whole_plan(value):
    with pytest.raises(ValueError, match="integer"):
        copy_layer((pin(1),), (), 1, 1, Options(angle=value))


@pytest.mark.parametrize(
    "source_width,destination_width", [(float("nan"), 1), (1, float("inf"))]
)
def test_nonfinite_width_refuses(source_width, destination_width):
    with pytest.raises(ValueError, match="finite"):
        copy_layer((), (), source_width, destination_width, Options())


def test_nonfinite_source_and_transformed_coordinates_are_not_silently_clamped():
    with pytest.raises(ValueError, match="coordinates"):
        copy_layer((pin(1, x=float("inf")),), (), 1, 1, Options())
    with pytest.raises(ValueError, match="Transformed"):
        # An integer-nonzero width is required: subunit widths deliberately
        # follow the original absolute fallback after getAdvance truncation.
        copy_layer((pin(1, x=1e308),), (), 1, 1e308, Options(relative=True))
    with pytest.raises(ValueError, match="conflicting"):
        copy_layer((pin(1),), (pin(1, x=7),), 1, 1, Options())
    with pytest.raises(ValueError, match="no available"):
        layer_pairs((), (), "*All masters*", "*All masters*")


def test_italic_zero_and_python_ties_even_apply_after_literal_proportion():
    assert (
        copy_layer((pin(1, y=12.5),), (), 2, 4, Options(italic=True, angle=0)).pins[0].x
        == 25.125
    )
    expected = 25.125 + round(-22.5 * math.tan(math.radians(20)))
    assert (
        copy_layer((pin(1, y=-22.5),), (), 2, 4, Options(italic=True, angle=20))
        .pins[0]
        .x
        == expected
    )
