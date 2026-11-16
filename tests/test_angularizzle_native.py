# this_file: tests/test_angularizzle_native.py
"""Owned strict native doubles; no FontLab or upstream execution."""

from copy import deepcopy
from time import monotonic
from types import SimpleNamespace as NS

import pytest

from fontlabapp.contours.angularizzle.native import NativeAdapterError, NativeBackend
from fontlabapp.contours.angularizzle.session import Session


class Point:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class Transform:
    def __init__(self, dx=0, dy=0, scale=1):
        self.tx, self.ty, self.scale = dx, dy, scale

    def isAffine(self):
        return True

    def isInvertible(self):
        return self.scale != 0

    def inverted(self):
        return Transform(-self.tx / self.scale, -self.ty / self.scale, 1 / self.scale)

    def map(self, p):
        return Point(p.x() * self.scale + self.tx, p.y() * self.scale + self.ty)

    def m11(self):
        return self.scale

    def m12(self):
        return 0

    def m13(self):
        return 0

    def m21(self):
        return 0

    def m22(self):
        return self.scale

    def m23(self):
        return 0

    def m31(self):
        return self.tx

    def m32(self):
        return self.ty

    def m33(self):
        return 1


_serial = 100


def identity():
    global _serial
    _serial += 1
    return _serial


class Node:
    def __init__(self, point, *, nodeType):
        assert nodeType == "on"
        self.id, self.position = identity(), point
        self.nodeState, self.name = 1, ""


class Contour:
    def __init__(self, nodes, *, closed):
        self.id, self._nodes, self.closed, self.isTT = (
            identity(),
            list(nodes),
            closed,
            False,
        )

    def nodes(self):
        return tuple(self._nodes)

    def segments(self):
        pairs = list(zip(self._nodes, self._nodes[1:]))
        if self.closed and self._nodes:
            pairs.append((self._nodes[-1], self._nodes[0]))
        return [tuple(n.position for n in pair) for pair in pairs]


class Shape:
    def __init__(self, contours=(), component=False):
        self.id, self.contours = identity(), list(contours)
        self.isComponent = component
        self.isComposite = component
        self.shapeData = NS(
            id=identity(),
            note="note",
            name="group",
            builder=None,
            componentGlyph="base",
            componentLayer="Regular",
        )
        self.transform = Transform()
        self.active, self.selected = True, False
        self.opacity, self.excluded, self.contentLocked = 1.0, False, False
        self.pen, self.brush = "pen", "brush"
        self.fail_clone = False

    def clone(self):
        if self.fail_clone:
            raise RuntimeError("clone failed")
        result = deepcopy(self)
        result.id, result.shapeData.id = identity(), identity()
        result.shapeData.note = ""  # old native clone defect is deliberately simulated
        for c in result.contours:
            c.id = identity()
            for n in c.nodes():
                n.id = identity()
                n.nodeState &= ~0x3008
        return result

    def removeContour(self, contour):
        self.contours.remove(contour)

    def addContour(self, contour, check_duplicate):
        assert check_duplicate is True
        if len(contour.nodes()) < 3:
            return
        self.contours.append(contour)


class Layer:
    def __init__(self, name, shapes):
        self.id, self.name, self.shapes = identity(), name, list(shapes)
        self.mark, self.autoLayer = 0, False
        self.note, self.recipe, self.lib = "layer note", "", {"nested": [1, True]}
        self.advanceWidth, self.advanceHeight = 600.0, 0.0
        self.metricsLeft = self.metricsRight = self.metricsWidth = ""
        self.transform, self.guidelines, self.anchors = Transform(), [], []
        self.tthProgram, self.ttData = [], NS(hasHints=lambda: False)
        self.events, self.fail_insert, self.fail_update = [], 0, False

    def removeShape(self, shape):
        self.events.append(("remove", shape.id))
        self.shapes.remove(shape)

    def insertShape(self, index, shape):
        self.events.append(("insert", shape.id))
        if self.fail_insert:
            self.fail_insert -= 1
            raise RuntimeError("insert failed")
        self.shapes.insert(index, shape)
        return shape

    def checkInitHistoryState(self, index):
        self.events.append(("history", index))

    def changed(self):
        self.events.append(("changed",))

    def update(self):
        if self.fail_update:
            raise RuntimeError("update failed")
        return True


