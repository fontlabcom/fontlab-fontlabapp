# this_file: src/fontlabapp/components/graph/elastic/view.py
# SPDX-License-Identifier: Apache-2.0
"""Distinct original view controls, scene caching and background instructions."""

from typing import Any

from fontlabapp.components.graph.elastic.physics import zoom_factor
from fontlabapp.qt.properties import value

MESSAGE = "Click and drag the nodes around, and zoom with the mouse wheel or the '+' and '-' keys"


def view_type(core: Any, gui: Any) -> type:
    """Use explicit native-base dispatch for PythonQt protected virtuals."""

    class View(gui.QGraphicsView):
        def __init__(self, owner: Any, scene: Any) -> None:
            gui.QGraphicsView.__init__(self, scene, owner)
            self.owner, self.timer_id, self.zoom = owner, 0, 1.0
            self.setRenderHint(gui.QPainter.Antialiasing, True)
            if owner.part == 3:
                self.setCacheMode(gui.QGraphicsView.CacheBackground)
                self.setViewportUpdateMode(gui.QGraphicsView.BoundingRectViewportUpdate)
                self.setTransformationAnchor(gui.QGraphicsView.AnchorUnderMouse)
                self.setResizeAnchor(gui.QGraphicsView.AnchorViewCenter)
                self.scale(0.8, 0.8)
                self.zoom = 0.8
                self.setMinimumSize(400, 400)

        def start_motion(self) -> None:
            if not self.owner.closed and not self.timer_id:
                self.timer_id = self.startTimer(40)

        def stop_motion(self) -> None:
            if self.timer_id:
                self.killTimer(self.timer_id)
                self.timer_id = 0

        def timerEvent(self, event: Any) -> None:
            if not self.owner.closed and (
                event is None or event.timerId() == self.timer_id
            ):
                self.owner.tick()

        def magnify(self, *, key: int = 0, wheel: int | None = None) -> None:
            if self.owner.closed:
                return
            factor = zoom_factor(self.owner.part, self.zoom, key=key, wheel=wheel)
            self.scale(factor, factor)
            self.zoom *= factor

        def wheelEvent(self, event: Any) -> None:
            self.magnify(wheel=int(value(event.angleDelta(), "y")))
            event.accept()

        def keyPressEvent(self, event: Any) -> None:
            if self.owner.closed:
                event.ignore()
                return
            key = value(event, "key")
            moves = {
                core.Qt.Key_Left: (-20, 0),
                core.Qt.Key_Right: (20, 0),
                core.Qt.Key_Up: (0, -20),
                core.Qt.Key_Down: (0, 20),
            }
            enter = core.Qt.Key_Return if self.owner.part == 2 else core.Qt.Key_Enter
            plus = (
                (core.Qt.Key_Plus, core.Qt.Key_Equal)
                if self.owner.part == 2
                else (core.Qt.Key_Plus,)
            )
            if key in moves and self.owner.nodes:
                center = self.owner.nodes[min(4, len(self.owner.nodes) - 1)]
                center.moveBy(*moves[key])
                self.owner.moved()
            elif key in (core.Qt.Key_Space, enter):
                self.owner.shuffle()
            elif key in plus or key == core.Qt.Key_Minus:
                self.magnify(key=-1 if key == core.Qt.Key_Minus else 1)
            else:
                gui.QGraphicsView.keyPressEvent(self, event)
                return
            event.accept()

        def drawBackground(self, painter: Any, rect: Any) -> None:
            try:
                if self.owner.part == 2:
                    gui.QGraphicsView.drawBackground(self, painter, rect)
                    return
                area = value(self, "sceneRect")
                right = core.QRectF(area.right(), area.top() + 5, 5, area.height())
                bottom = core.QRectF(area.left() + 5, area.bottom(), area.width(), 5)
                for shadow in (right, bottom):
                    if shadow.intersects(rect) or shadow.contains(rect):
                        painter.fillRect(shadow, gui.QColor(core.Qt.darkGray))
                gradient = gui.QLinearGradient(area.topLeft(), area.bottomRight())
                gradient.setColorAt(0, gui.QColor(core.Qt.white))
                gradient.setColorAt(1, gui.QColor(core.Qt.lightGray))
                painter.fillRect(rect.intersected(area), gui.QBrush(gradient))
                painter.setBrush(gui.QBrush(core.Qt.NoBrush))
                painter.drawRect(area)
                text = core.QRectF(
                    area.left() + 4, area.top() + 4, area.width() - 4, area.height() - 4
                )
                font = value(painter, "font")
                font.setBold(True)
                font.setPointSize(14)
                painter.setFont(font)
                painter.setPen(gui.QColor(core.Qt.lightGray))
                painter.drawText(text.translated(2, 2), MESSAGE)
                painter.setPen(gui.QColor(core.Qt.black))
                painter.drawText(text, MESSAGE)
            except Exception as error:  # noqa: BLE001 - no exception across native paint
                self.owner.failure(error)

    return View
