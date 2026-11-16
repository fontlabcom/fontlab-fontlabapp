# this_file: tests/test_anchor_edit.py
# SPDX-License-Identifier: Apache-2.0
"""Native-shaped point moves: preparation never opens history."""

from itertools import count
from types import SimpleNamespace as NS

import pytest

import fontlabapp.anchors.edit as api


@pytest.fixture
def owned(monkeypatch):
    events, ids, glyphs = [], count(1), {}

    def point(x, y):
        events.append(("point", x, y))
        return NS(x=lambda: x, y=lambda: y)

    def glyph(name="H", points=(("top", 13.25, 27.75),), auto=False):
        pins = [
            NS(
                id=next(ids),
                name=n,
                point=NS(x=lambda x=x: x, y=lambda y=y: y),
                appearance=9,
                anchor=True,
                expressionX="x",
                expressionY="y",
                style=0,
                cloudEnabled=True,
                markEnabled=False,
            )
            for n, x, y in points
        ]
        layer = NS(
            id=next(ids),
            isNull=False,
            autoLayer=auto,
            anchors=pins,
            advanceWidth=600,
            shapes=[],
            recipe="",
            boundingBox=NS(
                x=lambda: 10, y=lambda: 20, width=lambda: 200, height=lambda: 400
            ),
            checkInitHistoryState=lambda _: events.append(("init-layer", name)),
        )
        g = NS(
            id=next(ids),
            name=name,
            isNull=False,
            layers=[layer],
            activeLayer=layer,
            findLayer=lambda m: layer if m == "Regular" else None,
            lastModified="before",
            checkInitHistoryState=lambda _: events.append(("init-glyph", name)),
        )
        glyphs[name] = g
        return g, layer

    native = NS(
        UpdateAll=lambda: events.append(("update",)),
        flItems=lambda: NS(
            notifyChangesApplied=lambda title, items: events.append(
                ("notify", title, items)
            )
        ),
    )
    qt = NS(QtCore=NS(QPointF=point, QDateTime=NS(currentDateTimeUtc=lambda: "UTC")))
    monkeypatch.setattr(
        api, "_native", lambda name: native if name == "fontlab" else qt
    )
    monkeypatch.setattr(
        api,
        "dependency_values",
        lambda p: tuple(
            (
                g.name,
                l.autoLayer,
                tuple(s.shapeData.componentGlyph for s in l.shapes if s.isComponent),
            )
            for g in glyphs.values()
            for l in g.layers
        ),
    )
    package = NS(
        id=99, master="Regular", masters=["Regular", "Bold"], findName=glyphs.get
    )
    return NS(events=events, glyph=glyph, package=package, native=native)


def extra_master(glyph, regular, master, recipe):
    """Add an inactive master without changing the glyph's notification layer."""
    extra = NS(**regular.__dict__)
    extra.id += 1000
    extra.recipe = recipe
    extra.anchors = [NS(**pin.__dict__) for pin in regular.anchors]
    for pin in extra.anchors:
        pin.id += 2000
    glyph.layers.append(extra)
    glyph.findLayer = {"Regular": regular, master: extra}.get
    return extra


@pytest.mark.parametrize("problem", ["explicit", "missing", "foreign"])
def test_target_active_layer_preflight_has_no_target_exclusion(
    owned, monkeypatch, problem
):
    g, regular = owned.glyph()
    bold = extra_master(
        g, regular, "Bold", "Hbase+acute" if problem == "explicit" else ""
    )
    bold.autoLayer = True
    g.activeLayer = bold
    if problem == "missing":
        g.activeLayer = None
    elif problem == "foreign":
        g.activeLayer = NS(id=99999, isNull=False)
    monkeypatch.setattr(
        api,
        "dependency_values",
        lambda _: (("H", False, ()), ("H", True, ("base",)), ("base", False, ())),
    )
    with pytest.raises(ValueError, match="recipe|active layer"):
        api.prepare_point_moves(
            owned.package, [(g, "Regular", [(regular.anchors[0], (20, 27.75))])]
        )
    assert not owned.events