class Glyph:
    def __init__(self, name, layers):
        self.id, self.name, self.layers = identity(), name, layers
        self.lastModified, self.events = "old date", []
        self._history = 0

    def currentHistoryState(self):
        return self._history

    def findLayer(self, name):
        return next((l for l in self.layers if l.name == name), None)

    def checkInitHistoryState(self, index):
        self.events.append(("history", index))

    def changed(self):
        pass

    def update(self):
        return True


def square(x=0):
    return Contour(
        [
            Node(Point(x + a, b), nodeType="on")
            for a, b in [(0, 0), (200, 0), (200, 200), (0, 200)]
        ],
        closed=True,
    )


@pytest.fixture
def host():
    layer = Layer("Regular", [Shape([square()]), Shape(component=True)])
    glyph = Glyph("a", [layer])
    package = NS(id=10, fgId=20, master="Regular", masters=["Regular"])
    package.findName = lambda name: glyph if name == glyph.name else None
    workspace = NS(currentPackage=package, packages=lambda: [package])
    font = NS(id=20, glyphs=[NS(name="a")])
    events = []
    native = NS(
        flWorkspace=NS(instance=lambda: workspace),
        flPackage=lambda p: p,
        CurrentFont=lambda: font,
        flNode=Node,
        flContour=Contour,
        flShape=Shape,
        flItems=lambda: NS(notifyChangesApplied=lambda *args: events.append(args)),
        UpdateAll=lambda: events.append("update"),
    )
    qt = NS(
        QtCore=NS(QPointF=Point, QDateTime=NS(currentDateTimeUtc=lambda: "new date"))
    )
    occ = NS(package=package, glyph=glyph, layer=layer, block_id=1, index=0)
    selection = NS(context=(10, "Regular", "editor", 1), occurrences=(occ,))

    def provider(deadline):
        return NS(
            context=selection.context,
            occurrences=tuple(
                NS(
                    package=o.package,
                    glyph=o.glyph,
                    layer=o.layer,
                    block_id=o.block_id,
                    index=o.index,
                    package_id=o.package.id,
                    glyph_id=o.glyph.id,
                    layer_id=o.layer.id,
                )
                for o in selection.occurrences
            ),
        )

    backend = NativeBackend(
        provider=provider, native=lambda name: {"fontlab": native, "PythonQt": qt}[name]
    )
    return NS(
        layer=layer,
        glyph=glyph,
        package=package,
        workspace=workspace,
        font=font,
        native=native,
        qt=qt,
        selection=selection,
        occ=occ,
        events=events,
        backend=backend,
    )


def test_capture_process_repeat_cancel_preserves_components_raw_and_metadata(host):
    original = host.layer.shapes[0]
    original.contours[0].nodes()[0].nodeState |= 0x3008
    original.transform = Transform(10, 20, 2)
    component = host.layer.shapes[1]
    session = Session(host.backend)
    assert session.source.layers[0].paths[0].segments[0].points == (
        (10.0, 20.0),
        (410.0, 20.0),
    )
    assert session.process("80", True)
    first = session.current.copy()
    assert session.process("80", True) and session.current == first
    assert host.layer.shapes[1] is component and host.layer.mark == 280
    assert host.layer.shapes[0].shapeData.note == "note"
    assert session.cancel()
    restored = host.layer.shapes[0]
    assert restored.contours[0].nodes()[0].nodeState == 0x3009
    assert restored.shapeData.name == "group" and restored.transform.tx == 10
    assert host.layer.note == "layer note" and host.layer.lib == {"nested": [1, True]}
    assert host.layer.shapes[1] is component and host.layer.mark == 280
    assert len([e for e in host.events if e != "update"]) == 3


