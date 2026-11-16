# this_file: tests/test_issue205_geometry_painting.py
"""Original component, anchor, guide and interpolated geometry reaches real pixels."""

from issue205_painting import (
    QtCore,
    QtGui,
    painting as painting,
    render,
    legacy_qt as legacy_qt,
)
from types import SimpleNamespace as NS
import pytest


def test_component_badges_when_reflowed_then_cards_counts_and_master_markers_are_drawn(
    painting,
):
    module = painting.modules["components.inspect.views"]
    grid = painting.own(module.BadgeGrid())
    assert grid.card_height() == module.DRAW_H + module.LINE_H + 2 * module.PAD
    cards = [
        (
            "A",
            painting.path,
            painting.path.boundingRect(),
            [
                ("Regular", 1, 2, False, False),
                ("Very long master", 3, 4, True, False),
                ("Bold", 0, 1, False, True),
            ],
        )
    ] * 4
    grid.set_cards(cards, 460)
    assert grid.columns == 2 and grid.height == 2 * (grid.card_height() + 8) + 4
    result = render(grid)
    assert len(result.paths) == 4
    assert result.labels.count("A") == 4 and "Very lon…" in result.labels
    assert {"1 comp", "2 cont", "3 comp", "4 cont"} <= set(result.labels)
    grid.resize(900, grid.height)
    grid.resizeEvent(
        QtGui.QResizeEvent(
            QtCore.QSize(900, grid.height), QtCore.QSize(460, grid.height)
        )
    )
    assert grid.columns == 4
    grid.set_cards([], 1)
    assert grid.columns == 1 and render(grid).paths == []


def test_anchor_panels_when_geometry_present_or_missing_then_notes_and_paths_are_complete(
    painting,
):
    module = painting.modules["anchors.inspect.views"]
    cloud = painting.own(module.CloudView())
    assert render(cloud).labels == ["Select glyphs with anchors"]
    cloud.set_panels(
        [
            ("Regular", [painting.path], [("A", 20, 700), ("B", 30, 710)]),
            ("Empty", [], []),
        ]
    )
    result = render(cloud)
    assert result.paths == [painting.path]
    assert "2 anchors\nx 20…30   y 700…710" in result.labels
    assert "no anchors of this name" in result.labels
    attached = painting.own(module.AttachmentView())
    assert render(attached).labels == ["No base / mark pair to show"]
    attached.set_panels(
        [
            ("Regular", painting.path, painting.path, (100, 700), 500, "attached"),
            ("Missing", painting.path, None, None, 500, "missing anchor"),
        ]
    )
    result = render(attached)
    assert len(result.paths) == 3 and {"attached", "missing anchor"} <= set(
        result.labels
    )


def test_guides_when_grid_covers_both_axes_then_exact_lines_and_outline_are_painted(
    painting,
):
    view = painting.own(painting.modules["guides.inspect.views"].GridPreview())
    empty = render(view)
    assert len(empty.lines) == 1 and empty.paths == []
    view.set_content(
        painting.path,
        500,
        [(0, 100, 0, "horizontal"), (250, 0, 90, "vertical")],
        (-200, 800),
    )
    result = render(view)
    assert result.paths == [painting.path] and len(result.lines) == 3
    horizontal, vertical = result.lines[-2:]
    assert horizontal[0].y() == horizontal[1].y()
    assert vertical[0].x() == vertical[1].x()


def test_interpolation_when_mixed_then_endpoint_paths_and_oncurve_nodes_are_drawn(
    painting,
):
    view = painting.own(painting.modules["masters.interpolation.view"].BlendView())
    view.message = "Owned interpolation"
    contours = [[(0, 0, True), (0, 100, False), (200, 100, False), (200, 0, True)]]
    view.a, view.b, view.mix = contours, contours, contours
    result = render(view)
    assert result.labels == ["Owned interpolation"] and len(result.paths) == 3
    assert len(result.dots) == 2 and not view._paint_error
    view.mix, view.message = [], ""
    assert len(render(view).paths) == 2


def test_inspector_geometry_when_fitted_then_curve_commands_and_contour_arrows_match(
    painting,
):
    module = painting.modules["proof.inspectors.views"]
    contours = [
        [(0, 0, True), (0, 50, False), (100, 50, False), (100, 0, True)],
        [(0, 0, True), (25, 100, False), (50, 0, True)],
        [(1, 1, False)],
    ]
    path = module.outline_path(contours)
    assert path.elementCount() > 6 and path.boundingRect().width() == 100
    assert module.fit_transform(QtCore.QRectF(), 300, 200).isIdentity()
    assert module.fit_transform(path.boundingRect(), 1, 1).isIdentity()
    fit = module.fit_transform(path.boundingRect(), 300, 200)
    assert fit.m11() > 0 and fit.m22() < 0
    order = painting.own(module.OrderView())
    assert render(order).labels == []
    info = [
        (0, contours[0], (0, 0), (100, 0), "cw"),
        (1, contours[1], (0, 0), (0, 0), "ccw"),
    ]
    order.columns = [("Regular", info), ("Bold", info)]
    result = render(order)
    assert result.labels == ["Regular", "1", "2", "Bold", "1", "2"]
    assert len(result.paths) == 4 and len(result.lines) == 3
    seen = []
    order.report = seen.append
    order.report_error("owned failure")
    assert (
        seen == ["Drawing failed: owned failure"]
        and order._paint_error == "owned failure"
    )


@pytest.mark.parametrize("numbers", [False, True])
def test_spacing_canvas_when_values_toggle_then_exact_labels_paths_and_boxes_survive(
    painting, numbers
):
    module = painting.modules["proof.inspectors.views"]
    owner = NS(
        rows=[],
        draw_guard=lambda: None,
        paint_report=lambda error: None,
        paint_cleanup=lambda: None,
        empty_message=lambda: "No owned glyphs",
        ascender=800,
        descender=-200,
        show_numbers=NS(isChecked=lambda: numbers),
        show_boxes=NS(isChecked=lambda: numbers),
        path=lambda name: painting.path,
    )
    view = painting.own(module.Canvas(owner))
    assert render(view).labels == ["No owned glyphs"]
    owner.rows = [("A", 0, 500, 10, 20), ("B", 500, 200, None, None)]
    result = render(view)
    assert len(result.paths) == 2
    assert result.labels == (["10", "20"] if numbers else [])
    assert len(result.lines) == 1


def test_owned_painters_when_source_and_cleanup_fail_then_diagnostics_and_callbacks_are_retained(
    painting,
):
    def fail(*args):
        raise ValueError("owned paint failure")

    for name, cls in (
        ("components.inspect.views", "BadgeGrid"),
        ("guides.inspect.views", "GridPreview"),
        ("proof.inspectors.views", "OrderView"),
    ):
        view = painting.own(getattr(painting.modules[name], cls)())
        view.before_draw = fail
        view.failure_cleanup = fail
        view.paintEvent(None)
        assert (
            "owned paint failure" in view.paint_error and "cleanup:" in view.paint_error
        )
    owner = NS(draw_guard=fail, paint_report=lambda text: None, paint_cleanup=fail)
    view = painting.own(painting.modules["proof.inspectors.views"].Canvas(owner))
    view.paintEvent(None)
    assert "cleanup:" in view.paint_error
