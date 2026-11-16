# this_file: src/fontlabapp/components/graph/elastic/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Owned modeless graph panels with complete refresh, simulation and drag lifetime."""

import random
import sys
from time import monotonic
from typing import Any

from fontlabapp.core.signals.scope import Scope
from fontlabapp.components.graph.elastic.items import item_types
from fontlabapp.components.graph.elastic.physics import Graph, fixed, step
from fontlabapp.components.graph.elastic.view import view_type
from fontlabapp.qt.properties import value


def panel_type(core: Any, gui: Any) -> type:
    """Bind generic scene mechanics; caller supplies the whole-font capture."""
    profiles = {part: item_types(core, gui, part) for part in (2, 3)}
    View = view_type(core, gui)

    class ComponentGraph(gui.QWidget):
        def __init__(self, parent: Any, capture: Any, part: int = 2) -> None:
            gui.QWidget.__init__(self, parent, core.Qt.Window | core.Qt.WindowStaysOnTopHint)
            if part not in (2, 3):
                raise ValueError("Choose elastic profile 2 or 3.")
            self.part, self.capture = part, capture
            self.KEY = "component_graph" + str(part)
            self.closed = self.dead = self.building = False
            self.nodes, self.edges, self.held = [], [], None
            self.graph, self.ticks, self.settled = Graph((), (), ()), 0, False
            self.last_error, self.status = "", None
            self.scope, self.terminal = Scope(self.failure), Scope(self.failure)
            self.rng = random.Random()
            try:
                self.terminal.connect(
                    self.destroyed,
                    lambda *args: self.dispose(destroyed=True),
                    closing=True,
                )
                self.build()
                self.refresh()
            except BaseException:
                if self.close() is False:
                    sys.__dict__.setdefault("_fontlab_samples", {})[self.KEY] = self
                    self.show()
                raise

        def build(self) -> None:
            self.setWindowTitle(
                "Component Dependency Graph"
                + (" - Degree Forces" if self.part == 3 else "")
            )
            self.setAttribute(core.Qt.WA_QuitOnClose, False)
            self.resize(760, 560)
            layout = gui.QVBoxLayout(self)
            intro = gui.QLabel(
                "Captured current-master components; arrows retain the original graph profile. Drag/shuffle changes only this local scene. Refresh after font changes. Hover a node for its exact name; report lists directed glyph → base references."
            )
            intro.setWordWrap(True)
            layout.addWidget(intro)
            row = gui.QHBoxLayout()
            self.mode = gui.QComboBox(self)
            self.mode.addItems(["Current Font Components", "Original Nine-node Graph"])
            row.addWidget(self.mode)
            self.scope.connect(
                self.mode.currentIndexChanged, lambda *args: self.refresh()
            )
            for name, text, call in (
                ("refresh_button", "Refresh", self.refresh),
                ("shuffle_button", "Shuffle", self.shuffle),
                ("stop_button", "Stop Motion", self.stop),
                ("close_button", "Close", self.close),
            ):
                button = gui.QPushButton(text, self)
                setattr(self, name, button)
                row.addWidget(button)
                self.scope.connect(
                    button.clicked,
                    lambda *args, call=call: call(),
                    closing=name == "close_button",
                    retry=name == "close_button",
                )
            layout.addLayout(row)
            self.scene = gui.QGraphicsScene(self)
            if self.part == 3:
                self.scene.setItemIndexMethod(gui.QGraphicsScene.NoIndex)
            self.scene.setSceneRect(
                *(
                    (-300.0, -250.0, 600.0, 500.0)
                    if self.part == 2
                    else (-200.0, -200.0, 400.0, 400.0)
                )
            )
            if self.part == 2:
                self.scene.setBackgroundBrush(gui.QBrush(gui.QColor("#e2e7e9")))
            self.view = View(self, self.scene)
            layout.addWidget(self.view)
            self.report = gui.QTextEdit(self)
            self.report.setReadOnly(True)
            self.report.setMaximumHeight(110)
            layout.addWidget(self.report)
            self.status = gui.QLabel()
            self.status.setWordWrap(True)
            layout.addWidget(self.status)
            self.timer = core.QTimer(self)
            self.scope.connect(self.timer.timeout, self.tick)

        def failure(self, error: Exception) -> None:
            """Reporting must never let a second exception escape a native paint."""
            self.last_error = str(error)
            try:
                self.stop()
            except Exception as failure:  # noqa: BLE001 - retain teardown diagnosis
                self.last_error += "; motion stop failed: " + str(failure)
            if not self.dead and self.status is not None:
                try:
                    self.status.setText(self.last_error)
                except Exception as failure:  # noqa: BLE001 - reporting is terminal
                    self.last_error += "; status unavailable: " + str(failure)

        def points(self) -> tuple:
            return tuple(node.xy() for node in self.nodes)

        def clear(self) -> None:
            self.stop()
            for node in self.nodes:
                node.links.clear()
            self.edges.clear()
            self.nodes.clear()
            if hasattr(self, "scene"):
                self.scene.clear()
            self.graph = Graph((), (), ())

        def publish(self, graph: Graph) -> None:
            Node, Edge = profiles[self.part]
            self.clear()
            self.building = True
            try:
                deadline = monotonic() + 2.0
                for i, (name, point) in enumerate(
                    zip(graph.names, graph.points, strict=True)
                ):
                    if monotonic() >= deadline:
                        raise TimeoutError(
                            "Scene construction expired; no partial graph."
                        )
                    node = Node(self, i, name)
                    self.nodes.append(node)
                    self.scene.addItem(node)
                    node.setPos(*point)
                for source, dest in graph.edges:
                    if monotonic() >= deadline:
                        raise TimeoutError(
                            "Scene construction expired; no partial graph."
                        )
                    edge = Edge(self, self.nodes[source], self.nodes[dest])
                    self.edges.append(edge)
                    self.scene.addItem(edge)
                    if edge.arrow is not None:
                        self.scene.addItem(edge.arrow)
                self.graph = graph
                lines = [f"{graph.names[a]} → {graph.names[b]}" for a, b in graph.edges]
                connected = {n for pair in graph.edges for n in pair}
                lines += [
                    f"{name} (isolated)"
                    for i, name in enumerate(graph.names)
                    if i not in connected
                ]
                self.report.setPlainText("\n".join(lines))
            except BaseException:
                self.clear()
                self.report.setPlainText("")
                raise
            finally:
                self.building = False

        def refresh(self) -> None:
            if self.closed:
                return
            if self.held is not None:
                self.failure(RuntimeError("Finish the drag before refreshing."))
                return
            try:
                graph = (
                    fixed(self.part)
                    if value(self.mode, "currentIndex") == 1
                    else self.capture(deadline=monotonic() + 2.0)
                )
                if self.closed:
                    return
                self.publish(graph)
                self.last_error = ""
                self.status.setText(
                    f"{len(graph.names)} nodes; {len(graph.edges)} references; {len(graph.missing)} missing bases. Snapshot only; no font changes."
                )
                self.moved()
            except Exception as error:  # noqa: BLE001 - stale capture cannot remain actionable
                self.clear()
                self.report.setPlainText("")
                self.failure(error)

        def moved(self) -> None:
            if self.closed or self.building:
                return
            self.settled = False
            if self.part == 2:
                self.timer.start(30)
            else:
                self.view.start_motion()

        def stop(self) -> None:
            if self.dead:
                return
            if hasattr(self, "timer"):
                self.timer.stop()
            if hasattr(self, "view"):
                self.view.stop_motion()

        def tick(self) -> None:
            if self.closed:
                return
            try:
                before = self.points()
                after = step(
                    before,
                    self.graph.edges,
                    self.part,
                    self.held,
                    deadline=monotonic() + 0.1,
                )
                self.building = True
                for node, point in zip(self.nodes, after, strict=True):
                    node.setPos(*point)
                self.ticks += 1
                self.settled = (
                    all(
                        abs(a - c) + abs(b - d) < 0.2
                        for (a, b), (c, d) in zip(before, after, strict=True)
                    )
                    if self.part == 2
                    else before == after
                )
                if self.settled:
                    self.stop()
            except Exception as error:  # noqa: BLE001 - owned timer boundary
                self.failure(error)
            finally:
                self.building = False

        def shuffle(self) -> None:
            if self.closed or self.held is not None:
                return
            for node in self.nodes:
                point = (
                    (self.rng.uniform(-220, 220), self.rng.uniform(-180, 180))
                    if self.part == 2
                    else (self.rng.randrange(-150, 150), self.rng.randrange(-150, 150))
                )
                node.setPos(*point)
            self.moved()

        def dispose(self, *, destroyed: bool = False) -> bool:
            if self.held is not None and not destroyed:
                self.failure(RuntimeError("Finish the drag before closing this graph."))
                return False
            self.closed = True
            if not destroyed:
                self.stop()
            self.dead, self.capture = destroyed, None
            if not self.scope.finish(destroyed=destroyed):
                return False
            if not destroyed:
                self.clear()
            else:
                for node in self.nodes:
                    node.links.clear()
                self.nodes.clear()
                self.edges.clear()
                self.terminal.finish(destroyed=True)
            windows = getattr(sys, "_fontlab_samples", {})
            if windows.get(self.KEY) is self:
                windows.pop(self.KEY)
            return True

        def closeEvent(self, event: Any) -> None:
            try:
                if not self.dispose():
                    event.ignore()
                    return
                gui.QWidget.closeEvent(self, event)
                self.deleteLater()
            except Exception as error:  # noqa: BLE001 - native close boundary
                self.failure(error)
                event.ignore()

    return ComponentGraph