def test_native_capture_has_separate_selected_input_and_first_master_target(host):
    auxiliary = Layer("Other", [Shape([square(30)])])
    host.glyph.layers.append(auxiliary)
    host.occ.layer = auxiliary
    session = Session(host.backend)
    assert session.source.layers[0].key != session.source.inputs[0].key
    assert session.process("80", True)
    assert auxiliary.mark == 0
    assert (
        session.cancel()
        and host.layer.shapes[0].contours[0].nodes()[0].position.x() == 0
    )


@pytest.mark.parametrize(
    "change",
    ["mark", "note", "raw", "component", "master", "context", "selection", "closed"],
)
def test_process_refuses_changed_native_source_before_mutation(host, change):
    session = Session(host.backend)
    if change == "mark":
        host.layer.mark = 30
    elif change == "note":
        host.layer.note = "edited"
    elif change == "raw":
        host.layer.shapes[0].contours[0].nodes()[0].nodeState ^= 8
    elif change == "component":
        host.layer.shapes[1].shapeData.componentLayer = "Bold"
    elif change == "master":
        host.package.master = "Bold"
    elif change == "context":
        host.selection.context = (10, "Regular", "editor", 2)
    elif change == "selection":
        host.selection.occurrences = ()
    else:
        host.workspace.packages = list
    with pytest.raises(
        (ValueError, NativeAdapterError),
        match="changed|registered|selection|context|master",
    ):
        session.process("80", True)
    assert not host.layer.events


def test_cancel_allows_only_selection_change(host):
    session = Session(host.backend)
    session.process("80", True)
    host.selection.occurrences = ()
    assert session.cancel()


@pytest.mark.parametrize(
    "unsupported", ["auto", "hint", "tt", "nested", "builder", "singular", "quadratic"]
)
def test_unsupported_native_capture_is_whole_call_refusal(host, unsupported):
    own = host.layer.shapes[0]
    if unsupported == "auto":
        host.layer.autoLayer = True
    elif unsupported == "hint":
        host.layer.guidelines = [NS(id=8, isHint=True)]
    elif unsupported == "tt":
        host.layer.ttData = NS(hasHints=lambda: True)
    elif unsupported == "nested":
        own.isComposite = True
    elif unsupported == "builder":
        own.shapeData.builder = NS(isNull=False)
    elif unsupported == "singular":
        own.transform = Transform(scale=0)
    else:
        own.contours[0].isTT = True
    with pytest.raises((ValueError, NativeAdapterError)):
        Session(host.backend)
    assert not host.layer.events


def test_copy_failure_and_expired_deadline_leave_font_untouched(host):
    session = Session(host.backend)
    host.layer.shapes[0].fail_clone = True
    with pytest.raises(NativeAdapterError, match="staging|clone"):
        session.process("80", True)
    assert not host.layer.events
    with pytest.raises(TimeoutError):
        host.backend.capture(monotonic() - 1)


def test_failed_insert_restores_geometry_and_diagnoses_failure(host):
    session = Session(host.backend)
    old = host.layer.shapes[0]
    host.layer.fail_insert = 1
    with pytest.raises(NativeAdapterError, match="failed"):
        session.process("80", True)
    assert host.layer.shapes[0] is old
    assert host.layer.shapes[1].isComponent
    with pytest.raises(NativeAdapterError, match="failed|reopen"):
        session.process("80", True)


def test_duplicate_batch_occurrences_preserve_order_and_close(host):
    host.selection.occurrences = (host.occ, host.occ)
    session = Session(host.backend)
    assert (
        len(session.source.layers) == 2
        and session.process("80", False)
        and session.closed
    )


def test_multishape_provenance_does_not_move_paths_between_styles(host):
    second = Shape([square(400)])
    second.shapeData.name = "second"
    host.layer.shapes.insert(1, second)
    session = Session(host.backend)
    assert session.process("80", True)
    assert [s.shapeData.name for s in host.layer.shapes] == ["group", "second", "group"]
    assert min(n.position.x() for n in host.layer.shapes[1].contours[0].nodes()) == 400


def test_empty_output_is_refused_before_history(host):
    session = Session(host.backend)
    with pytest.raises((ValueError, NativeAdapterError), match="empty|collapsed"):
        session.process("1000", False)
    assert not host.layer.events


