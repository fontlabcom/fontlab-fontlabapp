# this_file: src/fontlabapp/metrics/zones/write_plan.py
# SPDX-License-Identifier: Apache-2.0
"""Preflight a complete native Alignment Zones batch without native operations.

Retained rows carry their original whole native payload. Every other guide id is
kept in source order. This plan does not decode, allocate, mutate or add history;
the native writer must recheck the entire Capture immediately before those steps
and qualify metadata, one-step Undo/Redo, caches and persistence independently.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from fontlabapp.metrics.zones.model import Editor
from fontlabapp.metrics.zones.capture_data import Capture, GuideBuffer
from fontlabapp.metrics.zones.data import Change, Master, Snapshot, Zone, Zones
from fontlabapp.metrics.zones.native_rules import is_top
from fontlabapp.metrics.zones.rows import normalize


@dataclass(frozen=True)
class WriteRow:
    """One construction row; retained source payload stays in zone.origin."""

    kind: Literal["Top", "Bottom"]
    zone: Zone
    source_id: int | None


@dataclass(frozen=True)
class MasterWrite:
    """One complete changed master, preserving all unedited guide identities."""

    master: str
    source: GuideBuffer
    remove_ids: tuple[int, ...]
    keep_ids: tuple[int, ...]
    rows: tuple[WriteRow, ...]


@dataclass(frozen=True)
class WritePlan:
    """One whole prevalidated batch and its complete all-master source fence."""

    before: Capture
    masters: tuple[MasterWrite, ...]


def _zones(zones: Zones) -> None:
    """Require immutable row collections before retaining source or staged data."""
    if (
        not isinstance(zones, Zones)
        or type(zones.top) is not tuple
        or type(zones.bottom) is not tuple
    ):
        raise ValueError("Zone collections must be immutable tuples.")


def _identifier(zone: Zone) -> int:
    """Parse the canonical native id and nonempty whole-payload provenance."""
    origin = zone.origin
    if origin is None or not origin.metadata:
        raise ValueError("Native zone source identity/payload is missing; recapture.")
    try:
        identifier = int(origin.key)
    except ValueError as error:
        raise ValueError("Native zone source identity is not canonical.") from error
    if identifier <= 0 or str(identifier) != origin.key:
        raise ValueError("Native zone source identity is not canonical.")
    return identifier


def _frame(master: Master, frame: GuideBuffer) -> tuple[int, ...]:
    """Check complete guide order, raw buffer and captured editable membership."""
    if not isinstance(frame, GuideBuffer) or frame.master != master.name:
        raise ValueError("Native guide master domain/order differs from the snapshot.")
    if (
        type(frame.ids) is not tuple
        or type(frame.data) is not bytes
        or not frame.data
        or any(type(i) is not int or i <= 0 for i in frame.ids)
        or len(set(frame.ids)) != len(frame.ids)
    ):
        raise ValueError("Native guide identity/buffer data is incomplete.")
    _zones(master.zones)
    editable = {_identifier(zone) for zone in (*master.zones.top, *master.zones.bottom)}
    if not editable.issubset(frame.ids):
        raise ValueError("A captured editable zone is absent from its guide buffer.")
    return tuple(identifier for identifier in frame.ids if identifier in editable)


def _source(before: Capture) -> dict[str, tuple[Master, GuideBuffer, tuple[int, ...]]]:
    """Parse the complete captured domain before considering any staged change."""
    if (
        not isinstance(before, Capture)
        or not isinstance(before.snapshot, Snapshot)
        or type(before.guides) is not tuple
        or type(before.snapshot.masters) is not tuple
    ):
        raise ValueError("An immutable complete native Capture is required.")
    snapshot = before.snapshot
    if (
        type(snapshot.package_id) is not int
        or snapshot.package_id <= 0
        or len(before.guides) != len(snapshot.masters)
    ):
        raise ValueError("Native font/guide master domain is incomplete.")
    Editor(snapshot)
    return {
        master.name: (master, frame, _frame(master, frame))
        for master, frame in zip(snapshot.masters, before.guides, strict=True)
    }


def _changes(source: dict, changes: Iterable[Change]) -> tuple[Change, ...]:
    """Materialize and check the whole request; stale raw baselines never rebase."""
    requested, seen = tuple(changes), set()
    for change in requested:
        if (
            not isinstance(change, Change)
            or change.master not in source
            or change.master in seen
        ):
            raise ValueError("Unknown or duplicate master in native zone plan.")
        seen.add(change.master)
        _zones(change.after)
        if change.before != source[change.master][0].zones:
            raise ValueError("Native zone raw baseline changed; recapture.")
        if change.after != normalize(change.after):
            raise ValueError(
                "Native zone changes must come from the normalized editor plan."
            )
    return requested


def _master(change: Change, frame: GuideBuffer, remove: tuple[int, ...]) -> MasterWrite:
    """Sort construction rows and refuse kinds that native reads would change."""
    rows = []
    for kind, values in (("Top", change.after.top), ("Bottom", change.after.bottom)):
        for zone in values:
            signed = zone.width if kind == "Top" else -zone.width
            if is_top(signed, zone.name, zone.position) != (kind == "Top"):
                raise ValueError(
                    f"Native zone kind cannot round-trip: {change.master!r}, {kind}, {zone.name!r}."
                )
            rows.append(
                WriteRow(kind, zone, None if zone.origin is None else _identifier(zone))
            )
    return MasterWrite(
        change.master,
        frame,
        remove,
        tuple(i for i in frame.ids if i not in remove),
        tuple(rows),
    )


def build(before: Capture, changes: Iterable[Change]) -> WritePlan:
    """Return all effective masters in source order, or reject the entire batch.

    Editor validation retains exact source metadata and rejects duplicate/foreign
    origins. No-op rows create no work. Unrepresentable kinds remain explicit
    native gates; no label changes, silent row loss or alternate kind is applied.
    """
    source = _source(before)
    requested = _changes(source, changes)
    editor = Editor(before.snapshot, tuple((c.master, c.after) for c in requested))
    masters = tuple(
        _master(c, source[c.master][1], source[c.master][2]) for c in editor.plan()
    )
    return WritePlan(before, masters)


def require_current(plan: WritePlan, current: Capture) -> None:
    """Refuse any source font/master/metric/id/buffer delta before native work."""
    _source(current)
    if plan.before != current:
        raise ValueError(
            "The complete native zone source changed; recapture before writing."
        )
