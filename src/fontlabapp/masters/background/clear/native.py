# this_file: src/fontlabapp/masters/background/clear/native.py
# SPDX-License-Identifier: Apache-2.0
"""Remove original background objects after whole-font mapping preflight.

No payload reconstruction or rollback is attempted. A native failure after an
attempted write is finalized once and diagnosed for the user's native Undo.
Native full-font history, metadata and reopen qualification remains separate.
"""
from threading import current_thread, main_thread
from time import monotonic
from typing import Any

import fontlabapp.core.edit_guards as edit_guards
from fontlabapp import _native
from fontlabapp.glyphs.catalog.native import _context, _stamp
from fontlabapp.masters.background.clear.model import (
    Snapshot,
    plan,
    automatic_dependants,
)
from fontlabapp.masters.background.clear.capture import check, read
from fontlabapp.core.scripting import current_package


def layer_ids(glyph: Any, deadline: float) -> tuple[int, ...]:
    """Read complete surviving order with a checkpoint before every native entry."""
    check(deadline)
    result = []
    for layer in glyph.layers:
        check(deadline)
        result.append(int(layer.id))
    return tuple(result)


def expected_survivors(work: list, owners: dict, deadline: float) -> dict:
    """Group removals once; prepare complete expected order before any history."""
    check(deadline)
    masks: dict[int, set[int]] = {}
    for glyph, mask in work:
        check(deadline)
        masks.setdefault(int(glyph.id), set()).add(int(mask.id))
    expected = {}
    for identity, glyph in owners.items():
        check(deadline)
        expected[identity] = tuple(identity_ for identity_ in layer_ids(glyph, deadline)
                                   if identity_ not in masks[identity])
    check(deadline)
    return expected


class PartialWriteError(RuntimeError):
    """An attempted batch failed; never represent it as successful or rolled back."""

    def __init__(self, attempted: int, removed: int, errors: list[str]) -> None:
        self.attempted, self.removed = attempted, removed
        super().__init__(f"Background clearing failed after {attempted} attempts, "
                         f"{removed} confirmed removals. Use Undo to inspect/recover. "
                         + "; ".join(errors))