def test_different_preview_planes_keep_original_multishape_provenance(host):
    second = Shape([square(400)])
    host.layer.shapes.insert(1, second)
    session = Session(host.backend)
    assert session.process("80", True)
    assert session.process("110", True)
    assert min(n.position.x() for n in host.layer.shapes[1].contours[0].nodes()) == 400
    assert session.cancel()


def test_mixed_open_paths_drop_only_per_source_rule_and_restore(host):
    open_path = square(500)
    open_path.closed = False
    host.layer.shapes[0].contours.append(open_path)
    session = Session(host.backend)
    assert len(session.source.layers[0].paths) == 2
    session.process("80", True)
    assert len(host.layer.shapes[0].contours) == 1
    session.cancel()
    assert [c.closed for c in host.layer.shapes[0].contours] == [True, False]


def test_cross_layer_multishape_ambiguity_has_no_native_history(host):
    host.layer.shapes.insert(1, Shape([square(400)]))
    auxiliary = Layer("Other", [Shape([square()])])
    host.glyph.layers.append(auxiliary)
    host.occ.layer = auxiliary
    session = Session(host.backend)
    with pytest.raises(ValueError, match="correspondence"):
        session.process("80", True)
    assert host.layer.events == []


@pytest.mark.parametrize(
    "failure", ["notification", "update", "recovery", "postflight"]
)
def test_late_failures_poison_and_retain_diagnosed_history(host, failure):
    session = Session(host.backend)
    if failure == "notification":

        def notify(*args):
            raise RuntimeError("notification failed")

        host.native.flItems = lambda: NS(notifyChangesApplied=notify)
    elif failure == "update":
        host.layer.fail_update = True
    elif failure == "recovery":
        host.layer.fail_insert = 2
    else:

        def corrupt(*args):
            host.events.append(args)
            host.layer.note = "observer change"

        host.native.flItems = lambda: NS(notifyChangesApplied=corrupt)
    with pytest.raises(NativeAdapterError, match="failed") as caught:
        session.process("80", True)
    assert host.backend.poisoned
    if failure != "postflight":
        assert caught.value.errors
    with pytest.raises(NativeAdapterError, match="failed"):
        session.cancel() if session.processed else session.process("80", True)


def test_cancel_context_provider_works_after_invalid_selection(host):
    session = Session(host.backend)
    session.process("80", True)
    host.backend.context_provider = lambda deadline: host.selection.context

    def invalid(deadline):
        raise ValueError("selection cannot resolve")

    host.backend.provider = invalid
    assert session.cancel()


def test_auto_dependant_scan_refuses_entire_capture(host):
    dependent = Glyph("dependent", [Layer("Regular", [Shape(component=True)])])
    dependent.layers[0].autoLayer = True
    dependent.layers[0].shapes[0].shapeData.componentGlyph = "a"
    host.font.glyphs.append(NS(name="dependent"))
    host.package.findName = lambda name: {"a": host.glyph, "dependent": dependent}.get(
        name
    )
    with pytest.raises(ValueError, match="automatic dependants"):
        Session(host.backend)
    assert host.layer.events == []


@pytest.mark.parametrize(
    "change",
    [
        "glyph",
        "layer",
        "carrier",
        "no-master",
        "missing-master",
        "empty",
        "cross-package",
    ],
)
def test_missing_or_unbound_native_sources_refuse_capture(host, change):
    if change == "glyph":
        host.package.findName = lambda name: None
    elif change == "layer":
        host.occ.layer = Layer("gone", [Shape([square()])])
    elif change == "carrier":
        host.font.id = 99
    elif change == "no-master":
        host.package.masters = []
    elif change == "missing-master":
        host.package.masters = ["gone"]
    elif change == "empty":
        host.selection.occurrences = ()
    else:
        other = NS(**vars(host.occ))
        other.package = NS(id=999)
        host.selection.occurrences = (host.occ, other)
    with pytest.raises(ValueError):
        Session(host.backend)
    assert host.layer.events == []


