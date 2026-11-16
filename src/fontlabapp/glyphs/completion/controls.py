# this_file: src/fontlabapp/glyphs/completion/controls.py
# SPDX-License-Identifier: Apache-2.0
"""Build both original menu policies and draft/Refresh/Close controls."""

from typing import Any


def build(panel: Any, gui: Any) -> None:
    """Compose owned controls; lifecycle and action policy stay on the panel."""
    panel.menu_bar = gui.QMenuBar(panel)
    panel.menu_bar.setNativeMenuBar(False)
    panel.root.addWidget(panel.menu_bar)
    panel.menu_actions: dict[str, Any] = {}
    file_menu = panel.menu_bar.addMenu("File")
    if not panel.official:
        panel._action(file_menu, "New", lambda: panel.controls.widget.clear())
    panel._action(file_menu, "Exit" if panel.official else "Close", panel.close)
    about_menu = panel.menu_bar.addMenu("About")
    if panel.official:
        panel._action(
            about_menu,
            "About",
            lambda: panel.status.setText(
                "Complete glyph-name suggestions with Qt's custom-completer key, focus and popup behavior."
            ),
        )
        panel._action(
            about_menu,
            "About Qt",
            lambda: panel.status.setText(
                "This example uses FontLab’s existing Qt 5.15 runtime."
            ),
        )
        panel.controls.widget.setPlainText(
            "Type a glyph name. Completion starts at three characters; Ctrl+E also completes shorter prefixes."
        )
    else:
        panel._action(about_menu, "Vocabulary", panel._show_vocabulary)
    panel.root.addWidget(panel.controls.widget, 1)
    panel.root.addWidget(panel.status)
    buttons = gui.QHBoxLayout()
    buttons.addStretch(1)
    panel.refresh_button, panel.close_button = (
        gui.QPushButton("Refresh"),
        gui.QPushButton("Close"),
    )
    for button, slot in (
        (panel.refresh_button, panel.refresh),
        (panel.close_button, panel.close),
    ):
        buttons.addWidget(button)
        panel._connect(
            button.clicked,
            lambda *args, call=slot: call(),
            closing=button is panel.close_button,
        )
    panel.root.addLayout(buttons)