def test_target_default_active_auto_layer_initializes_without_notification(
    owned, monkeypatch
):
    g, regular = owned.glyph()
    bold = extra_master(g, regular, "Bold", "")
    bold.autoLayer = True
    bold.checkInitHistoryState = lambda _: owned.events.append(("init-active", "H"))
    g.activeLayer = bold
    monkeypatch.setattr(
        api,
        "dependency_values",
        lambda _: (("H", False, ()), ("H", True, ("base",)), ("base", False, ())),
    )
    prepared = api.prepare_point_moves(
        owned.package, [(g, "Regular", [(regular.anchors[0], (20, 27.75))])]
    )
    api.apply_point_moves(prepared, "target auto")
    assert ("init-active", "H") in owned.events
    items = next(event[2] for event in owned.events if event[0] == "notify")
    assert bold not in items and regular in items and g in items


def test_target_inactive_explicit_recipe_stays_supported_and_frozen(owned, monkeypatch):
    g, regular = owned.glyph()
    bold = extra_master(g, regular, "Bold", "Hbase+acute")
    bold.autoLayer = True
    monkeypatch.setattr(
        api,
        "dependency_values",
        lambda _: (("H", False, ()), ("H", True, ("base",)), ("base", False, ())),
    )
    prepared = api.prepare_point_moves(
        owned.package, [(g, "Regular", [(regular.anchors[0], (20, 27.75))])]
    )
    api.apply_point_moves(prepared, "inactive target")
    assert bold.recipe == "Hbase+acute" and g.activeLayer is regular


def test_unrelated_target_master_recipe_does_not_veto_mixed_master_batch(
    owned, monkeypatch
):
    g, regular = owned.glyph()
    inactive = extra_master(g, regular, "Bold", "base+acute")
    inactive.autoLayer = True
    other, other_regular = owned.glyph("other")
    other_bold = extra_master(other, other_regular, "Bold", "")
    monkeypatch.setattr(
        api,
        "dependency_values",
        lambda _: (
            ("H", False, ()),
            ("H", True, ("base",)),
            ("base", False, ()),
            ("other", False, ()),
        ),
    )
    prepared = api.prepare_point_moves(
        owned.package,
        [
            (g, "Regular", [(regular.anchors[0], (20, 27.75))]),
            (other, "Bold", [(other_bold.anchors[0], (30, 27.75))]),
        ],
    )
    api.apply_point_moves(prepared, "mixed masters")
    assert inactive.recipe == "base+acute" and inactive.anchors[0].point.x() == 13.25


@pytest.mark.parametrize(
    "setter_fails,cleanup_fails", [(True, False), (False, False), (True, True)]
)
def test_postwrite_getter_failure_finalizes_and_preserves_first_error(
    owned, monkeypatch, setter_fails, cleanup_fails
):
    g, layer = owned.glyph()
    dependent, pending_layer = owned.glyph("shared-target")
    unrelated, unrelated_layer = owned.glyph("unattempted")
    monkeypatch.setattr(
        api,
        "dependency_values",
        lambda _: (
            ("H", False, ()),
            ("shared-target", False, ("H",)),
            ("unattempted", False, ()),
        ),
    )

    class FailsAfterWrite:
        def __init__(self, pin):
            self.__dict__.update(pin.__dict__)
            self._stored = pin.point
            self._written = False

        @property
        def point(self):
            if self._written:
                raise ValueError("postwrite getter failed")
            return self._stored

        @point.setter
        def point(self, value):
            self._stored, self._written = value, True
            if setter_fails:
                raise RuntimeError("original partial setter")

    pin = layer.anchors[0] = FailsAfterWrite(layer.anchors[0])
    prepared = api.prepare_point_moves(
        owned.package,
        [
            (g, "Regular", [(pin, (20, 27.75))]),
            (dependent, "Regular", [(pending_layer.anchors[0], (30, 27.75))]),
            (unrelated, "Regular", [(unrelated_layer.anchors[0], (40, 27.75))]),
        ],
    )
    if cleanup_fails:

        def fail_refresh():
            owned.events.append(("update",))
            raise RuntimeError("cleanup refresh")

        owned.native.UpdateAll = fail_refresh
    with pytest.raises(
        RuntimeError if setter_fails else ValueError,
        match="original partial setter" if setter_fails else "postwrite getter failed",
    ) as caught:
        api.apply_point_moves(prepared, "uncertain move")
    assert pin._stored.x() == 20 and g.lastModified == "UTC"
    assert dependent.lastModified == "UTC"
    notified = next(event[2] for event in owned.events if event[0] == "notify")
    assert dependent in notified
    if setter_fails:
        assert unrelated.lastModified == "before" and unrelated not in notified
        assert (
            pending_layer.anchors[0].point.x()
            == unrelated_layer.anchors[0].point.x()
            == 13.25
        )
    else:
        assert unrelated.lastModified == "UTC" and unrelated in notified
    assert [event[0] for event in owned.events[-2:]] == ["notify", "update"]
    assert any(
        "read" in note.lower() and "uncertain" in note.lower()
        for note in caught.value.__notes__
    )
    if cleanup_fails:
        assert any("cleanup refresh" in note for note in caught.value.__notes__)


