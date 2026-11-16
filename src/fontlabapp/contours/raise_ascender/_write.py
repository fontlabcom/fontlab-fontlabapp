# this_file: src/fontlabapp/contours/raise_ascender/_write.py
# SPDX-License-Identifier: MIT AND Apache-2.0
"""Balanced per-occurrence native history; never global Undo or UpdateAll."""

from collections.abc import Callable
from typing import Any

import fontlabapp.core.edit_guards as edit_guards

from fontlabapp.contours.raise_ascender.model import check


class PartialWriteError(RuntimeError):
    """Stop after any uncertain partial edit and retain all finalization errors."""

    def __init__(self, completed: int, errors: list[Exception]) -> None:
        self.completed, self.errors = completed, tuple(errors)
        super().__init__(
            f"Raise Ascender failed after {completed} completed occurrences; native changes may remain. "
            "Inspect the font and use Edit > Undo. " + "; ".join(map(str, errors))
        )


def publish(
    glyph: Any,
    layer: Any,
    jobs: tuple,
    dependants: tuple,
    native: Any,
    qt: Any,
    deadline: float,
) -> None:
    """Attempt exactly one final history notification after any shape mutation."""
    check(deadline)
    glyphs = (glyph, *dependants)
    objects = [layer, *glyphs]
    for item in objects:
        check(deadline)
        item.checkInitHistoryState(0)
    stamp = qt.QtCore.QDateTime.currentDateTimeUtc()
    errors, attempted = [], False
    try:
        for index, old, new in jobs:
            check(deadline)
            if int(layer.shapes[index].id) != int(old.id):
                raise ValueError(
                    "A staged own-shape identity changed before attachment."
                )
            attempted = True
            layer.removeShape(old)
            inserted = layer.insertShape(index, new)
            if inserted is not None and int(inserted.id) != int(new.id):
                raise RuntimeError("Native attachment changed staged shape identity.")
            if int(layer.shapes[index].id) != int(new.id):
                raise RuntimeError("Native attachment did not retain the staged shape.")
        layer.changed()
        if layer.update() is False:
            raise RuntimeError("Native geometry cache update failed.")
        check(deadline)
    except Exception as error:  # noqa: BLE001 - retain native failure and still finalize attempted history
        errors.append(error)
    if attempted:
        for owner in glyphs:
            try:
                owner.lastModified = stamp
            except Exception as error:  # noqa: BLE001 - retain native failure and still finalize attempted history
                errors.append(error)
        try:
            native.flItems().notifyChangesApplied("Raise Ascender", objects)
        except Exception as error:  # noqa: BLE001 - retain native failure and still finalize attempted history
            errors.append(error)
        for owner in glyphs:
            try:
                owner.lastModified = stamp
            except Exception as error:  # noqa: BLE001 - retain native failure and still finalize attempted history
                errors.append(error)
    if errors:
        if attempted:
            raise PartialWriteError(0, errors) from errors[0]
        raise errors[0]


def run(
    work: tuple, validate: Callable, native: Any, qt: Any, deadline: float
) -> dict[str, int]:
    """Preserve original sequential scopes, stopping before later untrusted writes."""
    owners = []
    for glyph, _, jobs, dependants, _, _ in work:
        if jobs:
            for owner in (glyph, *dependants):
                if owner not in owners:
                    owners.append(owner)
    edit_guards.require_history_scope(owners, native=native)
    completed = nodes = 0
    for glyph, layer, jobs, dependants, expected, changed in work:
        check(deadline)
        if jobs:
            try:
                publish(glyph, layer, jobs, dependants, native, qt, deadline)
            except PartialWriteError as error:
                raise PartialWriteError(completed, list(error.errors)) from error
            completed += 1
            nodes += changed
        try:
            validate(expected)
        except Exception as error:
            if completed:
                raise PartialWriteError(completed, [error]) from error
            raise
    return {"occurrences": len(work), "undo_steps": completed, "nodes": nodes}