def test_lib_and_segment_boundaries_refuse_opaque_or_nonfinite_data(host):
    host.layer.lib = {"object": object()}
    with pytest.raises(ValueError, match="opaque"):
        Session(host.backend)
    host.layer.lib = {"float": float("nan")}
    with pytest.raises(ValueError, match="nonfinite"):
        Session(host.backend)
    host.layer.lib = {"float": 2.5, "none": None, "data": b"x"}
    host.layer.shapes[0].contours[0].segments = lambda: [(Point(0, 0),)]
    with pytest.raises(ValueError, match="line or cubic"):
        Session(host.backend)


def test_capture_read_twice_and_final_deadline_fence(host):
    calls = 0
    original = host.backend.provider

    def changing(deadline):
        nonlocal calls
        result = original(deadline)
        calls += 1
        if calls == 2:
            result.context = ("changed",)
        return result

    host.backend.provider = changing
    with pytest.raises(ValueError, match="during capture"):
        Session(host.backend)
    assert host.layer.events == []


def test_native_clone_must_detach_data_and_preserve_counts(host):
    session = Session(host.backend)
    host.layer.shapes[0].clone = lambda: host.layer.shapes[0]
    with pytest.raises(ValueError, match="detach"):
        session.process("80", True)
    assert not host.layer.events


def test_unchanged_open_input_colors_without_geometry_swaps(host):
    host.layer.shapes[0].contours[0].closed = False
    session = Session(host.backend)
    session.process("80", True)
    assert host.layer.mark == 280
    assert all(event[0] not in ("remove", "insert") for event in host.layer.events)
    session.cancel()


def test_default_provider_is_imported_lazily(host, monkeypatch):
    import fontlabapp.masters.layers.selection as provider

    monkeypatch.setattr(provider, "capture", host.backend.provider)
    monkeypatch.setattr(
        provider,
        "document_context",
        lambda deadline: host.selection.context,
        raising=False,
    )
    host.backend.provider = None
    session = Session(host.backend)
    session.process("80", True)
    assert session.cancel()


def test_forged_or_duplicate_apply_plan_refused(host):
    session = Session(host.backend)
    with pytest.raises(ValueError, match="belong"):
        host.backend.check(object(), selection=True, deadline=monotonic() + 1)
    with pytest.raises(ValueError, match="already"):
        host.backend.capture(monotonic() + 1)
    before = tuple(session.current.values())
    with pytest.raises(ValueError, match="one before/after"):
        host.backend.apply(
            session.source,
            before + before,
            before + before,
            restore=False,
            deadline=monotonic() + 1,
        )
    with pytest.raises(ValueError, match="bound native target"):
        host.backend.apply(
            session.source, before, before, restore=False, deadline=monotonic() + 1
        )
    assert not host.layer.events


def test_empty_target_can_receive_selected_auxiliary_paths_and_cancel(host):
    host.layer.shapes = host.layer.shapes[1:]
    component = host.layer.shapes[0]
    auxiliary = Layer("Other", [Shape([square()])])
    host.glyph.layers.append(auxiliary)
    host.occ.layer = auxiliary
    session = Session(host.backend)
    assert session.process("80", True)
    assert host.layer.shapes[0] is component and len(host.layer.shapes) == 2
    session.process("110", True)
    assert session.cancel() and host.layer.shapes == [component]


def test_poisoned_backend_retains_recovery_handles_and_error(host):
    session = Session(host.backend)
    host.layer.fail_insert = 1
    with pytest.raises(NativeAdapterError):
        session.process("80", True)
    assert host.backend.poisoned and host.backend.recovery and host.backend.error


def test_capture_source_changes_during_second_read_can_retry(host):
    original = host.backend.provider
    calls = 0

    def change(deadline):
        nonlocal calls
        calls += 1
        if calls == 3:
            host.layer.note = "changed during read"
        return original(deadline)

    host.backend.provider = change
    with pytest.raises(ValueError, match="source changed"):
        Session(host.backend)
    host.backend.provider = original
    assert Session(host.backend).source.layers


