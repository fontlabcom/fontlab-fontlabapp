# this_file: tests/test_contour_copy.py
"""Contour copies, Qt path contours and PostScript hint counts (issue 122, T14h).

The doubles copy contours like FontLab can: ``cloneMapped`` drops node names
and raw node flags (fl#8569 covers this and more). The guide double gives a
role (``isHorizontal()``/``isVertical()``) and an angle flag that can differ,
so the tests show which one ``hint_counts`` reads. They do not prove native
FontLab behaviour.
"""

import sys
from types import SimpleNamespace as NS

import pytest

import fontlabapp.contours.copy as cc
import fontlabapp.hints.postscript as hints  # noqa: PLR0402 - from-import hits the package __getattr__

SELECTED = 0x0020


class Matrix:
    def __init__(self, m11=1.0, m12=0.0, m21=0.0, m22=1.0, dx=0.0, dy=0.0):
        self.m = (m11, m12, m21, m22, dx, dy)

    def point(self, x, y):
        m11, m12, m21, m22, dx, dy = self.m
        return m11 * x + m21 * y + dx, m12 * x + m22 * y + dy


class Node:
    def __init__(self, x, y, name="", state=0, kind="on"):
        self.x, self.y, self.name, self.nodeState, self.type = x, y, name, state, kind


class Contour:
    def __init__(self, points, names=(), states=(), closed=True, drop=False):
        names, states = list(names), list(states)
        self._nodes = [
            Node(x, y, names[i] if i < len(names) else "", states[i] if i < len(states) else 0)
            for i, (x, y) in enumerate(points)
        ]
        self.closed, self.drop = closed, drop

    def nodes(self):
        return list(self._nodes)

    def points(self):
        return [(n.x, n.y) for n in self._nodes]

    def cloneMapped(self, matrix):
        points = [matrix.point(n.x, n.y) for n in self._nodes]
        return Contour(points[:-1] if self.drop else points, drop=self.drop)


def square(left, bottom, right, top, **kwargs):
    return Contour([(left, bottom), (right, bottom), (right, top), (left, top)], **kwargs)


class Shape:
    def __init__(self, contours=(), component=False, matrix=None):
        self.isComponent, self.contours = component, list(contours)
        self.transform = matrix or Matrix()


def layer(*shapes):
    return NS(shapes=list(shapes))


# ---------------------------------------------------------------- contour copies
def test_contour_shapes_when_mixed_then_own_shapes_with_contours_in_order():
    a, b = Shape([square(0, 0, 1, 1)]), Shape([square(0, 0, 1, 1)], matrix=Matrix(2.0))
    assert cc.contour_shapes(layer(a, Shape(component=True), Shape(), b)) == [a, b]


def test_copy_contours_when_copied_then_mapped_names_and_raw_flags_kept_selection_cleared():
    shape = Shape([square(0, 0, 10, 20, names=["a", "", "", "d"], states=[SELECTED | 0x3, 0x1, 0, 0])],
                  matrix=Matrix(dx=5.0))  # fmt: skip
    copies = cc.copy_contours(layer(shape, Shape(component=True)), Matrix(2.0, 0.0, 0.0, 2.0, 0.0, 1.0))
    assert [c.points() for c in copies] == [[(10, 1), (30, 1), (30, 41), (10, 41)]]
    assert [n.name for n in copies[0].nodes()] == ["a", "", "", "d"]
    assert [n.nodeState for n in copies[0].nodes()] == [0x3, 0x1, 0, 0], "raw flags kept, selection bit cleared"
    assert shape.contours[0].points() == [(0, 0), (10, 0), (10, 20), (0, 20)], "source untouched"


def test_copy_contours_when_node_count_changes_then_runtime_error():
    with pytest.raises(RuntimeError, match="node count"):
        cc.copy_contours(layer(Shape([square(0, 0, 9, 9, drop=True)])), Matrix())


def test_repair_nodes_doc_when_read_then_claims_only_names_and_raw_flags():
    doc = cc.repair_nodes.__doc__ + cc.__doc__
    assert "node names and raw node flags" in doc
    assert "corner" not in doc.lower() and "properties are copied" not in doc


# ---------------------------------------------------------------- Qt path contours
class Path:
    def __init__(self, elements):
        self.elements = [NS(type=t, x=x, y=y) for t, x, y in elements]

    def elementCount(self):
        return len(self.elements)

    def elementAt(self, index):
        return self.elements[index]


@pytest.fixture
def native(monkeypatch):
    fontlab = NS(
        flNode=lambda point, nodeType="on": Node(point.x(), point.y(), kind=nodeType),
        flContour=lambda nodes, closed=False: NS(nodes=nodes, closed=closed),
    )
    qt = NS(QtCore=NS(QPointF=lambda x, y: NS(x=lambda: x, y=lambda: y)))
    monkeypatch.setitem(sys.modules, "fontlab", fontlab)
    monkeypatch.setitem(sys.modules, "PythonQt", qt)