def test_regular_move_keeps_inactive_explicit_master_recipe_snapshot(
    owned, monkeypatch
):
    g, layer = owned.glyph()
    dependent, regular = owned.glyph("automatic", auto=True)
    bold = extra_master(dependent, regular, "Bold", "H+acute")
    monkeypatch.setattr(
        api,
        "dependency_values",
        lambda _: (("H", False, ()), ("automatic", True, ("H",))),
    )
    prepared = api.prepare_point_moves(
        owned.package, [(g, "Regular", [(layer.anchors[0], (20, 27.75))])]
    )
    assert [d.name for d in prepared.dependants] == ["automatic"]
    api.apply_point_moves(prepared, "Regular only")
    assert bold.recipe == "H+acute" and dependent.activeLayer is regular
    notified = next(e[2] for e in owned.events if e[0] == "notify")
    assert regular not in notified and bold not in notified


@pytest.mark.parametrize("change", ["recipe", "active"])
def test_inactive_master_and_active_layer_drift_are_stale(owned, monkeypatch, change):
    g, layer = owned.glyph()
    dependent, regular = owned.glyph("automatic", auto=True)
    bold = extra_master(dependent, regular, "Bold", "H+acute")
    monkeypatch.setattr(
        api,
        "dependency_values",
        lambda _: (("H", False, ()), ("automatic", True, ("H",))),
    )
    prepared = api.prepare_point_moves(
        owned.package, [(g, "Regular", [(layer.anchors[0], (20, 27.75))])]
    )
    if change == "recipe":
        bold.recipe = "H+grave"
    else:
        dependent.activeLayer = bold
    with pytest.raises(ValueError, match="changed"):
        api.apply_point_moves(prepared, "stale")
    assert not any(e[0].startswith("init") for e in owned.events)


@pytest.mark.parametrize("affected", ["active", "edited-master"])
def test_actually_affected_explicit_master_recipe_remains_refused(
    owned, monkeypatch, affected
):
    g, layer = owned.glyph()
    dependent, regular = owned.glyph("automatic", auto=True)
    bold = extra_master(dependent, regular, "Bold", "H+acute")
    monkeypatch.setattr(
        api,
        "dependency_values",
        lambda _: (("H", False, ()), ("automatic", True, ("H",))),
    )
    jobs = [(g, "Regular", [(layer.anchors[0], (20, 27.75))])]
    if affected == "active":
        dependent.activeLayer = bold
    else:
        source_bold = extra_master(g, layer, "Bold", "")
        jobs.append((g, "Bold", [(source_bold.anchors[0], (30, 27.75))]))
        source_bold.anchors = [NS(**layer.anchors[0].__dict__)]
        source_bold.anchors[0].id += 1000
        jobs[-1] = (g, "Bold", [(source_bold.anchors[0], (30, 27.75))])
    with pytest.raises(ValueError, match="recipe"):
        api.prepare_point_moves(owned.package, jobs)
    assert not owned.events


