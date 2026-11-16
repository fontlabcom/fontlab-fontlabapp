# this_file: src/fontlabapp/fontui/preview.py
# SPDX-License-Identifier: Apache-2.0
"""Read-only glyph detail canvas using explicit PythonQt paths."""

from PythonQt import QtCore, QtGui

from fontlabapp.fontui.lifecycle import Owned, follow_changes
from fontlabapp.fontui.model import outline, partition_paths, viewport


class Preview(Owned):
    def __init__(self, font, name=None, parent=None, follow=True):
        super().__init__(parent)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSizeConstraint(QtGui.QLayout.SetMinimumSize)
        self.font, self.name = font, name
        self.zoom = 1.0
        self.options = {
            "fill": True,
            "stroke": True,
            "metrics": True,
            "anchors": False,
            "oncurve": False,
            "offcurve": False,
        }
        self.diagnostic = QtGui.QLabel(self.widget)
        self.layout.addWidget(self.diagnostic)
        toolbar = QtGui.QGridLayout()
        self.layout.addLayout(toolbar)
        self.zoom_control = QtGui.QDoubleSpinBox(self.widget)
        self.zoom_control.setRange(0.05, 20.0)
        self.zoom_control.setValue(1.0)
        self.zoom_control.setAccessibleName("Preview zoom multiplier")
        zoom_row = QtGui.QHBoxLayout()
        toolbar.addLayout(zoom_row, 0, 0, 1, 3)
        zoom_row.addWidget(self.zoom_control)
        self.connect(self.zoom_control.valueChanged, self._zoom)
        self.zoom_buttons = {}
        for text, factor in [("Fit", None), ("−", 0.8), ("+", 1.25)]:
            button = QtGui.QPushButton(text, self.widget)
            self.zoom_buttons[text] = button
            zoom_row.addWidget(button)
            self.connect(
                button.clicked,
                lambda *a, f=factor: self.zoom_control.setValue(
                    1.0 if f is None else self.zoom * f
                ),
            )
        self.option_controls = {}
        for column, (key, enabled) in enumerate(self.options.items()):
            box = QtGui.QCheckBox(key.title(), self.widget)
            self.option_controls[key] = box
            box.setChecked(enabled)
            toolbar.addWidget(box, 1 + column // 3, column % 3)
            self.connect(box.toggled, lambda value, k=key: self.set_option(k, value))
        owner = self

        class Canvas(QtGui.QWidget):
            def paintEvent(self, event):
                owner.paint(self)

            def resizeEvent(self, event):
                QtGui.QWidget.resizeEvent(self, event)
                self.update()

        self.canvas = Canvas(self.widget)
        self.canvas.setMinimumSize(260, 220)
        self.layout.insertWidget(0, self.canvas, 1)
        self.refresh()
        if follow:
            follow_changes(self, self.refresh, lambda: [self.font])

    def _zoom(self, value):
        if self.closed:
            return
        self.zoom = float(value)
        self.canvas.update()

    def set_option(self, key, value):
        if self.closed:
            raise RuntimeError("Preview is closed")
        if key not in self.options:
            raise ValueError(f"Unknown overlay: {key}")
        self.options[key] = bool(value)
        box = self.option_controls[key]
        blocked = box.blockSignals(True)
        try:
            box.setChecked(self.options[key])
        finally:
            box.blockSignals(blocked)
        self.canvas.update()

    def set_glyph(self, name):
        if self.closed:
            raise RuntimeError("Preview is closed")
        self.name = name
        self.refresh()

    def refresh(self):
        if self.closed:
            return
        self.data = None
        try:
            if self.font is None or self.name is None:
                raise ValueError("No glyph selected")
            self.data = outline(self.font, self.name)
            self.diagnostic.setText(self.name)
        except Exception as error:  # noqa: BLE001 - backend/paint boundary retains diagnostic
            self.diagnostic.setText(str(error))
        self.canvas.update()

    def paint(self, canvas):
        from fontTools.pens.qtPen import QtPen
        from fontTools.pens.recordingPen import replayRecording

        painter = QtGui.QPainter(canvas)
        try:
            painter.fillRect(canvas.rect, QtGui.QColor("white"))
            if self.closed or self.data is None:
                return
            # Refresh at paint time so deletion never leaves a stale outline.
            data = outline(self.font, self.name)
            info = self.font.info
            descent = getattr(info, "descender", None)
            ascent = getattr(info, "ascender", None)
            descent = -200 if descent is None else descent
            ascent = 800 if ascent is None else ascent
            scale, dx, dy = viewport(
                data.bounds,
                data.width,
                descent,
                ascent,
                canvas.width,
                canvas.height,
                self.zoom,
            )
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.translate(dx, dy)
            painter.scale(scale, -scale)
            pen = QtGui.QPen(QtGui.QColor("#222222"))
            pen.setWidthF(1 / scale)
            painter.setPen(pen)
            painter.setBrush(
                QtGui.QBrush(QtGui.QColor("#303030"))
                if self.options["fill"]
                else QtGui.QBrush(QtCore.Qt.NoBrush)
            )
            path = QtGui.QPainterPath()
            path.setFillRule(QtCore.Qt.WindingFill)
            closed, opened = partition_paths(data.recording)
            replayRecording(closed, QtPen(None, path=path))
            if not self.options["stroke"]:
                painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
            painter.drawPath(path)
            open_path = QtGui.QPainterPath()
            replayRecording(opened, QtPen(None, path=open_path))
            painter.setBrush(QtGui.QBrush(QtCore.Qt.NoBrush))
            painter.drawPath(open_path)
            if self.options["metrics"]:
                painter.setPen(QtGui.QPen(QtGui.QColor("#8092b0")))
                for y in (0, descent, ascent):
                    painter.drawLine(
                        QtCore.QPointF(0, y), QtCore.QPointF(data.width, y)
                    )
                for x in (0, data.width):
                    painter.drawLine(
                        QtCore.QPointF(x, descent), QtCore.QPointF(x, ascent)
                    )
            painter.setPen(pen)
            painter.setBrush(QtGui.QBrush(QtGui.QColor("#b04040")))
            for operation, points in data.recording:
                for index, point in enumerate(points):
                    if point is None:
                        continue
                    oncurve = index == len(points) - 1
                    if self.options["oncurve" if oncurve else "offcurve"]:
                        painter.drawEllipse(
                            QtCore.QPointF(*point), 3 / scale, 3 / scale
                        )
            if self.options["anchors"]:
                for x, y, name in data.anchors:
                    painter.drawEllipse(QtCore.QPointF(x, y), 5 / scale, 5 / scale)
        except Exception as error:  # noqa: BLE001 - backend/paint boundary retains diagnostic
            self.data = None
            self.diagnostic.setText(str(error))
        finally:
            painter.end()
