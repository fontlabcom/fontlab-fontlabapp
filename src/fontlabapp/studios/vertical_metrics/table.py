# this_file: src/fontlabapp/studios/vertical_metrics/table.py
# SPDX-License-Identifier: Apache-2.0
"""Metrics table tab: Master Metrics Table (Font Info).

One editable row per master: ascender, descender, x-height and cap height,
read as the writer reads them back (``master_values``). An edited cell is
validated with the original rule (``validate_metrics``: finite 16-bit values,
descender ≤ 0 ≤ x-height ≤ cap height ≤ ascender) and listed in the dry run
("Master · field", "Current", "New"). "Set metrics" writes exactly that list
through the original route-A writer, ``metrics.master_writer.write_master_metrics``,
as one ``Vertical Metrics: set metrics of <masters>`` Undo step; it first
refuses without the Font window (``require_font_window``) and refuses a value
that changed since the preview. Selecting a row shows that master in the
TMetrics preview and draws its edited metrics as five labelled guides with
a shaded x-height band. The Diagram tab draws every master.

The writer changes master metadata only; it never moves glyphs, so a selected
composite and its base cannot be shifted twice (Scriptmix TODO:74 is
disclosed, and the capHeight write is measured natively in T29).
"""

import math
from typing import Any

from PythonQt import QtCore, QtGui

from .._kerning import ERRORS, Tool
from .._kerning_ui import Panel, button, get, label
from . import _shared
from ._shared import MasterTable
from .diagram import Diagram, frame

MASTER_FIELDS = ["ascender", "descender", "xHeight", "capHeight"]
COLUMNS = ["Master", "Ascender", "Descender", "x-height", "Cap height"]
FIELD_LABELS = dict(zip(MASTER_FIELDS, COLUMNS[1:], strict=True))


def validate_metrics(values: list[float]) -> list[float]:
    """Require four finite ordered metrics within signed 16-bit limits."""
    if len(values) != 4 or not all(
        math.isfinite(v) and -32768 <= v <= 32767 for v in values
    ):
        msg = "Use finite metrics between −32768 and 32767."
        raise ValueError(msg)
    asc, desc, xheight, cap = values
    if not desc <= 0 <= xheight <= cap <= asc:
        msg = "Expected descender ≤ 0 ≤ x-height ≤ cap-height ≤ ascender."
        raise ValueError(msg)
    return values


def master_values(package: Any) -> list[tuple[str, list[float]]]:
    """Read all master metrics, as the writer reads them back; restore the master (original)."""
    master_metrics = _shared.backends().master_metrics
    properties = [
        master_metrics.FIELDS[master_metrics.ALIASES.get(key, key)]
        for key in MASTER_FIELDS
    ]
    original = package.master
    result = []
    try:
        for master in package.masters:
            package.setMaster(master, False)
            result.append(
                (master, [float(getattr(package, name)) for name in properties]),
            )
    finally:
        package.setMaster(original, False)
    return result


def write_changes(package: Any, changes: list[tuple], title: str) -> dict[str, Any]:
    """Write the changed values of a validated plan as one Undo step named ``title`` (original).

    ``changes`` holds ``(master, field, previous, value)``. Refuse when a
    previous value differs from the font; write nothing when no value changes.
    """
    found = _shared.backends()
    found.font_history.require_font_window(
        package
    )  # before master_values switches masters
    current = dict(master_values(package))
    request: dict[str, dict[str, float]] = {}
    for master, field, previous, value in changes:
        if (
            master not in current
            or current[master][MASTER_FIELDS.index(field)] != previous
        ):
            msg = f"{master} {field} changed since preview; refresh the tool."
            raise ValueError(msg)
        if value != previous:
            request.setdefault(master, {})[field] = value
    if not request:
        return {"changed": 0}
    result = found.master_metrics.write_master_metrics(package, request, title=title)
    return {
        "changed": sum(len(fields) for fields in request.values()),
        "pending_updates": result.pending_updates,
        "pending_note": result.pending_note,
    }


def plan(
    old: list[tuple[str, list[float]]], rows: list[tuple[str, list[float]]]
) -> list[tuple]:
    """Validate every proposed row (as ``run`` did) and return the changed ``(master, field, previous, value)``."""
    before = dict(old)
    changes = []
    for master, values in rows:
        validate_metrics(values)
        changes.extend(
            (master, key, previous, value)
            for key, previous, value in zip(
                MASTER_FIELDS, before[master], values, strict=False
            )
            if value != previous
        )
    return changes


def number(value: float) -> str:
    return f"{value:g}"


