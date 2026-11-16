# this_file: src/fontlabapp/fontui/transform_view.py
# SPDX-License-Identifier: Apache-2.0
"""Original composition and compare canvas for the transform controls."""

from typing import Any

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.qtPen import QtPen
from fontTools.pens.recordingPen import DecomposingRecordingPen, replayRecording
from PythonQt import QtCore, QtGui

from .model import Outline, partition_paths

MATRIX = (
    ("xx", "x scale (xx)"),
    ("xy", "x→y shear (xy)"),
    ("yx", "y→x shear (yx)"),
    ("yy", "y scale (yy)"),
    ("dx", "x offset (dx)"),
    ("dy", "y offset (dy)"),
)
UNAVAILABLE = (
    "Unavailable methods: interpolation toward a bold/compatible master "
    "(Fontport has no interpolation engine) and stem- or topology-preserving "
    "scaling (not implemented). Only affine transforms are offered."
)


def exact_text(value: float) -> str:
    """Shortest text that parses back to the same number (repr round-trips)."""
    value = float(value)
    return str(int(value)) if value.is_integer() and abs(value) < 2**53 else repr(value)


def record(font: Any, glyph: Any) -> Outline:
    """Decompose components against the source font; never edits either glyph."""
    pen = DecomposingRecordingPen(font, skipMissingComponents=False)
    glyph.draw(pen)
    bounds = BoundsPen(None)
    pen.replay(bounds)
    return Outline(tuple(pen.value), bounds.bounds, float(glyph.width or 0), ())


def build(owner: Any) -> None:
    """Create owned controls; Fontport validates every recipe value."""
    form = QtGui.QFormLayout()
    owner.layout.addLayout(form)
    owner.glyph_control = QtGui.QComboBox(owner.widget)
    owner.method_control = QtGui.QComboBox(owner.widget)
    owner.method_control.addItems(["Affine matrix"])
    owner.enabled_control = QtGui.QCheckBox("&Enabled", owner.widget)
    owner.enabled_control.setChecked(True)
    rows = [("&Glyph", owner.glyph_control), ("&Method", owner.method_control)]
    owner.matrix = {}
    for key, text in MATRIX:
        control = QtGui.QLineEdit(owner.widget)
        owner.matrix[key] = control
        rows.append((text, control))
    owner.intensity_slider = QtGui.QSlider(QtCore.Qt.Horizontal, owner.widget)
    owner.intensity_slider.setRange(0, 100)
    owner.intensity_field = QtGui.QLineEdit(owner.widget)
    owner.intensity_field.setToolTip("Exact intensity, 0–100 percent")
    for control in (owner.intensity_slider, owner.intensity_field):
        control.setAccessibleName("Intensity percent")
    intensity = QtGui.QHBoxLayout()
    intensity.addWidget(owner.intensity_slider)
    intensity.addWidget(owner.intensity_field)
    for text, control in rows:
        control.setAccessibleName(text.replace("&", ""))
        caption = QtGui.QLabel(text, owner.widget)
        caption.setBuddy(control)
        form.addRow(caption, control)
    caption = QtGui.QLabel("&Intensity", owner.widget)
    caption.setBuddy(owner.intensity_field)
    form.addRow(caption, intensity)
    form.addRow(owner.enabled_control)
    note = QtGui.QLabel(UNAVAILABLE, owner.widget)
    note.setWordWrap(True)
    owner.layout.addWidget(note)
    buttons = QtGui.QHBoxLayout()
    owner.layout.addLayout(buttons)
    owner.compare_control = QtGui.QCheckBox("&Compare with original", owner.widget)
    owner.compare_control.setChecked(True)
    buttons.addWidget(owner.compare_control)
    owner.buttons = {}
    for key, text in (
        ("reset", "Reset &transform"),
        ("view", "Reset &view"),
        ("zoom", "&Zoom in"),
        ("script", "Show &script"),
        ("save", "Sa&ve settings…"),
        ("load", "&Load settings…"),
    ):
        owner.buttons[key] = QtGui.QPushButton(text, owner.widget)
        buttons.addWidget(owner.buttons[key])
    owner.diagnostic = QtGui.QLabel(owner.widget)
    owner.diagnostic.setWordWrap(True)
    owner.layout.addWidget(owner.diagnostic)

    class Canvas(QtGui.QWidget):
        def paintEvent(self, event: Any) -> None:
            paint(owner, self)

    owner.canvas = Canvas(owner.widget)
    owner.canvas.setMinimumSize(360, 300)
    owner.layout.addWidget(owner.canvas)
    owner.script_view = QtGui.QPlainTextEdit(owner.widget)
    owner.script_view.setReadOnly(True)
    owner.script_view.setAccessibleName("Generated script")
    owner.script_view.hide()
    owner.layout.addWidget(owner.script_view)


def _draw(painter: Any, recording: tuple, colour: str, fill: bool) -> None:
    """Paint closed paths (filled if ``fill``) and open paths (outline only)."""
    closed, opened = partition_paths(recording)
    for part, solid in ((closed, fill), (opened, False)):
        path = QtGui.QPainterPath()
        path.setFillRule(QtCore.Qt.WindingFill)
        replayRecording(part, QtPen(None, path=path))
        painter.setBrush(
            QtGui.QBrush(QtGui.QColor(colour))
            if solid
            else QtGui.QBrush(QtCore.Qt.NoBrush)
        )
        painter.drawPath(path)


def paint(owner: Any, canvas: Any) -> None:
    """Draw the result, and the original on top if Compare is on.

    The body is wrapped in try/except and the painter always ends in
    ``finally``: an exception that leaves a paint event with an active
    QPainter crashes FontLab.
    """
    painter = QtGui.QPainter(canvas)
    try:
        painter.fillRect(canvas.rect, QtGui.QColor("white"))
        if owner.closed or owner.result is None:
            return
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        scale, x, y = owner.view(canvas.width, canvas.height)
        painter.translate(x, y)
        painter.scale(scale, -scale)
        pen = QtGui.QPen(QtGui.QColor("#303030"))
        pen.setWidthF(1 / scale)
        painter.setPen(pen)
        _draw(painter, owner.result.recording, "#303030", True)
        if owner.compare_control.checked:
            pen.setColor(QtGui.QColor("#d04040"))
            painter.setPen(pen)
            _draw(painter, owner.original.recording, "#d04040", False)
    except Exception as error:  # noqa: BLE001 - never let a paint failure escape into Qt
        owner.diagnostic.setText(str(error))
    finally:
        painter.end()