@pytest.mark.parametrize("bad", ["missing-active", "foreign-active", "missing-master"])
def test_unknown_notification_layer_or_affected_master_refuses(owned, monkeypatch, bad):
    g, layer = owned.glyph()
    dependent, _ = owned.glyph("automatic", auto=True)
    monkeypatch.setattr(
        api,
        "dependency_values",
        lambda _: (("H", False, ()), ("automatic", True, ("H",))),
    )
    if bad == "missing-active":
        dependent.activeLayer = None
    elif bad == "foreign-active":
        dependent.activeLayer = NS(id=999, isNull=False)
    else:
        dependent.findLayer = lambda _: None
    with pytest.raises(ValueError, match="layer"):
        api.prepare_point_moves(
            owned.package, [(g, "Regular", [(layer.anchors[0], (20, 27.75))])]
        )
    assert not owned.events


def test_prepare_then_apply_preserves_pin_values_and_one_final_history(owned):
    g, layer = owned.glyph()
    pin = layer.anchors[0]
    prepared = api.prepare_point_moves(
        owned.package, [(g, "Regular", [(pin, (20, 27.75))])]
    )
    assert [e[0] for e in owned.events] == ["point"]
    assert api.apply_point_moves(prepared, "Owned move") == {"anchors": 1, "layers": 1}
    assert layer.anchors[0] is pin and pin.point.y() == 27.75
    assert (pin.appearance, pin.style, pin.expressionX, pin.expressionY) == (
        9,
        0,
        "x",
        "y",
    )
    assert g.lastModified == "UTC"
    assert [e[0] for e in owned.events] == [
        "point",
        "init-layer",
        "init-glyph",
        "notify",
        "update",
    ]


@pytest.mark.parametrize(
    "axis,value", [(0, float("nan")), (1, float("inf")), (0, "12"), (1, None)]
)
def test_invalid_later_point_refuses_entire_batch_without_constructors(
    owned, axis, value
):
    g, layer = owned.glyph(points=(("top", 1, 2), ("bottom", 3, 4)))
    bad = [5, 6]
    bad[axis] = value
    with pytest.raises(ValueError):
        api.prepare_point_moves(
            owned.package,
            [
                (
                    g,
                    "Regular",
                    [(layer.anchors[0], (10, 20)), (layer.anchors[1], tuple(bad))],
                )
            ],
        )
    assert not owned.events


def test_origin_noop_has_no_construction_history_or_dates(owned):
    g, layer = owned.glyph(points=(("bottom", 0, 0),))
    prepared = api.prepare_point_moves(
        owned.package, [(g, "Regular", [(layer.anchors[0], (0, 0))])]
    )
    assert api.apply_point_moves(prepared, "noop") == {"anchors": 0, "layers": 0}
    assert not owned.events and g.lastModified == "before"


def test_changing_origin_is_refused_before_history(owned):
    g, layer = owned.glyph()
    with pytest.raises(ValueError, match="Redo"):
        api.prepare_point_moves(
            owned.package, [(g, "Regular", [(layer.anchors[0], (0, 0))])]
        )
    assert not owned.events


@pytest.mark.parametrize(
    "change",
    ["point", "style", "pin", "glyph", "master", "bounds", "width", "dependency"],
)
def test_stale_source_or_identity_refuses_before_history(owned, change):
    g, layer = owned.glyph()
    pin = layer.anchors[0]
    prepared = api.prepare_point_moves(
        owned.package, [(g, "Regular", [(pin, (20, 27.75))])]
    )
    if change == "point":
        pin.point = NS(x=lambda: 13.26, y=lambda: 27.75)
    elif change == "style":
        pin.style = 1
    elif change == "pin":
        pin.id += 100
    elif change == "glyph":
        g.id += 100
    elif change == "master":
        owned.package.master = "Bold"
    elif change == "bounds":
        layer.boundingBox.x = lambda: 11
    elif change == "width":
        layer.advanceWidth = 601
    else:
        owned.glyph("new")
    with pytest.raises(ValueError, match="changed"):
        api.apply_point_moves(prepared, "stale")
    assert not any(e[0].startswith("init") for e in owned.events)


