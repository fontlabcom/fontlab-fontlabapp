# this_file: src/fontlabapp/masters/angles/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Complete staged italic-angle editor on the existing owned Masters lifecycle."""

from contextlib import suppress
from typing import Any

from fontlabapp.masters.angles import model as data
from fontlabapp.masters.angles.views import Gauge
from fontlabapp.masters.inspect.ui import MastersDialog, QtCore, QtGui, make_table


def readable(spin: Any) -> Any:
    """Retain legible original active-theme text in native spin boxes."""
    spin.setStyleSheet(
        f"color: {spin.palette.color(QtGui.QPalette.Active, QtGui.QPalette.WindowText).name()};"
    )
    return spin


def compact(spin: Any, width: int = 150) -> Any:
    """Keep the original compact right-aligned numeric control."""
    spin.setAlignment(QtCore.Qt.AlignRight)
    spin.setMaximumWidth(width)
    return readable(spin)


class ItalicAngleDialog(MastersDialog):
    """Bind source data after Close exists; stale reads clear every actionable value."""

    def build(self) -> None:
        """Build the complete original table, gauge and staging state before reads."""
        self.spins, self.saved, self._spin_connections = {}, {}, []
        self._angle_snapshot, self.last_result = None, None
        self.table = make_table(["Master", "Italic angle"], 120)
        self.root.addWidget(self.table, 1)
        self.gauge = self.chart = Gauge()
        self.gauge.report = self.paint_report
        self.add_proof_view(self.gauge)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(200)
        self.gauge.on_error = self.gauge.report_error

    def load_initial(self) -> None:
        """Capture all master values before constructing any source-dependent row."""
        if self.package is None:
            return
        snapshot = data.capture(self.package)
        self._angle_snapshot = snapshot
        self.current_master = snapshot.current_master
        self.saved = dict(snapshot.angles)
        self.masters = list(self.saved)
        self.table.setRowCount(len(self.masters))
        for row, master in enumerate(self.masters):
            label = QtGui.QTableWidgetItem(
                master + ("  (current)" if master == self.current_master else "")
            )
            label.setForeground(
                QtGui.QBrush(
                    self.palette.color(QtGui.QPalette.Active, QtGui.QPalette.WindowText)
                )
            )
            self.table.setItem(row, 0, label)
            spin = QtGui.QDoubleSpinBox()
            spin.setRange(data.MIN_ANGLE, data.MAX_ANGLE)
            spin.setDecimals(1)
            spin.setSuffix("°")
            spin.setValue(self.saved[master])
            compact(spin, 120)
            self._connect(spin.valueChanged, lambda *a: self.refresh())
            self._spin_connections.append(self._connections[-1])
            self.table.setCellWidget(row, 1, spin)
            self.spins[master] = spin

    def source_values(self, *, cached: bool = False) -> Any:
        """Compare the complete native source; a cached read publishes no new handles."""
        return self._angle_snapshot if cached else data.capture(self.package)

    def edited(self) -> dict[str, float]:
        """Return staged original-order spin values, without touching the font."""
        return {master: spin.value for master, spin in self.spins.items()}

    def refresh(self) -> None:
        """Publish pending values only while the captured source remains exact."""
        try:
            self.prepare_initial()
            self.check_binding()
            if self.package is None:
                self.subtitle.setText("Open a font first.")
                self.apply_button.setEnabled(False)
                return
            if self._snapshot_valid:
                self.ensure_snapshot()
            self._source = self._angle_snapshot
            self._display_masters, self._display_master = (
                tuple(self.masters),
                self.current_master,
            )
            self._snapshot_valid, self._scanned_id = True, self._bound_id
            self.gauge.before_draw = self.ensure_snapshot
            edited = self.edited()
            self.subtitle.setText(
                f"{len(self.masters)} masters · negative angles lean right"
            )
            self.gauge.masters = list(self.masters)
            self.gauge.set_angles([(master, edited[master]) for master in self.masters])
            pending = [
                master
                for master in self.masters
                if edited[master] != self.saved[master]
            ]
            self.apply_button.setEnabled(bool(pending))
            self.status.setText(
                f"{len(pending)} master{'s' if len(pending) != 1 else ''} changed"
                if pending
                else "Edit an angle to change it"
            )
            self.last_error = ""
        except Exception:
            self.invalidate()
            raise

    def apply(self) -> None:
        """Independently preflight the complete source and execute one native batch."""
        try:
            self.ensure_snapshot()
            changed = data.apply(self._angle_snapshot, self.edited())
            self._angle_snapshot = self._source = data.capture(self.package)
            self.saved = dict(self._angle_snapshot.angles)
            self.last_result = {"changed": changed, "angles": dict(self.saved)}
            self.refresh()
            self.status.setText(f"Set the italic angle of {len(changed)} masters")
        except Exception:
            self.invalidate()
            raise

    def invalidate(self) -> None:
        """Disconnect spin callbacks before the table destroys their native widgets."""
        slots = {id(slot) for _, slot in self._spin_connections}
        self._connections = [
            (signal, slot)
            for signal, slot in self._connections
            if id(slot) not in slots
        ]
        for signal, slot in self._spin_connections:
            with suppress(RuntimeError, TypeError, ValueError):
                signal.disconnect(slot)
        self.spins, self.saved, self._spin_connections = {}, {}, []
        self._angle_snapshot = None
        self.last_result = None
        self.gauge.before_draw = None
        self.gauge.set_angles([])
        super().invalidate()

    def teardown(self) -> None:
        """Release the gauge callbacks before native Close destroys owned widgets."""
        self.gauge.report = self.gauge.before_draw = self.gauge.on_error = None
