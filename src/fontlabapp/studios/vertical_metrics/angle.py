# this_file: src/fontlabapp/studios/vertical_metrics/angle.py
# SPDX-License-Identifier: Apache-2.0
"""Italic angle tab: Italic Angle (Masters).

Refresh captures every master's italic angle (``masters.angles.model.capture``,
an immutable ``AngleSnapshot``). One row per master with an angle box
(−45° to 45°, one decimal; "(current)" marks the current master) and the
original gauge of slanted stems. The status line counts the masters whose
box differs from the snapshot. "Set angles" writes exactly those through
the original writer ``masters.angles.model.apply`` (it refuses a font that is
no longer current or whose angles or masters changed since Refresh, and the
blueScale check, fl#8531) as one ``Vertical Metrics: set italic angle of
<masters>`` Undo step. Native qualification of the writer stays with T29
(Scriptmix TODO:31, App TODO:65).
"""

from typing import Any

from PythonQt import QtGui

from fontlabapp.core.scripting import vertical_metrics_views

from .._kerning import Tool
from .._kerning_ui import Panel, button, get, label, spin
from . import _shared


class AnglePanel(Panel):
    """Italic Angle."""

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.view = QtGui.QTableWidget(0, 2, self.widget)
        self.view.setHorizontalHeaderLabels(["Master", "Italic angle"])
        self.view.setAccessibleName("Italic angles")
        self.view.horizontalHeader().setStretchLastSection(True)
        self.layout.addWidget(self.view, 1)
        self.gauge: Any = None
        self.gauge_layout = self.layout
        self.status = label(self.widget, self.layout)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        button(self.widget, buttons, "Refresh", tool.reload)
        self.apply_button = button(
            self.widget, buttons, "Set angles", lambda: self.run(self.apply)
        )
        self.snapshot: Any = None
        self.spins: dict[str, Any] = {}

    def make_gauge(self) -> None:
        if self.gauge is None:
            self.gauge = vertical_metrics_views().Gauge(self.widget)
            self.gauge.setMinimumHeight(160)
            self.layout.insertWidget(2, self.gauge, 1)

    def clear(self) -> None:
        self.snapshot, self.spins = None, {}
        self.view.setRowCount(0)
        if self.gauge is not None:
            self.gauge.set_angles([])
        self.apply_button.setEnabled(False)

    def refresh(self) -> None:
        self.clear()
        tool = self.tool
        if tool.package is None:
            self.subtitle.setText("Open a font first.")
            self.status.setText("")
            return
        self.make_gauge()
        snapshot = _shared.backends().angles.capture(tool.package)
        found = _shared.backends().angles
        self.view.setRowCount(len(snapshot.angles))
        for number, (master, angle) in enumerate(snapshot.angles):
            current = "  (current)" if master == snapshot.current_master else ""
            self.view.setItem(number, 0, QtGui.QTableWidgetItem(master + current))
            box = spin(self.widget, found.MIN_ANGLE, found.MAX_ANGLE, angle, suffix="°", decimals=1,
                       slot=_shared.keep(self, self.show_plan))  # fmt: skip
            box.setAccessibleName(f"Italic angle of {master}")
            self.view.setCellWidget(number, 1, box)
            self.spins[master] = box
        self.snapshot = snapshot
        self.gauge.masters = [master for master, _ in snapshot.angles]
        self.subtitle.setText(
            f"{_shared.plural(len(snapshot.angles), 'master')} · negative angles lean right"
        )
        self.show_plan()

    def edited(self) -> dict[str, float]:
        return {master: float(get(box.value)) for master, box in self.spins.items()}

    def pending(self) -> list[str]:
        if self.snapshot is None:
            return []
        edited = self.edited()
        return [master for master, old in self.snapshot.angles if edited[master] != old]

    def show_plan(self) -> None:
        edited = self.edited()
        if self.gauge is not None and self.snapshot is not None:
            self.gauge.set_angles(
                [(master, edited[master]) for master, _ in self.snapshot.angles]
            )
        pending = self.pending()
        self.apply_button.setEnabled(bool(pending))
        self.status.setText(f"{_shared.plural(len(pending), 'master')} changed" if pending
                            else "Edit an angle to change it")  # fmt: skip

    def apply(self) -> None:
        pending = self.pending()
        if self.snapshot is None or not pending:
            raise ValueError("Nothing to change.")
        title = _shared.label("set italic angle", pending)
        changed = _shared.backends().angles.apply(
            self.snapshot, self.edited(), undo_name=title
        )
        self.tool.reload()
        self.tool.say(
            f"{title}. Set the italic angle of {_shared.plural(len(changed), 'master')}"
        )


__all__ = ["AnglePanel"]
