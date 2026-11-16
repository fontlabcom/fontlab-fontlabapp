# this_file: tests/test_background_stage.py
"""Detached edits must preserve metadata and operate in layer coordinates."""

from types import SimpleNamespace as NS

import pytest
from fontlabapp.masters.background.stage import selected_shapes, transform_shape
from fontlabapp.masters.background.model import Transform as Operation
from test_angularizzle_native import Contour, Node, Point, Shape, Transform, square
from test_background_native import CONSTRUCTORS

QT = NS(QtCore=NS(QPointF=Point), QtGui=NS(QTransform=Transform))


def test_scale_nodes_in_layer_coordinates_preserves_transform_flags_notes():
    source = Shape([square()])
    source.transform = Transform(10, 20, 2)
    source.contours[0].nodes()[0].nodeState |= 0x3008
    clone = transform_shape(source, Operation("scale", 50), 2, QT, 10**30)
    node = clone.contours[0].nodes()[0]
    assert (
        clone.transform.map(node.position).x(),
        clone.transform.map(node.position).y(),
    ) == (2.5, 5)
    assert node.nodeState == source.contours[0].nodes()[0].nodeState
    assert clone.shapeData.note == source.shapeData.note == "note"
    assert source.contours[0].nodes()[0].position.x() == 0


def test_scale_never_clones_or_changes_components():
    source = Shape(component=True)
    assert transform_shape(source, Operation("scale", 17), 4, QT, 10**30) is source


def test_selected_shape_copy_keeps_full_contours_and_clears_only_copy_selection():
    source = Shape([square(), square(400)])
    for node in source.contours[0].nodes():
        node.nodeState |= 0x20 | 0x3008
        node.selected = True
    for node in source.contours[1].nodes():
        node.selected = False
    copies = selected_shapes(
        NS(shapes=[source, Shape(component=True)]), CONSTRUCTORS, QT, 10**30
    )
    assert len(copies) == 1 and len(copies[0].contours) == 1
    assert copies[0].shapeData.note == "note" and source.contours[0].nodes()[0].selected
    assert not copies[0].contours[0].nodes()[0].nodeState & 0x20


def test_detached_failure_never_modifies_source():
    source = Shape([square()])
    source.fail_clone = True
    with pytest.raises(RuntimeError, match="clone failed"):
        transform_shape(source, Operation("shift", 12), 1, QT, 10**30)


@pytest.mark.parametrize(
    "closed,states", [(True, (1, 4, 4, 1)), (False, (1, 2, 1)), (True, ())]
)
def test_selected_copy_preserves_exact_cubic_quadratic_open_and_empty_nodes(
    closed, states
):
    def constructor(nodes, closed):
        result = Contour(nodes, closed=closed)
        result.isTT = any(n.nodeState & 2 for n in nodes)
        return result

    nodes = [
        Node(Point(i * 17.25, i * -3.5), nodeType="on") for i in range(len(states))
    ]
    for i, node in enumerate(nodes):
        node.nodeState = states[i] | 0x3008 | 0x20
        node.name = f"node-{i}"
        node.selected = True
    contour = constructor(nodes, closed)
    source = Shape([contour])
    constructors = NS(flShape=CONSTRUCTORS.flShape, flNode=Node, flContour=constructor)
    result = selected_shapes(NS(shapes=[source]), constructors, QT, 10**30)[0].contours[
        0
    ]
    assert result.closed == closed and result.isTT == contour.isTT
    assert [
        (n.position.x(), n.position.y(), n.nodeState, n.name) for n in result.nodes()
    ] == [(n.position.x(), n.position.y(), n.nodeState & ~0x20, n.name) for n in nodes]


def test_unselected_geometry_and_component_reference_are_never_read():
    class HiddenNode:
        selected = False

        @property
        def position(self):
            raise AssertionError("unselected geometry read")

    hidden = Shape([Contour([HiddenNode()], closed=True)])
    component = NS(isComponent=True)
    assert (
        selected_shapes(NS(shapes=[hidden, component]), CONSTRUCTORS, QT, 10**30) == ()
    )
    from fontlabapp.masters.background.records import selection_record

    assert selection_record(NS(shapes=[hidden, component]), 10**30)[0][2:] == ((), ())


@pytest.mark.parametrize("change", ["identity", "style", "reference"])
def test_component_clone_rejects_native_identity_style_or_reference_loss(change):
    from fontlabapp.masters.background.records import clone

    source = Shape(component=True)
    original = source.clone

    def broken():
        result = original()
        if change == "identity":
            return source
        if change == "style":
            result.opacity = 0.25
        else:
            result.shapeData.componentGlyph = "wrong"
        return result

    source.clone = broken
    with pytest.raises(ValueError, match="Background component clone"):
        clone(source, 10**30)
