# this_file: tests/test_node_duplicator_native.py
"""Native-shaped boundary controls; these do not qualify a FontLab binary."""

from dataclasses import replace
from types import SimpleNamespace as NS
from time import monotonic
import pytest
from fontlabapp.contours.nodes.duplicator.model import Node, Path, Layer, Source, plan
from fontlabapp.contours.nodes.duplicator._write import (
    stage,
    publish,
    representable,
    WriteError,
)


class Point:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class NativeNode:
    serial = 100

    def __init__(self, point=None, nodeType="on"):
        NativeNode.serial += 1
        self.id = NativeNode.serial
        self.position = point or Point(0.125, 0.375)
        self.nodeState = 1
        self.name = ""
        self.props = {}
        self.smartAngleR = 0

    def clone(self):
        n = NativeNode(self.position)
        n.nodeState = self.nodeState
        n.name = self.name
        n.props = self.props.copy()
        n.props["corner_smooth"] = 1.0
        return n

    def getProperty(self, k):
        return self.props.get(k)

    def setProperty(self, k, v):
        self.props[k] = v


class Contour:
    closed = False

    def __init__(self, node):
        self.row = [node]
        self.fail = False

    def nodes(self):
        return self.row[:]

    def insert(self, index, node):
        self.row.insert(index, node)
        node.position = Point(round(node.position.x()), round(node.position.y()))
        if self.fail:
            raise RuntimeError("after attachment")

    def removeOne(self, n):
        self.row.remove(n)


class Item:
    def __init__(self, id):
        self.id = id
        self.name = "a"
        self.events = []
        self.autoLayer = False
        self.tthProgram = ""
        self.ttData = NS(hasHints=lambda: False)
        self.guidelines = []

    def checkInitHistoryState(self, v):
        self.events.append("init")

    def changed(self):
        self.events.append("changed")

    def update(self):
        self.events.append("update")


def setup(mode="current"):
    n = NativeNode()
    n.name = "n"
    n.nodeState = 0x1009
    n.props = {"corner_smooth": 0.375, "hoi_point_id": "exact"}
    from fontlabapp.contours.nodes.duplicator._capture import node_record

    record = node_record(n, "line")
    path = Path(20, (record,), False)
    layer = Layer(30, 40, (path,))
    source = Source((layer,), (30,), ((0, n.id),), True)
    contour = Contour(n)
    glyph, live = Item(40), Item(30)
    capture = NS(
        source=source,
        native_nodes={30: {n.id: n, ("path", 0): contour}},
        bound={30: (glyph, live)},
    )
    calls = []
    native = NS(
        flNode=lambda value=None, nodeType="on": (
            value if isinstance(value, NativeNode) else NativeNode(value, nodeType)
        ),
        flItems=lambda: NS(notifyChangesApplied=lambda *args: calls.append(args)),
    )
    qt = NS(QtCore=NS(QPointF=Point, QDateTime=NS(currentDateTimeUtc=lambda: "stamp")))
    return capture, plan(source, mode), native, qt, calls, contour


@pytest.mark.parametrize("mode,count", [("current", 1), ("all", 1), ("handles", 3)])
def test_staging_restores_native_clone_normalization_and_attachment_rounding(
    mode, count
):
    c, r, n, q, calls, p = setup(mode)
    representable(c, r)
    staged = stage(c, r, n, q, monotonic() + 2)
    assert not calls and c.bound[30][0].events == []
    publish(c, r, staged, n, q, monotonic() + 2)
    assert len(p.nodes()) == count + 1 and len(calls) == 1
    assert (p.nodes()[-1].position.x(), p.nodes()[-1].position.y()) == (0.125, 0.375)
    assert p.nodes()[-1].getProperty("corner_smooth") == 0.375
    assert p.nodes()[0].nodeState == 0x1009
    assert calls[0][0] == "Duplicate Nodes" and len(calls[0][1]) == 2
    if mode == "handles":
        assert [node.nodeState & 7 for node in p.nodes()] == [1, 4, 4, 1]


def test_aliasing_clone_refused_before_any_history():
    c, r, n, q, calls, p = setup()
    p.nodes()[0].clone = lambda: p.nodes()[0]
    with pytest.raises(ValueError, match="identity"):
        stage(c, r, n, q, monotonic() + 2)
    assert c.bound[30][0].events == [] and not calls


def test_attachment_then_exception_removes_only_new_owned_nodes_and_reports_history():
    c, r, n, q, calls, p = setup()
    staged = stage(c, r, n, q, monotonic() + 2)
    p.fail = True
    with pytest.raises(WriteError, match="after attachment"):
        publish(c, r, staged, n, q, monotonic() + 2)
    assert len(p.nodes()) == 1 and len(calls) == 1


