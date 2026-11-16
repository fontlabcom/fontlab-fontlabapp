# this_file: tests/test_contour_sharing.py
"""Component users do not make a base glyph's outline "shared"."""

from types import SimpleNamespace as NS

import fontlabapp.contours.writer as outlines

sharing = outlines


def _transform():
    values = dict(zip(("m11", "m12", "m21", "m22", "dx", "dy"), (1, 0, 0, 1, 0, 0)))
    return NS(**{k: lambda v=v: v for k, v in values.items()})


def _component(base, layer=""):
    return NS(
        isComponent=True,
        contours=[],
        shapeData=NS(referenceCount=1, componentGlyph=base, componentLayer=layer),
    )


def font(refs=34, users=33, other_layer_users=0, layer_as_object=False):
    """Fake package: base ``a`` plus composites on Regular and Bold."""
    shape = NS(
        id=3,
        isComponent=False,
        contours=[NS()],
        shapeData=NS(referenceCount=refs),
        transform=_transform(),
    )
    base_layer = NS(name="Regular", shapes=[shape])
    glyphs = {"a": NS(name="a", layers=[base_layer])}
    base_layer.glyph = glyphs["a"]
    for i in range(users):
        target = NS(name="Regular") if layer_as_object else "Regular"
        glyphs[f"a{i}"] = NS(name=f"a{i}", layers=[NS(name="Regular", shapes=[_component(NS(name="a"), target)])])
    for i in range(other_layer_users):
        glyphs[f"b{i}"] = NS(name=f"b{i}", layers=[NS(name="Regular", shapes=[_component("a", "Bold")])])
    for glyph in glyphs.values():
        glyph.findLayer = lambda name, g=glyph: next((x for x in g.layers if x.name == name), None)
    package = NS(
        id=1,
        fgPackage=NS(glyphs=[NS(name=n) for n in glyphs]),
        findName=glyphs.get,
    )
    glyphs["a"].package = package
    return shape, base_layer, package


def test_component_base_is_editable():
    shape, layer, _ = font()
    assert not sharing.element_shared(shape, layer)
    assert outlines.outline_shapes(layer) == ([shape], [])


def test_component_layer_object_and_empty_name_count():
    shape, layer, _ = font(layer_as_object=True)
    assert not sharing.element_shared(shape, layer)
    shape, layer, _ = font(refs=3, users=0)
    assert sharing.element_shared(shape, layer)


def test_element_reference_beyond_components_stays_shared():
    shape, layer, _ = font(refs=35)
    assert sharing.element_shared(shape, layer)
    assert outlines.outline_shapes(layer) == ([], ["shared outline, kept"])


def test_component_on_other_layer_is_not_counted():
    shape, layer, _ = font(refs=34, users=32, other_layer_users=1)
    assert sharing.element_shared(shape, layer)


def test_unresolvable_package_is_conservative():
    shape = NS(shapeData=NS(referenceCount=2))
    assert sharing.element_shared(shape)
    assert sharing.element_shared(shape, NS(name="Regular", glyph=NS(name="a", package=NS(id=1))))
    assert not sharing.element_shared(NS(shapeData=NS(referenceCount=1)))


def test_operation_memoises_once_and_drops_after():
    shape, layer, package = font()
    calls = []
    original = package.findName
    package.findName = lambda name: calls.append(name) or original(name)
    with sharing.sharing_operation():
        sharing.element_shared(shape, layer)
        sharing.element_shared(shape, layer)
    assert len(calls) == 34
    shape.shapeData.referenceCount = 35
    assert sharing.element_shared(shape, layer)
    assert len(calls) == 68
