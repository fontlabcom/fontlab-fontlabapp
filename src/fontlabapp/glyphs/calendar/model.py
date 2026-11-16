# this_file: src/fontlabapp/glyphs/calendar/model.py
# SPDX-License-Identifier: Apache-2.0
"""Inspect complete captured glyph metadata by local modification calendar day.

The part2 calendar adaptation keeps its locale, limits and text-format controls.
A selected day lists every matching glyph in font order, all Unicode assignments
and its exact captured local timestamp. Refresh reads the current font again.
No font, selection, preference, history, clipboard or file writer is used.
"""

from datetime import date, datetime
from threading import current_thread, main_thread
from time import monotonic
from typing import Any

from fontlabapp.qt.tables.filter.model import Table


def _check(deadline: float) -> None:
    if monotonic() >= deadline:
        raise TimeoutError("Calendar metadata scan expired; no partial result.")


def on_day(table: Table, day: str, *, deadline: float | None = None) -> Table:
    """Return a complete ordered subset for one exact ISO local calendar day.

    Validate every observed timestamp, including nonmatching rows. Missing dates
    do not match. Keep complete scalar cells and optional epoch milliseconds;
    repeated local times at a daylight-saving fold remain separate observations.
    A malformed date or expired budget refuses the whole observation.
    """
    if not isinstance(table, Table):
        raise TypeError("Calendar metadata requires a complete immutable Table.")
    if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
        raise ValueError("Select an exact ISO calendar day.")
    limit = monotonic() + 2.0 if deadline is None else deadline
    _check(limit)
    rows, epochs = [], []
    for index, row in enumerate(table.rows):
        _check(limit)
        stamp = row[2]
        if stamp and (
            len(stamp) != 19
            or datetime.fromisoformat(stamp).isoformat(sep=" ", timespec="seconds")
            != stamp
        ):
            raise ValueError("Unreadable local glyph modification timestamp.")
        if stamp[:10] == day:
            rows.append(row)
            if table.epochs is not None:
                epochs.append(table.epochs[index])
    result = Table(
        table.headers, tuple(rows), tuple(epochs) if table.epochs is not None else None
    )
    _check(limit)
    return result


def _show(official: bool) -> Any:
    """Open either complete calendar policy with its own owned registry handle."""
    if current_thread() is not main_thread():
        raise RuntimeError("Open the glyph calendar on the main UI thread.")
    from fontlabapp.glyphs.calendar.ui import GlyphCalendarDialog
    from fontlabapp.glyphs.catalog.native import capture
    from fontlabapp.core.scripting import show_script_dialog

    if official:
        return show_script_dialog(
            lambda parent: GlyphCalendarDialog(parent, capture, official=True),
            "glyph_modification_calendar_official",
        )
    return show_script_dialog(
        lambda parent: GlyphCalendarDialog(parent, capture),
        "glyph_modification_calendar",
    )


def show() -> Any:
    """Open the complete part2 calendar and a read-only current-font day report."""
    return _show(False)


def show_official() -> Any:
    """Open the distinct complete part3 locales/week/header/date-format workflow."""
    return _show(True)
