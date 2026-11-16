# this_file: src/fontlabapp/studios/layer_manager/_modes.py
# SPDX-License-Identifier: Apache-2.0
"""A tab that holds several absorbed scripts, one per mode.

What: ``ModesPanel`` shows a "Mode" choice and the panel of the chosen
mode below it; the other modes' panels stay built but hidden. Every mode
panel keeps its own controls, dry-run table, status and verb button, and
refreshes with the tab (the mode panels are not separate tab views).
Used by the Backups, Clean-up and Deliver tabs.
"""

from typing import Any

from .._kerning import Tool
from .._kerning_ui import Panel, combo, get, row


class ModesPanel(Panel):
    """Subclasses set ``MODES``: ``((mode title, panel class), ...)``."""

    MODES: tuple[tuple[str, type], ...] = ()

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.mode = row(
            self.widget,
            self.layout,
            "Mode",
            combo(self.widget, [t for t, _ in self.MODES], self.switch),
        )
        self.panels = []
        for _, kind in self.MODES:
            panel = kind(tool)
            tool.views.remove(panel.reload_view)
            self.layout.addWidget(panel.widget, 1)
            self.panels.append(panel)
        self.switch()

    def current(self) -> Any:
        return self.panels[max(get(self.mode.currentIndex), 0)]

    def switch(self) -> None:
        for panel in self.panels:
            panel.widget.setVisible(panel is self.current())

    def refresh(self) -> None:
        for panel in self.panels:
            panel.reload_view()


__all__ = ["ModesPanel"]
