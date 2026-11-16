# this_file: src/fontlabapp/metrics/zones/model.py
# SPDX-License-Identifier: Apache-2.0
"""Stage the complete Alignment Zones table workflow without importing a host.

Adapted from retained Apache-2.0 metrics_zones_editor.py. Python rounding, outward
absolute widths, duplicate labels, source kind parsing and o/O overshoot rules
are retained. Invalid rows reject the whole proposal instead of silently dropping
data. All updates return independent immutable plans. Native capture/write and
owned UI qualification remain separate from this numerical/staging layer.
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace

from fontlabapp.metrics.zones.data import Change, Master, Origin, Snapshot, Zone, Zones
from fontlabapp.metrics.zones.rows import (
    inherit,
    key,
    normalize,
    parse_rows,
    require_origins,
    number as _number,
    origins as row_origins,
    rows as _rows,
    text as _text,
)

Row = tuple[str, float, float, str]
Extent = tuple[float, float] | None


def extent(y: float, height: float) -> Extent:
    """Return a positive-height vertical extent; flat/missing layers suggest none."""
    low, size = _number(y), _number(height)
    return None if size <= 0 else (low, _number(low + size))


def suggest(x_height: float, caps_height: float, lower: Extent, upper: Extent) -> Zones:
    """Replace one master's zones with the source o/O baseline/x-height/cap rules."""
    x_height, caps_height = _number(x_height), _number(caps_height)
    available = [item for item in (lower, upper) if item is not None]
    for low, high in available:
        if _number(high) <= _number(low):
            raise ValueError("A glyph extent must have positive height.")
    under = [-low for low, _high in available if low < 0]
    bottom = (Zone(0, round(max(under)), "baseline"),) if under else ()
    top = tuple(
        Zone(round(metric), round(_number(bounds[1] - metric)), label)
        for bounds, metric, label in (
            (lower, x_height, "x-height"),
            (upper, caps_height, "cap height"),
        )
        if bounds is not None and bounds[1] > metric
    )
    return Zones(tuple(sorted(top, key=key)), bottom)


@dataclass(frozen=True)
class Editor:
    """Keep each master's complete staged table independently of the UI selection.

    A failed update cannot alter this editor or any prior editor. A future native
    writer consumes plan(), checks the raw snapshot plus guideline metadata, and
    applies every change as one history operation. No native write occurs here.
    """

    snapshot: Snapshot
    staged: tuple[tuple[str, Zones], ...] = ()

    def __post_init__(self) -> None:
        """Parse the full source domain before any edit can be staged."""
        names = tuple(master.name for master in self.snapshot.masters)
        if (
            not names
            or len(set(names)) != len(names)
            or self.snapshot.current_master not in names
        ):
            raise ValueError("Source master order/current master is invalid.")
        for master in self.snapshot.masters:
            _text(master.name)
            _number(master.x_height)
            _number(master.caps_height)
            normalize(master.zones)
        if len(dict(self.staged)) != len(self.staged):
            raise ValueError("Duplicate staged master.")
        for name, zones in self.staged:
            source = self._master(name)
            require_origins(source.zones, normalize(zones))
        object.__setattr__(
            self,
            "staged",
            tuple((name, normalize(zones)) for name, zones in self.staged),
        )

    def _master(self, name: str) -> Master:
        """Resolve a declared master; unknown names never create a new domain."""
        for master in self.snapshot.masters:
            if master.name == name:
                return master
        raise ValueError(f"Unknown master: {name!r}.")

    def zones(self, master: str) -> Zones:
        """Return normalized staging values, keeping the raw snapshot unchanged."""
        source = self._master(master)
        return dict(self.staged).get(master, normalize(source.zones))

    def rows(self, master: str) -> tuple[Row, ...]:
        """Render one selected master's staged rows in source table order."""
        return _rows(self.zones(master))

    def origins(self, master: str) -> tuple[Origin | None, ...]:
        """Keep hidden source identity aligned with the exact visible row order."""
        return row_origins(self.zones(master))

    def stage(
        self,
        master: str,
        rows: Iterable[Iterable[object]],
        *,
        origins: Iterable[Origin | None] | None = None,
    ) -> "Editor":
        """Publish a new master table only after every proposed row parses."""
        source = self._master(master)
        if origins is None and any(item is not None for item in self.origins(master)):
            raise ValueError("Explicit row identities are required for this source.")
        proposed = parse_rows(rows, origins=origins)
        require_origins(source.zones, proposed)
        staged = {**dict(self.staged), master: proposed}
        return replace(self, staged=tuple(staged.items()))

    def add(self, master: str, kind: str) -> "Editor":
        """Add a 12-unit top at rounded x-height or bottom at zero, named as FontLab does.

        The name is ``"T: <position>"`` or ``"B: <position>"``, plus ``.1``,
        ``.2`` … when that kind already has it (``flZone::guaranteeName`` and
        ``_check_zone_name``, ``flpackage.cpp:1646,12035-12075``). So a native
        write keeps the name, and the read-back can match the row.
        """
        source = self._master(master)
        if kind not in ("Top", "Bottom"):
            raise ValueError("New zone kind must be Top or Bottom.")
        position = round(source.x_height) if kind == "Top" else 0
        rows = self.rows(master)
        taken = {row[3] for row in rows if row[0] == kind}
        name = base = f"{'T' if kind == 'Top' else 'B'}: {position}"
        counter = 1
        while name in taken:
            name, counter = f"{base}.{counter}", counter + 1
        return self.stage(
            master,
            (*rows, (kind, position, 12, name)),
            origins=(*self.origins(master), None),
        )

    def remove(self, master: str, selection: Iterable[int]) -> "Editor":
        """Remove all selected display rows once; refuse stale/invalid indices."""
        rows, selected = self.rows(master), tuple(selection)
        if any(
            type(index) is not int or not 0 <= index < len(rows) for index in selected
        ):
            raise ValueError("Zone row selection is invalid; refresh the table.")
        return self.stage(
            master,
            (row for index, row in enumerate(rows) if index not in selected),
            origins=(
                origin
                for index, origin in enumerate(self.origins(master))
                if index not in selected
            ),
        )

    def suggest(self, master: str, lower: Extent, upper: Extent) -> "Editor":
        """Replace only the chosen master's stage, preserving every other edit."""
        source = self._master(master)
        zones = suggest(source.x_height, source.caps_height, lower, upper)
        zones = inherit(zones, self.zones(master))
        return self.stage(master, _rows(zones), origins=row_origins(zones))

    def plan(self) -> tuple[Change, ...]:
        """Plan every changed master in source order; no-op tables create no work."""
        return tuple(
            Change(master.name, master.zones, self.zones(master.name))
            for master in self.snapshot.masters
            if self.zones(master.name) != normalize(master.zones)
        )

    def pending(self) -> tuple[str, ...]:
        """List dirty masters for the original per-master status feedback."""
        return tuple(change.master for change in self.plan())
