# this_file: tests/test_elastic_panel.py
"""Actual Qt scene/paint/keys/drag/timer events for each distinct elastic profile."""

from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from fontlabapp.components.graph.elastic.ui import panel_type
from fontlabapp.components.graph.elastic.physics import Graph, fixed
from test_spacing_worksheet import APP, GUI, QtCore, QTest, drain, valid


@pytest.fixture(params=[2, 3], ids=["part2", "part3"])
def panel(request):
    state = NS(
        error=None,
        calls=0,
        graph=Graph.from_rows(
            (("A", ()), ("a.alt", ("A", "A", "missing")), ("無", ("a.alt",)))
        ),
    )

    def capture(**kwargs):
        state.calls += 1
        if state.error:
            raise state.error
        return state.graph

    p = panel_type(QtCore, GUI)(None, capture, request.param)
    p.show()
    p.activateWindow()
    drain()
    p.stop()
    yield p, state
    if valid(p):
        p.held = None
        assert p.close()
    drain()


def test_full_font_order_missing_repeated_edges_and_real_paint(panel):
    p, state = panel
    assert p.graph == state.graph and len(p.nodes) == 4 and len(p.edges) == 4
    assert [n.toolTip() for n in p.nodes] == list(state.graph.names)
    assert p.report.isReadOnly() and p.report.toPlainText().count("a.alt → A") == 2
    assert "missing bases" in p.status.text() and not p.last_error
    image = p.grab().toImage()
    assert not image.isNull() and image.width() >= 760
    assert all(n.shape().contains(QtCore.QPointF(0, 0)) for n in p.nodes)
    for item in p.nodes + p.edges:
        assert item.boundingRect().isValid()
    assert p.nodes[0].type() == (
        GUI.QGraphicsEllipseItem().type()
        if p.part == 2
        else GUI.QGraphicsItem.UserType + 1
    )
    assert p.edges[0].type() == (
        GUI.QGraphicsLineItem().type()
        if p.part == 2
        else GUI.QGraphicsItem.UserType + 2
    )


def test_fixed_graph_controls_distinct_initial_positions_and_caching(panel):
    p, _state = panel
    p.mode.setCurrentIndex(1)
    p.stop()
    graph = fixed(p.part)
    assert p.points() == graph.points and p.graph.edges == graph.edges
    assert len(p.nodes) == 9 and len(p.edges) == 12
    assert (p.scene.sceneRect().width(), p.scene.sceneRect().height()) == (
        (600, 500) if p.part == 2 else (400, 400)
    )
    if p.part == 3:
        assert p.scene.itemIndexMethod() == GUI.QGraphicsScene.NoIndex
        assert p.view.cacheMode() == GUI.QGraphicsView.CacheBackground
        assert p.view.transformationAnchor() == GUI.QGraphicsView.AnchorUnderMouse
        assert p.view.resizeAnchor() == GUI.QGraphicsView.AnchorViewCenter
        assert p.view.zoom == 0.8
    else:
        assert p.view.zoom == 1
    before = p.nodes[4].xy()
    QTest.keyClick(p.view, QtCore.Qt.Key_Right)
    p.stop()
    assert p.nodes[4].xy() == (before[0] + 20, before[1])
    QTest.keyClick(p.view, QtCore.Qt.Key_Left)
    QTest.keyClick(p.view, QtCore.Qt.Key_Up)
    QTest.keyClick(p.view, QtCore.Qt.Key_Down)
    p.stop()
    assert p.nodes[4].xy() == before
    QTest.keyClick(p.view, QtCore.Qt.Key_Plus)
    assert p.view.zoom == pytest.approx(
        (1 if p.part == 2 else 0.8) * (1.15 if p.part == 2 else 1.2)
    )
    QTest.keyClick(p.view, QtCore.Qt.Key_Minus)
    assert p.view.zoom == pytest.approx(1 if p.part == 2 else 0.8)
    before = p.points()
    QTest.keyClick(p.view, QtCore.Qt.Key_Space)
    p.stop()
    assert p.points() != before
    if p.part == 3:
        assert all(x == int(x) and y == int(y) for x, y in p.points())
    key = QtCore.Qt.Key_Return if p.part == 2 else QtCore.Qt.Key_Enter
    before = p.points()
    QTest.keyClick(p.view, key)
    p.stop()
    assert p.points() != before
    QTest.keyClick(p.view, QtCore.Qt.Key_X)