def test_indexed_offcurve_line_and_final_smooth_control_remain_explicit_holds():
    c, r, n, q, calls, p = setup("all")
    a = c.source.layers[0]
    old = a.paths[0].nodes[0]
    off = replace(old, kind="off")
    a = replace(a, paths=(replace(a.paths[0], nodes=(off,)),))
    c.source = replace(c.source, layers=(a,))
    r = replace(r, operations=(replace(r.operations[0], source=off.key),))
    with pytest.raises(ValueError, match="segment mapping"):
        representable(c, r)
    assert not calls


from fontlabapp.contours.nodes.duplicator.native import execute
from fontlabapp.contours.nodes.duplicator._capture import (
    capture,
    guard_dependencies,
    check,
    scalar,
)


def host(mode="current"):
    c, r, n, q, calls, p = setup(mode)
    node = p.nodes()[0]
    node.nodeState |= 32
    glyph, layer = c.bound[30]
    glyph.currentHistoryState = lambda: 0
    data = NS(id=71, name="own", note="preserve", builder=None)
    shape = NS(
        id=70,
        shapeData=data,
        isComponent=False,
        isComposite=False,
        contours=[p],
        selected=False,
    )
    p.id = 20
    layer.shapes = [shape]
    layer.note = "layernote"
    layer.name = "Regular"
    layer.isMaskLayer = False
    layer.isService = False
    glyph.layers = [layer]
    package = NS(id=50, fgId=60, findName=lambda name: glyph)
    glyph.name = "a"
    glyph.package = package
    workspace = NS(packages=lambda: [package], currentPackage=package)
    n.flWorkspace = NS(instance=lambda: workspace)
    n.flPackage = lambda value: value
    n.CurrentFont = lambda: NS(id=60, glyphs=[NS(name="a")])
    n.flGlyph = NS(updatedFgGlyphs=lambda: [])
    occurrence = NS(
        package=package,
        glyph=glyph,
        layer=layer,
        package_id=50,
        glyph_id=40,
        layer_id=30,
        block_id=0,
        index=0,
    )
    selected = NS(
        context=(50, "Regular", "font", 1), occurrences=(occurrence,), carriers=()
    )
    return c, n, q, calls, p, lambda deadline: selected, selected


@pytest.mark.parametrize("mode,count", [("current", 1), ("all", 1), ("handles", 3)])
def test_real_boundary_two_pass_capture_stage_and_single_history(mode, count):
    c, n, q, calls, p, provider, selected = host(mode)
    result = execute(mode, native=n, qt=q, provider=provider, report=False)
    assert (
        result["inserted"] == count and len(p.nodes()) == count + 1 and len(calls) == 1
    )
    assert p.nodes()[0].nodeState == 0x1029


def test_stale_history_refuses_before_history():
    c, n, q, calls, p, provider, selected = host()
    count = [0]

    def changing(deadline):
        count[0] += 1
        if count[0] == 2:
            c.bound[30][0].currentHistoryState = lambda: 1
        return selected

    with pytest.raises(ValueError, match="changed before history"):
        execute("current", native=n, qt=q, provider=changing, report=False)
    assert not calls


def test_editor_selection_preserves_canvas_order_and_visual_only_selection_truth():
    c, n, q, calls, p, provider, s = host()
    node = p.nodes()[0]
    s.context = (50, "Regular", "editor", 1)
    s.carriers = (NS(selectedNodes=lambda: [NS(node=node)], selection=lambda: []),)
    assert capture("current", monotonic() + 2, n, provider).source.selection == (
        (0, node.id),
    )
    s.carriers = (NS(selectedNodes=lambda: [], selection=lambda: [object()]),)
    result = execute("current", native=n, qt=q, provider=provider, report=False)
    assert (
        result["inserted"] == 0
        and result["no_selection_message"] is False
        and not calls
    )


@pytest.mark.parametrize(
    "rows,targets,names,message",
    [
        (
            (
                ("a", 1, False, ((2, "", ((3, (4,)),)),)),
                ("b", 5, False, ((2, "", ()),)),
            ),
            {1},
            {"a"},
            "shares",
        ),
        (
            (("a", 1, False, ()), ("b", 2, True, ((3, "a", ()),))),
            {1},
            {"a"},
            "Automatic",
        ),
    ],
)
def test_dependency_and_alias_guards_are_specific(rows, targets, names, message):
    with pytest.raises(ValueError, match=message):
        guard_dependencies(rows, targets, names)


@pytest.mark.parametrize("value", [object(), float("nan"), float("inf"), []])
def test_opaque_or_nonfinite_copy_property_refused(value):
    with pytest.raises(ValueError):
        scalar(value)


def test_expired_deadline_is_checked():
    with pytest.raises(TimeoutError):
        check(0)
