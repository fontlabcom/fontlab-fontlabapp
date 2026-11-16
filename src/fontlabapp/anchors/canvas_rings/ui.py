# this_file: src/fontlabapp/anchors/canvas_rings/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Own duplicate-anchor controls on the reviewed RSB foreground lifecycle."""

from importlib import import_module
from typing import Any

from fontlabapp.metrics.canvas_rsb.ui import CanvasRSBDialog
from fontlabapp.glyphs.names.ui import NamesDialog, QtCore, QtGui

TITLE, KEY = "Duplicate Anchor Rings", "canvas_duplicate_anchor_rings"
HANDLES = (5, 8, 12)
api = import_module("fontlabapp.anchors.canvas_rings.model")


class CanvasAnchorRingsDialog(CanvasRSBDialog):
    """Reuse binding, activation, teardown and registry-safe Close from RSB."""

    def __init__(self, parent: Any = None) -> None:
        NamesDialog.__init__(self, parent, TITLE, KEY)
        self.app = self.glyph_view = self.drawing = None
        self._window_slot = None
        self.binding = None
        self.records: api.Snapshot | tuple = ()
        self.paint_error = ""
        self.subtitle.setText(
            "Foreground adaptation · Draws in this Glyph window across all tools. "
            "Choose handle size explicitly; no automatic text/hand-tool suppression. "
            "Does not edit the font."
        )
        self.enabled_box = QtGui.QCheckBox("Enabled")
        self.enabled_box.setChecked(True)
        self.root.addWidget(self.enabled_box)
        form = QtGui.QFormLayout()
        self.handle_size_combo = QtGui.QComboBox()
        self.handle_size_combo.addItems([str(size) for size in HANDLES])
        self.handle_size_combo.setCurrentIndex(1)
        form.addRow("Handle Size", self.handle_size_combo)
        self.root.addLayout(form)
        self.status = QtGui.QLabel()
        self.status.setWordWrap(True)
        self.root.addWidget(self.status)
        self.close_button = QtGui.QPushButton("Close")
        self.root.addWidget(self.close_button)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(250)
        self._connect(self.enabled_box.toggled, lambda *a: self.toggle())
        self._connect(
            self.handle_size_combo.currentIndexChanged, lambda *a: self.refresh()
        )
        self._connect(self.close_button.clicked, lambda *a: self.close())
        self._connect(self.timer.timeout, lambda *a: self.refresh())
        self.toggle()

    def refresh(self) -> None:
        """Publish two agreeing complete snapshots, including zero-ring sources."""
        if not self.enabled_box.isChecked():
            return
        try:
            if self.paint_error:
                raise RuntimeError(self.paint_error)
            index = self.handle_size_combo.currentIndex
            if index not in range(len(HANDLES)):
                raise ValueError("Choose handle size5,8 or12 before enabling.")
            package, window = self.context()
            size = HANDLES[index]
            records = api.capture(window.canvas, package, handle_size=size)
            if records != api.capture(window.canvas, package, handle_size=size):
                raise ValueError("Anchor layout changed during refresh; enable again.")
            self.context()
            if self.drawing is not None:
                self.drawing.raise_if_failed()
            if records != self.records:
                self.records = records
                if self.drawing is not None:
                    self.drawing.refresh()
            count = sum(len(item.rings) for item in records.occurrences)
            self.status.setText(
                f"{package.elidedName} · {package.master} · "
                f"{len(records.occurrences)} glyph occurrences · {count} anchor pairs"
            )
        except Exception as error:  # noqa: BLE001 - native timer/read boundary
            self.fail(error)

    def paint(self, painter: Any) -> None:
        """Paint numeric snapshots only; defer failure teardown until safe refresh."""
        if not self.records:
            return
        try:
            api.paint(painter, self.records)
        except Exception as error:  # noqa: BLE001 - never unwind through native Qt
            self.paint_error = str(error) or type(error).__name__
            self.records = ()
