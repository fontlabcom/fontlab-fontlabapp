# this_file: tests/test_anchor_duplicates_native.py
"""Exact identity removal, preflight atomicity and recoverable partial failures."""

from types import SimpleNamespace as NS
from unittest.mock import Mock

import fontlabapp.anchors.duplicates.native as api
import pytest
from fontlabapp.anchors.duplicates.model import Pin


@pytest.fixture
def owned(monkeypatch):
    events = []
    pins = [
        NS(
            id=i,
            name=n,
            point=NS(x=lambda: 12.5, y=lambda: -0.5),
            appearance=9,
            anchor=True,
            cloudEnabled=False,
            markEnabled=False,
            style=2,
            expressionX="x+4",
            expressionY="y",
            getProperties=list,
        )
        for i, n in [(1, "top"), (2, "top.1"), (3, "_a"), (4, "_b")]
    ]
    layer = NS(id=20, autoLayer=False, anchors=pins[:], isNull=False, name="Regular")
    glyph = NS(
        id=10,
        name="A",
        lastModified="before",
        isNull=False,
        findLayer=lambda master: layer,
        layers=[layer],
    )
    package = NS(
        id=7,
        fgId=70,
        master="Regular",
        masters=["Regular"],
        findName=lambda name: glyph,
    )
    layer.shapes = []
    layer.checkInitHistoryState = lambda n: events.append(("init-layer", n))
    glyph.checkInitHistoryState = lambda n: events.append(("init-glyph", n))

    def remove(pin):
        events.append(("remove", pin.id))
        layer.anchors[:] = [p for p in layer.anchors if p is not pin]

    layer.removeAnchor = remove
    native = NS(
        flItems=lambda: NS(
            notifyChangesApplied=lambda title, objects: events.append(
                ("notify", title, objects)
            )
        ),
        UpdateAll=Mock(side_effect=AssertionError("Global UpdateAll is unsafe")),
    )
    monkeypatch.setattr(
        api,
        "_native",
        lambda name: (
            native
            if name == "fontlab"
            else NS(QtCore=NS(QDateTime=NS(currentDateTimeUtc=lambda: "stamp")))
        ),
    )
    monkeypatch.setattr(api, "current_package", lambda: package)
    monkeypatch.setattr(
        api,
        "context",
        lambda p, deadline: (
            (int(p.id), int(p.fgId), p.master),
            ("A",),
            ("A",),
            tuple(p.masters),
        ),
    )
    backend = api.Backend()
    return NS(
        events=events,
        pins=pins,
        layer=layer,
        glyph=glyph,
        package=package,
        backend=backend,
        native=native,
    )


def test_capture_retains_order_identity_raw_points_known_attributes_and_double_pass(
    owned,
):
    o = owned
    facts = o.backend.capture()
    assert facts.layers[0].pins[0] == Pin(
        1, "top", 12.5, -0.5, (9, True, False, False, 2, "x+4", "y")
    )
    assert facts.selection == ("A",) and facts.masters == ("Regular",)
    assert facts.dependencies == (("A", False, ()),)
    assert not o.events


def test_apply_removes_only_original_extras_and_one_final_notification(owned):
    o = owned
    facts = o.backend.capture()
    survivor = o.pins[0]
    assert o.backend.apply(facts, False, False) == {"anchors": 1, "layers": 1}
    assert o.layer.anchors == [survivor, o.pins[2], o.pins[3]]
    assert [e[0] for e in o.events] == ["init-layer", "init-glyph", "remove", "notify"]
    assert o.events[-1][2] == [o.layer, o.glyph] and o.glyph.lastModified == "stamp"
    assert survivor.cloudEnabled is False and survivor.expressionX == "x+4"
    o.native.UpdateAll.assert_not_called()


@pytest.mark.parametrize(
    "change",
    [
        "point",
        "name",
        "identity",
        "auto",
        "font",
        "master",
        "selection",
        "dependencies",
        "pin-metadata",
    ],
)
def test_preflight_drift_refuses_before_history_or_writes(owned, monkeypatch, change):
    o = owned
    facts = o.backend.capture()
    if change == "point":
        o.pins[0].point.x = lambda: 12.51
    elif change == "name":
        o.pins[0].name = "other"
    elif change == "identity":
        o.layer.id = 99
    elif change == "auto":
        o.layer.autoLayer = True
    elif change == "font":
        o.package.id = 99
    elif change == "master":
        o.package.masters = ["Bold"]
    elif change == "selection":
        monkeypatch.setattr(
            api, "context", lambda p, d: ((7, 70, "Regular"), ("A",), (), ("Regular",))
        )
    elif change == "dependencies":
        o.layer.shapes = [NS(isComponent=True, shapeData=NS(componentGlyph="X"))]
    else:
        o.pins[0].appearance = 5
    with pytest.raises(ValueError):
        o.backend.apply(facts, False, False)
    assert not o.events and o.layer.anchors == o.pins


