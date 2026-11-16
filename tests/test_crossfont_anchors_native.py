# this_file: tests/test_crossfont_anchors_native.py
"""Canonical two-font identity/transaction controls, expressly not host proof."""

from copy import copy
from types import SimpleNamespace as NS

import fontlabapp.anchors.crossfont.capture as cap
import fontlabapp.anchors.crossfont.native as api
import pytest
from fontlabapp.anchors.crossfont.model import Options


class Point:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class Pin:
    serial = 1000

    def __init__(self, name="top", x=25, y=100):
        Pin.serial += 1
        self.id = Pin.serial
        self.name = name
        self.point = Point(x, y)
        self.appearance = 5
        self.anchor = True
        self.cloudEnabled = True
        self.markEnabled = True
        self.style = 2
        self.expressionX = ""
        self.expressionY = ""

    def clone(self):
        p = copy(self)
        Pin.serial += 1
        p.id = Pin.serial
        return p


class Item:
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.events = []

    def checkInitHistoryState(self, n):
        self.events.append("history")

    def currentHistoryState(self):
        return 0


class Layer(Item):
    def __init__(self, id, name, pins):
        super().__init__(id, name)
        self.anchors = pins[:]
        self.autoLayer = False
        self.advanceWidth = 200
        self.isNull = False
        self.shapes = []
        self.fail = False

    def addAnchor(self, p):
        self.anchors.append(p)
        if self.fail:
            raise RuntimeError("partial add")

    def removeAnchor(self, p):
        self.anchors.remove(p)


class Glyph(Item):
    isNull = False

    def __init__(self, id, name, layer):
        super().__init__(id, name)
        self.layers = [layer]

    def findLayer(self, name):
        return next((l for l in self.layers if l.name == name), None)


def host(monkeypatch):
    source_layer = Layer(11, "Regular", [Pin()])
    source_layer.advanceWidth = 100
    target_layer = Layer(12, "Other", [Pin("keep")])
    a, b = Glyph(21, "a", source_layer), Glyph(22, "a", target_layer)
    fa, fb = (
        NS(id=31, path="/one/same.vfj", glyphs=[NS(name="a")]),
        NS(id=32, path="/two/same.vfj", glyphs=[NS(name="a")]),
    )
    pa = NS(
        id=41,
        fgId=31,
        masters=("Regular",),
        findName=lambda name: a if name == "a" else None,
    )
    pb = NS(
        id=42,
        fgId=32,
        masters=("Other",),
        findName=lambda name: b if name == "a" else None,
    )
    workspace = NS(packages=lambda: [pa, pb], currentPackage=pa)
    events = []

    class NamingLayer(Layer):
        def addAnchor(self, pin):
            names = {p.name for p in self.anchors}
            name = pin.name.strip()
            dot = max(name.rfind("."), name.rfind("_"))
            suffix = name[dot + 1 :]
            counted = dot > 0 and suffix.isascii() and suffix.isdigit()
            base = name[:dot] if counted else name
            number = int(suffix) + 1 if counted else 1
            while name in names:
                name = f"{base}.{number}"
                number += 1
            pin.name = name
            self.anchors.append(pin)

        def clearAnchors(self):
            self.anchors.clear()

        def release(self):
            assert not self.anchors

    def pin_factory(value):
        if isinstance(value, Point):
            pin = Pin("", value.x(), value.y())
            pin.release = lambda: None
            return pin
        return value

    native = NS(
        flWorkspace=NS(instance=lambda: workspace),
        AllFonts=lambda: [fa, fb],
        flPackage=lambda p: p,
        flPinPoint=pin_factory,
        flLayer=lambda: NamingLayer(-101, "detached names", []),
        flGlyph=NS(updatedFgGlyphs=list),
        flItems=lambda: NS(notifyChangesApplied=lambda *args: events.append(args)),
    )
    qt = NS(
        QtCore=NS(
            QPointF=Point, QDateTime=NS(currentDateTimeUtc=lambda: "same UTC stamp")
        )
    )
    monkeypatch.setattr(cap, "_native", lambda name: native)
    monkeypatch.setattr(
        api, "_native", lambda name: qt if name == "PythonQt" else native
    )
    return NS(
        source=source_layer,
        target=target_layer,
        a=a,
        b=b,
        fa=fa,
        fb=fb,
        pa=pa,
        pb=pb,
        native=native,
        qt=qt,
        events=events,
    )


def test_crossfont_copy_uses_chosen_source_and_notifies_actual_inactive_destination(
    monkeypatch,
):
    h = host(monkeypatch)
    result = api.Backend().copy(
        41, 42, "Regular", "Other", False, Options(relative=True)
    )
    assert result["anchors"] == 1 and result["layers"] == 1
    assert [p.name for p in h.target.anchors] == ["keep", "top"]
    assert h.target.anchors[-1].point.x() == 50 and h.source.anchors[0].point.x() == 25
    assert len(h.events) == 1 and h.events[0][1] == [h.target, h.b]
    assert h.a.events == [] and h.a.__dict__.get("lastModified") is None
    assert h.b.lastModified == "same UTC stamp"