def test_deadline_during_staging_refuses_before_history(host, monkeypatch):
    from fontlabapp.contours.angularizzle import _native_records as records

    session = Session(host.backend)
    original = records._check_deadline
    calls = 0

    def expire(deadline):
        nonlocal calls
        calls += 1
        if calls == 70:
            raise TimeoutError("owned staging deadline")
        original(deadline)

    monkeypatch.setattr(records, "_check_deadline", expire)
    with pytest.raises(TimeoutError):
        session.process("80", True)
    assert not host.layer.events


def test_expiry_during_publication_retains_history_and_disables_writer(
    host, monkeypatch
):
    from fontlabapp.contours.angularizzle import _native_write as writer

    session = Session(host.backend)
    original = writer._check_deadline
    publishing = False
    calls = 0

    def expire(deadline):
        nonlocal calls
        if publishing:
            calls += 1
            if calls == 6:
                raise TimeoutError("owned publication deadline")
        original(deadline)

    original_publish = writer.publish

    def publish(*args):
        nonlocal publishing
        publishing = True
        return original_publish(*args)

    monkeypatch.setattr(writer, "_check_deadline", expire)
    monkeypatch.setattr("fontlabapp.contours.angularizzle.native.publish", publish)
    with pytest.raises(NativeAdapterError) as caught:
        session.process("80", True)
    assert isinstance(caught.value.errors[0], TimeoutError)
    assert host.backend.poisoned and host.events


@pytest.mark.parametrize("failure", ["count", "rejection", "clone-count"])
def test_bad_native_construction_cannot_reach_history(host, failure):
    session = Session(host.backend)
    if failure == "count":
        host.native.flContour = lambda nodes, closed: Contour(nodes[:-1], closed=closed)
    elif failure == "rejection":
        original = host.layer.shapes[0].clone

        def clone():
            value = original()
            value.addContour = lambda *args: None
            return value

        host.layer.shapes[0].clone = clone
    else:
        original = host.layer.shapes[0].clone

        def clone():
            value = original()
            value.contours = []
            return value

        host.layer.shapes[0].clone = clone
    with pytest.raises(ValueError):
        session.process("80", True)
    assert host.layer.events == []


def test_stamp_failures_still_attempt_history_notification(host, monkeypatch):
    session = Session(host.backend)

    def denied(self, value):
        raise RuntimeError("date setter failed")

    monkeypatch.setattr(
        Glyph, "lastModified", property(lambda self: "old date", denied), raising=False
    )
    with pytest.raises(NativeAdapterError) as caught:
        session.process("80", True)
    assert len(caught.value.errors) == 2
    assert host.events and host.backend.poisoned


def test_closed_registration_precedes_old_child_reads(host):
    session = Session(host.backend)
    host.backend.context_provider = lambda deadline: host.selection.context
    host.workspace.packages = list
    host.backend._bound[next(iter(host.backend._bound))].glyph = object()
    with pytest.raises(ValueError, match="registered"):
        host.backend.check(session.source, selection=False, deadline=monotonic() + 1)
    assert not host.layer.events


def test_replaced_or_removed_child_identity_is_rejected(host):
    session = Session(host.backend)
    original_find = host.package.findName
    host.package.findName = lambda name: Glyph("a", host.glyph.layers)
    with pytest.raises(ValueError, match="identity changed"):
        session.process("80", True)
    host.package.findName = original_find
    replacement = deepcopy(host.layer)
    replacement.id = identity()
    host.glyph.layers = [replacement]
    with pytest.raises(ValueError, match="layer identity changed"):
        session.process("80", True)


def test_invalid_path_plan_cannot_mutate_native_geometry(host):
    from dataclasses import replace

    from fontlabapp.contours.angularizzle.model import Path, Segment

    session = Session(host.backend)
    before = tuple(session.current.values())
    bad = Path((Segment(((0.0, 0.0), (5.0, 0.0))),) * 3)
    after = (replace(before[0], paths=(bad,), color=8),)
    with pytest.raises(ValueError, match="continuous"):
        host.backend.apply(
            session.source, before, after, restore=False, deadline=monotonic() + 1
        )
    assert not host.layer.events