def test_auto_dependency_initializes_all_layers_but_notifies_only_glyphs(owned):
    g, layer = owned.glyph()
    _, dependent = owned.glyph("Hacute", auto=True)
    dependent.shapes = [
        NS(
            id=500,
            isComponent=True,
            shapeData=NS(componentGlyph="H"),
            transform=NS(
                **{
                    k: lambda k=k: 1 if k in {"m11", "m22"} else 0
                    for k in ("m11", "m12", "m21", "m22", "dx", "dy")
                }
            ),
        )
    ]
    prepared = api.prepare_point_moves(
        owned.package, [(g, "Regular", [(layer.anchors[0], (20, 27.75))])]
    )
    api.apply_point_moves(prepared, "closure")
    assert ("init-layer", "Hacute") in owned.events
    notified = next(e[2] for e in owned.events if e[0] == "notify")
    assert dependent not in notified and [
        getattr(item, "name", None) for item in notified
    ] == [None, "H", "Hacute"]
    assert owned.package.findName("Hacute").lastModified == "UTC"


@pytest.mark.parametrize("master", ["unknown", "Bold"])
def test_unknown_or_missing_master_and_foreign_pin_refuse(owned, master):
    g, layer = owned.glyph()
    with pytest.raises(ValueError):
        api.prepare_point_moves(
            owned.package, [(g, master, [(layer.anchors[0], (20, 27.75))])]
        )
    assert not owned.events


def test_constructor_failure_leaves_history_and_original_points_untouched(
    owned, monkeypatch
):
    g, layer = owned.glyph()

    def fail(*args):
        raise RuntimeError("constructor")

    monkeypatch.setattr(api._native("PythonQt").QtCore, "QPointF", fail)
    with pytest.raises(RuntimeError, match="constructor"):
        api.prepare_point_moves(
            owned.package, [(g, "Regular", [(layer.anchors[0], (20, 27.75))])]
        )
    assert not owned.events and layer.anchors[0].point.x() == 13.25


@pytest.mark.parametrize("observer", ["notify", "update"])
@pytest.mark.parametrize("fails", [False, True])
def test_forward_observer_preserves_target_and_transitive_history_dates(
    owned, monkeypatch, observer, fails
):
    from contextlib import nullcontext

    target, layer = owned.glyph()
    bridge, _ = owned.glyph("bridge")
    dependent, auto = owned.glyph("accented", auto=True)
    unrelated, _ = owned.glyph("unrelated")
    affected, history, clocks = [target, bridge, dependent], [], []
    monkeypatch.setattr(
        api,
        "dependency_values",
        lambda _: (
            ("H", False, ()),
            ("bridge", False, ("H",)),
            ("accented", True, ("bridge",)),
            ("unrelated", False, ()),
        ),
    )
    prepared = api.prepare_point_moves(
        owned.package, [(target, "Regular", [(layer.anchors[0], (20, 27.75))])]
    )

    def clock():
        clocks.append(True)
        return "committed UTC"

    def overwrite():
        for glyph in affected:
            glyph.lastModified = "later UTC second"
        if fails:
            raise RuntimeError("owned observer failure")

    def notify(title, items):
        assert auto not in items, "Automatic layers must never be notified"
        history.append([glyph.lastModified for glyph in affected])
        if observer == "notify":
            overwrite()

    def update():
        if observer == "update":
            overwrite()

    monkeypatch.setattr(
        api._native("PythonQt").QtCore.QDateTime, "currentDateTimeUtc", clock
    )
    owned.native.flItems = lambda: NS(notifyChangesApplied=notify)
    owned.native.UpdateAll = update
    with (
        pytest.raises(RuntimeError, match="owned observer failure")
        if fails
        else nullcontext()
    ):
        api.apply_point_moves(prepared, "Owned date boundary")
    assert history == [["committed UTC"] * 3], (
        "History must capture every affected date"
    )
    assert [g.lastModified for g in affected] == history[0], (
        "Observers changed the recorded dates"
    )
    assert clocks == [True], "Finalization must reuse the chosen transaction timestamp"
    assert unrelated.lastModified == "before", "Unrelated dates must remain untouched"


