# this_file: src/fontlabapp/metrics/zones/native.py
# SPDX-License-Identifier: Apache-2.0
"""The native Alignment Zones backend: capture, check, bounds and apply.

What: ``backend()`` returns the ``zone_editor.Backend`` for the current font.
It reads and writes PostScript zones the way Font Info does
(``fontinfo_data.cpp:565-620``): per master ``setMaster(name, False)``, read
``ps_zonesT``/``ps_zonesB``, write ``convertZonesToGuidelines(top, bottom)``
then ``updateZonesFromGuidelines()``. Apply stages every changed master
through ``font_history.commit_masters`` (ONE Undo step, issue 122 M2 route A,
measured on FontLab 9.0.9790).

Values: zones are plain ``zone_data`` values. Both native lists hold positive
widths (FontLab stores a bottom zone as a guide with a negative extension,
``flpackage.cpp:12433-12523``). Origins carry no native id: a zone key is
``"Top:<name>"`` or ``"Bottom:<name>"`` from capture. FontLab keeps zone
names unique per list, so apply finds the source zone of a retained row by
its baseline kind and name, and copies that native zone (``flZone(zone)``):
its tags and lock state stay. A new row gets a new ``flZone``.

What the route changes: ``convertZonesToGuidelines`` replaces every zone
guide of a written master. The guides get new ids, x-centre 0 and the custom
font-guideline style; only position, width, name, tags and lock are kept.
Font Info does the same.

Refusals before any history call: ``RowRefusal`` (a ``ValueError``; the
dialog stays usable) for an empty zone name (FontLab would rename it
``T: 500``; ``Editor.add`` names new rows as FontLab does), a duplicate name
in one list (FontLab would add ``.1``) and a zero-width row whose kind
FontLab reads differently (``zone_native_rules.is_top``); then the GUI-thread
and Font-window guards; then ``ValueError(STALE_TEXT)`` for a stale snapshot.

Rollback: a failure before the notification restores the zones with the
same convert/update calls, so FontLab re-creates the zone guides with new
ids; the ``RolledBackError`` text says so (``RESTORED_TEXT``). Non-zone
guides are not rebuilt (``flpackage.cpp:12456-12462``). Restoring the
original guide objects would need ``guidelinesHost``, which is unmeasured.

fl#8554: this route never calls ``flModelProducer.getClipboardData``, so the
serializer arity defect does not affect it. The serializer modules
(``zone_capture``, ``zone_prepare``, ``zone_write_plan``) stay held.

Known host defect (fl#8574): after Undo/Redo, the font-metric guidelines show 3 of 9
until ``updateFontMetrics()`` or a reopen (see ``font_history``). Offline
tests prove the call order only.
"""

from collections.abc import Iterable
from time import monotonic
from typing import Any

from fontlabapp import _native
from fontlabapp.metrics.zones.model import Editor, Extent, extent
from fontlabapp.core.history.masters import (
    MasterEdit,
    commit_masters,
    require_font_window,
)
from fontlabapp.core.history.glyphs import unstored_error
from fontlabapp.contours.extent import vertical_extent
from fontlabapp.core.scripting import current_package
from fontlabapp.metrics.zones.data import Change, Master, Origin, Snapshot, Zone, Zones
from fontlabapp.metrics.zones.editor import Backend
from fontlabapp.metrics.zones.native_rules import is_top
from fontlabapp.metrics.zones.rows import key, normalize, number, ordered, text

#: The Undo name of a zone write.
TITLE = "Alignment Zones"
#: Seconds that one capture may take.
CAPTURE_SECONDS = 2.0
#: Glyphs whose bounds Suggest reads: lowercase, then uppercase.
BOUNDS_GLYPHS = ("o", "O")
#: The refusal text for a stale snapshot.
STALE_TEXT = "The font, its masters or its zones changed; reopen Alignment Zones."
#: The end of a zone ``RolledBackError``: the restore re-creates the zone guides.
RESTORED_TEXT = (
    "The zone values were restored; FontLab re-created the zone guides with new ids. "
    "Nothing was added to Undo."
)


class RowRefusal(ValueError):
    """A planned row that FontLab would rename or read as the other kind.

    Raised before any native call. The font is unchanged; the user can fix
    the row and apply again, so the dialog stays usable.
    """


def _check(deadline: float) -> None:
    """Raise ``TimeoutError`` after ``deadline``; return no partial capture."""
    if monotonic() >= deadline:
        raise TimeoutError("Zone capture exceeded its deadline; no partial capture.")


def _kind_zones(kind: str, values: Iterable[Any]) -> tuple[Zone, ...]:
    """Return plain sorted zones of one native list, with name-based origins."""
    zones, names = [], set()
    for item in values:
        position, width, name = number(item.position), number(item.width), text(item.name)
        if width < 0 or name in names:
            raise ValueError(f"Unreadable native {kind} zone {name!r}.")
        names.add(name)
        zones.append(Zone(position, width, name, Origin(f"{kind}:{name}", b"")))
    return tuple(sorted(zones, key=key))


