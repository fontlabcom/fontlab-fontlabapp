# this_file: tests/test_raise_ascender_geometry.py
"""Affine, own-control, raw-flag and staged-detachment regression controls."""

import os
from copy import deepcopy
from time import monotonic
from types import SimpleNamespace as NS

import fontlabapp.contours.raise_ascender._geometry as geometry
import pytest
from fontlabapp.contours.raise_ascender.model import Layer, plan

if os.environ.get('FONTLABAPP_TEST_QT5') == '1':
    from PyQt5 import QtCore as C, QtGui as G
else:
    from PySide6 import QtCore as C, QtGui as G


class Node:
    def __init__(self, identity, x, y, flags):
        self.id, self.nodeState, self.name = identity, flags, f"n{identity}"
        self.position = (x, y)

    @property
    def position(self):
        return C.QPointF(*self.xy)

    @position.setter
    def position(self, value):
        self.xy = value if isinstance(value, tuple) else (value.x(), value.y())


class Contour:
    closed, isTT = True, True

    def __init__(self):
        self.id = 21
        self.items = [Node(1, 2, 500, 0x100), Node(2, 4, 520, 0x400)]

    def nodes(self):
        return self.items


class Shape:
    isComponent = isComposite = False
    active, selected, opacity, excluded, contentLocked = True, False, 0.75, False, False
    pen, brush = "pen", "brush"

    def __init__(self, transform):
        self.id = 31
        self.shapeData = NS(id=41, name="authored", note="note", builder=None)
        self.transform = transform
        self.contours = [Contour()]

    def clone(self):
        clone = deepcopy(self)
        clone.id += 100
        clone.shapeData.id += 100
        clone.shapeData.note = ""
        for contour in clone.contours:
            contour.id += 100
            for node in contour.nodes():
                node.id += 100
                node.nodeState = 0
        return clone


def fixture(transform=None):
    transform = G.QTransform() if transform is None else transform
    layer = NS(
        shapes=[Shape(transform)],
        name="Regular.aux",
        note="layer note",
        recipe="",
        mark=7,
        advanceWidth=600.0,
        advanceHeight=0.0,
        metricsLeft="",
        metricsRight="",
        metricsWidth="",
        lib={"custom": [1, "x"]},
        anchors=[NS(id=88)],
        guidelines=[],
        isLocked=False,
        autoLayer=False,
        tthProgram="",
        ttData=NS(hasHints=lambda: False),
    )
    return layer


def deadline():
    return monotonic() + 10


def test_actual_affine_map_own_quadratic_controls_and_component_nonexpansion():
    transform = G.QTransform(2, 0, 0, 2, 3, 5)
    layer = fixture(transform)

    class Component:
        isComponent = True
        id = 90
        transform = G.QTransform()
        shapeData = NS(componentGlyph="A", componentLayer="Regular")

        @property
        def contours(self):
            raise AssertionError("do not expand components")

    component = Component()
    layer.shapes.append(component)
    points, _facts, _handles = geometry.read(layer, deadline())
    assert [(point.x, point.y) for point in points] == [(7, 1005), (11, 1045)]
    step = plan((Layer("a", 1000, points),), 10)[0]
    jobs, future = geometry.prepare(
        layer, step, tuple(layer.shapes), NS(QtCore=C), deadline()
    )
    clone = future[0]
    assert layer.shapes[0].contours[0].nodes()[1].position.y() == 520
    assert clone.contours[0].nodes()[1].position.y() == 525
    assert clone.shapeData.note == "note" and clone.shapeData.name == "authored"
    assert [node.nodeState for node in clone.contours[0].nodes()] == [0x100, 0x400]
    assert [node.name for node in clone.contours[0].nodes()] == ["n1", "n2"]
    assert future[1] is component and len(jobs) == 1
    assert clone.contours[0].isTT and clone.contours[0].closed


def test_repeated_staged_changes_use_previous_detached_shape_not_attached_original():
    layer = fixture()
    points, *_ = geometry.read(layer, deadline())
    source = Layer("a", 500, points)
    steps = plan((source, source), 10)
    first, shapes = geometry.prepare(
        layer, steps[0], tuple(layer.shapes), NS(QtCore=C), deadline()
    )
    second, final = geometry.prepare(layer, steps[1], shapes, NS(QtCore=C), deadline())
    assert second[0][1] is first[0][2]
    assert final[0].contours[0].nodes()[1].position.y() == 540
    assert layer.shapes[0].contours[0].nodes()[1].position.y() == 520


@pytest.mark.parametrize(
    "field,value", [("isLocked", True), ("autoLayer", True), ("tthProgram", "hint")]
)
def test_unsupported_whole_layer_refuses_without_attached_changes(field, value):
    layer = fixture()
    setattr(layer, field, value)
    points, *_ = geometry.read(layer, deadline())
    step = plan((Layer("a", 500, points),), 10)[0]
    with pytest.raises(ValueError, match="unsupported"):
        geometry.prepare(layer, step, tuple(layer.shapes), NS(QtCore=C), deadline())
    assert layer.shapes[0].contours[0].nodes()[1].position.y() == 520


def test_noop_does_not_clone_or_reject_unneeded_writer_domain():
    layer = fixture()
    layer.autoLayer = True
    points, *_ = geometry.read(layer, deadline())
    step = plan((Layer("a", 500, points),), 0)[0]
    jobs, future = geometry.prepare(
        layer, step, tuple(layer.shapes), NS(QtCore=C), deadline()
    )
    assert jobs == () and future[0] is layer.shapes[0]


def test_ps_hint_projective_generated_and_unrepresentable_native_setter_refusals():
    layer = fixture()
    points, *_ = geometry.read(layer, deadline())
    step = plan((Layer("a", 500, points),), 10)[0]
    layer.guidelines = [NS(id=1, isHint=True)]
    with pytest.raises(ValueError, match="hint-link"):
        geometry.prepare(layer, step, tuple(layer.shapes), NS(QtCore=C), deadline())
    layer = fixture(G.QTransform(1, 0, 0.1, 0, 1, 0, 0, 0, 1))
    with pytest.raises(ValueError):
        geometry.read(layer, deadline())
    layer = fixture()
    layer.shapes[0].shapeData.builder = NS(isNull=False)
    with pytest.raises(ValueError, match="Generated"):
        geometry.read(layer, deadline())


def test_every_entry_checks_expired_deadline_before_traversal():
    layer = fixture()
    with pytest.raises(TimeoutError):
        geometry.read(layer, 0)
