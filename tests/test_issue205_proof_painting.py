# this_file: tests/test_issue205_proof_painting.py
"""Complete proof and master painter output, including missing data and failures."""

from types import SimpleNamespace as NS

import pytest
from issue205_painting import (
    QtCore,
    QtGui,
    painting as painting,
    render,
    legacy_qt as legacy_qt,
)


def test_proof_grid_when_missing_slots_then_labels_advances_and_real_paths_match(
    painting,
):
    view = painting.own(painting.modules["proof"].Grid())
    view.set_content(
        [("A", [("Regular", painting.path, 500), ("Missing", None, 0)])],
        ["Regular", "Missing"],
        (-200, 800),
        120,
    )
    result = render(view)
    assert result.labels == ["Regular", "Missing", "A", "500", "–"]
    assert len(result.paths) == view.painted == 1
    assert result.paths[0] == painting.path
    assert view.minimumHeight() == 172
    view.set_content([], [], (-200, 800), 120)
    assert render(view).labels == [] and view.painted == 0


def test_proof_rows_and_waterfall_when_populated_then_all_sizes_and_missing_boxes_draw(
    painting,
):
    module = painting.modules["proof"]
    rows = painting.own(module.MasterRows())
    rows.set_content(
        [("Regular", [(painting.path, 500), (None, 200)], 700)], 40, 1000, (-200, 800)
    )
    result = render(rows)
    assert result.labels == ["Regular  ·  700 units"] and result.paths == [
        painting.path
    ]
    assert len(result.lines) == 1
    rows.set_content([], 40, 1000, (-200, 800))
    assert render(rows).paths == []
    waterfall = painting.own(module.WaterfallView())
    waterfall.set_content([(painting.path, 500), (None, 200)], [12, 48], 1000, 800)
    result = render(waterfall)
    assert result.labels == ["12", "48"]
    assert (
        result.paths == [painting.path, painting.path] and waterfall.width_units == 700
    )
    waterfall.set_content([], [], 1000, 800)
    assert render(waterfall).labels == [] and waterfall.minimumHeight() == 16


@pytest.mark.parametrize("count", [1, 3])
def test_master_charts_when_partial_series_then_master_glyph_labels_and_paths_are_complete(
    painting, count
):
    module = painting.modules["masters"]
    chart = painting.own(module.LineChart())
    assert render(chart).labels == []
    chart.masters = [f"M{i}" for i in range(count)]
    chart.series = [("A", [500] * count), ("B", [None] * count), ("C", [0] * count)]
    result = render(chart)
    assert set(chart.masters + ["A", "C"]) <= set(result.labels)
    assert "B" not in result.labels and result.lines
    assert result.image.pixelColor(0, 0) == chart.palette.color(QtGui.QPalette.Base)
    bars = painting.own(module.BarChart())
    assert render(bars).labels == []
    bars.masters, bars.groups = (
        ["Regular", "Bold"],
        [("A", [0, 1000]), ("B", [500, 800])],
    )
    result = render(bars)
    assert {"Regular", "Bold", "A", "B"} <= set(result.labels)
    assert (
        len(module.series_colors(bars, 5))
        == len({c.rgb() for c in module.series_colors(bars, 5)})
        == 5
    )
    seen = []
    chart.report = seen.append
    chart.report_error("owned failure")
    assert (
        seen == ["Drawing failed: owned failure"]
        and chart._paint_error == "owned failure"
    )


@pytest.mark.parametrize(
    "failure", ["before", "inactive", "draw", "end", "hook", "success"]
)
def test_paint_boundary_when_callbacks_or_painter_fail_then_error_is_contained_and_end_is_exact(
    painting, monkeypatch, failure
):
    module = painting.modules["proof"]
    view = painting.own(module.Grid())
    calls = []

    def boom():
        raise ValueError("owned failure")

    class FakePainter:
        def __init__(self, widget):
            calls.append("create")

        def isActive(self):
            return failure != "inactive"

        def end(self):
            calls.append("end")
            return failure != "end"

    monkeypatch.setattr(module.QtGui, "QPainter", FakePainter)
    view.before_draw = boom if failure == "before" else None
    view.draw = (
        lambda painter: boom() if failure in {"draw", "hook"} else calls.append("draw")
    )
    view.on_error = (lambda error: boom()) if failure == "hook" else calls.append
    view.paintEvent(None)
    assert calls.count("end") == (0 if failure == "before" else 1)
    assert bool(view.paint_error) is (failure != "success")
    if failure == "hook":
        assert "error hook" in view.paint_error
    if failure == "inactive":
        assert "draw" not in calls
    chart = painting.own(painting.modules["masters"].LineChart())
    chart.draw = lambda painter: calls.append("chart")
    chart.paintEvent(None)
    assert chart._paint_error == chart.paint_error
