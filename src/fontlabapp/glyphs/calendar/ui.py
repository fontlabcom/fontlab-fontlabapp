# this_file: src/fontlabapp/glyphs/calendar/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Own complete calendar controls, captured metadata and read-only date reports."""

import sys
from collections.abc import Callable
from time import monotonic
from types import SimpleNamespace
from typing import Any

from fontlabapp.glyphs.names.ui import NamesDialog, QtCore, QtGui
from fontlabapp.qt.calendars.classic.controls import Controls, value
from fontlabapp.qt.calendars.official.controls import Controls as OfficialControls
from fontlabapp.glyphs.calendar.model import _check, on_day
from fontlabapp.qt.tables.filter.model import Table


class GlyphCalendarDialog(NamesDialog):
    """Refresh the whole observation; a failure removes every displayed result."""

    KEY = "glyph_modification_calendar"

    def __init__(
        self, parent: Any, capture: Callable[..., Table], *, official: bool = False
    ) -> None:
        key = "glyph_modification_calendar_official" if official else self.KEY
        title = (
            "Glyph Modification Calendar — Locale and Formats"
            if official
            else "Glyph Modification Calendar"
        )
        super().__init__(parent, title, key)
        self.KEY, self.official = key, official
        self._capture, self._snapshot = capture, None
        self._closed, self.controls = False, None
        self._disconnect_errors: list[str] = []
        try:
            self.subtitle.setText(
                "Choose a local date to inspect glyph modification times. Refresh reads the current font again. Results are a read-only snapshot."
            )
            controls_type = OfficialControls if official else Controls
            self.controls = controls_type(
                SimpleNamespace(QtCore=QtCore, QtGui=QtGui), self, self._connect
            )
            self.root.addWidget(self.controls.widget)
            self.output = QtGui.QPlainTextEdit(self)
            self.output.setReadOnly(True)
            self.root.addWidget(self.output, 1)
            self.status = QtGui.QLabel()
            self.status.setWordWrap(True)
            self.root.addWidget(self.status)
            buttons = QtGui.QHBoxLayout()
            buttons.addStretch(1)
            self.refresh_button = QtGui.QPushButton("Refresh")
            self.close_button = QtGui.QPushButton("Close")
            for button, slot in (
                (self.refresh_button, self.refresh),
                (self.close_button, self.close),
            ):
                buttons.addWidget(button)
                self._connect(button.clicked, lambda *args, action=slot: action())
            self.root.addLayout(buttons)
            self._connect(
                self.controls.calendar.selectionChanged, lambda *args: self._update()
            )
            self._completion_lifetime.on_destroyed.append(self._dispose)
            if parent is not None:
                self._connect(parent.destroyed, lambda *args: self._dispose())
            self.resize(900, 780)
            self.refresh()
        except BaseException:
            self._dispose()
            self.deleteLater()
            raise

    def invalidate(self) -> None:
        """Clear the captured data and report after any owned callback failure."""
        self._snapshot = None
        if not getattr(self, "_closed", False) and hasattr(self, "output"):
            self.output.clear()

    def refresh(self) -> None:
        if self._closed:
            return
        self.invalidate()
        try:
            deadline = monotonic() + 2.0
            table = self._capture(deadline=deadline)
            if self._closed:
                return
            if not isinstance(table, Table):
                raise TypeError("Capture must return a complete immutable Table.")
            _check(deadline)
            self._snapshot = table
            self._update(deadline=deadline)
        except Exception as error:  # noqa: BLE001 - no partial observation after native/UI failure
            if not self._closed:
                self.invalidate()
                self.status.setText(str(error))

    def _update(self, *, deadline: float | None = None) -> None:
        if self._closed or self._snapshot is None:
            return
        try:
            limit = monotonic() + 2.0 if deadline is None else deadline
            day = value(self.controls.calendar, "selectedDate").toString("yyyy-MM-dd")
            snapshot = self._snapshot
            selected = on_day(snapshot, str(day), deadline=limit)
            if self._closed:
                return
            text = "\n".join(
                f"{name} — {codes or 'Not encoded'} — {stamp}"
                for name, codes, stamp in selected.rows
            )
            missing = sum(not row[2] for row in snapshot.rows)
            _check(limit)
            self.output.setPlainText(text)
            if self._closed:
                return
            _check(limit)
            self.status.setText(
                f"{day}: {len(selected.rows)} of {len(snapshot.rows)} glyphs; {missing} without a recorded date. Refresh after font changes."
            )
        except Exception as error:  # noqa: BLE001 - discard the full observation, not just one date
            if not self._closed:
                self.invalidate()
                self.status.setText(str(error))

    def _dispose(self) -> None:
        if self._closed:
            return
        self._closed, self._capture, self._snapshot = True, None, None
        if self.controls is not None:
            self.controls.close()
            self.controls = None
        for signal, slot in reversed(self._connections):
            try:
                signal.disconnect(slot)
            except Exception as error:  # noqa: BLE001 - attempt every disconnect after native teardown faults
                self._disconnect_errors.append(str(error))
        self._connections.clear()
        windows = getattr(sys, "_fontlab_samples", {})
        if windows.get(self.KEY) is self:
            windows.pop(self.KEY)

    def closeEvent(self, event: Any) -> None:
        self._dispose()
        super().closeEvent(event)
