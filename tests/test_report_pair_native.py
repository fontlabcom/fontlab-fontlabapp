# this_file: tests/test_report_pair_native.py
"""Native-shaped read fences, full master selection and SVG source boundaries."""

from time import monotonic
from types import SimpleNamespace as NS

import fontlabapp.masters.node_report.native as masters
import fontlabapp.contours.svg_path.native as svg
import pytest
from fontlabapp.masters.layers.compatibility.model import GlyphLayers, Layer


def selection(layer=None, context=(1, "Regular")):
    return NS(
        occurrences=(NS(layer=layer),) if layer is not None else (), context=context
    )


def install(monkeypatch, api, selections):
    stream = iter(selections)
    monkeypatch.setattr(api.selection, "capture", lambda deadline: next(stream))
    monkeypatch.setattr(
        api.selection, "document_context", lambda deadline: (1, "Regular")
    )


def point(x, y):
    return NS(x=lambda: x, y=lambda: y)


def source(segments=(), tt=False, closed=False):
    contour = NS(id=2, closed=closed, isTT=tt, segments=lambda: segments)
    transform = NS(
        map=lambda p: p,
        **{
            f"m{i}{j}": lambda i=i, j=j: int(i == j)
            for i in (1, 2, 3)
            for j in (1, 2, 3)
        },
    )
    shape = NS(
        transform=transform,
        id=3,
        isComponent=False,
        isComposite=False,
        contours=[contour],
    )
    return NS(shapes=[shape]), contour, shape


def test_svg_capture_when_mixed_segments_then_first_layer_and_components_omitted(
    monkeypatch,
):
    layer, contour, shape = source(
        [
            [point(-1, 2), point(3, 4)],
            [point(3, 4), point(5, 6), point(7, 8), point(9, 10)],
        ]
    )
    layer.shapes.append(NS(id=4, isComponent=True))
    current = selection(layer)
    current.occurrences += (NS(layer=NS(shapes="must not read")),)
    install(monkeypatch, svg, [current] * 3)
    assert svg.capture() == ((((-1, 2), (3, 4)), ((3, 4), (5, 6), (7, 8), (9, 10))),)
    assert shape.isComponent is False and contour.closed is False


@pytest.mark.parametrize(
    "mode,match",
    [
        ("role", "role"),
        ("generated", "Generated"),
        ("topology", "topology"),
        ("quadratic", "line or cubic"),
    ],
)
def test_svg_read_when_unsupported_then_whole_capture_fails(mode, match):
    layer, contour, shape = source([[point(0, 0), point(1, 1), point(2, 2)]])
    if mode == "role":
        shape.isComponent = 1
    if mode == "generated":
        shape.isComposite = True
    if mode == "topology":
        contour.closed = 1
    with pytest.raises(ValueError, match=match):
        svg._read(layer, monotonic() + 2)


def test_svg_read_when_tt_line_or_empty_then_keep_original_z_policy():
    layer, _, _ = source([[point(0, 0), point(1, 1)]], tt=True)
    assert len(svg._read(layer, monotonic() + 2)[0]) == 1
    empty, _, _ = source()
    assert svg._read(empty, monotonic() + 2)[0] == ((),)
    with pytest.raises(TimeoutError):
        svg._read(layer, 0)


@pytest.mark.parametrize(
    "kind", ["empty", "secondempty", "stale", "changedpaths", "context"]
)
def test_svg_capture_when_source_changes_then_no_prefix(monkeypatch, kind):
    layer, _contour, _ = source([[point(0, 0), point(1, 1)]])
    current = selection(layer)
    if kind == "empty":
        seq = [selection()]
    elif kind == "secondempty":
        seq = [current, selection()]
    elif kind == "stale":
        seq = [current, current, selection(NS(shapes=[]))]
    else:
        seq = [current] * 3
    install(monkeypatch, svg, seq)
    if kind == "changedpaths":
        calls = iter([((), ()), ((((),),), ())])
        monkeypatch.setattr(svg, "_read", lambda *args: next(calls))
    if kind == "context":
        monkeypatch.setattr(
            svg.selection, "document_context", lambda deadline: ("changed",)
        )
    with pytest.raises(ValueError):
        svg.capture()


def rows(missing=False):
    layers = (
        Layer("Bold", (("curve",),)),
        Layer("Regular", (("line",),)),
        Layer("Aux", ()),
    )
    if missing:
        layers = layers[:1]
    group = GlyphLayers("a", layers)
    return ((5, ("Regular", "Bold"), (), group),) * 2


def test_master_capture_when_repeats_and_auxiliary_then_unique_master_order(
    monkeypatch,
):
    current = selection(object())
    install(monkeypatch, masters, [current] * 3)
    monkeypatch.setattr(masters, "_read", lambda *args: rows())
    report = masters.capture()
    assert len(report) == 1 and [l.name for l in report[0].layers] == [
        "Regular",
        "Bold",
    ]


@pytest.mark.parametrize("mode", ["empty", "missing", "stale", "content", "context"])
def test_master_capture_when_invalid_domain_then_no_partial_report(monkeypatch, mode):
    current = selection(object())
    seq = [current] * 3 if mode != "empty" else [selection()]
    if mode == "stale":
        seq = [current, current, selection()]
    install(monkeypatch, masters, seq)
    monkeypatch.setattr(masters, "_read", lambda *args: rows(mode == "missing"))
    if mode == "content":
        stream = iter([rows(), ()])
        monkeypatch.setattr(masters, "_read", lambda *args: next(stream))
    if mode == "context":
        monkeypatch.setattr(masters.selection, "document_context", lambda deadline: ())
    with pytest.raises(ValueError):
        masters.capture()


def test_svg_when_shape_transformed_then_layer_coordinates_and_matrix_fence():
    layer, _, shape = source([[point(1, 2), point(3, 4)]])
    shape.transform.map = lambda p: point(p.x() * 2 + 7, p.y() * 3 - 5)
    paths, identities = svg._read(layer, monotonic() + 2)
    assert paths == ((((9, 1), (13, 7)),),)
    assert identities[0] == (3, (1, 0, 0, 0, 1, 0, 0, 0, 1))


def test_svg_when_projective_shape_transform_then_refuse_whole_report():
    layer, _, shape = source([[point(0, 0), point(0, 1), point(1, 1), point(1, 0)]])
    shape.transform.m13 = lambda: 1
    with pytest.raises(ValueError, match="Projective"):
        svg._read(layer, monotonic() + 2)
