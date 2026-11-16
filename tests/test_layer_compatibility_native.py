# this_file: tests/test_layer_compatibility_native.py
"""Owned native-shaped complete all-layer/occurrence reader controls."""

from types import SimpleNamespace as NS

import fontlabapp.masters.layers.compatibility._records as records
import fontlabapp.masters.layers.compatibility.native as api
import pytest
import test_layer_selection
from fontlabapp.masters.layers.compatibility.model import render

source = test_layer_selection.source


def path(kinds=(), closed=False, tt=False):
    return NS(
        id=41,
        closed=closed,
        isTT=tt,
        nodes=lambda: [
            NS(
                id=i,
                isNull=k == "null",
                isOn=lambda k=k: k == "on",
                isOff=lambda k=k: k == "off",
                isCurve=lambda k=k: k == "curve",
            )
            for i, k in enumerate(kinds)
        ],
    )


def shape(paths=(), base=None):
    return NS(
        id=51,
        isComponent=base is not None,
        isComposite=False,
        contours=paths,
        shapeData=NS(componentGlyph=base),
    )


@pytest.fixture
def domain(source):
    source.package.masters = ["Regular", "Bold"]
    for layer in (source.regular, source.bold):
        layer.isValid = True
        layer.isMasterLayer = True
        layer.isMaskLayer = layer.isService = False
        layer.glyph = source.glyph
        layer.shapes = []
        layer.anchors = []
    source.glyph.layers = [source.bold, source.regular]
    return source


@pytest.mark.parametrize(
    "kinds,closed,tt,expected",
    [
        ([], False, False, ()),
        (["on"], False, False, ("line",)),
        (["on", "curve", "on"], False, False, ("line", "offcurve", "curve")),
        (["on", "off", "on"], False, True, ("line", "offcurve", "qcurve")),
        (["on", "curve", "on"], False, True, ("line", "offcurve", "qcurve")),
        (
            ["on", "curve", "on", "off"],
            True,
            False,
            ("offcurve", "curve", "offcurve", "qcurve"),
        ),
        (["off", "off"], True, True, ("offcurve", "offcurve")),
        ([], True, True, ()),
    ],
)
def test_native_nodes_when_open_closed_cubic_quadratic_then_foreign_order(
    kinds, closed, tt, expected
):
    types, state = records.nodes(path(kinds, closed, tt), float("inf"))
    assert types == expected and state[1:3] == (closed, tt)


@pytest.mark.parametrize("kind", ["unknown", "null"])
def test_native_nodes_when_invalid_then_no_result(kind):
    with pytest.raises(ValueError):
        records.nodes(path(["on", kind]), float("inf"))


def test_capture_when_foreground_aux_masks_and_repeats_then_all_source_scope(domain):
    domain.workspace.activeFontPanel = None
    aux = NS(**vars(domain.regular))
    aux.id = 13
    aux.name = "Aux"
    aux.isMasterLayer = False
    mask = NS(**vars(aux))
    mask.id = 14
    mask.name = "Mask"
    mask.isMaskLayer = True
    service = NS(**vars(aux))
    service.id = 15
    service.name = "Cache"
    service.isService = True
    # Skipped background/cache records deliberately have no readable shapes.
    del mask.shapes
    del service.shapes
    domain.glyph.layers = [domain.bold, aux, mask, domain.regular, service]
    domain.regular.shapes = [
        shape([path(["on", "curve", "on"], True)]),
        shape(base="b"),
        shape(base="b"),
    ]
    domain.regular.anchors = [NS(id=80, name="top"), NS(id=81, name="top")]
    groups = api.capture()
    assert len(groups) == 3 and groups[0] == groups[1] == groups[2]
    assert [v.name for v in groups[0].layers] == ["Regular", "Bold", "Aux"]
    assert groups[0].layers[0].paths == (("offcurve", "curve", "line"),)
    assert groups[0].layers[0].anchors == frozenset({"top"})
    assert groups[0].layers[0].components == frozenset({"b"})
    assert render(groups).count("A is not compatible") == 3


@pytest.mark.parametrize(
    "fault",
    [
        "invalid",
        "null",
        "foreign",
        "duplicate_id",
        "duplicate_name",
        "role",
        "role_type",
        "name_type",
        "empty",
        "generated",
        "base",
        "anchor",
        "shape_role",
    ],
)
def test_capture_when_any_source_unreadable_then_never_return_valid_prefix(
    domain, fault
):
    layer = domain.bold
    if fault == "invalid":
        layer.isValid = False
    elif fault == "null":
        layer.isNull = True
    elif fault == "foreign":
        layer.glyph = NS(id=999)
    elif fault == "duplicate_id":
        layer.id = domain.regular.id
    elif fault == "duplicate_name":
        layer.name = "Regular"
    elif fault == "role":
        layer.isMasterLayer = False
    elif fault == "role_type":
        layer.isService = lambda: False
    elif fault == "name_type":
        layer.name = 3
    elif fault == "empty":
        domain.glyph.layers = []
    elif fault == "generated":
        layer.shapes = [shape()]
        layer.shapes[0].isComposite = True
    elif fault == "base":
        layer.shapes = [shape(base="b")]
        layer.shapes[0].shapeData.componentGlyph = None
    elif fault == "anchor":
        layer.anchors = [NS(id=83, name=None)]
    else:
        layer.shapes = [shape()]
        layer.shapes[0].isComponent = 1
    with pytest.raises(TypeError if fault == "anchor" else ValueError):
        api.capture()


def test_capture_when_only_present_master_then_source_reports_that_existing_layer(
    domain,
):
    domain.glyph.layers = [domain.regular]
    assert render(api.capture()) == "A is compatible\n\n\n"


def test_capture_when_no_selection_then_refuse_no_fallback(domain):
    domain.legacy.Selected = lambda i: False
    with pytest.raises(ValueError, match="Select"):
        api.capture()


@pytest.mark.parametrize(
    "masters", [[], ["Regular", "Regular"], ["Bold"], ["Regular", 3], ["Regular", ""]]
)
def test_capture_when_master_domain_invalid_then_refuse(domain, masters):
    domain.package.masters = masters
    with pytest.raises(ValueError, match="master"):
        api.capture()
