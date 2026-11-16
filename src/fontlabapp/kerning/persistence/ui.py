# this_file: src/fontlabapp/kerning/persistence/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Nonmodal exact-pair audit on the existing guarded Proof/Names lifecycle."""

import sys
from importlib import import_module
from typing import Any

from fontlabapp.proof.inspect.ui import ProofDialog, QtGui, snapshot_refresh

api = import_module("fontlabapp.kerning.persistence.model")


class KerningPersistenceDialog(ProofDialog):
    """Read-only current/all-master audit; no glyph selection or write actions."""

    TITLE = "Kerning Persistence Audit"
    KEY = "kerning_persistence_audit"

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent, self.TITLE, self.KEY)
        self._closed = False
        self._disconnect_errors = []
        self.rows, self.shown, self.snapshot = (), (), None
        self._result_options = None
        self.setModal(False)
        self.resize(980, 580)
        self.subtitle.setText(
            "FontLab 9.0.9784 VFJ load clips values outside +/-2*UPM. "
            "This read-only check reports explicit pairs, including zero; "
            "it does not guarantee every aspect of persistence."
        )
        controls = QtGui.QHBoxLayout()
        self.scope = QtGui.QComboBox()
        self.scope.addItems(["Current master", "All masters"])
        controls.addWidget(self.scope)
        self.search = QtGui.QLineEdit()
        self.search.setPlaceholderText("Search master, pair, value or reason")
        controls.addWidget(self.search, 1)
        self.refresh_button = QtGui.QPushButton("Refresh")
        controls.addWidget(self.refresh_button)
        self.root.addLayout(controls)
        self.table = self.make_table(
            ["Master", "UPM", "Left", "Right", "Value", "Reason"]
        )
        self.table.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(
            QtGui.QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.root.addWidget(self.table, 1)
        self.add_proof_footer()
        self.status.setWordWrap(True)
        self._connect(self.scope.currentIndexChanged, lambda *args: self.refresh())
        self._connect(self.search.textChanged, lambda *args: self.filter_rows())
        self._connect(self.refresh_button.clicked, lambda *args: self.refresh())
        self._connect(self.close_button.clicked, lambda *args: self.close())
        self._completion_lifetime.on_destroyed.append(self._destroyed)
        if parent is not None:
            self._connect(parent.destroyed, lambda *args: self._destroyed())
        self.initial_refresh()

    def _connect(self, signal: Any, slot: Any) -> None:
        """A retained queued slot must become inert before touching deleted Qt."""

        def live(*args: Any) -> None:
            if not self._closed:
                slot(*args)

        super()._connect(signal, live)

    def _destroyed(self) -> None:
        """Disconnect owned slots before parent/direct deletion reaches children."""
        self._closed = True
        # Qt5 QWidget emits destroyed before deleteChildren (qwidget.cpp:1379/1402).
        # Release PythonQt receivers while these owned child emitters still exist.
        for signal, slot in reversed(tuple(self._connections)):
            try:
                signal.disconnect(slot)
            except Exception as error:  # noqa: BLE001 - never escape a native destructor
                self._disconnect_errors.append(repr(error))
        self._connections.clear()
        self.rows, self.shown, self.snapshot = (), (), None
        self._result_options = None
        self._snapshot_valid, self._scanned_id = False, None
        self.package, self._bound_id = None, None
        windows = getattr(sys, "_fontlab_samples", {})
        if windows.get(self.KEY) is self:
            windows.pop(self.KEY)

    def load_initial(self) -> None:
        """Proof binds the font identity; kerning needs no selection/glyph getters."""

    def refresh(self) -> None:
        """Publish one complete checked source; never bind to a replacement font."""
        if not self._closed:
            self._refresh()

    @snapshot_refresh
    def _refresh(self) -> None:
        """Read only while the owned panel is alive."""
        self.invalidate()
        if self.package is None:
            self.status.setText("Open a font, then reopen this tool.")
            return
        options = self._options()
        snapshot = api.capture(self.package)
        rows = api.report(snapshot, all_masters=options[0] == 1)
        self._publish(snapshot, rows, options)

    def filter_rows(self) -> None:
        """Recheck the complete frozen source before filtering existing results."""
        if self._closed or self.snapshot is None:
            return
        try:
            self.check_binding()
            if self.scope.currentIndex != self._result_options[0]:
                raise ValueError("Audit scope changed; use Refresh.")
            self._publish(self.snapshot, self.rows, self._options())
        except Exception:
            self.invalidate()
            raise

    @staticmethod
    def cells(row: Any) -> tuple[str, ...]:
        """Preserve exact numeric text instead of rounding report values."""
        return tuple(
            str(value)
            for value in (
                row.master,
                row.upm,
                row.left,
                row.right,
                row.value,
                row.reason,
            )
        )

    def _options(self) -> tuple[int, str]:
        return self.scope.currentIndex, self.search.text

    def _publish(self, snapshot: Any, rows: tuple, options: tuple) -> None:
        api.ensure_snapshot(self.package, snapshot)
        query = options[1].casefold().strip()
        shown = tuple(
            row
            for row in rows
            if not query or query in " ".join(self.cells(row)).casefold()
        )
        self.table.setRowCount(0)
        self.table.setRowCount(len(shown))
        for index, row in enumerate(shown):
            for column, text in enumerate(self.cells(row)):
                item = QtGui.QTableWidgetItem(text)
                item.setToolTip(text)
                self.table.setItem(index, column, item)
        self.table.resizeRowsToContents()
        api.ensure_snapshot(self.package, snapshot)
        self.check_binding()
        if self._options() != options:
            raise ValueError("Audit options changed during refresh; use Refresh.")
        self.snapshot, self.rows, self.shown = snapshot, rows, shown
        self._result_options = options
        self._snapshot_valid, self._scanned_id = True, snapshot.package_id
        risk = sum(row.at_risk for row in rows)
        self.status.setText(
            f"{len(rows)} explicit pairs; {risk} at risk; {len(shown)} shown. "
            f"Current master: {snapshot.master}; UPM: {snapshot.upm}. "
            "No changes made."
        )

    def invalidate(self) -> None:
        """Discard every partial/cached row while retaining working Refresh/Close."""
        if self._closed:
            return
        super().invalidate()
        self.rows, self.shown, self.snapshot = (), (), None
        self._result_options = None
        table = getattr(self, "table", None)
        if table is not None:
            table.setRowCount(0)

    def closeEvent(self, event: Any) -> None:
        """Finish owned cleanup once, then ignore already queued actions."""
        if self._closed:
            event.accept()
            return
        super().closeEvent(event)
        self._closed = True
