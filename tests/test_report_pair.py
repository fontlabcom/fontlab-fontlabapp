# this_file: tests/test_report_pair.py
"""Full original reporting contracts and explicit false-verdict repairs."""

import pytest
from fontlabapp.masters.layers.compatibility.model import GlyphLayers, Layer
from fontlabapp.masters.node_report.model import compare_path_nodes, render
from fontlabapp.contours.svg_path.model import render as svg


def test_master_report_when_counts_equal_types_differ_then_no_false_compatible():
    group = GlyphLayers(
        "a",
        (
            Layer("Regular", (("line", "curve", "offcurve"),)),
            Layer("Bold", (("curve", "line", "offcurve"),)),
        ),
    )
    text = render((group,))
    assert "Nodes: 2 (Lines: 1 · Curves: 1)" in text
    assert "Handles: 1" in text and "Total Points: 3" in text
    assert "First difference at node #1: Expected LINE, Found CURVE" in text
    assert "fully compatible" not in text
    assert "not compatible with the reference master" in text


@pytest.mark.parametrize(
    "before,after,expected",
    [
        (((),), (), "missing in tested master"),
        ((), ((),), "missing in reference master"),
    ],
)
def test_master_report_when_path_missing_either_way_then_diagnosis(
    before, after, expected
):
    assert expected in render(
        (GlyphLayers("x", (Layer("A", before), Layer("B", after))),)
    )


def test_master_report_when_later_masters_equal_each_other_then_compare_first():
    text = render(
        (
            GlyphLayers(
                "x",
                (
                    Layer("A", (("line",),)),
                    Layer("B", (("qcurve", "offcurve"),)),
                    Layer("C", (("qcurve", "offcurve"),)),
                ),
            ),
        )
    )
    assert text.count("Expected (1, 0), Found (1, 1)") == 2
    assert "Master: C" in text
    assert "Found QCURVE" in text


def test_master_report_when_empty_paths_or_single_master_then_complete_counts():
    text = render((GlyphLayers("space", (Layer("A", ()),)),))
    assert "Paths: 0" in text and "fully compatible" in text
    with pytest.raises(ValueError, match="master"):
        render((GlyphLayers("x", ()),))
    with pytest.raises(ValueError, match="selected"):
        render(())


@pytest.mark.parametrize(
    "left,right,want",
    [
        (("line",), ("line",), None),
        ((), ("curve",), (0, None, "curve")),
        (("line",), (), (0, "line", None)),
        (("line",), ("curve",), (0, "line", "curve")),
    ],
)
def test_compare_path_nodes_when_unequal_then_first_difference(left, right, want):
    assert compare_path_nodes(left, right) == want


def test_svg_when_lines_cubics_and_empty_paths_then_original_print_contract():
    paths = ((((0, -2.5), (10, 20)), ((10, 20), (11, 21), (12, 22), (13, 23))), ())
    assert svg(paths) == "M 0 -2.5\nL 10 20\nC 11 21 12 22 13 23\nZ\n\nZ\n\n"
    assert svg(()) == ""


@pytest.mark.parametrize(
    "segment",
    [(), ((0, 0),), ((0, 0), (1, 1), (2, 2)), ((0, 0), (1, 1), (2, 2), (3, 3), (4, 4))],
)
def test_svg_when_unsupported_segment_then_whole_report_refused(segment):
    with pytest.raises(ValueError, match="line or cubic"):
        svg(((((0, 0), (1, 1)), segment),))


@pytest.mark.parametrize(
    "point", [(float("nan"), 1), (1, float("inf")), (True, 1), ("1", 1)]
)
def test_svg_when_invalid_coordinate_then_whole_report_refused(point):
    with pytest.raises(ValueError, match="finite"):
        svg((((point, (1, 1)),),))
