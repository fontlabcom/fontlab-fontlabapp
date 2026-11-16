# this_file: tests/test_zone_prepare_ownership.py
"""Owned graph/constraint failures: no original or rescued script is executed."""

from types import SimpleNamespace as NS

import pytest
from test_zone_prepare import host as shared_host

import fontlabapp.metrics.zones.prepare as api
from fontlabapp.metrics.zones.model import Editor


@pytest.fixture
def host(monkeypatch):
    return shared_host.__wrapped__(monkeypatch)


@pytest.mark.parametrize("part", ["center", "vector", "marker"])
def test_source_child_identity_is_refused_before_setters(host, part):
    package, _, before, state = host
    source = package.pool["Thin"][0]
    old_point = source.center.position

    def alias(objects):
        if part == "marker":
            objects[0].markers = (source.center,)
        else:
            setattr(objects[0], part, getattr(source, part))

    state.mutate = alias
    with pytest.raises(ValueError, match="identity"):
        api.prepare(before, Editor(before.snapshot).add("Thin", "Bottom").plan())
    assert source.center.position is old_point
    assert source.centerPoint.y() == 650.5


def test_witness_child_sharing_another_live_copy_is_refused(host):
    _, _, before, state = host

    def share(objects):
        if state.decode_calls == 2:
            objects[0].center = state.decoded[0].center

    state.mutate = share
    with pytest.raises(ValueError, match="identity"):
        api.prepare(before, Editor(before.snapshot).add("Thin", "Bottom").plan())


def test_source_graph_drift_with_identical_payload_is_refused(host):
    package, _, before, state = host

    def drift(objects):
        if state.decode_calls == 2:
            package.pool["Thin"][0].vector.id = 99999

    state.mutate = drift
    with pytest.raises(ValueError, match="graph changed"):
        api.prepare(before, Editor(before.snapshot).add("Thin", "Bottom").plan())


@pytest.mark.parametrize("fault", ["current", "select", "restore", "root", "child"])
def test_graph_capture_failures_restore_or_report_exact_master(host, fault):
    package, _, before, _ = host
    if fault == "current":
        package.master = "Thin"
    elif fault in ("select", "restore"):

        def switch(name, notify):
            if name == ("Thin" if fault == "select" else "Regular"):
                return
            package.master = name

        package.setMaster = switch
    elif fault == "root":
        package.pool["Thin"][0].id = 99999
    else:
        package.pool["Thin"][0].markers = (NS(id=True),)
    with pytest.raises((ValueError, RuntimeError)):
        api._protected(package, before, 3.0)
    assert package.master == ("Thin" if fault in ("current", "restore") else "Regular")


@pytest.mark.parametrize("field", ["width", "x"])
def test_native_constraint_refuses_unrepresentable_requested_row(host, monkeypatch, field):
    _, _, before, _ = host
    original = api.guide_ops.set_visible

    def rounded(guide, qt, values):
        original(guide, qt, values)
        if field == "width":
            guide.extPosition += 1
        else:
            guide.center.position = qt.QPointF(values[0] + 1, values[1])

    monkeypatch.setattr(api.guide_ops, "set_visible", rounded)
    with pytest.raises(ValueError, match="requested row"):
        api.prepare(before, Editor(before.snapshot).add("Thin", "Bottom").plan())


def test_later_decode_cannot_change_an_earlier_prepared_row(host):
    _, _, before, state = host

    def drift(objects):
        if state.decode_calls == 3:
            state.decoded[0].metadata["late"] = True

    state.mutate = drift
    plan = Editor(before.snapshot).add("Thin", "Bottom").remove("Regular", [0]).plan()
    with pytest.raises(ValueError, match="preparing the batch"):
        api.prepare(before, plan)


def test_opaque_witness_detects_alias_outside_known_identity_graph(host):
    _, native, before, state = host
    original = native.flModelProducer.getClipboardData
    count = 0

    def encode(identifier, upm, guides):
        nonlocal count
        result = original(identifier, upm, guides)
        if state.decode_calls == 2:
            count += 1
            if count == 1:
                state.decoded[0].metadata["shared_hidden_state"] = True
        return result

    encode.__doc__ = original.__doc__
    native.flModelProducer.getClipboardData = encode
    with pytest.raises(ValueError, match="witness aliases"):
        api.prepare(before, Editor(before.snapshot).add("Thin", "Bottom").plan())
