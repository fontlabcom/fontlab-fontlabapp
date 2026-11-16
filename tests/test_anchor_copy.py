# this_file: tests/test_anchor_copy.py
# SPDX-License-Identifier: Apache-2.0
"""Original copy arithmetic and whole-batch native write boundaries."""

from types import SimpleNamespace as NS

import pytest

import fontlabapp.anchors.copy.model as api


def layer(width=100, points=(), auto=False):
    return NS(
        advanceWidth=width,
        autoLayer=auto,
        isNull=False,
        anchors=[
            NS(
                name=n,
                point=NS(x=lambda x=x: x, y=lambda y=y: y),
                appearance=9,
                anchor=True,
            )
            for n, x, y in points
        ],
    )


@pytest.mark.parametrize(
    "source_width,target_width,scale,wanted",
    [
        (100, 200, True, 26),
        (0, 200, True, 13),
        (100, 0, True, 0),
        (-100, 200, True, -26),
        (100, 200, False, 13),
    ],
)
def test_plan_preserves_original_rounding_zero_negative_and_scale_rules(
    source_width,
    target_width,
    scale,
    wanted,
):
    source = layer(source_width, [("top", 12.6, 20.4)])
    target = layer(target_width, [("other", 3, 4)])
    assert api.plan(source, target, scale, True) == [
        ("top", None, (wanted, 20)),
        ("other", (3, 4), None),
    ]


@pytest.fixture
def owned(monkeypatch):
    events = []

    def point(x, y):
        events.append(("point", x, y))
        return NS(x=lambda: x, y=lambda: y)

    def pin(p):
        events.append(("pin",))
        return NS(point=p)

    native = NS(
        flPinPoint=pin,
        UpdateAll=lambda: events.append(("update",)),
        flItems=lambda: NS(
            notifyChangesApplied=lambda title, items: events.append(
                ("notify", title, items)
            )
        ),
    )
    qt = NS(
        QtCore=NS(QPointF=point, QDateTime=NS(currentDateTimeUtc=lambda: "UTC stamp"))
    )
    monkeypatch.setattr(
        api, "_native", lambda name: native if name == "fontlab" else qt
    )
    monkeypatch.setattr(api, "dependency_values", lambda package: (("h", False, ()),))

    def glyph(name, layers):
        g = NS(
            name=name,
            lastModified="before",
            findLayer=layers.get,
            checkInitHistoryState=lambda value: events.append(("init-glyph", name)),
        )
        for l in layers.values():
            l.checkInitHistoryState = lambda value: events.append(("init-layer",))
            l.addAnchor = lambda p, l=l: (events.append(("add",)), l.anchors.append(p))
            l.removeAnchor = lambda p, l=l: (
                events.append(("remove",)),
                l.anchors.remove(p),
            )
        return g

    return NS(events=events, glyph=glyph, package=NS(masters=["Regular", "Bold"]))


def test_run_preconstructs_new_points_before_one_history_and_stabilizes_appearance(
    owned,
):
    o = owned
    source = o.glyph("n", {"Regular": layer(points=[("top", 13, 20), ("_left", 1, 2)])})
    dst = layer(points=[("old", 1, 1)])
    target = o.glyph("h", {"Regular": dst})
    assert api.run(
        source, [target, source], ["Regular"], True, True, package=o.package
    ) == {
        "anchors": 3,
        "layers": 1,
        "skipped": [],
    }
    assert [(p.name, p.appearance, p.anchor) for p in dst.anchors] == [
        ("top", 5, True),
        ("_left", 7, True),
    ]
    kinds = [e[0] for e in o.events]
    assert kinds.count("notify") == 1 and kinds.count("update") == 1
    assert max(i for i, k in enumerate(kinds) if k in {"point", "pin"}) < kinds.index(
        "init-layer"
    )
    assert target.lastModified == "UTC stamp" and source.lastModified == "before"


def test_rounded_noop_preserves_raw_existing_position_style_and_history(owned):
    o = owned
    source = o.glyph("n", {"Regular": layer(points=[("top", 13, 20)])})
    dst = layer(points=[("top", 13.2, 20.1)])
    target = o.glyph("h", {"Regular": dst})
    assert (
        api.run(source, [target], ["Regular"], False, False, package=o.package)[
            "anchors"
        ]
        == 0
    )
    assert (
        not o.events
        and dst.anchors[0].point.x() == 13.2
        and dst.anchors[0].appearance == 9
    )