def test_automatic_dependant_refuses_whole_batch_before_history(owned, monkeypatch):
    o = owned
    facts = o.backend.capture()
    monkeypatch.setattr(
        api, "affected_auto_layers", lambda records, targets: ["Aacute"]
    )
    with pytest.raises(ValueError, match="automatic dependants"):
        o.backend.apply(facts, False, False)
    assert not o.events


def test_partial_remove_failure_still_notifies_once_and_never_claims_success_or_rebuilds(
    owned,
):
    o = owned
    facts = o.backend.capture()
    original = o.layer.removeAnchor

    def remove(pin):
        original(pin)
        if pin.id == 4:
            raise RuntimeError("injected after native removal")

    o.layer.removeAnchor = remove
    with pytest.raises(api.PartialWriteError, match="Edit > Undo") as error:
        o.backend.apply(facts, True, False)
    assert error.value.removed == 1 and error.value.attempted == 2
    assert [p.id for p in o.layer.anchors] == [1, 3]
    assert [e[0] for e in o.events].count("notify") == 1
    assert o.events[-1][0] == "notify" and o.glyph.lastModified == "stamp"


def test_notify_failure_is_a_failed_partial_outcome_with_retained_cause(owned):
    o = owned
    facts = o.backend.capture()
    o.native.flItems = lambda: NS(
        notifyChangesApplied=Mock(side_effect=RuntimeError("notify failed"))
    )
    with pytest.raises(api.PartialWriteError, match="notify failed"):
        o.backend.apply(facts, False, False)


def test_noop_initial_empty_and_automatic_layers_never_open_history(owned):
    o = owned
    o.layer.autoLayer = True
    facts = o.backend.capture()
    assert o.backend.apply(facts, True, False) == {"anchors": 0, "layers": 0}
    assert not o.events


def test_deadline_and_changed_between_capture_passes_abort_complete_result(
    owned, monkeypatch
):
    o = owned
    import fontlabapp.anchors.duplicates.capture as capture

    monkeypatch.setattr(capture, "monotonic", lambda: 100)
    monkeypatch.setattr(api, "monotonic", lambda: 100)
    with pytest.raises(TimeoutError):
        api.check(1)
    monkeypatch.setattr(api, "read", Mock(side_effect=[((), ()), ((1,), ())]))
    with pytest.raises(ValueError, match="during capture"):
        o.backend.capture()


def test_actual_font_carrier_selection_order_null_and_missing_layers(
    owned, monkeypatch
):
    import fontlabapp.anchors.duplicates.capture as c

    o = owned

    class Font:
        id = 70

        def __len__(self):
            return 2

        def __getitem__(self, index):
            return NS(name=("A", "B")[index])

    monkeypatch.setattr(
        c,
        "_native",
        lambda name: NS(fl=NS(font=Font(), Selected=lambda index: index == 1)),
    )
    assert c.context(o.package, c.monotonic() + 2) == (
        (7, 70, "Regular"),
        ("A", "B"),
        ("B",),
        ("Regular",),
    )
    o.package.fgId = 99
    with pytest.raises(ValueError, match="carrier"):
        c.context(o.package, c.monotonic() + 2)
    o.glyph.findLayer = lambda master: None
    assert c.read(o.package, ("A",), ("Regular",), c.monotonic() + 2)[0] == ()
    o.glyph.findLayer = lambda master: NS(isNull=True)
    assert c.read(o.package, ("A",), ("Regular",), c.monotonic() + 2)[0] == ()
    o.package.findName = lambda name: None
    with pytest.raises(ValueError, match="Glyph source"):
        c.read(o.package, ("A",), ("Regular",), c.monotonic() + 2)


def test_empty_font_binding_and_wrong_thread_never_create_history(owned, monkeypatch):
    import fontlabapp.anchors.duplicates.capture as c

    o = owned
    monkeypatch.setattr(api, "current_package", lambda: None)
    assert o.backend.capture() is None
    monkeypatch.setattr(api, "current_package", lambda: o.package)
    with pytest.raises(ValueError, match="original font"):
        o.backend.capture()
    monkeypatch.setattr(c, "current_thread", lambda: None)
    with pytest.raises(RuntimeError, match="main UI thread"):
        api.Backend().capture()
    assert not o.events