def test_crossfont_copy_when_title_given_then_destination_undo_named_by_caller(monkeypatch):
    from fontlabapp.anchors.crossfont.transaction import TITLE

    h = host(monkeypatch)
    api.Backend().copy(41, 42, "Regular", "Other", False, Options(relative=True), title="Anchor Transfer: x")
    assert [event[0] for event in h.events] == ["Anchor Transfer: x"]
    h = host(monkeypatch)
    api.Backend().copy(41, 42, "Regular", "Other", False, Options(relative=True))
    assert [event[0] for event in h.events] == [TITLE]


def test_font_labels_may_match_but_ids_and_master_lists_do_not_alias(monkeypatch):
    h = host(monkeypatch)
    h.pa.masters = ("Regular", "#internal")
    rows = api.Backend().fonts()
    assert [r.label for r in rows] == ["same.vfj", "same.vfj"]
    assert [r.identity for r in rows] == [41, 42] and rows[0].masters == ("Regular",)


def test_selected_repair_checks_chosen_source_before_reading_legacy_selection(
    monkeypatch,
):
    h = host(monkeypatch)
    api.Backend().fonts()
    calls = []
    monkeypatch.setattr(
        cap, "_require_selection_window", lambda id: calls.append(("window", id))
    )
    monkeypatch.setattr(
        cap,
        "names_font_window_selection",
        lambda **kw: calls.append(("read", kw["expected_fg_id"])) or ["a"],
    )
    api.Backend().copy(42, 41, "Other", "Regular", True, Options())
    assert calls and all(c[1] == 42 if c[0] == "window" else c[1] == 32 for c in calls)
    assert h.events[0][1] == [h.source, h.a]


def test_selected_wrong_source_active_window_refuses_before_history(monkeypatch):
    h = host(monkeypatch)

    def refuse(id):
        raise ValueError("wrong active Font window")

    monkeypatch.setattr(cap, "_require_selection_window", refuse)
    with pytest.raises(ValueError, match="Activate the chosen source"):
        api.Backend().copy(42, 41, "Other", "Regular", True, Options())
    assert not h.events and not h.a.events and not h.b.events


@pytest.mark.parametrize(
    "kind",
    [
        "pending",
        "auto",
        "dependent",
        "clone_alias",
        "clone_metadata",
        "stale",
        "closed",
    ],
)
def test_precise_preflight_refusals_never_start_history(monkeypatch, kind):
    h = host(monkeypatch)
    if kind == "pending":
        h.native.flGlyph.updatedFgGlyphs = lambda: [99]
    elif kind == "auto":
        h.target.autoLayer = True
    elif kind == "dependent":
        h.target.shapes = [NS(isComponent=True, shapeData=NS(componentGlyph="a"))]
        h.target.autoLayer = True
    elif kind == "clone_alias":
        h.source.anchors[0].clone = lambda: h.source.anchors[0]
    elif kind == "clone_metadata":

        def changed():
            p = Pin()
            p.appearance = 6
            return p

        h.source.anchors[0].clone = changed
    elif kind == "stale":
        previous = h.native.AllFonts
        count = [0]

        def mutation():
            count[0] += 1
            if count[0] == 2:
                h.source.anchors[0].name = "changed"
            return previous()

        h.native.AllFonts = mutation
    elif kind == "closed":
        h.native.AllFonts = lambda: [h.fa]
    with pytest.raises(ValueError):
        api.Backend().copy(41, 42, "Regular", "Other", False, Options())
    assert not h.events and not h.a.events and not h.b.events


def test_missing_glyph_layer_and_empty_selected_requests_are_complete_noops(
    monkeypatch,
):
    h = host(monkeypatch)
    h.fb.glyphs = []
    result = api.Backend().copy(41, 42, "Regular", "Other", False, Options())
    assert result["anchors"] == 0 and result["skipped"] == (
        "Destination glyph not found: a",
    )
    h.fb.glyphs = [NS(name="a")]
    result = api.Backend().copy(41, 42, "missing", "Other", False, Options())
    assert result["anchors"] == 0 and len(result["skipped"]) == 1
    monkeypatch.setattr(cap, "selected", lambda source, deadline: ())
    assert (
        api.Backend().copy(41, 42, "Regular", "Other", True, Options())["anchors"] == 0
    )
    assert not h.events


def test_partial_attachment_is_finalized_once_and_not_rolled_back_or_false_success(
    monkeypatch,
):
    h = host(monkeypatch)
    h.target.fail = True
    with pytest.raises(api.PartialWriteError, match="partial add") as error:
        api.Backend().copy(41, 42, "Regular", "Other", False, Options())
    assert (
        error.value.attempted == 1 and len(h.target.anchors) == 2 and len(h.events) == 1
    )
    assert not h.a.events and h.b.lastModified == "same UTC stamp"


