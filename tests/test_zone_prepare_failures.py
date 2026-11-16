# this_file: tests/test_zone_prepare_failures.py
"""No partial prepared batch or source mutation on profile/copy failures."""

from dataclasses import replace

import pytest
from test_zone_prepare import host as shared_host

import fontlabapp.metrics.zones.capture as capture_api
import fontlabapp.metrics.zones.prepare as api
from fontlabapp.metrics.zones.model import Editor


@pytest.fixture
def host(monkeypatch):
    return shared_host.__wrapped__(monkeypatch)


@pytest.mark.parametrize("profile", ["serializer", "decoder"])
def test_legacy_profile_is_refused_before_decode_or_source_capture(
    host, monkeypatch, profile
):
    _, native, before, state = host
    method = (
        native.flModelProducer.getClipboardData
        if profile == "serializer"
        else native.flModelProducer.getObjectsFromData
    )
    method.__doc__ = "legacy"
    monkeypatch.setattr(
        api, "capture", lambda identifier: pytest.fail("Unqualified source capture")
    )
    with pytest.raises(RuntimeError):
        api.prepare(before, Editor(before.snapshot).add("Thin", "Bottom").plan())
    assert state.decode_calls == 0


@pytest.mark.parametrize("values", [None, [], [1], [1, 2]])
def test_bad_decoder_shape_is_rejected(host, values):
    _, native, before, _ = host

    def bad(buffer):
        return values

    bad.__doc__ = native.flModelProducer.getObjectsFromData.__doc__
    native.flModelProducer.getObjectsFromData = bad
    with pytest.raises(ValueError, match="guide"):
        api.prepare(before, Editor(before.snapshot).add("Thin", "Bottom").plan())
    assert capture_api.capture() == before


@pytest.mark.parametrize("identifier", [0, True, -1, 101])
def test_invalid_or_source_root_id_is_rejected_before_editing(host, identifier):
    _, _, before, state = host
    state.mutate = lambda objects: setattr(objects[0], "id", identifier)
    with pytest.raises(ValueError, match="identity"):
        api.prepare(before, Editor(before.snapshot).add("Thin", "Bottom").plan())
    assert capture_api.capture() == before


def test_reused_live_preparation_id_is_refused(host):
    _, _, before, state = host
    state.mutate = lambda objects: setattr(objects[0], "id", 9999)
    with pytest.raises(ValueError, match="identity"):
        api.prepare(before, Editor(before.snapshot).add("Thin", "Bottom").plan())


def test_lossy_decode_is_refused_before_geometry_changes(host):
    _, _, before, state = host
    state.mutate = lambda objects: objects[0].metadata.clear()
    with pytest.raises(ValueError, match="round-trip"):
        api.prepare(before, Editor(before.snapshot).add("Thin", "Bottom").plan())
    assert capture_api.capture() == before


def test_lossy_restoration_witness_refuses_entire_batch(host):
    _, _, before, state = host

    def lose_after_first(objects):
        if state.decode_calls == 2:
            objects[0].metadata.clear()

    state.mutate = lose_after_first
    with pytest.raises(ValueError, match="witness lost"):
        api.prepare(before, Editor(before.snapshot).add("Thin", "Bottom").plan())
    assert capture_api.capture() == before


def test_source_closed_after_capture_refuses_before_decode(host, monkeypatch):
    _, _, before, state = host
    monkeypatch.setattr(api, "current_package", lambda identifier: None)
    with pytest.raises(ValueError, match="closed"):
        api.prepare(before, Editor(before.snapshot).add("Thin", "Bottom").plan())
    assert state.decode_calls == 0


def test_stale_source_is_refused_before_decode(host):
    package, _, before, state = host
    package.pool["Thin"][0].metadata["external"] = True
    with pytest.raises(ValueError, match="changed"):
        api.prepare(before, Editor(before.snapshot).add("Thin", "Bottom").plan())
    assert state.decode_calls == 0


def test_bad_or_mutable_change_request_does_not_reach_native(host, monkeypatch):
    _, _, before, _ = host
    monkeypatch.setattr(
        api, "_native", lambda name: pytest.fail("Invalid request touched native")
    )
    with pytest.raises(ValueError, match="immutable"):
        api.prepare(before, [])
    change = Editor(before.snapshot).add("Thin", "Bottom").plan()[0]
    with pytest.raises(ValueError):
        api.prepare(before, (replace(change, before=change.after),))


def test_total_deadline_stops_immediately_after_a_slow_decoder(host):
    _, _, before, state = host
    state.mutate = lambda objects: setattr(state, "expire", True)
    with pytest.raises(TimeoutError):
        api.prepare(before, Editor(before.snapshot).add("Thin", "Bottom").plan())
    assert state.decode_calls == 1
