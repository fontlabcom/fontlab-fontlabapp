# this_file: tests/test_anchor_coordinates.py
# SPDX-License-Identifier: Apache-2.0
"""Original preview arithmetic and raw untouched-axis behavior."""

from types import SimpleNamespace as NS

import pytest
from test_anchor_edit import owned as owned  # noqa: PLC0414 - shared pytest fixture

import fontlabapp.anchors.coordinates.model as api


def test_center_advance_ink_italic_and_empty_box(owned):
    _, layer = owned.glyph()
    assert api.parse_names(" top; bottom, ,top ") == ["top", "bottom", "top"]
    assert api.target_x(layer, "advance", 0.5, -45, 100) == pytest.approx(400)
    assert api.target_x(layer, "ink", 0.3, -45, 100) == pytest.approx(-50)
    layer.boundingBox.width, layer.boundingBox.height = lambda: 0, lambda: 0
    assert api.target_x(layer, "ink", 0.5, 0, 100) is None
    assert api.center_plan(layer, ["missing"], "advance", 0.5, 0) == []


@pytest.mark.parametrize("value,result", [(-15, -10), (-5, 0), (5, 10), (15, 20)])
def test_snap_uses_original_negative_half_up(value, result):
    assert api.snap(value, 10) == result


@pytest.mark.parametrize("value", [0, -1, float("nan"), "10", None])
def test_bad_step_refuses(value):
    with pytest.raises(ValueError):
        api.snap(12, value)


def test_original_rounded_previews_and_raw_untouched_axis(owned, monkeypatch):
    g, layer = owned.glyph()
    assert api.center_plan(layer, ["top"], "advance", 0.5, 0) == [
        ("top", (13, 28), 300)
    ]
    assert api.round_plan(layer, 10, True, False, []) == [("top", (13, 28), (10, 28))]
    assert api.metric_plan(layer, ["top"], 520) == [("top", (13, 28), 520)]
    monkeypatch.setattr(
        api, "_native", lambda _: NS(FontMetrics=lambda p, m: NS(xHeight=499.5))
    )
    assert api.metric_value(owned.package, "Regular", None) == 0
    assert api.metric_value(owned.package, "Regular", "xHeight") == 500
    assert api.run_round(
        [g], ["Regular"], 10, True, False, [], package=owned.package
    ) == {"anchors": 1, "layers": 1, "skipped": []}
    assert layer.anchors[0].point.y() == 27.75
    assert (
        api.run_center(
            [g], ["Regular"], ["top"], "advance", 0.5, 0, package=owned.package
        )["anchors"]
        == 1
    )
    assert layer.anchors[0].point.y() == 27.75
    assert (
        api.run_metrics(owned.package, [g], ["Regular"], ["top"], "xHeight", 20)[
            "anchors"
        ]
        == 1
    )
    assert (layer.anchors[0].point.x(), layer.anchors[0].point.y()) == (300, 520)


def test_noop_auto_skip_missing_and_unknown_master(owned):
    g, _ = owned.glyph(points=(("top", 10.2, 20.3),))
    auto, _ = owned.glyph("auto", points=(("top", 13, 27),), auto=True)
    assert api.run_round(
        [g, auto], ["Regular", "Bold"], 10, True, True, [], package=owned.package
    ) == {"anchors": 0, "layers": 0, "skipped": ["auto/Regular"]}
    assert not owned.events
    with pytest.raises(ValueError, match="Masters"):
        api.run_center([g], ["bad"], ["top"], "advance", 0.5, 0, package=owned.package)


@pytest.mark.parametrize(
    "reference,fraction,angle",
    [("bad", 0.5, 0), ("ink", float("inf"), 0), ("advance", 0.5, "bad")],
)
def test_bad_center_input_refuses(owned, reference, fraction, angle):
    _, layer = owned.glyph()
    with pytest.raises(ValueError):
        api.target_x(layer, reference, fraction, angle, 100)


def test_both_axes_enabled_preserves_raw_axis_without_a_grid_move(owned):
    g, layer = owned.glyph(points=(("top", 13.25, 20.3),))
    api.run_round([g], ["Regular"], 10, True, True, [], package=owned.package)
    assert (layer.anchors[0].point.x(), layer.anchors[0].point.y()) == (10, 20.3)


def test_round_name_filter_and_empty_center_and_metric_validation(owned):
    _, layer = owned.glyph()
    assert api.round_plan(layer, 10, True, True, ["missing"]) == []
    layer.boundingBox.width, layer.boundingBox.height = lambda: 0, lambda: 0
    assert api.center_plan(layer, ["top"], "ink", 0.5, 0) == [("top", (13, 28), None)]
    with pytest.raises(ValueError, match="Metric"):
        api.metric_value(owned.package, "Regular", "unknown")


def test_duplicate_name_with_one_aligned_pin_refuses_before_mutation(owned):
    g, layer = owned.glyph(points=(("top", 10, 20), ("top", 13, 24)))
    with pytest.raises(ValueError, match="Duplicate"):
        api.run_round([g], ["Regular"], 10, True, True, [], package=owned.package)
    assert not owned.events and layer.anchors[1].point.x() == 13
