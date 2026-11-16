# this_file: tests/test_studio_component_bases.py
"""Studios edit component base glyphs; only genuinely shared outlines are refused (Task 4)."""

import logging
from types import SimpleNamespace as NS

import pytest

from fontlabapp.contours import writer
from fontlabapp.core import sharing
from fontlabapp.studios import _contours
from fontlabapp.studios.align_nudge import model as nudge
from fontlabapp.studios.interpolation_doctor import model as interpolation
from fontlabapp.studios.outline_doctor import model as outline
from fontlabapp.studios.transform_studio import geometry, native
from fontlabapp.studios.transform_studio import model as transform


def _transform():
    values = dict(zip(("m11", "m12", "m21", "m22", "dx", "dy"), (1, 0, 0, 1, 0, 0)))
    return NS(**{k: lambda v=v: v for k, v in values.items()})


def _component(base="a"):
    return NS(isComponent=True, contours=[], shapeData=NS(referenceCount=1, componentGlyph=base, componentLayer="Regular"))


def font(refs=34, composites=((1,),) * 33):
    """Base ``a`` on Regular; each composite holds the given number of ``a`` components."""
    node = NS(selected=True, x=10.0, y=20.0, smooth=False, isOn=lambda: True)
    contour = NS(nodes=lambda: [node], transform=None, closed=True)
    shape = NS(
        isComponent=False,
        contours=[contour],
        shapeData=NS(referenceCount=refs),
        transform=_transform(),
        includesList=[],
        contentLocked=False,
    )
    layer = NS(name="Regular", shapes=[shape], isLocked=False, anchors=[], advanceWidth=500.0)
    glyphs = {"a": NS(name="a", layers=[layer])}
    layer.glyph = glyphs["a"]
    for i, (count,) in enumerate(composites):
        glyphs[f"a{i}"] = NS(name=f"a{i}", layers=[NS(name="Regular", shapes=[_component() for _ in range(count)])])
    for glyph in glyphs.values():
        glyph.findLayer = lambda name, g=glyph: next((x for x in g.layers if x.name == name), None)
    package = NS(id=7, fgPackage=NS(glyphs=[NS(name=n) for n in glyphs]), findName=glyphs.get)
    glyphs["a"].package = package
    return shape, layer, package


def test_core_module_is_the_writer_helper():
    assert writer.element_shared is sharing.element_shared
    assert writer.sharing_operation is sharing.sharing_operation


def test_component_base_is_scanned_and_fixed_by_the_doctors():
    shape, layer, _ = font()
    assert outline.outline_shapes(layer) == ([(0, shape)], [])
    assert interpolation.shape_notes(layer) == []
    assert interpolation.editable_contours(layer, interpolation.shape_notes) == shape.contours
    assert [found[0] for found in _contours.selected_contours(layer)] == [shape]


def test_genuinely_shared_outline_is_still_refused():
    _, layer, _ = font(refs=35)
    assert outline.outline_shapes(layer) == ([], ["shared outline, kept"])
    assert interpolation.shape_notes(layer) == ["shared outline, kept"]
    with pytest.raises(ValueError, match="shared"):
        _contours.selected_contours(layer)


def test_included_element_stays_refused_by_selected_contours():
    shape, layer, _ = font()
    shape.includesList = [object()]
    with pytest.raises(ValueError, match="shared"):
        _contours.selected_contours(layer)


def test_uncountable_users_keep_the_refusal_and_log(caplog):
    _, layer, _ = font()
    layer.glyph = NS(name="a", package=NS(id=7))  # no fgPackage: users cannot be counted
    with caplog.at_level(logging.DEBUG, logger=sharing.__name__):
        assert outline.outline_shapes(layer) == ([], ["shared outline, kept"])
        assert interpolation.shape_notes(layer) == ["shared outline, kept"]
    assert any("fgPackage" in record.getMessage() or record.exc_info for record in caplog.records)


def test_each_component_shape_counts_one_reference():
    # Lato Hairline: FontLab adds one reference per component shape, so a
    # composite holding two components of ``a`` gives ``a`` refcount 3.
    shape, layer, _ = font(refs=3, composites=((2,),))
    assert not sharing.element_shared(shape, layer)
    shape.shapeData.referenceCount = 4
    assert sharing.element_shared(shape, layer)


def test_scan_counts_users_once_per_pass():
    _, layer, package = font()
    calls = []
    original = package.findName
    package.findName = lambda name: calls.append(name) or original(name)
    with sharing.sharing_operation():
        for _ in range(3):
            outline.outline_shapes(layer)
            interpolation.shape_notes(layer)
    assert len(calls) == 34


ROTATE = (0.0, -1.0, 1.0, 0.0, 0.0, 0.0)


def _refused(rows):
    return [row.problem for row in rows if row.problem]


def test_align_nudge_and_transform_edit_component_base_points():
    _, layer, _ = font()
    snap = native.snapshot(layer)
    assert not snap.shapes[0].shared
    assert nudge.outline_shapes(snap) == ([0], [])
    assert not _refused(transform.selection_changes(snap, ROTATE))


def test_align_nudge_and_transform_refuse_shared_outline_points():
    _, layer, _ = font(refs=35)
    snap = native.snapshot(layer)
    assert snap.shapes[0].shared
    assert nudge.outline_shapes(snap) == ([], ["shared outline, kept"])
    assert _refused(transform.selection_changes(snap, ROTATE)) == ["Selected outline data is shared; unlink it first."]


def test_uncountable_users_keep_point_moves_refused():
    _, layer, _ = font()
    layer.glyph = NS(name="a", package=NS(id=7))
    assert native.snapshot(layer).shapes[0].shared


def test_bake_rule_keeps_the_raw_count_for_component_bases():
    _, layer, _ = font()
    snap = native.snapshot(layer)
    assert snap.shapes[0].linked
    steps = [s for row in geometry.transform_changes(snap, geometry.translate(5, 0), False, "move") for s in (row.edit or ())]
    assert ("shape", 0, geometry.translate(5, 0), False) in steps  # composed, not baked
    assert transform.smart_changes(snap, 10.0, True, False) == "component, locked or linked outline, kept"
