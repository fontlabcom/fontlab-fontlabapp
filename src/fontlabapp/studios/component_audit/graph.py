# this_file: src/fontlabapp/studios/component_audit/graph.py
# SPDX-License-Identifier: Apache-2.0
"""Graph tab: the Scriptmix "Component Graph" (Scripts/Components/Component Graph.py).

The original only opened the shared App elastic component graph
(``fontlabapp.components.graph.model.show``): a modeless, movable node graph
of the current master's component dependencies with its own Refresh,
Shuffle, Stop and Close and its own timer lifetime. This tab keeps that
panel unchanged (its read-only and Close policies, App TODO:48) and opens or
raises it with "Open component graph". Read-only: moving nodes moves only a
picture; no history, selection or glyph is touched.
"""

from typing import Any

from .._kerning_ui import button
from ._shared import AuditPanel, backends, hline

INTRO = (
    "A movable graph of the current master: each node is a glyph, each arrow joins a composite "
    "to a glyph it uses as a component. It opens in its own window with Refresh and Close; "
    "press Refresh there after you change components."
)


class GraphPanel(AuditPanel):
    def build_controls(self) -> None:
        buttons = hline(self.layout)
        self.open_button = button(
            self.widget,
            buttons,
            "Open component graph",
            lambda: self.run(self.open_graph),
        )
        self.window: Any = None

    def refresh(self) -> None:
        """Nothing to read here: the graph window captures the font itself."""
        has_font = self.tool.package is not None
        self.subtitle.setText(INTRO if has_font else "Open a font first.")
        self.open_button.setEnabled(has_font)

    def clear_view(self) -> None:
        pass

    def open_graph(self) -> Any:
        self.window = backends().graph.show()
        self.say("Component graph opened")
        return self.window


__all__ = ["INTRO", "GraphPanel"]