class Backend:
    """Bind the original current font; keep scans and writer preparation bounded."""

    def __init__(self) -> None:
        self._identity: tuple | None = None

    def capture(self, deadline: float | None = None) -> Snapshot | None:
        """Double-read complete ordered facts without creating background layers."""
        deadline = monotonic() + 2 if deadline is None else deadline
        check(deadline)
        if current_thread() is not main_thread():
            raise RuntimeError("Background tools require the FontLab UI thread.")
        package = current_package()
        if package is None:
            if self._identity is not None:
                raise ValueError("Reopen the tool for its original font.")
            return None
        context, package, font = _context(deadline)
        identity = (int(package.id), int(package.fgId))
        if self._identity is not None and identity != self._identity:
            raise ValueError("Reopen the tool for its original font.")
        masters = tuple(package.masters)
        first = read(package, font, deadline, _stamp)
        second = read(package, font, deadline, _stamp)
        after, _, _ = _context(deadline)
        if first != second or context != after or masters != tuple(package.masters):
            raise ValueError("Font changed during capture; refresh the complete table.")
        self._identity = identity
        return Snapshot(context, masters, *first)

    def apply(self, source: Snapshot, masters: bool, *,
              disclosure: dict[str, Any] | None = None) -> dict[str, Any]:
        """Remove entire original masks in source order with one final notification."""
        status = {"pending_updates": (), "pending_note": ""}
        edit_guards.disclose(status, disclosure)
        deadline = monotonic() + 2
        if self.capture(deadline=deadline) != source:
            raise ValueError("Background table is stale; refresh before clearing.")
        removals = plan(source, masters, deadline)
        check(deadline)
        if not removals:
            return {"backgrounds": 0, "glyphs": 0, "layers": 0, **status}
        by_id = {row.identity: row for row in source.layers}
        resolved = {fact[1]: fact[5] for fact in source.glyphs}
        for item in removals:
            if by_id[item.mask_id].locked:
                raise ValueError("A locked background has an unobservable active pointer; clearing is unsupported.")
            if resolved[item.glyph_id] == item.mask_id:
                raise ValueError("An active background cannot be removed while preserving the active layer.")
        targets = {item.glyph for item in removals}
        if automatic_dependants(source, targets, deadline):
            raise ValueError("Automatic layers or dependants require separate native qualification.")
        native = _native("fontlab")
        package = current_package()
        glyphs, layers = {}, {}
        for fact in source.glyphs:
            check(deadline)
            glyph = package.findFgId(fact[0])
            glyphs[fact[1]] = glyph
            for layer in glyph.layers:
                check(deadline)
                layers[int(layer.id)] = layer
        work, foregrounds, owners = [], {}, {}
        for item in removals:
            check(deadline)
            glyph, mask = glyphs[item.glyph_id], layers[item.mask_id]
            work.append((glyph, mask))
            owners[item.glyph_id] = glyph
            for identity in item.foreground_ids:
                foregrounds.setdefault(identity, layers[identity])
        stamp = _native("PythonQt").QtCore.QDateTime.currentDateTimeUtc()
        notifier = native.flItems()
        objects = [*foregrounds.values(), *owners.values()]
        expected = expected_survivors(work, owners, deadline)
        if self.capture(deadline=deadline) != source:
            raise ValueError("Background mapping changed before history preparation.")
        check(deadline)
        edit_guards.require_history_scope(list(owners.values()), native=native)
        ids = edit_guards.pending_updates(native)
        status = {"pending_updates": ids, "pending_note": edit_guards.pending_note(ids)}
        edit_guards.disclose(status, disclosure)
        for obj in objects:
            check(deadline)
            obj.checkInitHistoryState(0)
        result = self._remove(work, foregrounds, owners, objects, notifier, stamp, deadline, expected)
        return {**result, **status}

    @staticmethod
    def _remove(work: list, foregrounds: dict, owners: dict, objects: list,
                notifier: Any, stamp: Any, deadline: float, expected: dict | None = None) -> dict[str, int]:
        """Finalize any attempted batch once, including exceptional native outcomes."""
        attempted = removed = 0
        failures: list[tuple[str, BaseException]] = []
        check(deadline)
        expected = expected_survivors(work, owners, deadline) if expected is None else expected
        try:
            for glyph, mask in work:
                check(deadline)
                attempted += 1
                glyph.removeLayer(mask)
                if int(mask.id) in layer_ids(glyph, deadline):
                    raise RuntimeError("Native background removal did not take effect.")
                removed += 1
            for identity, glyph in owners.items():
                if layer_ids(glyph, deadline) != expected[identity]:
                    raise RuntimeError("Surviving layer identity/order changed.")
            for layer in foregrounds.values():
                background = layer.getMaskLayer(False)
                if background is not None and not background.isNull and background.isValid:
                    raise RuntimeError("Background fallback remains after clearing.")
        except BaseException as error:  # retain interruption identity through cleanup
            failures.append(("", error))
        finally:
            if attempted:
                for glyph in owners.values():
                    try:
                        glyph.lastModified = stamp
                    except BaseException as error:
                        failures.append(("Pre-notification date: ", error))
                try:
                    notifier.notifyChangesApplied("Clear backgrounds", objects)
                except BaseException as error:
                    failures.append(("Final notification: ", error))
                for glyph in owners.values():
                    try:
                        glyph.lastModified = stamp
                    except BaseException as error:
                        failures.append(("Post-notification date: ", error))
        for _, error in failures:
            if not isinstance(error, Exception):
                if attempted:
                    for phase, other in failures:
                        if other is not error:
                            error.add_note(f"{phase}{type(other).__name__}: {other}")
                    error.add_note(f"Background clearing interrupted after {attempted} attempts, "
                                   f"{removed} confirmed removals. Use Undo to inspect/recover.")
                raise error
        errors = [phase + str(error) for phase, error in failures]
        if errors and not attempted:
            raise RuntimeError("No background removal was attempted: " + "; ".join(errors))
        if errors:
            raise PartialWriteError(attempted, removed, errors) from failures[0][1]
        return {"backgrounds": removed, "glyphs": len(owners), "layers": len(foregrounds)}
