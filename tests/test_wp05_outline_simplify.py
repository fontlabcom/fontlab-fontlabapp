# this_file: tests/test_wp05_outline_simplify.py
"""Retained polygon-only simplification, with cross-master structure refusals."""
import importlib
from types import SimpleNamespace as NS

import pytest
from _outline_fakes import OContour, OShape, T


@pytest.fixture
def module():
    return importlib.import_module('fontlabapp.fontui.outline_simplify')


def layer(contour):
    return NS(shapes=[OShape([contour], transform=T())], name='Regular')


def test_alternate_selected_preserves_endpoints_and_minimum(module):
    polygon = OContour([(i, 0, True, True) for i in range(6)])
    assert module.removals(polygon) == [1, 3, 5]
    polygon.closed = False
    assert module.removals(polygon) == [1, 3]
    polygon.nodes()[1].on = False
    assert module.removals(polygon) == []


def test_cross_master_plan_write_and_verify(module):
    contour = OContour([(i, 0, True, True) for i in range(6)])
    target = layer(contour)
    rows = module.changes(target, target)
    steps = [r.edit for r in rows if r.edit]
    editor = module.SimplifyEditor()
    assert editor.check([(target, steps)]) == ['Regular']
    editor.write(target, steps)
    assert editor.check([(target, steps)]) == []
    assert [n.x for n in contour.nodes()] == [0, 2, 4]
    assert module.changes(layer(OContour([(0,0,True)]))) == []


def test_incompatible_contour_and_node_shapes_refuse(module):
    a = layer(OContour([(0,0,True), (1,1,True), (2,0,True)]))
    assert module.changes(a, NS(shapes=[]))[0].problem
    for other in (OContour([(0,0,True)]), OContour([(0,0,True), (1,1,True), (2,0,True)], closed=False), OContour([(0,0,True), (1,1,False), (2,0,True)])):
        assert module.changes(a, layer(other))[0].problem