def test_path_contours_when_elements_then_closed_typed_nodes_and_stubs_dropped(native):
    path = Path([
        (0, 0, 0), (1, 10, 0), (2, 10, 5), (3, 5, 10), (3, 0, 10), (1, 0, 0),
        (0, 2, 2), (1, 8, 2), (1, 8, 8), (1, 2, 2),
        (0, 50, 50), (1, 60, 50),
    ])  # fmt: skip
    contours = cc.path_contours(path)
    assert [[(n.x, n.y) for n in c.nodes] for c in contours] == [
        [(0, 0), (10, 0), (10, 5), (5, 10), (0, 10)],
        [(2, 2), (8, 2), (8, 8)],
    ]
    assert [n.type for n in contours[0].nodes] == ["on", "on", "curve", "curve", "on"]
    assert all(c.closed is True for c in contours)


# ---------------------------------------------------------------- hint counts (S7 M1)
class Guide:
    """``role`` is FontLab's role flag; ``isVerticalQuarter`` is the angle test."""

    def __init__(self, role, hint=True, quarter=None):
        self.isHint, self.role = hint, role
        self.isVerticalQuarter = role == "v" if quarter is None else quarter

    def isHorizontal(self):
        return self.role == "h"

    def isVertical(self):
        return self.role == "v"


def test_hint_counts_when_guides_then_counted_by_role_not_angle():
    guides = [
        Guide("h"), Guide("h"), Guide("v"),
        Guide("h", quarter=True),  # role horizontal, angle says vertical: FontLab removes it as horizontal
        Guide("v", hint=False),  # a plain guideline
        Guide(""),  # no role: FontLab's removeHints removes it in every direction
    ]  # fmt: skip
    assert hints.hint_counts(NS(guidelines=guides)) == (3, 1)


def test_hint_counts_when_no_guides_then_zero():
    assert hints.hint_counts(NS(guidelines=[])) == (0, 0)


def test_restore_shape_when_clone_loses_fields_then_restore_data_keep_clone_selection():
    before = Contour([(0, 0), (1, 2)], names=["on", "control"], states=[0x8000, 0x4000 | SELECTED])
    after = Contour([(0, 0), (1, 2)], states=[SELECTED, 0])
    before.name, after.name = "outline", ""
    source = NS(shapeData=NS(note="note", name="element"), contours=[before])
    clone = NS(shapeData=NS(note="", name=""), contours=[after], active=False, selected=True)
    cc.restore_shape(source, clone)
    assert (clone.shapeData.note, clone.shapeData.name, after.name) == ("note", "element", "outline")
    assert [(n.name, n.nodeState) for n in after.nodes()] == [("on", 0x8000 | SELECTED), ("control", 0x4000)]
    assert clone.active is False and clone.selected is True
    assert before.nodes()[1].nodeState == 0x4000 | SELECTED


def test_restore_shape_when_contour_count_differs_then_refused():
    with pytest.raises(RuntimeError, match="contour count"):
        cc.restore_shape(NS(contours=[]), NS(contours=[object()]))


def test_restore_shape_when_node_count_differs_then_refused():
    source = NS(shapeData=NS(note="n", name="s"), contours=[Contour([(0, 0)])])
    clone = NS(shapeData=NS(note="", name=""), contours=[Contour([])])
    with pytest.raises(RuntimeError, match="node count"):
        cc.restore_shape(source, clone)


@pytest.mark.parametrize("keep_view_state", [False, True])
def test_restore_shape_when_subset_then_pair_selected_contours_and_view_mode(keep_view_state):
    before = [Contour([(i, 0)], names=[str(i)], states=[0x8000 | SELECTED]) for i in range(3)]
    after = [Contour([(2, 0)], states=[0]), Contour([(0, 0)], states=[0])]
    for i, c in enumerate(before):
        c.name = f"contour {i}"
    source = NS(shapeData=NS(note="note", name="shape"), contours=before, active=True, selected=False)
    clone = NS(shapeData=NS(note="", name=""), contours=after, active=False, selected=True)
    cc.restore_shape(source, clone, keep_view_state, indexes=[2, 0])
    assert [c.name for c in after] == ["contour 2", "contour 0"]
    assert [c.nodes()[0].name for c in after] == ["2", "0"]
    assert [c.nodes()[0].nodeState for c in after] == [0x8000 | (SELECTED if keep_view_state else 0)] * 2
    assert (clone.active, clone.selected) == ((True, False) if keep_view_state else (False, True))
    assert (clone.shapeData.note, clone.shapeData.name) == ("note", "shape")