class SelectedDiagram(Diagram):
    """Five metric guides from the selected editable row, using shared paint cleanup."""

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        if self.paint_error:
            self.owner.status.setText(self.paint_error)

    def draw(self, painter: Any, width: Any, height: Any) -> None:
        rows = self.owner.rows()
        if not rows:
            return
        selected = self.owner.grid.selected()
        master, values = rows[selected[0] if selected else 0]
        metrics = dict(zip(MASTER_FIELDS, values, strict=True))
        area = frame(get(width), get(height), [metrics], 1)
        palette = get(self.palette)
        accent = QtGui.QColor(palette.color(QtGui.QPalette.Link))
        band = QtGui.QColor(accent)
        band.setAlpha(40)
        painter.fillRect(QtCore.QRectF(8, area.y(metrics["xHeight"]), get(width) - 16,
                                     area.y(0) - area.y(metrics["xHeight"])), band)
        painter.setPen(palette.color(QtGui.QPalette.WindowText))
        painter.drawText(QtCore.QPointF(8, 16), f"{master} master")
        guides = [("Baseline", 0)] + [(FIELD_LABELS[key], metrics[key]) for key in MASTER_FIELDS]
        for name, units in guides:
            y = area.y(units)
            painter.setPen(accent if name == "Baseline" else palette.color(QtGui.QPalette.Mid))
            painter.drawLine(QtCore.QPointF(8, y), QtCore.QPointF(get(width) - 8, y))
            painter.setPen(palette.color(QtGui.QPalette.WindowText))
            painter.drawText(QtCore.QPointF(8, y - 3), f"{name} {units:g}")


class MetricsTablePanel(Panel):
    """Master Metrics Table."""

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.grid = MasterTable(
            self.widget,
            self.layout,
            COLUMNS,
            editable=(1, 2, 3, 4),
            changed=_shared.keep(self, self.edited),
            chosen=self.show_master,
        )
        label(self.widget, self.layout, "Changes")
        self.dry = MasterTable(
            self.widget, self.layout, ["Master · field", "Current", "New"]
        )
        self.status = label(self.widget, self.layout)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        button(self.widget, buttons, "Refresh", tool.reload)
        self.apply_button = button(
            self.widget, buttons, "Set metrics", lambda: self.run(self.apply)
        )
        self.diagram = SelectedDiagram(self)
        self.layout.addWidget(self.diagram)
        self.values: list[tuple[str, list[float]]] = []
        self.changes: list[tuple] = []

    def clear(self) -> None:
        self.values, self.changes = [], []
        self.grid.set_rows([])
        self.show_plan()

    def refresh(self) -> None:
        tool = self.tool
        self.values, self.changes = [], []
        if tool.package is None:
            self.subtitle.setText("Open a font first.")
        else:
            self.values = master_values(tool.package)
            self.subtitle.setText(f"{_shared.plural(len(self.values), 'master')}: double-click a value to "
                                  "edit it. Expected descender ≤ 0 ≤ x-height ≤ cap height ≤ ascender.")  # fmt: skip
        self.grid.set_rows([(m, *map(number, values)) for m, values in self.values])
        self.show_plan()

    def rows(self) -> list[tuple[str, list[float]]]:
        """The table as ``(master, values)``; a cell that is not a number refuses."""
        found = []
        for number_, (master, _) in enumerate(self.values):
            texts = [self.grid.cell(number_, column) for column in range(1, 5)]
            try:
                found.append((master, [float(text) for text in texts]))
            except ValueError as error:
                raise ValueError(f"{master}: enter numbers only.") from error
        return found

    def edited(self) -> None:
        self.changes = []
        try:
            self.changes = plan(self.values, self.rows())
        finally:
            self.show_plan()

    def show_plan(self) -> None:
        self.dry.set_rows(
            [
                (f"{m} · {FIELD_LABELS[k]}", number(old), number(new))
                for m, k, old, new in self.changes
            ]
        )
        self.status.setText(f"{_shared.plural(len(self.changes), 'metric field')} to change"
                            if self.changes else "Edit a value to change it")  # fmt: skip
        self.apply_button.setEnabled(bool(self.changes))
        self.diagram.update()

    def show_master(self, master: str) -> None:
        self.diagram.update()
        if self.tool.preview is not None and master:
            self.tool.preview.set_layer(master)

    def apply(self) -> None:
        changes = list(self.changes)
        if not changes or self.tool.package is None:
            raise ValueError("Nothing to change.")
        title = _shared.label("set metrics", [c[0] for c in changes])
        try:
            result = write_changes(self.tool.package, changes, title)
        except ERRORS:
            self.changes = []
            self.show_plan()
            raise
        self.last_result = result
        refresh_error = ""
        try:
            self.tool.reload()
        except ERRORS as error:
            refresh_error = f" · Refresh failed: {error}"
        note = f" · {result['pending_note']}" if result.get("pending_note") else ""
        self.tool.say(
            f"{title}. Changed {_shared.plural(result['changed'], 'metric field')}{note}{refresh_error}"
        )


__all__ = [
    "MASTER_FIELDS",
    "MetricsTablePanel",
    "master_values",
    "plan",
    "validate_metrics",
    "write_changes",
]