def read_zones(package: Any) -> Zones:
    """Return the zones of the selected master as plain values."""
    return Zones(
        _kind_zones("Top", package.ps_zonesT), _kind_zones("Bottom", package.ps_zonesB)
    )


def _master(package: Any, name: str) -> Master:
    """Return one master's plain values; the master must be selected."""
    return Master(
        name,
        number(package.xHeight_value),
        number(package.capsHeight_value),
        read_zones(package),
    )


def capture(expected_id: int | None = None) -> Snapshot:
    """Read every master of the current font; restore the starting master.

    ``expected_id``: the ``flPackage.id`` to require (default: the current
    font). Raise ``ValueError`` without a font or for unreadable values, and
    ``TimeoutError`` after ``CAPTURE_SECONDS``. Calls ``setMaster(name,
    False)`` only; no history, no refresh.
    """
    deadline = monotonic() + CAPTURE_SECONDS
    package = current_package(expected_id)
    if package is None:
        raise ValueError("Open the font before you edit its zones.")
    identifier, original = int(package.id), str(package.master)
    names = tuple(str(name) for name in package.masters)
    if not names or len(set(names)) != len(names) or original not in names:
        raise ValueError("Unreadable font masters.")
    masters = []
    try:
        for name in names:
            _check(deadline)
            package.setMaster(name, False)
            if str(package.master) != name:
                raise ValueError(f"FontLab did not select master {name!r}.")
            masters.append(_master(package, name))
    finally:
        package.setMaster(original, False)
    snapshot = Snapshot(identifier, original, tuple(masters))
    Editor(snapshot)
    return snapshot


def _visible(snapshot: Snapshot) -> tuple:
    """Return the snapshot without origins, for staleness checks."""
    return (
        snapshot.package_id,
        snapshot.current_master,
        tuple(
            (m.name, m.x_height, m.caps_height, _rows(m.zones)) for m in snapshot.masters
        ),
    )


def _rows(zones: Zones) -> tuple:
    """Return sorted ``(kind, position, width, name)`` rows without origins."""
    return tuple(
        sorted((kind, z.position, z.width, z.name) for kind, z in ordered(zones))
    )


def check(snapshot: Snapshot) -> None:
    """Refuse with ``ValueError(STALE_TEXT)`` unless the font equals ``snapshot``."""
    try:
        live = capture(snapshot.package_id)
    except (ValueError, TimeoutError) as error:
        raise ValueError(STALE_TEXT) from error
    if _visible(live) != _visible(snapshot):
        raise ValueError(STALE_TEXT)


def bounds(snapshot: Snapshot, master: str) -> tuple[Extent, Extent]:
    """Return the vertical extents of ``o`` and ``O`` in ``master``.

    A missing glyph, layer or a flat layer gives ``None``. Reads
    ``findName``, ``findLayer`` and the outline nodes
    (``outline_extent.vertical_extent``), never the cached ``boundingBox``,
    which stays stale after a Python node move (fl#8575).
    """
    package = current_package(snapshot.package_id)
    if package is None:
        raise ValueError(STALE_TEXT)
    found = []
    for name in BOUNDS_GLYPHS:
        glyph = package.findName(name)
        layer = None if glyph is None else glyph.findLayer(master)
        if layer is None or layer.isNull:
            found.append(None)
            continue
        span = vertical_extent(layer)
        found.append(None if span is None else extent(span[0], span[1] - span[0]))
    return found[0], found[1]


def _require_rows(change: Change) -> None:
    """Raise ``RowRefusal`` for rows that FontLab would rename or read as the other kind."""
    for kind, values in (("Top", change.after.top), ("Bottom", change.after.bottom)):
        names = [zone.name for zone in values]
        if any(not name for name in names):
            raise RowRefusal(f"Name every zone of {change.master!r} before Apply.")
        if len(set(names)) != len(names):
            raise RowRefusal(f"Zone names repeat in {kind} of {change.master!r}.")
        for zone in values:
            signed = zone.width if kind == "Top" else -zone.width
            if is_top(signed, zone.name, zone.position) != (kind == "Top"):
                raise RowRefusal(
                    f"FontLab would read zone {zone.name!r} of {change.master!r} as the other kind."
                )


def _changes(before: Snapshot, changes: tuple[Change, ...]) -> tuple[Change, ...]:
    """Return the checked changes in font order, or raise ``ValueError``."""
    source = {master.name: master for master in before.masters}
    seen = set()
    for change in changes:
        if not isinstance(change, Change) or change.master not in source or change.master in seen:
            raise ValueError("Unknown or duplicate master in the zone plan.")
        seen.add(change.master)
        if change.before != source[change.master].zones or change.after != normalize(change.after):
            raise ValueError("The zone plan is not from this snapshot; reopen Alignment Zones.")
        _require_rows(change)
    Editor(before, tuple((change.master, change.after) for change in changes))
    order = [master.name for master in before.masters]
    return tuple(sorted(changes, key=lambda change: order.index(change.master)))


