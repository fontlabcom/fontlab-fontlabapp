# this_file: tests/test_layer_extrema.py
"""Own extrema values; never execute either third-party source."""

import pytest

from fontlabapp.masters.layers.extrema.model import LayerExtent, choose, render


def test_all_negative_positive_zero_and_unbounded_coordinates_keep_real_extrema():
    rows = (
        LayerExtent("first", "Thin", -12, 0),
        LayerExtent("other", "Bold", -10001, -1),
    )
    result = choose(rows)
    assert result.highest is rows[0] and result.lowest is rows[1]
    rows = (LayerExtent("huge", "Regular", 20000, 30000),)
    assert choose(rows).highest is rows[0] and choose(rows).lowest is rows[0]


def test_stable_ties_and_repeated_winner_keep_both_layer_references():
    rows = (LayerExtent("a", "Thin", -1, 4), LayerExtent("b", "Bold", -1, 4))
    result = choose(rows)
    assert result.highest is rows[0] and result.lowest is rows[0]
    assert result.layers == (("a", "Thin"), ("a", "Thin"))
    assert (
        render(result)
        == "highest: 4\nlowest: -1\n\nHighest: a [Thin]\nLowest: a [Thin]"
    )


@pytest.mark.parametrize(
    "rows",
    [
        (),
        (None,),
        (LayerExtent("", "Regular", 0, 2),),
        (LayerExtent("a", None, 0, 2),),
        (LayerExtent("a", "Regular", float("nan"), 2),),
        (LayerExtent("a", "Regular", 0, float("inf")),),
        (LayerExtent("a", "Regular", 3, 2),),
        (LayerExtent("a", "Regular", False, 2),),
    ],
)
def test_invalid_or_empty_source_never_returns_a_prefix(rows):
    with pytest.raises(ValueError):
        choose(rows)


def test_interrupted_iterable_has_no_partial_result():
    def interrupted():
        yield LayerExtent("a", "Regular", 0, 2)
        raise OSError("unreadable tail")

    with pytest.raises(OSError):
        choose(interrupted())


def test_first_zero_bottom_is_not_replaced_by_later_positive_bottom():
    rows = (
        LayerExtent("first", "Regular", 0, 10),
        LayerExtent("next", "Regular", 5, 6),
    )
    result = choose(rows)
    assert result.lowest is rows[0] and result.highest is rows[0]


def test_finite_large_coordinates_do_not_hit_arbitrary_sentinel_limits():
    row = LayerExtent("huge", "Sketch", -1e308, 1e308)
    result = choose((row,))
    assert result.highest is row and result.lowest is row
