# this_file: src/fontlabapp/glyphs/unicode/duplicates/native.py
# SPDX-License-Identifier: Apache-2.0
"""Font-owned Unicode removal, precise preflight and one final history batch.

Never call flGlyph.fgGlyph (note-cache loss), UpdateAll (pending updates), clear
native queues or reconstruct glyphs. Full native history/reopen remains pending.
"""

from threading import current_thread, main_thread
from time import monotonic

from fontlabapp import _native
from fontlabapp.glyphs.catalog.native import _context, _stamp
from fontlabapp.glyphs.unicode.duplicates.model import TITLE, Snapshot, plan
from fontlabapp.glyphs.unicode.duplicates.capture import check, read, require_no_editors
from fontlabapp.guides.inspect.model import affected_auto_layers
from fontlabapp.core.scripting import (
    _require_selection_window as require_font_window,
    current_package,
)


class PartialWriteError(RuntimeError):
    """An attempted setter/finalizer failed; changes may require native Undo."""

    def __init__(
        self, changed: list[str], attempted: int, errors: list[Exception]
    ) -> None:
        """Record confirmed glyphs, attempted setter count and all finalizer errors."""
        self.changed, self.attempted = tuple(changed), attempted
        self.errors = tuple(str(error) for error in errors)
        super().__init__(
            f"Edit failed after {attempted} attempted glyphs ({len(changed)} confirmed). Native changes may remain; use Edit > Undo and inspect the font. "
            + "; ".join(self.errors)
        )


class Backend:
    """Rescan explicitly binds the current whole font; Apply requires exact facts."""

    def capture(self, *, deadline: float | None = None) -> Snapshot | None:
        """Two complete equal passes fence context/order/codes/dates/dependencies."""
        if current_thread() is not main_thread():
            raise RuntimeError("Use this editor on the main UI thread.")
        limit = monotonic() + 2.0 if deadline is None else deadline
        check(limit)
        if current_package() is None:
            return None
        a, package, font = _context(limit)
        first = read(package, font, limit, _stamp)
        b, package, font = _context(limit)
        second = read(package, font, limit, _stamp)
        c, _, _ = _context(limit)
        if a != b or b != c or first != second:
            raise ValueError("Font metadata or context changed; rescan.")
        check(limit)
        return Snapshot(a, *first)

    def apply(self, facts: Snapshot, removals: list[tuple[str, int]]) -> dict:
        """Validate all targets before history; preserve every surviving code order."""
        limit = monotonic() + 2.0
        if facts is None or self.capture(deadline=limit) != facts:
            raise ValueError("The preview is stale; rescan before removing codes.")
        jobs = plan(facts, removals)
        if not jobs:
            return {"changed": [], "removals": 0}
        blocked = affected_auto_layers(facts.dependencies, {g.name for g, _ in jobs})
        if blocked:
            raise ValueError(
                "Automatic layers/dependants cannot safely Undo this edit: "
                + ", ".join(blocked)
            )
        native = _native("fontlab")
        if tuple(native.flGlyph.updatedFgGlyphs()):
            raise ValueError(
                "Native glyph updates are pending; finish the current edit before retrying."
            )
        require_font_window(facts.context[0])
        context, package, font = _context(limit)
        records = {int(record.id): record for record in font.glyphs}
        work = []
        for source, remaining in jobs:
            check(limit)
            glyph = package.findFgId(source.fg_id)
            record = records[source.fg_id]
            if (
                int(glyph.id) != source.identity
                or tuple(record.unicodes) != source.codes
            ):
                raise ValueError("Target changed before history; rescan.")
            layers = tuple(glyph.layers)
            if not layers or any(layer.autoLayer for layer in layers):
                raise ValueError("Unicode history requires existing manual layers.")
            work.append((source, glyph, record, layers, remaining))
        if context != facts.context or self.capture(deadline=limit) != facts:
            raise ValueError("Font changed before history; rescan.")
        check(limit)
        if tuple(native.flGlyph.updatedFgGlyphs()):
            raise ValueError(
                "Native glyph updates are pending; retry after the current edit."
            )
        require_font_window(facts.context[0])
        require_no_editors(_native("PythonQt"), limit)
        return write(work, limit)


def write(work: list, deadline: float) -> dict:
    """Initialize before mutation; finalize attempted objects exactly once, even on failure."""
    native = _native("fontlab")
    stamp = _native("PythonQt").QtCore.QDateTime.currentDateTimeUtc()
    for _, glyph, _, layers, _ in work:
        for item in (*layers, glyph):
            check(deadline)
            item.checkInitHistoryState(0)
    changed, attempted, errors, count = [], [], [], 0
    try:
        for source, glyph, record, layers, remaining in work:
            check(deadline)
            attempted.append((glyph, layers))
            record.unicodes = list(remaining)
            if tuple(record.unicodes) != remaining:
                raise RuntimeError(
                    "Native setter did not preserve the exact planned Unicode list."
                )
            changed.append(source.name)
            count += len(source.codes) - len(remaining)
    except Exception as error:  # noqa: BLE001 - preserve attempted writes and finalize
        errors.append(error)
    if attempted:
        for glyph, _ in attempted:
            try:
                glyph.lastModified = stamp
            except Exception as error:  # noqa: BLE001 - still attempt final history
                errors.append(error)
        objects = [layer for _, layers in attempted for layer in layers] + [
            g for g, _ in attempted
        ]
        try:
            native.flItems().notifyChangesApplied(TITLE, objects)
        except Exception as error:  # noqa: BLE001 - never report successful removal
            errors.append(error)
        finally:
            for glyph, _ in attempted:
                try:
                    glyph.lastModified = stamp
                except Exception as error:  # noqa: BLE001 - retain observer errors too
                    errors.append(error)
    if errors:
        if not attempted:
            raise errors[0]
        raise PartialWriteError(changed, len(attempted), errors) from errors[0]
    return {"changed": sorted(changed), "removals": count}