def _sources(package: Any, before: Zones) -> dict[Origin, Any]:
    """Map each baseline origin to a copy of its live native zone."""
    native = _native("fontlab")
    live = {
        ("Top", str(z.name)): z for z in package.ps_zonesT
    } | {("Bottom", str(z.name)): z for z in package.ps_zonesB}
    found = {}
    for kind, zone in ordered(before):
        if zone.origin is not None:
            found[zone.origin] = native.flZone(live[(kind, zone.name)])
    return found


def _native_zone(native: Any, zone: Zone, source: Any) -> Any:
    """Return a native zone with the row's position, width and name."""
    item = native.flZone() if source is None else source
    item.position = float(zone.position)
    item.width = float(zone.width)
    item.name = zone.name
    return item


def _apply_zones(package: Any, change: Change) -> None:
    """Write ``change.after`` on the selected master, the Font Info way."""
    native = _native("fontlab")
    sources = _sources(package, change.before)
    lists = []
    for values in (change.after.top, change.after.bottom):
        lists.append(
            [_native_zone(native, z, sources.get(z.origin)) for z in values]
        )
    package.convertZonesToGuidelines(lists[0], lists[1])
    package.updateZonesFromGuidelines()


def _save(package: Any) -> tuple[list[Any], list[Any]]:
    """Return copies of the selected master's native zones, for a restore."""
    native = _native("fontlab")
    return (
        [native.flZone(z) for z in package.ps_zonesT],
        [native.flZone(z) for z in package.ps_zonesB],
    )


def _restore(package: Any, saved: tuple[list[Any], list[Any]]) -> None:
    """Write the saved native zones back on the selected master."""
    package.convertZonesToGuidelines(saved[0], saved[1])
    package.updateZonesFromGuidelines()


def _edit(package: Any, change: Change) -> MasterEdit:
    """Return the ``MasterEdit`` for one changed master."""
    planned = _rows(change.after)

    def verify(found: Zones) -> list[str]:
        rows = _rows(found)
        if rows == planned:
            return []
        return [f"zones {rows!r} (planned {planned!r})"]

    return MasterEdit(
        lambda: _save(package),
        lambda: _apply_zones(package, change),
        lambda: read_zones(package),
        verify,
        lambda saved: _restore(package, saved),
    )


def apply(before: Snapshot, changes: tuple[Change, ...], *, title: str = TITLE) -> Snapshot:
    """Write every changed master as ONE Undo step named ``title``; return the new baseline.

    Refuse rows first (``RowRefusal``), then off the GUI thread or without
    an active Font window (``font_history.require_font_window``), before any
    master switch. Check that the font still equals ``before`` and that every row can be
    stored as planned, then ``font_history.commit_masters``. Print the queued
    glyph ids note to Output (``edit_guards.disclose``). Then read back every
    master and the current master again (``capture``); a difference or a
    failed read raises ``history.unstored_error``, whose rule this module
    keeps: the text makes no claim about Undo. Return ``before``
    with each changed master's zones replaced by its verified plan.
    No ``ValueError`` is raised after ``commit_masters`` returns, so a
    caller may treat a ``ValueError`` as a refusal made before any write.
    """
    import fontlabapp.core.edit_guards as edit_guards  # noqa: PLR0402 - the package __getattr__ is native

    ordered_changes = _changes(before, tuple(changes))
    if not ordered_changes:
        return before
    package = current_package(before.package_id)
    if package is None:
        raise ValueError(STALE_TEXT)
    require_font_window(package, _native("fontlab"))  # before check() switches masters
    check(before)
    edits = {change.master: _edit(package, change) for change in ordered_changes}
    result = commit_masters(package, title, edits, restored_text=RESTORED_TEXT)
    edit_guards.disclose(result)
    after = {change.master: change.after for change in ordered_changes}
    baseline = Snapshot(
        before.package_id,
        before.current_master,
        tuple(
            Master(m.name, m.x_height, m.caps_height, after.get(m.name, m.zones))
            for m in before.masters
        ),
    )
    planned = _visible(baseline)
    try:
        found = _visible(capture(before.package_id))
    except Exception as error:  # the Undo step exists; report, do not hide it
        raise unstored_error([f"zones of every master ({error})"]) from error
    if found != planned:
        missed = [f"zones of master {p[0]}" for p, f in zip(planned[2], found[2], strict=False) if p != f]
        raise unstored_error(missed or ["the font or its current master"])
    return baseline


def backend(package_id: int | None = None, *, title: str = TITLE) -> Backend:
    """Return the native ``zone_editor.Backend`` for ``package_id`` or the current font.

    Its ``apply`` names the Undo step ``title`` (default ``TITLE``; the
    Vertical Metrics & Zones app passes its own label).
    """
    if title == TITLE:
        return Backend(lambda: capture(package_id), check, bounds, apply)
    return Backend(lambda: capture(package_id), check, bounds, lambda before, changes: apply(before, changes, title=title))


__all__ = [
    "BOUNDS_GLYPHS",
    "CAPTURE_SECONDS",
    "RESTORED_TEXT",
    "STALE_TEXT",
    "TITLE",
    "RowRefusal",
    "apply",
    "backend",
    "bounds",
    "capture",
    "check",
    "read_zones",
]
