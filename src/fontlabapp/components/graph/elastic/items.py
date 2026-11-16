# this_file: src/fontlabapp/components/graph/elastic/items.py
# SPDX-License-Identifier: Apache-2.0
"""Injected Qt scene items: original node/edge shapes, directed arrows and drag."""

from typing import Any

from fontlabapp.components.graph.elastic.physics import geometry
from fontlabapp.qt.properties import value


def item_types(core: Any, gui: Any, part: int) -> tuple[type, type]:
    """Declare virtuals lazily; keep Python state only on Python subclasses."""
    edge_base = gui.QGraphicsLineItem if part == 2 else gui.QGraphicsItem
    node_base = gui.QGraphicsEllipseItem if part == 2 else gui.QGraphicsItem

    class Edge(edge_base):
        def __init__(self, owner: Any, source: Any, dest: Any) -> None:
            edge_base.__init__(self)
            self.owner, self.source, self.dest = owner, source, dest
            self.points = None
            self.arrow = None
            if part == 2:
                color = gui.QColor("#536579")
                self.setPen(gui.QPen(color, 2))
                self.arrow = gui.QGraphicsPolygonItem(gui.QPolygonF())
                self.arrow.setPen(gui.QPen(color))
                self.arrow.setBrush(gui.QBrush(color))
            self.setAcceptedMouseButtons(core.Qt.NoButton)
            self.setZValue(-1.0)
            source.links.append(self)
            dest.links.append(self)
            self.adjust()

        def type(self) -> int:
            if part == 2:
                return gui.QGraphicsLineItem.type(self)
            return gui.QGraphicsItem.UserType + 2

        def adjust(self) -> None:
            self.prepareGeometryChange()
            self.points = geometry(self.source.xy(), self.dest.xy(), self.owner.part)
            if self.owner.part == 2:
                self.setVisible(self.points is not None)
                self.arrow.setVisible(self.points is not None)
                if self.points is not None:
                    a, b, arrows = self.points
                    self.setLine(*a, *b)
                    self.arrow.setPolygon(
                        gui.QPolygonF([core.QPointF(*p) for p in arrows[0]])
                    )
            self.update()

        def boundingRect(self) -> Any:
            if part == 2:
                return gui.QGraphicsLineItem.boundingRect(self)
            if self.points is None:
                # The original short part3 edge paints nothing but retains its
                # eleven-unit geometry box around the source point.
                x, y = self.source.xy()
                return core.QRectF(x - 5.5, y - 5.5, 11.0, 11.0)
            a, b, _ = self.points
            extra = 5.5
            return (
                core.QRectF(core.QPointF(*a), core.QPointF(*b))
                .normalized()
                .adjusted(-extra, -extra, extra, extra)
            )

        def paint(self, painter: Any, option: Any, widget: Any = None) -> None:
            try:
                if self.points is None or self.owner.closed:
                    return
                if part == 2:
                    gui.QGraphicsLineItem.paint(self, painter, option, widget)
                    return
                a, b, arrows = self.points
                color = gui.QColor("black")
                painter.setPen(
                    gui.QPen(
                        color,
                        1,
                        core.Qt.SolidLine,
                        core.Qt.RoundCap,
                        core.Qt.RoundJoin,
                    )
                )
                painter.setBrush(gui.QBrush(color))
                painter.drawLine(core.QLineF(core.QPointF(*a), core.QPointF(*b)))
                for triangle in arrows:
                    painter.drawPolygon(
                        gui.QPolygonF([core.QPointF(*p) for p in triangle])
                    )
            except Exception as error:  # noqa: BLE001 - native paint virtual must not escape
                self.owner.failure(error)

    class Node(node_base):
        def __init__(self, owner: Any, index: int, label: str) -> None:
            if part == 2:
                gui.QGraphicsEllipseItem.__init__(self, -16.0, -16.0, 32.0, 32.0)
                self.setBrush(gui.QBrush(gui.QColor("#e7bb46")))
            else:
                gui.QGraphicsItem.__init__(self)
            self.owner, self.index, self.links = owner, index, []
            self.setToolTip(label)
            self.setFlag(gui.QGraphicsItem.ItemIsMovable, True)
            self.setFlag(gui.QGraphicsItem.ItemIsSelectable, owner.part == 2)
            self.setFlag(gui.QGraphicsItem.ItemSendsGeometryChanges, True)
            if owner.part == 3:
                self.setCacheMode(gui.QGraphicsItem.DeviceCoordinateCache)
            if part == 3:
                self.setZValue(1.0)
            self.label = label

        def type(self) -> int:
            if part == 2:
                return gui.QGraphicsEllipseItem.type(self)
            return gui.QGraphicsItem.UserType + 1

        def xy(self) -> tuple[float, float]:
            point = self.pos()
            return float(value(point, "x")), float(value(point, "y"))

        def boundingRect(self) -> Any:
            return (
                gui.QGraphicsEllipseItem.boundingRect(self)
                if part == 2
                else core.QRectF(-12, -12, 25, 25)
            )

        def shape(self) -> Any:
            if part == 2:
                return gui.QGraphicsEllipseItem.shape(self)
            path = gui.QPainterPath()
            path.addEllipse(-10, -10, 20, 20)
            return path

        def paint(self, painter: Any, option: Any, widget: Any = None) -> None:
            try:
                if self.owner.closed:
                    return
                if self.owner.part == 3:
                    painter.setPen(core.Qt.NoPen)
                    painter.setBrush(gui.QBrush(gui.QColor(core.Qt.darkGray)))
                    painter.drawEllipse(-7, -7, 20, 20)
                    gradient = gui.QRadialGradient(-3, -3, 10)
                    if option.state & gui.QStyle.State_Sunken:
                        gradient.setCenter(3, 3)
                        gradient.setFocalPoint(3, 3)
                        gradient.setColorAt(1, gui.QColor(core.Qt.yellow).lighter(120))
                        gradient.setColorAt(
                            0, gui.QColor(core.Qt.darkYellow).lighter(120)
                        )
                    else:
                        gradient.setColorAt(0, gui.QColor(core.Qt.yellow))
                        gradient.setColorAt(1, gui.QColor(core.Qt.darkYellow))
                    painter.setBrush(gui.QBrush(gradient))
                    painter.setPen(gui.QPen(core.Qt.black, 0))
                    painter.drawEllipse(-10, -10, 20, 20)
                else:
                    gui.QGraphicsEllipseItem.paint(self, painter, option, widget)
            except Exception as error:  # noqa: BLE001 - native paint boundary
                self.owner.failure(error)

        def itemChange(self, change: Any, result: Any) -> Any:
            try:
                if (
                    change == gui.QGraphicsItem.ItemPositionHasChanged
                    and not self.owner.closed
                ):
                    for edge in self.links:
                        edge.adjust()
                    self.owner.moved()
            except Exception as error:  # noqa: BLE001 - native geometry boundary
                self.owner.failure(error)
            return gui.QGraphicsItem.itemChange(self, change, result)

        def mousePressEvent(self, event: Any) -> None:
            if self.owner.closed:
                event.ignore()
                return
            self.owner.held = self.index
            self.update()
            node_base.mousePressEvent(self, event)

        def mouseMoveEvent(self, event: Any) -> None:
            if self.owner.closed:
                event.ignore()
                return
            node_base.mouseMoveEvent(self, event)
            self.owner.moved()

        def mouseReleaseEvent(self, event: Any) -> None:
            if self.owner.closed:
                event.ignore()
                return
            node_base.mouseReleaseEvent(self, event)
            self.owner.held = None
            self.update()
            self.owner.moved()

    return Node, Edge
