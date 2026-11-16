# this_file: src/fontlabapp/kerning/batch.py
# SPDX-License-Identifier: Apache-2.0
"""Preflight native @class edits across masters, then checkpoint one whole batch.

Reuse Fontport's measured zero-seed/scale and before/after history protocol, at
all-master native notation rather than its key-master UFO model. FontLab source
pyfontgate/fgkerning.cxx defines explicit items and (id, mode) setters. The native
history protocol may add a no-op checkpoint; first Undo/Redo must restore the
entire batch. No glyph or auto-layer notifications are issued.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from fontlabapp import _native
from fontlabapp.kerning.edit.model import whole_value
from fontlabapp.kerning.identity import Edits, Pair, Pairs, native_side, pair_key
from fontlabapp.core.scripting import current_package, kerning_pairs

MODES = {"KernLeft": (0,), "KernRight": (1,), "KernBothSide": (0, 1)}


@dataclass(frozen=True)
class KerningSnapshot:
    """Complete independent pair/class/master values binding a modeless preview."""

    package_id: int
    masters: tuple[str, ...]
    pairs: dict[str, Pairs]
    groups: dict[str, dict[str, tuple[tuple[str, ...], str]]]
    typed: bool = False


def snapshot_kerning(package: Any, *, typed: bool = False) -> KerningSnapshot:
    """Read every named master without changing the active master; refuse stale fonts."""
    if package is None or current_package(package.id) is None:
        raise ValueError("The original font is no longer current; reopen this tool.")
    masters = tuple(package.masters)
    pairs, groups = {}, {}
    for master in masters:
        pairs[master] = (
            kerning_pairs(package, master, typed=True)
            if typed
            else kerning_pairs(package, master)
        )
        groups[master] = {
            name: (tuple(members), mode)
            for name, (members, mode) in package.kerning(master).groups.items()
        }
    if current_package(package.id) is None or tuple(package.masters) != masters:
        raise ValueError(
            "Font or masters changed during scan; Refresh before applying."
        )
    return KerningSnapshot(package.id, masters, pairs, groups, typed)


def ensure_snapshot(package: Any, expected: KerningSnapshot) -> KerningSnapshot:
    """Reject any pair/class/master change since the displayed complete scan."""
    if expected is None or current_package(expected.package_id) is None:
        raise ValueError("The original font is no longer current; reopen this tool.")
    if (
        tuple(package.masters) != expected.masters
        or snapshot_kerning(package, typed=expected.typed) != expected
    ):
        raise ValueError("Kerning results are stale; use Refresh before applying.")
    return expected


def validate_pair(
    package: Any, master: str, pair: Pair, *, groups: Mapping | None = None,
    members: bool = True,
) -> tuple:
    """Require existing glyphs or classes of the correct side/mode before any write.

    ``members=False`` checks only the class identity; it is used for pairs the
    batch merely re-seeds, so a stale class member elsewhere in the font (common
    in subset fonts) does not block unrelated edits.
    """
    if not isinstance(pair, tuple) or len(pair) != 2:
        raise ValueError("Kerning key must be a tuple of two names")
    if master not in tuple(package.masters):
        raise ValueError(f"Unknown kerning master: {master}")
    if groups is None:
        groups = dict(package.kerning(master).groups.items())
    for side, encoded in enumerate(pair):
        name, mode = native_side(encoded)
        if mode == "groupMode":
            group = groups.get(name)
            if group is None or side not in MODES.get(group[1], ()):
                raise ValueError(
                    f"Unknown or wrong-side kerning class: {name} on {master}"
                )
            names = group[0] if members else ()
        else:
            names = (name,)
        for member in names:
            glyph = package.findName(member)
            if glyph is None or glyph.isNull:
                raise ValueError(f"Unknown glyph: {member} on {master}")
    return tuple(native_side(name) for name in pair)


def _validate_persistence_range(desired: dict[str, Pairs], upm: Any) -> None:
    """Refuse final values the native load pipeline would clamp and mark.

    FontLab's ioengine.cpp checks every master's pairs against twice UPM on
    every load, including its own VFJ saves. Validate final values so a repair
    or deletion of existing extreme values remains possible; never clamp here.
    """
    message = "The font needs valid positive units per em before editing kerning."
    if isinstance(upm, bool) or not isinstance(upm, (int, float)):
        raise ValueError(message)  # noqa: TRY004 - one user-facing numeric boundary
    try:
        upm = float(upm)
    except OverflowError as error:
        raise ValueError(message) from error
    if not math.isfinite(upm) or upm <= 0:
        raise ValueError(message)
    limit = 2 * upm
    for master, values in desired.items():
        for (left, right), value in values.items():
            if abs(value) > limit:
                raise ValueError(
                    f"Kerning on {master}: {left} {right} = {value:g} exceeds FontLab’s save/reopen range of ±{limit:g} units (twice units per em); no changes applied."
                )


def _side_text(side: Any) -> str:
    """Display one pair side: a class as ``@name``, a glyph by name."""
    if isinstance(side, tuple):
        name, mode = side
        return f"@{name}" if mode != "glyphMode" else str(name)
    return str(side)


def _whole(master: str, pair: Pair, value: Any) -> Any:
    """``whole_value`` whose refusal names the master, pair and value."""
    try:
        return whole_value(value)
    except ValueError as error:
        left, right = (_side_text(side) for side in pair)
        raise ValueError(
            f"Kerning on {master}: {left} {right} = {value:g} is not a whole "
            f"number; {error}. Round that pair first; no changes applied."
        ) from error


def _stage(package: Any, edits: Edits, before: KerningSnapshot) -> tuple[dict, dict]:
    """Validate the entire batch and every affected history value before checkpointing."""
    desired = {master: dict(values) for master, values in before.pairs.items()}
    keys = {}
    for master, changes in edits.items():
        if master not in desired:
            raise ValueError(f"Unknown kerning master: {master}")
        seen = set()
        for pair, value in changes.items():
            pair = pair_key(pair, typed=before.typed)
            if pair in seen:
                raise ValueError("Repeated native kerning identity in one edit batch")
            seen.add(pair)
            keys[master, pair] = validate_pair(
                package, master, pair, groups=before.groups[master]
            )
            if value is None:
                desired[master].pop(pair, None)
            else:
                desired[master][pair] = _whole(master, pair, value)
    changed = {m: values for m, values in desired.items() if values != before.pairs[m]}
    if changed:
        for master, values in before.pairs.items():
            for pair, value in values.items():
                _whole(master, pair, value)
        # Only masters this batch changes are range-checked (Scriptmix TODO:80);
        # an untouched master's existing extreme value does not block other edits.
        _validate_persistence_range(changed, package.upm)
        # Zero seeding scales every pair in its master, so resolve all desired
        # keys up front, including unchanged nonzero pairs that must be restored.
        keys.update({
            (m, pair): validate_pair(package, m, pair, groups=before.groups[m], members=False)
            for m, values in changed.items()
            for pair in values
            if (m, pair) not in keys
        })
    return changed, keys


def _replace(
    native: Any, before: Pairs, desired: Pairs, keys: dict[Pair, tuple]
) -> None:
    """Retain explicit zero via nonzero seeds and restore every scaled nonzero pair."""
    for pair in before.keys() - desired.keys():
        native.remove(tuple(native_side(name) for name in pair))
    zeros = [
        pair for pair, value in desired.items() if value == 0 and before.get(pair) != 0
    ]
    for pair in zeros:
        native.set(keys[pair], 1)
    if zeros:
        native.scale(0.0)
    for pair, value in desired.items():
        if value != 0 and (zeros or pair not in before or before[pair] != value):
            native.set(keys[pair], value)
    native.scale(1.0)


def write_kerning(
    package: Any,
    edits: Edits,
    undo_name: str,
    *,
    expected: KerningSnapshot | None = None,
) -> bool:
    """Apply one fully staged batch; no-op adds no history, partial failures retain Undo.

    Fractional source history on any master is refused because the package-wide
    native checkpoint rounds it. All validation and native container acquisition
    precede notification. Every final master must also fit the native save/reopen
    range of +/-2*positive finite UPM; no values are silently clamped.
    Failed writes/readback honestly report possible partial
    mutation rather than pretending that a manual rollback was an Undo.
    """
    if not isinstance(undo_name, str) or not undo_name.strip():
        raise ValueError("Undo name must not be blank")
    before = (
        snapshot_kerning(
            package,
            typed=any(
                isinstance(pair, tuple)
                and any(isinstance(side, tuple) for side in pair)
                for changes in edits.values()
                for pair in changes
            ),
        )
        if expected is None
        else ensure_snapshot(package, expected)
    )
    desired, keys = _stage(package, edits, before)
    if not desired:
        return False
    active = package.master
    native = {master: package.kerning(master) for master in desired}
    items = [package, package.mastersContainer(), package.kerningContainer()]
    notify = _native("fontlab").flItems.notifyChangesApplied
    package.checkInitHistoryState(0)
    # Deliberate pre+post notify (live a2 round 11): the first notify records
    # history-less edits a script made earlier as their own Undo row. Without
    # it the next Undo would silently revert them together with this batch.
    notify(undo_name, items)
    failure = None
    try:
        for master, values in desired.items():
            _replace(
                native[master],
                before.pairs[master],
                values,
                {pair: keys[master, pair] for pair in values},
            )
    except Exception as error:  # noqa: BLE001 - preserve native Undo / contain UI callbacks
        failure = error
    finally:
        try:
            notify(undo_name, items)
        except Exception as error:  # noqa: BLE001 - preserve native Undo / contain UI callbacks
            failure = failure or error
    try:
        after = snapshot_kerning(package, typed=before.typed)
        wanted = dict(before.pairs)
        wanted.update(desired)
        if (
            after.pairs != wanted
            or after.groups != before.groups
            or after.masters != before.masters
            or package.master != active
        ):
            raise RuntimeError(
                "Native kerning readback differs from the complete requested batch"
            )
    except Exception as error:  # noqa: BLE001 - preserve native Undo / contain UI callbacks
        failure = failure or error
    if failure is not None:
        raise RuntimeError(
            f"Kerning may be partially changed; use Undo and Refresh. {failure}"
        ) from failure
    return True