def test_external_undo_history_change_invalidates_preview(host):
    session = Session(host.backend)
    session.process("80", True)
    host.glyph._history += 1
    with pytest.raises(ValueError, match="source changed"):
        session.cancel()
    assert not session.closed


@pytest.mark.parametrize("damage", ["geometry", "transform", "topology"])
def test_clone_damage_is_refused_before_any_history(host, damage):
    session = Session(host.backend)
    original = host.layer.shapes[0].clone

    def clone():
        value = original()
        if damage == "geometry":
            value.contours[0].nodes()[0].position = Point(1, 2)
        elif damage == "transform":
            value.transform = Transform(99)
        else:
            value.contours[0].closed = False
        return value

    host.layer.shapes[0].clone = clone
    with pytest.raises(ValueError, match="clone changed"):
        session.process("80", True)
    assert not host.layer.events


def test_cubic_native_segment_capture_process_and_raw_cancel(host):
    contour = host.layer.shapes[0].contours[0]
    nodes = contour.nodes()
    nodes[0].position = Point(0, 0)
    nodes[1].position = Point(200, 0)
    nodes[2].position = Point(200, 200)
    nodes[3].position = Point(0, 200)
    nodes[1].nodeState = 4 | 0x3008
    nodes[2].nodeState = 4
    contour.segments = lambda: [
        tuple(n.position for n in nodes),
        (nodes[-1].position, nodes[0].position),
    ]
    session = Session(host.backend)
    assert len(session.source.layers[0].paths[0].segments[0].points) == 4
    assert session.process("80", True) and session.cancel()
    assert host.layer.shapes[0].contours[0].nodes()[1].nodeState == 0x300C


def test_deadline_is_checked_between_native_shape_detachment_and_attachment(
    host, monkeypatch
):
    from fontlabapp.contours.angularizzle import _native_write as writer

    session = Session(host.backend)
    original = writer._check_deadline
    expired = False

    def expire(deadline):
        nonlocal expired
        if (
            deadline is not None
            and any(event[0] == "remove" for event in host.layer.events)
            and not expired
        ):
            expired = True
            raise TimeoutError("expired after native detach")
        original(deadline)

    monkeypatch.setattr(writer, "_check_deadline", expire)
    before = tuple(host.layer.shapes)
    with pytest.raises(NativeAdapterError) as caught:
        session.process("80", True)
    assert tuple(host.layer.shapes) == before
    assert caught.value.geometry_recovery_attempted


def test_notification_only_error_does_not_claim_geometry_rollback(host):
    session = Session(host.backend)

    def denied(*args):
        raise RuntimeError("notify denied")

    host.native.flItems = lambda: NS(notifyChangesApplied=denied)
    with pytest.raises(NativeAdapterError) as caught:
        session.process("80", True)
    assert not caught.value.geometry_recovery_attempted


def test_deadline_aware_dependency_walk_handles_cycles_and_manual_chains():
    from fontlabapp.contours.angularizzle.native import _unsafe_dependants

    records = (
        ("manual", False, ("a",)),
        ("auto", True, ("manual",)),
        ("a", False, ("auto",)),
    )
    assert _unsafe_dependants(records, {"a"}, monotonic() + 1) == ["auto"]
    with pytest.raises(TimeoutError):
        _unsafe_dependants(records, {"a"}, monotonic() - 1)


def test_clone_style_loss_is_refused_before_native_history(host):
    session = Session(host.backend)
    original = host.layer.shapes[0].clone

    def clone():
        value = original()
        value.opacity = 0.5
        return value

    host.layer.shapes[0].clone = clone
    with pytest.raises(ValueError, match="retained shape style"):
        session.process("80", True)
    assert not host.layer.events


def test_untouched_singular_component_transform_does_not_narrow_source_scope(host):
    component = host.layer.shapes[1]
    component.transform = Transform(scale=0)
    session = Session(host.backend)
    session.process("80", True)
    session.cancel()
    assert host.layer.shapes[1] is component and component.transform.scale == 0
