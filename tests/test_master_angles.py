# this_file: tests/test_master_angles.py
# SPDX-License-Identifier: Apache-2.0
"""Complete source guards and one history batch for staged italic angles."""

from dataclasses import FrozenInstanceError
from types import SimpleNamespace as NS

import pytest

import fontlabapp.masters.angles.model as api


class Package:
    def __init__(self):
        self.id, self.master = 31, "Regular"
        self.masters = ["Thin", "Regular", "Black"]
        self.values = dict.fromkeys(self.masters, -10.0)
        self.hints = dict.fromkeys(self.masters, 0.039625)
        self.info = NS(postscriptBlueScale=0.039625)
        self.events, self.fail_read, self.fail_write = [], None, None
        self.container = NS(
            checkInitHistoryState=lambda n: self.events.append(("init", n))
        )

    def setMaster(self, name, notify=False):
        self.master = name
        if notify:
            self.events.append(("restore", name))

    @property
    def italicAngle_value(self):
        if self.master == self.fail_read:
            raise RuntimeError("read failed")
        return self.values[self.master]

    @italicAngle_value.setter
    def italicAngle_value(self, value):
        self.values[self.master] = value
        self.events.append(("write", self.master, value))
        if self.master == self.fail_write:
            raise RuntimeError("setter failed after writing")

    def mastersContainer(self):
        return self.container

    @property
    def hinting(self):
        return NS(blueScale=self.hints[self.master])

    def changed(self):
        self.events.append(("changed",))


@pytest.fixture
def owned(monkeypatch):
    p = Package()
    active = [p]
    monkeypatch.setattr(
        api,
        "current_package",
        lambda expected_id=None: (
            active[0] if active[0] is not None and active[0].id == expected_id else None
        ),
    )
    native = NS(
        flItems=NS(
            notifyChangesApplied=lambda title, items: p.events.append(
                ("notify", title, items)
            )
        ),
        UpdateAll=lambda: p.events.append(("update",)),
    )
    monkeypatch.setattr(api, "_native", lambda name: native)
    return p, active


def test_capture_is_immutable_and_restores_current_master_without_history(owned):
    p, _ = owned
    snapshot = api.capture(p)
    assert snapshot.package_id == 31 and snapshot.current_master == "Regular"
    assert snapshot.angles == (("Thin", -10), ("Regular", -10), ("Black", -10))
    with pytest.raises(FrozenInstanceError):
        snapshot.current_master = "Black"
    assert p.master == "Regular" and p.events == []


def test_capture_read_failure_restores_current_master(owned):
    p, _ = owned
    p.fail_read = "Black"
    with pytest.raises(RuntimeError, match="read failed"):
        api.capture(p)
    assert p.master == "Regular" and p.events == []


def test_apply_uses_one_container_history_and_restores_master(owned):
    p, _ = owned
    snapshot = api.capture(p)
    assert api.apply(snapshot, {"Regular": -11, "Thin": -12}) == ["Thin", "Regular"]
    assert p.values == {"Thin": -12, "Regular": -11, "Black": -10}
    assert p.master == "Regular"
    assert p.events == [
        ("init", 0),
        ("write", "Thin", -12),
        ("write", "Regular", -11),
        ("restore", "Regular"),
        ("notify", "Italic Angle", [p.container]),
        ("update",),
    ]


@pytest.mark.parametrize("values", [{}, {"Thin": -10}, {"Thin": -10.0, "Black": -10}])
def test_noop_makes_no_history_or_native_update(owned, values):
    p, _ = owned
    assert api.apply(api.capture(p), values) == []
    assert p.events == [] and p.master == "Regular"


@pytest.mark.parametrize(
    "value",
    [
        True,
        None,
        "12",
        float("nan"),
        float("inf"),
        -45.1,
        45.1,
        1e300,
        pytest.param(10**500, id="huge-integer"),
    ],
)
def test_invalid_later_value_refuses_entire_batch_before_history(owned, value):
    p, _ = owned
    with pytest.raises(ValueError, match="angle"):
        api.apply(api.capture(p), {"Thin": -12, "Black": value})
    assert not p.events and set(p.values.values()) == {-10}


@pytest.mark.parametrize(
    "drift", ["font", "closed", "master", "order", "value", "membership"]
)
def test_changed_source_refuses_before_history(owned, drift):
    p, active = owned
    snapshot = api.capture(p)
    if drift == "font":
        active[0] = Package()
        active[0].id = 32
    elif drift == "closed":
        active[0] = None
    elif drift == "master":
        p.master = "Black"
    elif drift == "order":
        p.masters.reverse()
    elif drift == "value":
        p.values["Black"] = -9
    else:
        p.masters.pop()
    with pytest.raises(ValueError, match="font|Source"):
        api.apply(snapshot, {"Thin": -12})
    assert p.events == []


def test_unknown_master_refuses_before_history(owned):
    p, _ = owned
    with pytest.raises(ValueError, match="master"):
        api.apply(api.capture(p), {"Missing": -12})
    assert p.events == []


def test_partial_setter_error_retains_one_history_batch_and_restores_master(owned):
    p, _ = owned
    snapshot = api.capture(p)
    p.fail_write = "Regular"
    with pytest.raises(RuntimeError, match="setter failed"):
        api.apply(snapshot, {"Thin": -12, "Regular": -11})
    assert p.master == "Regular"
    assert p.events[-2:] == [("notify", "Italic Angle", [p.container]), ("update",)]
    assert sum(e[0] == "init" for e in p.events) == 1


def test_inclusive_angle_limits_are_accepted_without_rounding(owned):
    p, _ = owned
    assert (
        api.apply(api.capture(p), {"Thin": -45, "Regular": 45, "Black": 0.125})
        == p.masters
    )
    assert p.values == {"Thin": -45, "Regular": 45, "Black": 0.125}


@pytest.mark.parametrize(
    "problem", ["empty", "duplicate", "current", "nonfinite", "changing-order"]
)
def test_incomplete_capture_refuses_without_any_history(owned, problem):
    p, _ = owned
    if problem == "empty":
        p.masters = []
    elif problem == "duplicate":
        p.masters.append("Thin")
    elif problem == "current":
        p.master = "Unknown"
    elif problem == "nonfinite":
        p.values["Thin"] = float("nan")
    else:
        original = p.setMaster

        def change(name):
            original(name)
            if name == "Black":
                p.masters.reverse()

        p.setMaster = change
    with pytest.raises(ValueError, match="Source"):
        api.capture(p)
    assert p.events == []


def test_notification_error_still_updates_native_ui_and_restores_master(owned):
    p, _ = owned

    def fail(title, objects):
        raise RuntimeError("notify failed")

    api._native("fontlab").flItems.notifyChangesApplied = fail
    with pytest.raises(RuntimeError, match="notify failed"):
        api.apply(api.capture(p), {"Thin": -12})
    assert p.master == "Regular" and p.events[-1] == ("update",)
