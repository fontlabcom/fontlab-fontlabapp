# this_file: tests/test_zone_write_plan.py
"""Preflight whole native zone batches before any allocation/history operation."""

from dataclasses import FrozenInstanceError, replace

import pytest

import fontlabapp.metrics.zones.write_plan as api
from fontlabapp.metrics.zones.model import Editor
from fontlabapp.metrics.zones.capture_data import Capture, GuideBuffer
from fontlabapp.metrics.zones.data import Change, Master, Origin, Snapshot, Zone, Zones


@pytest.fixture
def captured():
    return Capture(
        Snapshot(
            31,
            "Regular",
            (
                Master(
                    "Thin",
                    400.5,
                    650.5,
                    Zones(
                        (Zone(650.5, 12.5, "caps", Origin("11", b"thin-full-payload")),)
                    ),
                ),
                Master(
                    "Regular",
                    500,
                    700,
                    Zones(
                        (
                            Zone(500, 12, "", Origin("21", b"first")),
                            Zone(500, 12, "", Origin("22", b"second")),
                        ),
                        (Zone(0, 15, "base", Origin("23", b"bottom")),),
                    ),
                ),
            ),
        ),
        (
            GuideBuffer("Thin", (91, 11, 92), b"all-thin-guides"),
            GuideBuffer("Regular", (21, 95, 22, 23, 96), b"all-regular-guides"),
        ),
    )


def test_whole_plan_keeps_source_order_raw_payloads_and_uneditable_guide_ids(captured):
    editor = Editor(captured.snapshot).remove("Regular", [0]).add("Thin", "Bottom")
    plan = api.build(captured, reversed(editor.plan()))
    assert plan.before is captured and [m.master for m in plan.masters] == [
        "Thin",
        "Regular",
    ]
    thin, regular = plan.masters
    assert thin.source is captured.guides[0] and thin.remove_ids == (11,)
    assert thin.keep_ids == (91, 92) and regular.keep_ids == (95, 96)
    assert regular.remove_ids == (21, 22, 23), (
        "Delete only captured editable rows, in source guide order"
    )
    assert [(row.kind, row.zone.position) for row in thin.rows] == [
        ("Top", 650),
        ("Bottom", 0),
    ]
    assert (
        thin.rows[0].source_id == 11
        and thin.rows[0].zone.origin.metadata == b"thin-full-payload"
    )
    assert thin.rows[1].source_id is None and thin.rows[1].zone.origin is None
    assert regular.rows[0].zone.origin == Origin("21", b"first"), (
        "Removing an identical row must retain the right metadata"
    )
    assert captured.snapshot.masters[0].zones.top[0].position == 650.5
    with pytest.raises(FrozenInstanceError):
        thin.master = "changed"


def test_noop_batch_is_empty_and_normalized_display_does_not_create_history(captured):
    assert api.build(captured, ()).masters == ()
    source = captured.snapshot.masters[0]
    after = Editor(captured.snapshot).zones("Thin")
    assert api.build(captured, (Change("Thin", source.zones, after),)).masters == ()


def test_empty_after_removes_all_editable_zones_and_keeps_all_other_guides(captured):
    source = captured.snapshot.masters[1]
    plan = api.build(captured, (Change("Regular", source.zones, Zones()),))
    assert plan.masters[0].rows == ()
    assert plan.masters[0].remove_ids == (21, 22, 23) and plan.masters[0].keep_ids == (
        95,
        96,
    )


@pytest.mark.parametrize(
    "problem",
    [
        "before",
        "unknown",
        "duplicate",
        "raw_after",
        "foreign_origin",
        "metadata",
        "duplicate_origin",
    ],
)
def test_entire_batch_refuses_stale_or_invalid_changes_without_returning_a_prefix(
    captured, problem
):
    valid = Editor(captured.snapshot).add("Thin", "Bottom").plan()[0]
    source = captured.snapshot.masters[1]
    change = Change("Regular", source.zones, Zones())
    if problem == "before":
        change = replace(change, before=Zones())
    elif problem == "unknown":
        change = replace(change, master="foreign")
    elif problem == "raw_after":
        change = replace(change, after=Zones((Zone(500.5, -12.5, ""),)))
    elif problem == "foreign_origin":
        change = replace(
            change, after=Zones((Zone(510, 12, "", Origin("95", b"nonzone")),))
        )
    elif problem == "metadata":
        change = replace(
            change, after=Zones((Zone(510, 12, "", Origin("21", b"tampered")),))
        )
    elif problem == "duplicate_origin":
        change = replace(
            change, after=Zones((source.zones.top[0], source.zones.top[0]))
        )
    batch = (valid, change, change) if problem == "duplicate" else (valid, change)
    with pytest.raises(ValueError):
        api.build(captured, batch)
    assert captured.snapshot.masters[1].zones is source.zones


@pytest.mark.parametrize(
    "kind,name,position",
    [
        ("Top", "", 500),
        ("Top", "base", 500),
        ("Bottom", "T: 0", 0),
        ("Bottom", "custom", 500),
    ],
)
def test_zero_width_kind_that_native_read_would_reclassify_refuses_before_history(
    captured, kind, name, position
):
    source = captured.snapshot.masters[1]
    after = (
        Editor(captured.snapshot)
        .stage("Regular", ((kind, position, 0, name),), origins=(None,))
        .zones("Regular")
    )
    with pytest.raises(ValueError, match="kind"):
        api.build(captured, (Change("Regular", source.zones, after),))


@pytest.mark.parametrize(
    "kind,name,position",
    [
        ("Top", "T: 0", 0),
        ("Top", "custom", 500),
        ("Bottom", "", 500),
        ("Bottom", "base", 500),
        ("Bottom", "custom", -10),
    ],
)
def test_representable_zero_width_kinds_and_labels_are_retained(
    captured, kind, name, position
):
    editor = Editor(captured.snapshot).stage(
        "Regular", ((kind, position, 0, name),), origins=(None,)
    )
    row = api.build(captured, editor.plan()).masters[0].rows[0]
    assert row.kind == kind and row.zone.name == name and row.zone.width == 0


def test_native_row_construction_is_ascending_top_then_bottom(captured):
    rows = (
        ("Top", 700, 15, "cap"),
        ("Top", 500, 12, "x"),
        ("Bottom", 0, 15, "base"),
        ("Bottom", -200, 12, "desc"),
    )
    editor = Editor(captured.snapshot).stage("Regular", rows, origins=(None,) * 4)
    rows = api.build(captured, editor.plan()).masters[0].rows
    assert [(row.kind, row.zone.position) for row in rows] == [
        ("Top", 500),
        ("Top", 700),
        ("Bottom", -200),
        ("Bottom", 0),
    ]
