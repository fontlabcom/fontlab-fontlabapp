# this_file: tests/test_point_counts_native.py
"""Owned native-shaped records exercise the real shared selection provider."""

from types import SimpleNamespace as NS

import pytest
import test_layer_selection

import fontlabapp.contours.point_counts.native as api
from fontlabapp.contours.point_counts.model import Counts

source = test_layer_selection.source


def contour(kinds, closed=False, ident=100):
    nodes = [
        NS(
            id=i,
            isNull=False,
            isOff=lambda k=k: k == "off",
            isCurve=lambda k=k: k == "control",
            isOn=lambda k=k: k == "on",
        )
        for i, k in enumerate(kinds)
    ]
    return NS(id=ident, closed=closed, nodes=lambda: nodes)


@pytest.fixture
def domain(source):
    source.glyph.layers = [source.bold, source.regular]
    for layer in source.glyph.layers:
        layer.isValid = True
        layer.isMaskLayer = layer.isService = False
        layer.shapes = []
    return source


def shape(paths=(), component=False, composite=False):
    return NS(id=40, isComponent=component, isComposite=composite, contours=paths)


@pytest.mark.parametrize(
    "kinds,closed,expected",
    [
        ([], False, Counts(0, 0, 0, 1)),
        (["on", "on"], False, Counts(2, 0, 0, 1)),
        (["on", "control", "control", "on"], False, Counts(1, 1, 2, 1)),
        (["on", "off", "on"], False, Counts(1, 1, 1, 1)),
        (["on", "off"], True, Counts(0, 1, 1, 1)),
        (["off", "off"], True, Counts(0, 0, 2, 1)),
        (["on", "off"], False, Counts(1, 0, 1, 1)),
    ],
)
def test_open_closed_cubic_quadratic_and_empty_paths(kinds, closed, expected):
    count, state = api._nodes(contour(kinds, closed), float("inf"))
    assert count == expected
    assert state[1] == closed


def test_all_foreground_layers_native_order_empty_layers_and_editor_repeats(domain):
    domain.workspace.activeFontPanel = None
    auxiliary = NS(
        id=14,
        name="Auxiliary",
        isValid=True,
        isMaskLayer=False,
        isService=False,
        shapes=[shape([contour(["on", "off", "on"]), contour([])])],
    )
    mask = NS(id=15, name="Mask", isValid=True, isMaskLayer=True, isService=False)
    service = NS(id=16, name="Service", isValid=True, isMaskLayer=False, isService=True)
    domain.glyph.layers += [auxiliary, mask, service]
    domain.bold.shapes = [shape(component=True)]
    groups = api.capture()
    assert len(groups) == 3 and groups[0] == groups[1] == groups[2]
    assert [layer.name for layer in groups[0].layers] == [
        "Bold",
        "Regular",
        "Auxiliary",
    ]
    assert groups[0].layers[0].counts == Counts(0, 0, 0, 0)
    assert groups[0].layers[-1].counts == Counts(1, 1, 1, 2)
    assert "3 points" in api.render(groups)


@pytest.mark.parametrize("problem", ["invalid", "nested", "unknown", "null"])
def test_failed_native_records_never_publish_a_valid_prefix(domain, problem):
    path = contour(["on", "on"])
    domain.regular.shapes = [shape([path])]
    if problem == "invalid":
        domain.regular.isValid = False
    if problem == "nested":
        domain.regular.shapes[0].isComposite = True
    if problem == "unknown":
        path.nodes()[1].isOn = lambda: False
    if problem == "null":
        path.nodes()[1].isNull = True
    with pytest.raises(ValueError):
        api.capture()


@pytest.mark.parametrize("field", ["id", "name", "isNull", "package"])
def test_selected_glyph_identity_changes_refuse(domain, monkeypatch, field):
    original = api.selection.capture

    def select(deadline):
        selected = original(deadline)
        setattr(
            domain.glyph,
            field,
            {"id": 55, "name": "changed", "isNull": True, "package": NS(id=66)}[field],
        )
        return selected

    monkeypatch.setattr(api.selection, "capture", select)
    with pytest.raises(ValueError, match="identity changed"):
        api.capture()


@pytest.mark.parametrize("field", ["id", "name", "isNull"])
def test_selected_layer_identity_changes_refuse(domain, monkeypatch, field):
    original = api.selection.capture

    def select(deadline):
        selected = original(deadline)
        setattr(
            domain.regular, field, {"id": 55, "name": "changed", "isNull": True}[field]
        )
        return selected

    monkeypatch.setattr(api.selection, "capture", select)
    with pytest.raises(ValueError, match="identity changed"):
        api.capture()


def test_empty_selection_refuses_without_fallback(domain):
    domain.legacy.Selected = lambda index: False
    with pytest.raises(ValueError, match="Select glyph"):
        api.capture()


@pytest.mark.parametrize("drift", ["node", "layer", "context", "selection"])
def test_double_read_and_final_context_fence_reject_drift(domain, monkeypatch, drift):
    path = contour(["on", "off", "on"])
    domain.regular.shapes = [shape([path])]
    original = api.selection.capture
    calls = []

    def select(deadline):
        calls.append(1)
        if len(calls) == 2:
            if drift == "node":
                path.nodes()[1].id += 1
            if drift == "layer":
                domain.glyph.layers.reverse()
            if drift == "selection":
                domain.legacy.Selected = lambda index: False
        return original(deadline)

    monkeypatch.setattr(api.selection, "capture", select)
    if drift == "context":
        monkeypatch.setattr(
            api.selection, "document_context", lambda deadline: ("changed",)
        )
    with pytest.raises(ValueError, match="changed"):
        api.capture()


def test_deadline_before_nodes_and_after_final_fence_prevents_partial_result(
    domain, monkeypatch
):
    with pytest.raises(TimeoutError):
        api._nodes(contour(["on"]), 0)
    with pytest.raises(TimeoutError):
        api._layer(domain.regular, 0)
    clock = [0]
    monkeypatch.setattr(api, "monotonic", lambda: clock[0])
    original = api.selection.document_context

    def context(deadline):
        result = original(float("inf"))
        clock[0] = 10
        return result

    # Provider uses its own real clock; keep its deadlines independent for this fence test.
    original_capture = api.selection.capture
    monkeypatch.setattr(
        api.selection, "capture", lambda deadline: original_capture(float("inf"))
    )
    monkeypatch.setattr(api.selection, "document_context", context)
    with pytest.raises(TimeoutError):
        api.capture()