def test_partial_setter_failure_still_notifies_and_refreshes(owned):
    g, layer = owned.glyph(points=(("top", 1, 2), ("bottom", 3, 4)))

    class Broken:
        def __init__(self, pin):
            self.__dict__.update(pin.__dict__)

        def __setattr__(self, name, value):
            if name == "point":
                raise RuntimeError("setter")
            object.__setattr__(self, name, value)

    layer.anchors[1] = Broken(layer.anchors[1])
    prepared = api.prepare_point_moves(
        owned.package, [(g, "Regular", [(p, (10, 20)) for p in layer.anchors])]
    )
    with pytest.raises(RuntimeError, match="setter"):
        api.apply_point_moves(prepared, "partial")
    assert layer.anchors[0].point.x() == 10 and g.lastModified == "UTC"
    assert [e[0] for e in owned.events[-2:]] == ["notify", "update"]


def test_notify_failure_still_attempts_refresh(owned):
    g, layer = owned.glyph()
    prepared = api.prepare_point_moves(
        owned.package, [(g, "Regular", [(layer.anchors[0], (20, 27.75))])]
    )

    def fail(*args):
        raise RuntimeError("notify")

    owned.native.flItems = lambda: NS(notifyChangesApplied=fail)
    with pytest.raises(RuntimeError, match="notify"):
        api.apply_point_moves(prepared, "partial")
    assert owned.events[-1] == ("update",)


@pytest.mark.parametrize(
    "records,match",
    [
        ((("other", False, ()),), "changed"),
        ((("H", False, ()), ("Hacute", True, ("missing",))), "missing"),
        ((("H", False, ()), ("empty", True, ())), "Unverified"),
        ((("H", False, ("Hacute",)), ("Hacute", True, ("H",))), "cyclic"),
    ],
)
def test_invalid_component_graphs_refuse_entire_batch(
    owned, monkeypatch, records, match
):
    g, layer = owned.glyph()
    monkeypatch.setattr(api, "dependency_values", lambda _: records)
    with pytest.raises(ValueError, match=match):
        api.prepare_point_moves(
            owned.package, [(g, "Regular", [(layer.anchors[0], (20, 27.75))])]
        )
    assert not owned.events


def test_transitive_manual_bridge_enrolls_automatic_descendants(owned, monkeypatch):
    g, layer = owned.glyph()
    bridge, _ = owned.glyph("manual")
    dependent, _ = owned.glyph("automatic", auto=True)
    records = (
        ("H", False, ()),
        ("manual", False, ("H",)),
        ("automatic", True, ("manual",)),
    )
    monkeypatch.setattr(api, "dependency_values", lambda _: records)
    prepared = api.prepare_point_moves(
        owned.package, [(g, "Regular", [(layer.anchors[0], (20, 27.75))])]
    )
    assert [d.name for d in prepared.dependants] == ["automatic", "manual"]
    api.apply_point_moves(prepared, "bridge")
    assert bridge.lastModified == dependent.lastModified == g.lastModified == "UTC"
    with pytest.raises(ValueError, match="changed"):
        api.apply_point_moves(prepared, "repeat")


def test_explicit_recipe_refuses_before_construction(owned, monkeypatch):
    g, layer = owned.glyph()
    _, dependent = owned.glyph("automatic", auto=True)
    dependent.recipe = "H+acute"
    monkeypatch.setattr(
        api,
        "dependency_values",
        lambda _: (("H", False, ()), ("automatic", True, ("H",))),
    )
    with pytest.raises(ValueError, match="recipe"):
        api.prepare_point_moves(
            owned.package, [(g, "Regular", [(layer.anchors[0], (20, 27.75))])]
        )
    assert not owned.events