def test_postnotification_source_mutation_is_detected_as_partial_failure(monkeypatch):
    h = host(monkeypatch)

    def notification(*args):
        h.events.append(args)
        h.source.anchors[0].name = "unrelated source mutation"

    h.native.flItems = lambda: NS(notifyChangesApplied=notification)
    with pytest.raises(api.PartialWriteError, match="differ from the plan"):
        api.Backend().copy(41, 42, "Regular", "Other", False, Options())
    assert len(h.events) == 1


def test_appearance_history_hold_and_suffixed_default_appearance_are_precise(
    monkeypatch,
):
    h = host(monkeypatch)
    h.source.anchors[0].appearance = 0
    with pytest.raises(ValueError, match="default-appearance"):
        api.Backend().copy(41, 42, "Regular", "Other", False, Options())
    assert not h.events
    h.target.anchors = [Pin("top")]
    result = api.Backend().copy(
        41,
        42,
        "Regular",
        "Other",
        False,
        Options(rename_destination=False, suffix=".bak"),
    )
    assert (
        result["anchors"] == 1
        and h.target.anchors[-1].appearance == 0
        and h.target.anchors[-1].name == "top.bak"
    )


@pytest.mark.parametrize(
    "rename,rename_destination", [(False, False), (True, False), (True, True)]
)
def test_same_font_same_layer_is_a_real_writer_not_a_noop(
    monkeypatch, rename, rename_destination
):
    h = host(monkeypatch)
    h.source.anchors.append(Pin("top"))
    result = api.Backend().copy(
        41,
        41,
        "Regular",
        "Regular",
        False,
        Options(rename=rename, rename_destination=rename_destination),
    )
    assert result["anchors"] == 2 and result["layers"] == 1
    assert len(h.source.anchors) == (4 if rename else 2)
    assert len(h.events) == 1 and h.events[0][1] == [h.source, h.a] and not h.b.events


def test_missing_registration_and_source_glyph_disappearance_fail_closed(monkeypatch):
    h = host(monkeypatch)
    h.native.flWorkspace.instance().packages = lambda: [h.pa]
    with pytest.raises(ValueError, match="not registered"):
        api.Backend().fonts()
    h = host(monkeypatch)
    h.pa.findName = lambda name: None
    with pytest.raises(ValueError, match="identity changed"):
        api.Backend().copy(41, 42, "Regular", "Other", False, Options())
    assert not h.events


def test_unrelated_auto_dependant_refuses_without_initializing_history(monkeypatch):
    h = host(monkeypatch)
    layer = Layer(55, "Other", [])
    layer.autoLayer = True
    layer.shapes = [NS(isComponent=True, shapeData=NS(componentGlyph="a"))]
    dependent = Glyph(56, "aacute", layer)
    h.fb.glyphs.append(NS(name="aacute"))
    h.pb.findName = lambda name: h.b if name == "a" else dependent
    with pytest.raises(ValueError, match="dependants"):
        api.Backend().copy(41, 42, "Regular", "Other", False, Options())
    assert not h.events and not h.a.events and not h.b.events


def test_notification_exception_is_not_false_success_and_keeps_actual_destination_stamp(
    monkeypatch,
):
    h = host(monkeypatch)

    def refuse(*args):
        raise RuntimeError("notification failure")

    h.native.flItems = lambda: NS(notifyChangesApplied=refuse)
    with pytest.raises(api.PartialWriteError, match="notification failure"):
        api.Backend().copy(41, 42, "Regular", "Other", False, Options())
    assert h.b.lastModified == "same UTC stamp" and len(h.target.anchors) == 2


@pytest.mark.parametrize("delta", ["metrics", "metadata", "count", "dependency"])
def test_final_notification_deltas_are_complete_failed_writes_not_green_counts(
    monkeypatch, delta
):
    h = host(monkeypatch)

    def mutate(*args):
        h.events.append(args)
        if delta == "metrics":
            h.target.advanceWidth += 1
        elif delta == "metadata":
            h.target.anchors[-1].appearance = 8
        elif delta == "count":
            h.target.anchors.append(Pin("extra"))
        else:
            h.target.shapes.append(
                NS(isComponent=True, shapeData=NS(componentGlyph="base"))
            )

    h.native.flItems = lambda: NS(notifyChangesApplied=mutate)
    with pytest.raises(api.PartialWriteError):
        api.Backend().copy(41, 42, "Regular", "Other", False, Options())
    assert len(h.events) == 1


def test_clone_source_mutation_is_detected_before_history(monkeypatch):
    h = host(monkeypatch)
    original = h.source.anchors[0].clone

    def mutate():
        result = original()
        h.source.anchors[0].name = "mutated"
        return result

    h.source.anchors[0].clone = mutate
    with pytest.raises(ValueError, match="before history"):
        api.Backend().copy(41, 42, "Regular", "Other", False, Options())
    assert not h.events and not h.a.events and not h.b.events
