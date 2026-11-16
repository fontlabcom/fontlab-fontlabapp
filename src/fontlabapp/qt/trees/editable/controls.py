# this_file: src/fontlabapp/qt/trees/editable/controls.py
# SPDX-License-Identifier: Apache-2.0
"""Build both original local-menu policies and explicit draft reload controls."""

from typing import Any


def build(panel: Any, qt: Any) -> None:
    g = qt.QtGui
    panel.root = g.QVBoxLayout(panel)
    panel.root.setContentsMargins(20, 18, 20, 16)
    panel.menu_bar = g.QMenuBar(panel)
    panel.menu_bar.setNativeMenuBar(False)
    panel.root.addWidget(panel.menu_bar)
    heading = g.QLabel(
        "Editable Glyph Tree" if panel.official else "Editable Glyph Outline"
    )
    heading.setStyleSheet("font-size: 18px; font-weight: 600;")
    panel.root.addWidget(heading)
    panel.subtitle = g.QLabel(
        "Edit a local glyph-metadata draft. No font data changes. Refresh keeps edited drafts; Reset Draft explicitly loads the current font."
    )
    panel.subtitle.setWordWrap(True)
    panel.root.addWidget(panel.subtitle)
    panel.menu_actions = {}
    if panel.official:
        file_menu, actions_menu = (
            panel.menu_bar.addMenu("&File"),
            panel.menu_bar.addMenu("&Actions"),
        )
    else:
        actions_menu, file_menu = (
            panel.menu_bar.addMenu("Actions"),
            panel.menu_bar.addMenu("File"),
        )

    def action(
        menu: Any, label: str, call: Any, shortcut: str = "", closing: bool = False
    ) -> None:
        item = g.QAction(
            "E&xit" if panel.official and label == "Exit" else label, panel
        )
        menu.addAction(item)
        panel.menu_actions[label] = item
        if shortcut:
            item.setShortcut(g.QKeySequence(shortcut))
        panel.scope.connect(item.triggered, lambda *args: call(), closing=closing)

    action(file_menu, "Exit", panel.close, "Ctrl+Q" if panel.official else "", True)
    entries = (
        [
            ("Insert Row", "sibling", "Ctrl+I, R"),
            ("Insert Column", "column", "Ctrl+I, C"),
            ("Remove Row", "remove", "Ctrl+R, R"),
            ("Remove Column", "remove_column", "Ctrl+R, C"),
            ("Insert Child", "child", "Ctrl+N"),
        ]
        if panel.official
        else [
            ("Add row", "sibling", ""),
            ("Add child", "child", ""),
            ("Remove row", "remove", ""),
            ("Add column", "column", ""),
            ("Remove column", "remove_column", ""),
        ]
    )
    for label, operation, shortcut in entries:
        if panel.official and label in {"Remove Row", "Insert Child"}:
            actions_menu.addSeparator()
        action(
            actions_menu,
            label,
            lambda kind=operation: panel.controller.run(kind),
            shortcut,
        )
    if panel.official:
        panel.scope.connect(
            actions_menu.aboutToShow, lambda *args: panel.controller.update()
        )
    panel.container = g.QVBoxLayout()
    panel.root.addLayout(panel.container, 1)
    panel.selection_status, panel.status = g.QLabel(), g.QLabel()
    for label in (panel.subtitle, panel.selection_status, panel.status):
        label.setTextFormat(qt.QtCore.Qt.PlainText)
    panel.status.setWordWrap(True)
    panel.root.addWidget(panel.selection_status)
    panel.root.addWidget(panel.status)
    buttons = g.QHBoxLayout()
    panel.refresh_button, panel.reset_button, panel.close_button = (
        g.QPushButton("Refresh"),
        g.QPushButton("Reset Draft"),
        g.QPushButton("Close"),
    )
    for button, call in (
        (panel.refresh_button, panel.refresh),
        (panel.reset_button, lambda: panel.refresh(discard=True)),
        (panel.close_button, panel.close),
    ):
        button.setAutoDefault(False)
        button.setDefault(False)
        buttons.addWidget(button)
        panel.scope.connect(
            button.clicked,
            lambda *args, invoke=call: invoke(),
            closing=button is panel.close_button,
            retry=button is panel.close_button,
        )
    panel.root.addLayout(buttons)