@pytest.mark.parametrize("problem", ["duplicate", "foreign", "auto", "foreign-glyph"])
def test_invalid_pin_or_target_identity_refuses_whole_batch(owned, problem):
    g, layer = owned.glyph()
    pin = layer.anchors[0]
    moves = [(pin, (20, 27.75))]
    if problem == "duplicate":
        moves *= 2
    elif problem == "foreign":
        moves = [(NS(id=999), (20, 27.75))]
    elif problem == "auto":
        layer.autoLayer = True
    else:
        g = NS(name=g.name, id=999)
    with pytest.raises(ValueError):
        api.prepare_point_moves(owned.package, [(g, "Regular", moves)])
    assert not owned.events


def test_first_setter_failure_without_mutation_makes_no_empty_notification(owned):
    g, layer = owned.glyph()

    class Refuses:
        def __init__(self, pin):
            self.__dict__.update(pin.__dict__)

        def __setattr__(self, name, value):
            if name == "point":
                raise RuntimeError("setter refused")
            object.__setattr__(self, name, value)

    pin = layer.anchors[0] = Refuses(layer.anchors[0])
    prepared = api.prepare_point_moves(
        owned.package, [(g, "Regular", [(pin, (20, 27.75))])]
    )
    with pytest.raises(RuntimeError, match="setter refused"):
        api.apply_point_moves(prepared, "empty")
    assert (
        not any(e[0] == "notify" for e in owned.events) and g.lastModified == "before"
    )


def test_refresh_error_after_setter_failure_does_not_hide_original(owned):
    g, layer = owned.glyph(points=(("top", 1, 2), ("bottom", 3, 4)))

    class Refuses:
        def __init__(self, pin):
            self.__dict__.update(pin.__dict__)

        def __setattr__(self, name, value):
            if name == "point":
                raise RuntimeError("original setter")
            object.__setattr__(self, name, value)

    layer.anchors[1] = Refuses(layer.anchors[1])
    prepared = api.prepare_point_moves(
        owned.package, [(g, "Regular", [(p, (10, 20)) for p in layer.anchors])]
    )

    def fail():
        raise RuntimeError("refresh")

    owned.native.UpdateAll = fail
    with pytest.raises(RuntimeError, match="original setter") as caught:
        api.apply_point_moves(prepared, "partial")
    assert any("refresh" in note for note in caught.value.__notes__)


def test_clock_failure_still_records_history_and_refresh(owned, monkeypatch):
    g, layer = owned.glyph()
    prepared = api.prepare_point_moves(
        owned.package, [(g, "Regular", [(layer.anchors[0], (20, 27.75))])]
    )

    def fail():
        raise RuntimeError("clock")

    monkeypatch.setattr(
        api._native("PythonQt").QtCore.QDateTime, "currentDateTimeUtc", fail
    )
    with pytest.raises(RuntimeError, match="clock"):
        api.apply_point_moves(prepared, "clock-failure")
    assert [e[0] for e in owned.events[-2:]] == ["notify", "update"]


def test_ignored_native_setter_is_reported_without_empty_history(owned):
    g, layer = owned.glyph()

    class Ignores:
        def __init__(self, pin):
            self.__dict__.update(pin.__dict__)

        def __setattr__(self, name, value):
            if name != "point":
                object.__setattr__(self, name, value)

    pin = layer.anchors[0] = Ignores(layer.anchors[0])
    prepared = api.prepare_point_moves(
        owned.package, [(g, "Regular", [(pin, (20, 27.75))])]
    )
    with pytest.raises(RuntimeError, match="requested anchor point"):
        api.apply_point_moves(prepared, "ignored")
    assert (
        not any(e[0] == "notify" for e in owned.events) and g.lastModified == "before"
    )
