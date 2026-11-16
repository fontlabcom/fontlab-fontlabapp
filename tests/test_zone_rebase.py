# this_file: tests/test_zone_rebase.py
"""Verify complete Apply-result identity binding before UI rebasing."""

from dataclasses import FrozenInstanceError, replace

import pytest
from test_zone_origins import editor

from fontlabapp.metrics.zones.model import Editor
from fontlabapp.metrics.zones.data import Master, Origin, Snapshot, Zones
from fontlabapp.metrics.zones.editor import check_result


def test_writer_can_bind_new_rows_to_fresh_origins_then_edit_again():
    initial = editor().add("Regular", "Bottom")
    change = initial.plan()[0]
    bound = replace(
        change.after,
        bottom=(
            replace(change.after.bottom[0], origin=Origin("new", b"new defaults")),
        ),
    )
    after = replace(
        initial.snapshot,
        masters=(
            initial.snapshot.masters[0],
            replace(initial.snapshot.masters[1], zones=bound),
        ),
    )
    check_result(initial.snapshot, (change,), after)
    rebased = Editor(after).stage(
        "Regular",
        (("Top", 600, 12, ""), *Editor(after).rows("Regular")[1:]),
        origins=Editor(after).origins("Regular"),
    )
    assert Origin("new", b"new defaults") in rebased.origins("Regular")
    with pytest.raises(FrozenInstanceError):
        bound.bottom[0].origin.metadata = b"changed"


@pytest.mark.parametrize(
    "bad",
    [
        Origin("a", b"recycled"),
        Origin("b", b"recycled"),
        Origin("new", []),
        Origin("", b"bad"),
    ],
)
def test_new_writer_rows_cannot_steal_captured_identities_or_return_invalid_metadata(
    bad,
):
    initial = editor().add("Regular", "Bottom")
    change = initial.plan()[0]
    zones = replace(change.after, bottom=(replace(change.after.bottom[0], origin=bad),))
    after = replace(
        initial.snapshot,
        masters=(
            initial.snapshot.masters[0],
            replace(initial.snapshot.masters[1], zones=zones),
        ),
    )
    with pytest.raises(ValueError):
        check_result(initial.snapshot, (change,), after)


def test_removed_source_identity_cannot_be_recycled_as_a_new_zone():
    initial = editor()
    removed = initial.origins("Regular")[0]
    staged = initial.remove("Regular", [0]).add("Regular", "Bottom")
    change = staged.plan()[0]
    zones = replace(
        change.after, bottom=(replace(change.after.bottom[0], origin=removed),)
    )
    after = replace(
        initial.snapshot,
        masters=(
            initial.snapshot.masters[0],
            replace(initial.snapshot.masters[1], zones=zones),
        ),
    )
    with pytest.raises(ValueError, match="differs"):
        check_result(initial.snapshot, (change,), after)


def test_new_duplicate_rows_bind_once_each_and_cannot_duplicate_one_identity():
    initial = (
        Editor(Snapshot(31, "R", (Master("R", 500, 700),)))
        .add("R", "Top")
        .add("R", "Top")
    )
    change = initial.plan()[0]
    zones = Zones(
        tuple(
            replace(z, origin=Origin(str(i), bytes([i])))
            for i, z in enumerate(change.after.top)
        )
    )
    after = replace(
        initial.snapshot, masters=(replace(initial.snapshot.masters[0], zones=zones),)
    )
    check_result(initial.snapshot, (change,), after)
    duplicate = replace(zones, top=(zones.top[0], zones.top[0]))
    with pytest.raises(ValueError, match="identity"):
        check_result(
            initial.snapshot,
            (change,),
            replace(after, masters=(replace(after.masters[0], zones=duplicate),)),
        )
