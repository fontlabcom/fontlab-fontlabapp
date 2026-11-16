# this_file: src/fontlabapp/metrics/zones/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Complete staged modeless Alignment Zones panel with explicit native I/O.

The panel locks on ``zone_native.STALE_TEXT``, while Suggest Zones From
Overshoots stays usable: this panel's staged rows came from the old snapshot,
so they cannot be applied to the changed font; the user must reopen.
"""

from collections.abc import Callable
from typing import Any

from fontlabapp.metrics.zones import controls as ui
from fontlabapp.glyphs.names.ui import NamesDialog
from fontlabapp.metrics.zones.model import Editor
from fontlabapp.core.history.masters import THREAD_TEXT, WINDOW_TEXT, RolledBackError
from fontlabapp.core.scripting import connect_guarded
from fontlabapp.metrics.zones.editor import KEY, Backend, check_result
from fontlabapp.metrics.zones.native import RowRefusal


def _unchanged(error: ValueError) -> bool:
    """Return True for an Apply error that left the font as it was."""
    if isinstance(error, (RowRefusal, RolledBackError)):
        return True
    return type(error) is ValueError and str(error) in (THREAD_TEXT, WINDOW_TEXT)


class AlignmentZonesDialog(NamesDialog):
    """Keep every master stage, invalid table and owned callback under one owner."""

    KEY = KEY

    def __init__(self, parent: Any = None, *, backend: Backend) -> None:
        """Build complete controls and Close before capturing the bound source."""
        super().__init__(parent, "Alignment Zones", self.KEY)
        self._backend, self.editor = backend, None
        self._closed = self._invalid = self._filling = self._busy = False
        self._disconnect_errors: list[str] = []
        self._terminal_connections = []
        self._current, self._names = "", []
        ui.build(self)
        for signal, slot in (
            (self.master.currentIndexChanged, lambda *a: self.choose()),
            (self.table.itemChanged, lambda *a: self.store()),
            (self.suggest_button.clicked, lambda *a: self.suggest()),
            (self.add_top.clicked, lambda *a: self.add("Top")),
            (self.add_bottom.clicked, lambda *a: self.add("Bottom")),
            (self.remove_button.clicked, lambda *a: self.remove_selected()),
            (self.apply_button.clicked, lambda *a: self.apply()),
            (self.close_button.clicked, lambda *a: self.close()),
        ):
            self._connect(signal, slot)
        self._connect(self.finished, lambda *a: ui.complete(self))
        self._terminal_connections.append(self._connections[-1])
        connect_guarded(
            self, self.destroyed, lambda *a: ui.dispose(self, destroyed=True)
        )
        self._terminal_connections.append(self._connections[-1])
        if parent is not None:
            connect_guarded(self, parent.destroyed, lambda *a: self._dispose())
        try:
            self.editor = Editor(backend.capture())
            backend.check(self.editor.snapshot)
            self._names = [master.name for master in self.editor.snapshot.masters]
            self._current = self.editor.snapshot.current_master
            self._filling = True
            self.master.addItems(self._names)
            self.master.setCurrentIndex(self._names.index(self._current))
            ui.fill(self)
        except Exception as error:  # noqa: BLE001 - retain a diagnosed closable panel
            self._invalid = True
            ui.enabled(self, False)
            self.status.setText(str(error))
        finally:
            self._filling = False

    def _connect(self, signal: Any, slot: Callable[..., Any]) -> None:
        """Contain errors without clearing invalid table text or prior stages."""

        def guarded(*args: Any) -> None:
            """Keep late errors as data after Close, without touching native widgets."""
            if self._closed or self._filling:
                return
            try:
                slot(*args)
            except Exception as error:  # noqa: BLE001 - contain native callback errors
                self.slot_error = repr(error)
                if not self._closed:
                    self.status.setText(str(error))

        connect_guarded(self, signal, guarded)

    def _ready(self) -> bool:
        """Check the bound source before every action and fence reentrant Apply."""
        if self._closed:
            return False
        if self._busy:
            raise ValueError("Zone Apply is already in progress.")
        try:
            if self._invalid or self.editor is None:
                raise ValueError("Reopen this tool to capture a complete source.")
            self._backend.check(self.editor.snapshot)
        except Exception:
            self._invalid = True
            ui.enabled(self, False)
            raise
        return True

    def _stage(self, rows: tuple, origins: tuple) -> None:
        """Keep the current plan intact until every proposed cell validates."""
        try:
            proposed = self.editor.stage(self._current, rows, origins=origins)
        except Exception:
            self.apply_button.setEnabled(False)
            raise
        if proposed != self.editor:
            self.editor = proposed
        ui.status(self)

    def store(self) -> bool:
        """Publish a table only after all cells validate; invalid text remains visible."""
        if not self._ready():
            return False
        self._stage(ui.rows(self.table), self._row_origins)
        return True

    def choose(self) -> None:
        """Retain edits on master switches; refuse leaving an invalid table."""
        try:
            if not self.store():
                return
        except Exception:
            self._filling = True
            try:
                self.master.setCurrentIndex(self._names.index(self._current))
            finally:
                self._filling = False
            raise
        self._current = self._names[ui.value(self.master, "currentIndex")]
        ui.fill(self)

    def add(self, kind: str) -> None:
        """Preserve pending cells before adding the source default zone."""
        if self.store():
            self.editor = self.editor.add(self._current, kind)
            ui.fill(self)

    def remove_selected(self) -> None:
        """Allow removing invalid rows without dropping any unselected data."""
        if not self._ready():
            return
        selected = {
            index.row() for index in self.table.selectionModel().selectedRows(0)
        }
        self._stage(
            tuple(
                row
                for index, row in enumerate(ui.rows(self.table))
                if index not in selected
            ),
            tuple(
                origin
                for index, origin in enumerate(self._row_origins)
                if index not in selected
            ),
        )
        ui.fill(self)

    def suggest(self) -> None:
        """Replace only the chosen stage after checked o/O reads."""
        if not self.store():
            return
        lower, upper = self._backend.bounds(self.editor.snapshot, self._current)
        if self._ready():
            self.editor = self.editor.suggest(self._current, lower, upper)
            ui.fill(self)

    def apply(self) -> None:
        """Send one whole batch; failed/foreign results keep stages for diagnosis.

        A ``RowRefusal``, a ``RolledBackError`` or the GUI-thread or
        Font-window refusal (``font_history.THREAD_TEXT``/``WINDOW_TEXT``,
        raised before any master switch) leaves the font unchanged: show its
        text and keep the panel usable. Every other error (stale source,
        ``UnrestoredError``, a read-back gap, a foreign result) locks the panel.
        """
        if not self.store():
            return
        changes = self.editor.plan()
        if changes:
            self._busy = True
            ui.enabled(self, False)
            try:
                snapshot = self._backend.apply(self.editor.snapshot, changes)
                if self._closed:
                    return
                check_result(self.editor.snapshot, changes, snapshot)
                proposed = Editor(snapshot)
                self._backend.check(snapshot)
                self.editor = proposed
            except ValueError as error:
                if not _unchanged(error):
                    self._invalid = True
                    raise
                # Nothing changed in the font: keep the stages, stay usable.
                if not self._closed:
                    ui.enabled(self, True)
                    ui.fill(self)
                    self.status.setText(str(error))
                return
            except Exception:
                self._invalid = True
                raise
            finally:
                self._busy = False
            ui.enabled(self, True)
            ui.fill(self)
        self.last_result = {"masters": len(changes)}
        self.status.setText(
            f"Wrote the zones of {len(changes)} master{'s' if len(changes) != 1 else ''}"
        )

    def _dispose(self) -> None:
        """Fence retained callbacks and release the adapter before native deletion."""
        ui.dispose(self)

    def closeEvent(self, event: Any) -> None:
        """Disconnect before the shared native Close/deleteLater protocol."""
        self._dispose()
        super().closeEvent(event)