def test_wheel_direction_zoom_limits_and_held_node(panel):
    p, _ = panel
    p.mode.setCurrentIndex(1)
    p.stop()
    event = NS(angleDelta=lambda: QtCore.QPoint(0, 120), accept=Mock())
    p.view.wheelEvent(event)
    assert event.accept.called
    assert p.view.zoom == pytest.approx(1.15 if p.part == 2 else 0.8 * 2 ** (-0.5))
    p.view.zoom = 5 if p.part == 2 else 100
    p.view.magnify(key=1)
    assert p.view.zoom == (5 if p.part == 2 else 100)
    p.held = 4
    before = p.nodes[4].xy()
    p.tick()
    assert p.nodes[4].xy() == before
    assert not p.close() and not p.closed and "drag" in p.last_error
    p.refresh()
    assert "drag" in p.last_error
    p.shuffle()
    assert p.nodes[4].xy() == before
    p.held = None


def test_original_zero_y_wheel_and_node_selection_flags_with_native_events(panel):
    p, _ = panel
    p.mode.setCurrentIndex(1)
    p.stop()
    for delta in (QtCore.QPoint(120, 0), QtCore.QPoint(0, 0)):
        before = p.view.zoom
        wheel = GUI.QWheelEvent(
            QtCore.QPointF(30, 30),
            QtCore.QPointF(30, 30),
            QtCore.QPoint(),
            delta,
            QtCore.Qt.NoButton,
            QtCore.Qt.NoModifier,
            QtCore.Qt.NoScrollPhase,
            False,
        )
        APP.sendEvent(p.view.viewport(), wheel)
        assert p.view.zoom == pytest.approx(before / 1.15 if p.part == 2 else before)
    selectable = GUI.QGraphicsItem.ItemIsSelectable
    assert all(bool(n.flags() & selectable) == (p.part == 2) for n in p.nodes)
    # Part3 must not acquire part2's multi-selection drag behavior.
    for node in p.nodes[:2]:
        node.setSelected(True)
    assert [n.isSelected() for n in p.nodes[:2]] == [p.part == 2, p.part == 2]


def test_real_press_drag_close_refusal_release_refresh_and_reopen(panel):
    p, state = panel
    p.mode.setCurrentIndex(1)
    p.stop()
    pos = p.view.mapFromScene(p.nodes[4].pos())
    QTest.mousePress(p.view.viewport(), QtCore.Qt.LeftButton, pos=pos)
    assert p.held == 4
    assert not p.close() and not p.closed
    QTest.mouseMove(p.view.viewport(), pos + QtCore.QPoint(30, 25), delay=10)
    # Offscreen QTest.mouseMove has no pressed-button mask on macOS. Send the
    # actual native viewport event with LeftButton held; the scene dispatches it.
    move = GUI.QMouseEvent(
        QtCore.QEvent.MouseMove,
        QtCore.QPointF(pos + QtCore.QPoint(30, 25)),
        QtCore.Qt.NoButton,
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier,
    )
    APP.sendEvent(p.view.viewport(), move)
    QTest.mouseRelease(
        p.view.viewport(), QtCore.Qt.LeftButton, pos=pos + QtCore.QPoint(30, 25)
    )
    assert p.held is None
    assert p.nodes[4].xy() != (0.0, 0.0), (
        "The real scene drag must move the centre node"
    )
    p.stop()
    p.mode.setCurrentIndex(0)
    p.stop()
    assert p.graph == state.graph
    assert p.close()
    drain()
    assert p.closed and not p.nodes and not p.edges
    again = panel_type(QtCore, GUI)(None, lambda **kwargs: state.graph, p.part)
    assert again.graph == state.graph
    assert again.close()
    drain()


