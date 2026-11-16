# this_file: tests/test_interpolation.py
# SPDX-License-Identifier: Apache-2.0
"""Original endpoint geometry, node compatibility and complete path construction."""

from copy import deepcopy
from importlib import import_module
from types import SimpleNamespace as NS

import pytest

api = import_module("fontlabapp.masters.interpolation.model")


@pytest.mark.parametrize("t", [0, 0.25, 0.5, 0.8, 1])
def test_blend_preserves_every_node_flag_endpoints_and_input_data(t):
    a = [[(0, 10, True), (5, 20, False), (10, 10, True)]]
    b = [[(20, 30, True), (15, 40, False), (30, 30, True)]]
    original = deepcopy((a, b))
    assert api.problem(a, b) is None
    assert api.blend(a, b, t) == [
        [
            (20 * t, 10 + 20 * t, True),
            (5 + 10 * t, 20 + 20 * t, False),
            (10 + 20 * t, 10 + 20 * t, True),
        ]
    ]
    assert (a, b) == original


def test_incompatible_contours_nodes_and_node_kinds_are_diagnosed():
    assert api.problem([], [[]]) == "0 vs 1 contours"
    assert (
        api.problem([[(0, 0, True)]], [[]])
        == "contour 1: 1 vs 0 nodes or different node types"
    )
    assert api.problem([[(0, 0, True)]], [[(0, 0, False)]]) is not None
    assert api.blend([], [], 0.5) == []


def test_layer_lookup_excludes_native_null_and_outline_places_shape_transform(
    monkeypatch,
):
    node = NS(x=10, y=20, isOn=lambda: False)
    contour = NS(nodes=lambda: [node])
    transform = NS(
        isIdentity=lambda: False,
        map=lambda p: NS(x=lambda: p[0] + 30, y=lambda: p[1] - 5),
    )
    layer = NS(isNull=False, shapes=[NS(transform=transform, contours=[contour])])
    glyph = NS(findLayer=lambda m: layer if m == "Light" else NS(isNull=True))
    monkeypatch.setattr(
        api, "_native", lambda _: NS(QtCore=NS(QPointF=lambda x, y: (x, y)))
    )
    assert api.master_layers(glyph, ["Light", "Missing"]) == {"Light": layer}
    assert api.node_points(contour) == [(10, 20, False)]
    assert api.outline(layer) == [[(40, 15, False)]]


def test_path_rotates_first_oncurve_keeps_quadratic_cubic_and_closes(monkeypatch):
    calls = []

    class Path:
        def moveTo(self, *values):
            calls.append(("move", *values))

        def lineTo(self, *values):
            calls.append(("line", *values))

        def quadTo(self, *values):
            calls.append(("quad", *values))

        def cubicTo(self, *values):
            calls.append(("cubic", *values))

        def closeSubpath(self):
            calls.append(("close",))

    monkeypatch.setattr(api, "_native", lambda _: NS(QtGui=NS(QPainterPath=Path)))
    api.outline_path(
        [[(1, 1, False), (2, 2, True), (3, 3, False), (4, 4, True), (5, 5, False)]]
    )
    assert calls == [
        ("move", 2, 2),
        ("quad", 3, 3, 4, 4),
        ("cubic", 5, 5, 1, 1, 2, 2),
        ("close",),
    ]
    calls.clear()
    api.outline_path([[(1, 1, False)]])
    assert calls == []


def test_fit_transform_handles_empty_tiny_and_ordinary_draw_areas(monkeypatch):
    monkeypatch.setattr(
        api, "_native", lambda _: NS(QtGui=NS(QTransform=lambda *args: args))
    )
    rect = NS(width=lambda: 100, height=lambda: 200, x=lambda: 10, y=lambda: -20)
    assert api.fit_transform(rect, 232, 432) == (2, 0, 0, -2, -4, 376)
    assert api.fit_transform(rect, 10, 10) == ()
    rect.width = lambda: 0
    assert api.fit_transform(rect, 232, 432) == ()


def test_selected_names_retains_original_falsey_current_glyph_fallback(monkeypatch):
    class Current:
        name = "E"

        def __bool__(self):
            return False

    monkeypatch.setattr(api, "_selected_names", list)
    monkeypatch.setattr(api, "_native", lambda _: NS(CurrentGlyph=lambda: Current()))
    assert api.selected_names() == ["E"]
    monkeypatch.setattr(api, "_selected_names", lambda: ["O", "a"])
    assert api.selected_names() == ["O", "a"]


def test_selected_names_keeps_original_current_fallback_after_font_window_read_error(
    monkeypatch,
):
    def unavailable():
        raise RuntimeError("owned Font-window read failure")

    monkeypatch.setattr(api, "_selected_names", unavailable)
    monkeypatch.setattr(api, "_native", lambda _: NS(CurrentGlyph=lambda: NS(name="H")))
    assert api.selected_names() == ["H"]
