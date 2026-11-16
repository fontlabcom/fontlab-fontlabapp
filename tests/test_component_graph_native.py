# this_file: tests/test_component_graph_native.py
"""SDK-shaped source fences; no original or live FontLab code is executed."""

from concurrent.futures import ThreadPoolExecutor
from time import monotonic
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from fontlabapp.components.graph import native as api
from fontlabapp.glyphs.catalog import native as context


class Glyph(NS):
    @property
    def fgGlyph(self):
        raise AssertionError("destructive cache getter forbidden")


@pytest.fixture
def source(monkeypatch):
    package = NS(id=2, fgId=20, master="Regular", isNull=False)
    font = NS(id=20, glyphs=[NS(id=1, name="無"), NS(id=2, name="a.alt")])
    shapes = [
        NS(id=30, isComponent=True, shapeData=NS(componentGlyph="無")),
        NS(id=31, isComponent=False),
        NS(id=32, isComponent=True, shapeData=NS(componentGlyph="無")),
    ]
    layers = {
        1: NS(id=101, isNull=False, shapes=[]),
        2: NS(id=102, isNull=False, shapes=shapes),
    }
    glyphs = {
        g.id: Glyph(
            id=200 + g.id,
            fgGlyphId=g.id,
            name=g.name,
            package=package,
            isNull=False,
            isValid=True,
            findLayer=lambda master, i=g.id: layers[i],
        )
        for g in font.glyphs
    }
    package.findFgId = lambda i: glyphs[i]
    workspace = NS(currentPackage=package)
    module = NS(
        flWorkspace=NS(instance=lambda: workspace), CurrentFont=Mock(return_value=font)
    )
    monkeypatch.setattr(context, "_native", lambda n: module)
    return NS(**locals())


def test_complete_whole_font_order_repeated_components_and_no_geometry_cache(source):
    graph = api.capture(deadline=monotonic() + 2)
    assert graph.names == ("無", "a.alt") and graph.edges == ((1, 0), (1, 0))
    source.font.glyphs = []
    assert api.capture(deadline=monotonic() + 2).names == ()


@pytest.mark.parametrize(
    "problem",
    [
        "duplicate",
        "empty",
        "missing",
        "null",
        "invalid",
        "owner",
        "identity",
        "name",
        "missing-layer",
        "null-layer",
        "role",
        "base",
        "empty-base",
        "native-duplicate",
    ],
)
def test_invalid_snapshot_never_publishes_partial_graph(source, problem):
    g = source.glyphs[1]
    if problem == "duplicate":
        source.font.glyphs.append(source.font.glyphs[0])
    elif problem == "empty":
        source.font.glyphs[0].name = ""
    elif problem == "missing":
        source.glyphs[1] = None
    elif problem == "null":
        g.isNull = True
    elif problem == "invalid":
        g.isValid = False
    elif problem == "owner":
        g.package = NS(id=99)
    elif problem == "identity":
        g.fgGlyphId = 99
    elif problem == "name":
        g.name = "changed"
    elif problem == "missing-layer":
        source.layers[1] = None
    elif problem == "null-layer":
        source.layers[1].isNull = True
    elif problem == "role":
        source.shapes[0].isComponent = None
    elif problem == "base":
        source.shapes[0].shapeData.componentGlyph = None
    elif problem == "empty-base":
        source.shapes[0].shapeData.componentGlyph = ""
    else:
        source.glyphs[2].id = g.id
    with pytest.raises(ValueError):
        api.capture(deadline=monotonic() + 2)


def test_context_change_shape_mutation_deadline_and_thread_refuse(source):
    def change():
        source.shapes[0].shapeData.componentGlyph = "different"
        return source.font

    source.module.CurrentFont.side_effect = [source.font, change(), source.font]
    # A reader changes the second shape observation, not only initial fixture state.
    calls = 0

    def current():
        nonlocal calls
        calls += 1
        if calls == 2:
            source.shapes[0].shapeData.componentGlyph = "changed-again"
        return source.font

    source.module.CurrentFont.side_effect = current
    with pytest.raises(ValueError, match="changed"):
        api.capture(deadline=monotonic() + 2)
    with pytest.raises(TimeoutError):
        api.capture(deadline=0)
    with (
        ThreadPoolExecutor(max_workers=1) as pool,
        pytest.raises(RuntimeError, match="main UI"),
    ):
        pool.submit(api.capture, deadline=monotonic() + 2).result()
