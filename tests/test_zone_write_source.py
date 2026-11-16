# this_file: tests/test_zone_write_source.py
"""Reject incomplete native source fences before returning any write operation."""

from dataclasses import replace

import pytest
from test_zone_write_plan import captured as source_fixture

import fontlabapp.metrics.zones.write_plan as api
from fontlabapp.metrics.zones.model import Editor
from fontlabapp.metrics.zones.capture_data import Capture
from fontlabapp.metrics.zones.data import Change, Origin, Zones


@pytest.fixture
def captured():
    return source_fixture.__wrapped__()


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "snapshot",
        "guide_list",
        "master_list",
        "missing",
        "extra",
        "order",
        "font_id",
    ],
)
def test_invalid_complete_capture_domain_is_refused_even_for_noop(captured, fault):
    bad = captured
    if fault == "none":
        bad = None
    elif fault == "snapshot":
        bad = replace(captured, snapshot=None)
    elif fault == "guide_list":
        bad = replace(captured, guides=list(captured.guides))
    elif fault == "master_list":
        bad = replace(
            captured,
            snapshot=replace(
                captured.snapshot, masters=list(captured.snapshot.masters)
            ),
        )
    elif fault == "missing":
        bad = replace(captured, guides=captured.guides[:1])
    elif fault == "extra":
        bad = replace(captured, guides=(*captured.guides, captured.guides[0]))
    elif fault == "order":
        bad = replace(captured, guides=tuple(reversed(captured.guides)))
    elif fault == "font_id":
        bad = replace(captured, snapshot=replace(captured.snapshot, package_id=True))
    with pytest.raises(ValueError):
        api.build(bad, ())


@pytest.mark.parametrize("ids", [(91, 11, 11), (0,), (True,), [91, 11, 92], (91, 92)])
def test_bad_guide_ids_or_missing_editable_membership_refuse(captured, ids):
    bad = replace(
        captured, guides=(replace(captured.guides[0], ids=ids), captured.guides[1])
    )
    with pytest.raises(ValueError):
        api.build(bad, ())


@pytest.mark.parametrize("data", [b"", "text", bytearray(b"mutable"), None])
def test_missing_or_mutable_native_buffer_refuses(captured, data):
    bad = replace(
        captured, guides=(replace(captured.guides[0], data=data), captured.guides[1])
    )
    with pytest.raises(ValueError):
        api.build(bad, ())


@pytest.mark.parametrize(
    "origin",
    [
        None,
        Origin("11", b""),
        Origin("0", b"x"),
        Origin("-1", b"x"),
        Origin("011", b"x"),
        Origin("foreign", b"x"),
    ],
)
def test_noncanonical_source_identity_or_missing_payload_refuses(captured, origin):
    master = captured.snapshot.masters[0]
    altered = replace(
        master, zones=Zones((replace(master.zones.top[0], origin=origin),))
    )
    bad = replace(
        captured,
        snapshot=replace(
            captured.snapshot, masters=(altered, captured.snapshot.masters[1])
        ),
    )
    with pytest.raises(ValueError):
        api.build(bad, ())


def test_source_and_proposed_zone_collections_cannot_remain_mutable(captured):
    master = captured.snapshot.masters[0]
    mutable = Zones(list(master.zones.top))
    altered = replace(
        captured,
        snapshot=replace(
            captured.snapshot,
            masters=(replace(master, zones=mutable), captured.snapshot.masters[1]),
        ),
    )
    with pytest.raises(ValueError, match="immutable"):
        api.build(altered, ())
    with pytest.raises(ValueError, match="immutable"):
        api.build(captured, (Change("Thin", master.zones, mutable),))


def test_nonchange_request_and_wrong_frame_type_refuse(captured):
    with pytest.raises(ValueError):
        api.build(captured, (None,))
    with pytest.raises(ValueError):
        api.build(replace(captured, guides=(None, captured.guides[1])), ())


@pytest.mark.parametrize("fault", ["master", "metrics", "frame_ids", "nonzone_payload"])
def test_final_source_fence_refuses_any_complete_source_delta(captured, fault):
    plan = api.build(captured, Editor(captured.snapshot).add("Thin", "Bottom").plan())
    api.require_current(plan, captured)
    if fault == "master":
        current = replace(
            captured, snapshot=replace(captured.snapshot, current_master="Thin")
        )
    elif fault == "metrics":
        masters = (
            replace(captured.snapshot.masters[0], x_height=401),
            captured.snapshot.masters[1],
        )
        current = replace(
            captured, snapshot=replace(captured.snapshot, masters=masters)
        )
    elif fault == "frame_ids":
        current = replace(
            captured,
            guides=(replace(captured.guides[0], ids=(93, 11, 92)), captured.guides[1]),
        )
    else:
        current = replace(
            captured,
            guides=(
                replace(captured.guides[0], data=b"unrelated-guide-changed"),
                captured.guides[1],
            ),
        )
    with pytest.raises(ValueError, match="changed"):
        api.require_current(plan, current)


def test_plan_consumes_actual_capture_adapter_records_with_owned_native_boundary(
    monkeypatch,
):
    from test_zone_capture import host

    import fontlabapp.metrics.zones.capture as native_capture

    package, _, _, _ = host.__wrapped__(monkeypatch)
    before = native_capture.capture()
    plan = api.build(before, Editor(before.snapshot).add("Regular", "Bottom").plan())
    assert plan.masters[0].keep_ids == (5,) and plan.masters[0].remove_ids == (2, 3, 4)
    assert len(plan.masters[0].rows) == 4 and package.master == "Regular"
    api.require_current(plan, native_capture.capture())
    assert isinstance(before, Capture)


def test_interrupted_change_iterable_never_returns_a_partial_plan(captured):
    def interrupted():
        yield Editor(captured.snapshot).add("Thin", "Bottom").plan()[0]
        raise RuntimeError("owned interruption")

    with pytest.raises(RuntimeError, match="interruption"):
        api.build(captured, interrupted())