def test_unsafe_later_target_refuses_complete_batch_before_construction(
    owned, monkeypatch
):
    o = owned
    source = o.glyph("n", {"Regular": layer(points=[("top", 13, 20)])})
    targets = [o.glyph(n, {"Regular": layer()}) for n in ["h", "A"]]
    monkeypatch.setattr(
        api,
        "dependency_values",
        lambda p: (("h", False, ()), ("A", False, ()), ("Aacute", True, ("A",))),
    )
    with pytest.raises(ValueError, match="automatic dependants"):
        api.run(source, targets, ["Regular"], True, False, package=o.package)
    assert not o.events and all(not g.findLayer("Regular").anchors for g in targets)


def test_bad_later_constructor_leaves_all_targets_and_history_unchanged(
    owned, monkeypatch
):
    o = owned
    source = o.glyph(
        "n", {"Regular": layer(points=[("top", 13, 20), ("bottom", 3, 4)])}
    )
    dst = layer()
    target = o.glyph("h", {"Regular": dst})
    old = api._native("fontlab").flPinPoint

    def fail(point):
        if point.x() == 3:
            raise ValueError("later constructor failed")
        return old(point)

    api._native("fontlab").flPinPoint = fail
    with pytest.raises(ValueError, match="later constructor"):
        api.run(source, [target], ["Regular"], True, False, package=o.package)
    assert not dst.anchors and not any(e[0].startswith("init") for e in o.events)


def test_partial_native_error_retains_one_named_undo_and_target_utc(owned):
    o = owned
    source = o.glyph("n", {"Regular": layer(points=[("top", 13, 20)])})
    dst = layer()
    target = o.glyph("h", {"Regular": dst})

    def fail(pin):
        raise RuntimeError("native add failed")

    dst.addAnchor = fail
    with pytest.raises(RuntimeError, match="native add failed"):
        api.run(source, [target], ["Regular"], True, False, package=o.package)
    assert target.lastModified == "UTC stamp"
    assert o.events[-2][0] == "notify" and o.events[-1] == ("update",)


def test_auto_and_missing_layers_skip_without_history_and_unknown_master_refuses(owned):
    o = owned
    source = o.glyph("n", {"Regular": layer(points=[("top", 13, 20)])})
    target = o.glyph("h", {"Regular": layer(auto=True)})
    assert api.run(
        source, [target], ["Regular", "Bold"], True, False, package=o.package
    ) == {
        "anchors": 0,
        "layers": 0,
        "skipped": ["h/Regular"],
    }
    with pytest.raises(ValueError, match="Masters"):
        api.run(source, [target], ["unknown"], True, False, package=o.package)
    assert not o.events


def test_existing_pin_moves_without_replacing_style_or_other_native_values(owned):
    o = owned
    source = o.glyph("n", {"Regular": layer(points=[("top", 13, 20)])})
    dst = layer(points=[("top", 7, 8)])
    target = o.glyph("h", {"Regular": dst})
    pin = dst.anchors[0]
    pin.expressionX, pin.expressionY = "owned x", "owned y"
    assert (
        api.run(source, [target], ["Regular"], False, False, package=o.package)[
            "anchors"
        ]
        == 1
    )
    assert dst.anchors[0] is pin and pin.point.x() == 13 and pin.appearance == 9
    assert (pin.expressionX, pin.expressionY) == ("owned x", "owned y")


@pytest.mark.parametrize("coordinate", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_native_coordinates_refuse_before_any_history(owned, coordinate):
    o = owned
    source = o.glyph("n", {"Regular": layer(points=[("top", coordinate, 20)])})
    dst = layer()
    target = o.glyph("h", {"Regular": dst})
    with pytest.raises((ValueError, OverflowError)):
        api.run(source, [target], ["Regular"], True, False, package=o.package)
    assert not o.events and not dst.anchors


def test_missing_source_and_duplicate_masters_refuse_before_native_work(owned):
    o = owned
    with pytest.raises(ValueError, match="source"):
        api.run(None, [], [], True, False, package=o.package)
    with pytest.raises(ValueError, match="Masters"):
        api.run(
            NS(name="n"), [], ["Regular", "Regular"], True, False, package=o.package
        )
    assert not o.events


def test_existing_origin_move_refuses_the_whole_batch_before_native_history(owned):
    o = owned
    source = o.glyph(
        "n", {"Regular": layer(points=[("bottom", 0, 0), ("top", 13, 20)])}
    )
    dst = layer(points=[("bottom", 13, 0)])
    target = o.glyph("h", {"Regular": dst})
    with pytest.raises(ValueError, match="Redo"):
        api.run(source, [target], ["Regular"], False, False, package=o.package)
    assert not o.events and dst.anchors[0].point.x() == 13
