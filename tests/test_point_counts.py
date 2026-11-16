# this_file: tests/test_point_counts.py
"""Original report ordering/markers and explicit quadratic-count correction."""

from fontlabapp.contours.point_counts.model import (
    Counts,
    GlyphCount,
    LayerCount,
    render,
)


def test_original_two_previous_counts_marker_and_repeat_groups_are_preserved():
    layers = tuple(
        LayerCount(str(i), Counts(value, 0, 0, 1))
        for i, value in enumerate((10, 12, 10, 15, 12))
    )
    group = GlyphCount("A", layers)
    text = render((group, group))
    expected = (
        "---------- A ----------\n"
        "10 points - 10 lines, 0 curves, 0 offcurves, 1 paths - 0\n"
        "? 12 points - 12 lines, 0 curves, 0 offcurves, 1 paths - 1\n"
        "10 points - 10 lines, 0 curves, 0 offcurves, 1 paths - 2\n"
        "? 15 points - 15 lines, 0 curves, 0 offcurves, 1 paths - 3\n"
        "? 12 points - 12 lines, 0 curves, 0 offcurves, 1 paths - 4\n\n"
    )
    assert text == expected * 2
    assert render(()) == ""
    assert render((GlyphCount("empty", ()),)) == "---------- empty ----------\n\n"


def test_zero_empty_paths_and_all_point_types_keep_exact_totals():
    assert Counts(0, 0, 0, 2).points == 0
    counts = Counts(2, 3, 6, 2)
    assert counts.points == 11
    assert "11 points - 2 lines, 3 curves, 6 offcurves, 2 paths" in render(
        (GlyphCount("é", (LayerCount("Auxiliary", counts),)),)
    )