def test_settling_timer_callbacks_errors_stale_refresh_and_empty(panel):
    p, state = panel
    p.publish(Graph(("a",), (), ((0.0, 0.0),)))
    p.tick()
    assert p.settled and not p.timer.isActive() and not p.view.timer_id
    p.shuffle()
    assert p.timer.isActive() if p.part == 2 else p.view.timer_id
    p.stop_button.click()
    assert not p.timer.isActive() and not p.view.timer_id
    p.view.timerEvent(NS(timerId=lambda: -55))
    state.error = ValueError("stale capture")
    p.refresh()
    assert (
        not p.nodes
        and not p.edges
        and p.graph.names == ()
        and p.report.toPlainText() == ""
    )
    assert "stale capture" in p.last_error
    state.error = None
    state.graph = Graph((), (), ())
    p.refresh()
    p.tick()
    assert p.graph.names == () and p.settled and not p.last_error
    p.refresh_button.click()
    assert state.calls >= 3
    p.close_button.click()
    drain()
    ticks = p.ticks
    p.tick()
    p.shuffle()
    p.refresh()
    p.view.magnify(key=1)
    assert p.ticks == ticks and p.closed and not p.scope.records


def test_construction_failure_and_destroyed_disposal(panel, monkeypatch):
    p, _ = panel
    p.held = None
    p.dispose(destroyed=True)
    assert not p.nodes and not p.edges and p.dead and not p.scope.records
    assert not p.terminal.records
    p.deleteLater()
    drain()
    kind = panel_type(QtCore, GUI)
    monkeypatch.setattr(
        GUI, "QPushButton", Mock(side_effect=RuntimeError("build failed"))
    )
    with pytest.raises(RuntimeError, match="build failed"):
        kind(None, lambda **kw: Graph((), (), ()), 2)
    drain()


def test_public_lazy_fly_route_and_thread_guard(monkeypatch):
    from importlib import import_module

    import fontlabapp
    import fontlabapp.components.graph.model as facade
    import fontlabapp.components.graph.elastic.ui as module

    # App intentionally owns a lazy native export named scripting. Import the
    # submodule explicitly, independent of preceding tests' import order.
    scripting = import_module("fontlabapp.core.scripting")

    calls = []
    monkeypatch.setattr(fontlabapp, "_native", lambda n: NS(QtCore=QtCore, QtGui=GUI))
    monkeypatch.setattr(
        module, "panel_type", lambda *args: lambda parent, capture, part: part
    )
    monkeypatch.setattr(
        scripting,
        "show_script_dialog",
        lambda build, key: calls.append((build(None), key)),
    )
    facade.show()
    facade.show_official()
    assert calls == [(2, "component_graph2"), (3, "component_graph3")]
    monkeypatch.setattr(facade, "current_thread", lambda: object())
    with pytest.raises(RuntimeError, match="main UI"):
        facade.show()


def test_native_paint_geometry_and_timer_faults_are_fenced(panel, monkeypatch):
    p, _ = panel
    p.mode.setCurrentIndex(1)
    p.stop()
    node, edge = p.nodes[0], p.edges[0]
    painter = Mock()
    painter.setPen.side_effect = ValueError("paint failed")
    if p.part == 2:
        for base in (GUI.QGraphicsEllipseItem, GUI.QGraphicsLineItem):
            monkeypatch.setattr(
                base, "paint", Mock(side_effect=ValueError("paint failed"))
            )
    node.paint(painter, NS(state=GUI.QStyle.State_Sunken))
    assert "paint failed" in p.last_error
    edge.paint(painter, NS())
    assert "paint failed" in p.last_error
    p.view.drawBackground(painter, p.scene.sceneRect())
    if p.part == 3:
        assert "paint failed" in p.last_error
    original = edge.source.xy()
    edge.source.setPos(*edge.dest.xy())
    assert edge.points is None
    if p.part == 2:
        assert not edge.isVisible() and not edge.arrow.isVisible()
    else:
        rect = edge.boundingRect()
        assert rect.width() == rect.height() == 11
        assert (rect.center().x(), rect.center().y()) == edge.source.xy()
    edge.paint(painter, NS())
    edge.source.setPos(*original)
    edge.adjust()
    node.paint(Mock(), NS(state=GUI.QStyle.State_Sunken))
    monkeypatch.setattr(
        edge, "adjust", Mock(side_effect=RuntimeError("geometry failed"))
    )
    node.setPos(10, 20)
    assert "geometry failed" in p.last_error
    monkeypatch.setattr(p, "points", Mock(side_effect=ValueError("timer failed")))
    p.tick()
    assert (
        "timer failed" in p.last_error
        and not p.timer.isActive()
        and not p.view.timer_id
    )


