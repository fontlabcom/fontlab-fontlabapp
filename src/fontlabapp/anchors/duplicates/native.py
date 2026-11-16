# this_file: src/fontlabapp/anchors/duplicates/native.py
# SPDX-License-Identifier: Apache-2.0
"""Direct identity removals with preflight and recoverable partial-write errors.

One final notification follows the existing anchor writer's layer+glyph protocol.
Its actual Undo/Redo/full-font preservation requires native acceptance. Never
append reconstructed pins as rollback or clear the process-global update queue.
"""

from time import monotonic
from typing import Any

import fontlabapp.core.edit_guards as edit_guards
from fontlabapp import _native
from fontlabapp.anchors.duplicates.model import TITLE, Snapshot, plan
from fontlabapp.anchors.duplicates.capture import (
    check,
    context,
    pin_value,
    read,
    require_main_thread,
)
from fontlabapp.guides.inspect.model import affected_auto_layers
from fontlabapp.core.scripting import current_package


class PartialWriteError(RuntimeError):
    """An attempted native write failed; notification can itself also fail."""

    def __init__(self, removed: int, attempted: int, errors: list[Exception]) -> None:
        self.removed, self.attempted = removed, attempted
        self.errors = tuple(str(error) for error in errors)
        super().__init__(
            f"Fix failed after {attempted} attempted removals ({removed} confirmed). "
            "Native changes may remain; use Edit > Undo and inspect the font. "
            + "; ".join(self.errors)
        )


class Backend:
    """Own only scalar binding facts; resolve native wrappers during each action."""

    def __init__(self) -> None:
        self.bound = False
        self.identity: int | None = None
        self.selection: tuple[str, ...] | None = None

    def package(self) -> Any:
        """Refuse a switched or closed font before touching old native handles."""
        package = current_package()
        identity = None if package is None else int(package.id)
        if self.bound and identity != self.identity:
            raise ValueError(
                "The original font is no longer current; reopen this tool."
            )
        self.bound, self.identity = True, identity
        return package

    def capture(self, *, deadline: float | None = None) -> Snapshot | None:
        """Publish two equal complete passes; keep the opening selection policy."""
        require_main_thread()
        deadline = monotonic() + 2.0 if deadline is None else deadline
        package = self.package()
        if package is None:
            return None
        a = context(package, deadline)
        first = read(package, a[1], a[3], deadline)
        b = context(self.package(), deadline)
        second = read(package, b[1], b[3], deadline)
        c = context(self.package(), deadline)
        check(deadline)
        if a != b or b != c or first != second:
            raise ValueError(
                "Font or anchors changed during capture; refresh or reopen."
            )
        if self.selection is None:
            self.selection = a[2]
        return Snapshot(a[0] + (a[2],), a[1], self.selection, a[3], *first)

    def validate(self, facts: Snapshot, *, deadline: float | None = None) -> None:
        """Reject every captured source/domain delta before a write or rerender."""
        if facts is None or self.capture(deadline=deadline) != facts:
            raise ValueError(
                "Source changed since preview; refresh or reopen this tool."
            )

    def apply(self, facts: Snapshot, coincident: bool, selected: bool) -> dict:
        """Remove only preflighted original pin objects; never reconstruct survivors."""
        require_main_thread()
        deadline = monotonic() + 2.0
        self.validate(facts, deadline=deadline)
        work = plan(facts, coincident, selected)
        if not work:
            return {"anchors": 0, "layers": 0}
        blocked = affected_auto_layers(
            facts.dependencies, {layer.name for layer, _ in work}
        )
        if blocked:
            raise ValueError(
                "Cannot safely undo changes to automatic dependants: "
                + ", ".join(blocked)
            )
        package = self.package()
        resolved = []
        for source, extras in work:
            check(deadline)
            glyph = package.findName(source.name)
            layer = glyph.findLayer(source.master)
            pins = tuple(layer.anchors)
            if (
                int(glyph.id),
                int(layer.id),
                bool(layer.autoLayer),
                tuple(pin_value(p, deadline) for p in pins),
            ) != (source.glyph_id, source.identity, False, source.pins):
                raise ValueError(
                    "Target changed before history; refresh or reopen this tool."
                )
            by_id = {int(pin.id): pin for pin in pins}
            resolved.append((glyph, layer, tuple(by_id[key] for key in extras)))
        self.validate(facts, deadline=deadline)
        check(deadline)
        return remove(resolved, deadline)


def remove(work: list, deadline: float) -> dict:
    """Initialize all histories, attempt edits, finalize once even on partial failure."""
    native = _native("fontlab")
    stamp = _native("PythonQt").QtCore.QDateTime.currentDateTimeUtc()
    glyphs = list({int(g.id): g for g, _, _ in work}.values())
    edit_guards.require_history_scope(glyphs, native=native)
    objects = [layer for _, layer, _ in work] + glyphs
    for obj in objects:
        check(deadline)
        obj.checkInitHistoryState(0)
    removed = attempted = 0
    errors = []
    try:
        for _, layer, pins in work:
            for pin in pins:
                check(deadline)
                attempted += 1
                layer.removeAnchor(pin)
                if any(int(p.id) == int(pin.id) for p in layer.anchors):
                    raise RuntimeError(
                        "FontLab did not remove the planned anchor identity."
                    )
                removed += 1
    except Exception as error:  # noqa: BLE001 - contain and finalize attempted native changes
        errors.append(error)
    if attempted:
        for glyph in glyphs:
            try:
                glyph.lastModified = stamp
            except Exception as error:  # noqa: BLE001 - still finalize the attempted history
                errors.append(error)
        try:
            native.flItems().notifyChangesApplied(TITLE, objects)
        except Exception as error:  # noqa: BLE001 - failed history is not a successful Fix
            errors.append(error)
        finally:
            for glyph in glyphs:
                try:
                    glyph.lastModified = stamp
                except Exception as error:  # noqa: BLE001 - retain observer/finalization failures
                    errors.append(error)
    if errors:
        raise PartialWriteError(removed, attempted, errors) from errors[0]
    return {"anchors": removed, "layers": len(work)}
