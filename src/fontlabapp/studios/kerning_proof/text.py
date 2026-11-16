# this_file: src/fontlabapp/studios/kerning_proof/text.py
# SPDX-License-Identifier: Apache-2.0
"""Retained Scriptmix Text Preview outline renderer for non-current-master kerning.

TMetrics currently cannot kern another master. This supplemental native outline
canvas keeps the original effective-value labels, fitted wrapping and controls.
"""

from typing import Any

from PythonQt import QtCore, QtGui

from fontlabapp.core.scripting import kerning_proof_geometry
from fontlabapp.studios._kerning_ui import get

MARGIN = 18


def parse_text(text: str, package: Any) -> list[str]:
    """Retain original slash tokens and Unicode spacing rather than word-pair parsing."""
    names, i = [], 0
    while i < len(text):
        char = text[i]
        if char == '/':
            j = i + 1
            while j < len(text) and text[j] not in ' /':
                j += 1
            token = text[i + 1:j]
            if token and package.findName(token) is not None:
                names.append(token)
            i = j + (1 if j < len(text) and text[j] == ' ' else 0)
            continue
        glyph = package.findUnicode(ord(char))
        if glyph is not None:
            names.append(glyph.name)
        i += 1
    return names


def outline(layer: Any) -> Any:
    """Read original transformed native contours, including component shapes."""
    path = QtGui.QPainterPath()
    path.setFillRule(QtCore.Qt.WindingFill)
    for shape in layer.shapes:
        part = QtGui.QPainterPath()
        for contour in shape.getContours():
            part.addPath(contour.path())
        path.addPath(shape.transform.map(part))
    return path


class Canvas(QtGui.QWidget):
    """Paint every fitted outline and optional effective-kerning label safely."""

    def __init__(self, owner: Any) -> None:
        QtGui.QWidget.__init__(self, owner.widget)
        self.owner = owner
        self.paint_error: str | None = None
        self.setMinimumHeight(180)

    def paintEvent(self, event: Any) -> None:
        painter = None
        try:
            painter = QtGui.QPainter(self)
            self.draw(painter)
            self.paint_error = None
        except Exception as error:  # noqa: BLE001 - Qt painting cannot propagate
            self.fail(error)
        finally:
            if painter is not None:
                try:
                    painter.end()
                except Exception as error:  # noqa: BLE001 - native painter cleanup
                    self.fail(error)

    def fail(self, error: Exception) -> None:
        self.paint_error = repr(error)
        try:
            self.owner.rows, self.owner.paths = [], {}
            self.owner.tool.say(f'Proof error: {self.paint_error}')
        except Exception:  # noqa: BLE001 - a destroyed owner cannot escape paint
            self.error_hook_failed = True

    def draw(self, painter: Any) -> None:
        owner, palette = self.owner, get(self.palette)
        painter.fillRect(get(self.rect), palette.color(QtGui.QPalette.Base))
        owner.ensure_target()
        if not owner.rows:
            painter.setPen(palette.color(QtGui.QPalette.WindowText))
            painter.drawText(get(self.rect), int(QtCore.Qt.AlignCenter), 'Open a font first.' if owner.tool.package is None else 'Type some text above.')
            return
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        scale = get(owner.size.value) / owner.upm
        values = owner.show_values.isChecked()
        bounds = {name: (path.boundingRect().left(), path.boundingRect().top(),
                         path.boundingRect().right(), path.boundingRect().bottom())
                  for name, path in owner.paths.items()}
        scale, positions = kerning_proof_geometry(owner.rows, bounds, get(self.width) - 2 * MARGIN,
                                                  get(self.height) - 2 * MARGIN, scale,
                                                  owner.ascender, owner.descender, values)
        label_scale = scale / (get(owner.size.value) / owner.upm)
        small = painter.font()
        small.setPointSizeF(max(0.1, max(small.pointSizeF() * 0.8, 8) * label_scale))
        painter.setFont(small)
        for name, left, baseline, kern in positions:
            left, baseline = left + MARGIN, baseline + MARGIN
            if kern and values:
                painter.setPen(palette.color(QtGui.QPalette.Link))
                painter.drawText(QtCore.QRectF(left - 20 * label_scale,
                                              baseline - owner.descender * scale + 2 * label_scale,
                                              40 * label_scale, 16 * label_scale),
                                 int(QtCore.Qt.AlignCenter), f'{kern:g}')
            painter.save()
            painter.translate(left, baseline)
            painter.scale(scale, -scale)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(palette.color(QtGui.QPalette.WindowText)))
            painter.drawPath(owner.paths[name])
            painter.restore()