def test_scene_build_failure_close_retry_and_late_virtuals(panel, monkeypatch):
    p, _ = panel
    import fontlabapp.components.graph.elastic.ui as module

    times = iter([0, 3])
    monkeypatch.setattr(module, "monotonic", lambda: next(times))
    with pytest.raises(TimeoutError, match="construction"):
        p.publish(fixed(p.part))
    assert not p.nodes and not p.edges
    monkeypatch.undo()
    p.refresh()
    p.stop()
    original = p.scope.finish
    monkeypatch.setattr(p.scope, "finish", lambda **kwargs: False)
    assert not p.close() and p.closed
    event = NS(ignore=Mock())
    for call in (
        p.nodes[0].mousePressEvent,
        p.nodes[0].mouseMoveEvent,
        p.nodes[0].mouseReleaseEvent,
        p.view.keyPressEvent,
    ):
        call(event)
    assert event.ignore.call_count == 4
    p.nodes[0].paint(Mock(), NS(state=0))
    p.edges[0].paint(Mock(), NS())
    p.view.timerEvent(None)
    monkeypatch.setattr(p.scope, "finish", original)
    assert p.close()
    drain()


def test_paint_reporting_failure_cannot_escape_native_virtual(panel, monkeypatch):
    p, _ = panel
    monkeypatch.setattr(p, "stop", Mock(side_effect=RuntimeError("stop unavailable")))
    monkeypatch.setattr(
        p.status, "setText", Mock(side_effect=RuntimeError("status unavailable"))
    )
    painter = Mock()
    painter.setPen.side_effect = ValueError("paint failed")
    if p.part == 2:
        monkeypatch.setattr(
            GUI.QGraphicsEllipseItem,
            "paint",
            Mock(side_effect=ValueError("paint failed")),
        )
    p.nodes[0].paint(painter, NS(state=0))
    assert "paint failed" in p.last_error and "stop unavailable" in p.last_error
    assert "status unavailable" in p.last_error


def test_part2_native_ellipse_shape_bounds_default_pen_and_selection_pixels(panel):
    p, _ = panel
    if p.part == 3:
        assert not isinstance(p.nodes[0], GUI.QGraphicsEllipseItem)
        return
    node = p.nodes[0]
    reference = GUI.QGraphicsEllipseItem(-16.0, -16.0, 32.0, 32.0)
    reference.setBrush(GUI.QBrush(GUI.QColor("#e7bb46")))
    reference.setFlag(GUI.QGraphicsItem.ItemIsSelectable, True)
    assert isinstance(node, GUI.QGraphicsEllipseItem)
    assert node.boundingRect() == reference.boundingRect()
    assert node.shape() == reference.shape() and node.pen() == reference.pen()
    assert node.type() == reference.type() and node.zValue() == 0
    edge = p.edges[0]
    assert isinstance(edge, GUI.QGraphicsLineItem)
    assert edge.pen() == GUI.QPen(GUI.QColor("#536579"), 2)
    assert edge.arrow.pen() == GUI.QPen(GUI.QColor("#536579"))
    assert edge.zValue() == -1 and edge.arrow.zValue() == 0

    def render(item, selected):
        image = GUI.QImage(80, 80, GUI.QImage.Format_ARGB32_Premultiplied)
        image.fill(0)
        painter = GUI.QPainter(image)
        try:
            painter.translate(40, 40)
            painter.setRenderHint(GUI.QPainter.Antialiasing, True)
            option = GUI.QStyleOptionGraphicsItem()
            option.state = (
                GUI.QStyle.State_Selected if selected else GUI.QStyle.State_None
            )
            item.setSelected(selected)
            item.paint(painter, option, None)
        finally:
            painter.end()
        return image

    for selected in (False, True):
        assert render(node, selected) == render(reference, selected)
    assert not p.last_error


def test_pythonqt_scene_rect_property_profile_paints_without_getter_call(
    panel, monkeypatch
):
    p, _ = panel
    reads = []

    def rectangle(view):
        reads.append(True)
        return GUI.QGraphicsView.sceneRect(view)

    monkeypatch.setattr(type(p.view), "sceneRect", property(rectangle))
    p.view.resetCachedContent()
    assert not p.grab().toImage().isNull()
    if p.part == 3:
        assert reads, "Exercise the actual part3 background's property getter"
    assert not p.last_error