def test_preparation_failure_and_native_noop_are_never_success(owned):
    o = owned
    facts = o.backend.capture()
    o.layer.removeAnchor = lambda pin: None
    with pytest.raises(api.PartialWriteError, match="did not remove"):
        o.backend.apply(facts, False, False)
    assert [p.id for p in o.layer.anchors] == [1, 2, 3, 4]
    o.events.clear()
    o.glyph.checkInitHistoryState = Mock(
        side_effect=RuntimeError("history init failed")
    )
    with pytest.raises(RuntimeError, match="history init failed"):
        o.backend.apply(facts, False, False)
    assert not any(event[0] in ("remove", "notify") for event in o.events)


def test_opening_selection_remains_captured_across_refresh(owned, monkeypatch):
    o = owned
    first = o.backend.capture()
    monkeypatch.setattr(
        api, "context", lambda p, d: ((7, 70, "Regular"), ("A",), (), ("Regular",))
    )
    refreshed = o.backend.capture()
    assert refreshed.selection == first.selection == ("A",)
    assert refreshed.context != first.context


def test_target_race_before_history_refuses_without_writes(owned, monkeypatch):
    o = owned
    facts = o.backend.capture()
    monkeypatch.setattr(o.backend, "validate", lambda *args, **kwargs: None)
    o.layer.id = 999
    with pytest.raises(ValueError, match="before history"):
        o.backend.apply(facts, False, False)
    assert not o.events


def test_aliasing_across_masters_is_refused_before_any_history(owned):
    import fontlabapp.anchors.duplicates.capture as c

    o = owned
    with pytest.raises(ValueError, match="ambiguous ownership"):
        c.read(o.package, ("A",), ("Regular", "Bold"), c.monotonic() + 2)
    assert not o.events


def test_stamp_failure_still_finalizes_once_and_reports_failed_partial_outcome(owned):
    o = owned

    class Glyph:
        id = 10

        @property
        def lastModified(self):
            return "before"

        @lastModified.setter
        def lastModified(self, value):
            raise RuntimeError("stamp refused")

        def checkInitHistoryState(self, index):
            o.events.append(("init-glyph", index))

    glyph = Glyph()
    with pytest.raises(api.PartialWriteError, match="stamp refused"):
        api.remove([(glyph, o.layer, (o.pins[1],))], api.monotonic() + 2)
    assert [event[0] for event in o.events].count("notify") == 1
    assert [p.id for p in o.layer.anchors] == [1, 3, 4]


@pytest.mark.parametrize("style", ["FreePosition", "ShapeBound", 2])
def test_native_style_scalar_survives_full_capture_and_identity_removal(owned, style):
    for pin in owned.pins:
        pin.style = style
    facts = owned.backend.capture()
    assert all(pin.state[4] == style for pin in facts.layers[0].pins)
    assert owned.events == []
    before = [(pin.id, pin.name, pin.style, pin.point) for pin in owned.pins]
    assert owned.backend.apply(facts, False, False) == {"anchors": 1, "layers": 1}
    assert [pin.id for pin in owned.layer.anchors] == [1, 3, 4]
    assert [(pin.id, pin.name, pin.style, pin.point) for pin in owned.pins] == before
    assert sum(event[0] == "notify" for event in owned.events) == 1


def test_native_style_scalar_change_is_stale_before_anchor_duplicate_history(owned):
    for pin in owned.pins:
        pin.style = "FreePosition"
    facts = owned.backend.capture()
    owned.pins[0].style = "ShapeBound"
    with pytest.raises(ValueError, match="Source changed"):
        owned.backend.apply(facts, False, False)
    assert owned.events == [] and owned.layer.anchors == owned.pins


def test_context_when_legacy_font_lacks_id_then_package_path_identifies_carrier(
    owned, monkeypatch
):
    """FontLab 9's FL.fl.font has no ``id`` (live 2026-11-03, Issue 250)."""
    import fontlabapp.anchors.duplicates.capture as c
    import fontlabapp.core.scripting as scripting

    o = owned
    o.package.isNull = False
    o.package.path = "/fonts/a.vfc"

    class Font:
        file_name = "/fonts/a.vfc"

        def __len__(self):
            return 1

        def __getitem__(self, index):
            return NS(name="A")

    def native(name):
        return NS(
            fl=NS(font=Font(), Selected=lambda index: True),
            flWorkspace=NS(instance=lambda: NS(currentPackage=o.package)),
        )

    monkeypatch.setattr(c, "_native", native)
    monkeypatch.setattr(scripting, "_native", native)
    assert c.context(o.package, c.monotonic() + 2)[0] == (7, 70, "Regular")
    o.package.path = "/fonts/other.vfc"
    with pytest.raises(ValueError, match="carrier"):
        c.context(o.package, c.monotonic() + 2)
