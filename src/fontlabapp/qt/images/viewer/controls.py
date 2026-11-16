# this_file: src/fontlabapp/qt/images/viewer/controls.py
# SPDX-License-Identifier: Apache-2.0
"""Keep both complete original menus, action states and shortcut differences."""
from typing import Any


def build(panel: Any, core: Any, gui: Any) -> None:
    part = panel.part
    panel.setWindowTitle("Font Reference Image Viewer" + (" — Bounded Zoom" if part == 3 else ""))
    panel.setAttribute(core.Qt.WA_QuitOnClose, False)
    panel.setAttribute(core.Qt.WA_DeleteOnClose, False)
    central = gui.QWidget(panel) if part == 3 else panel
    layout = gui.QVBoxLayout(central)
    panel.image_label = gui.QLabel(central)
    panel.scroll_area = gui.QScrollArea(central)
    if part == 3:
        panel.image_label.setBackgroundRole(gui.QPalette.Base)
        panel.image_label.setSizePolicy(gui.QSizePolicy.Ignored, gui.QSizePolicy.Ignored)
        panel.image_label.setScaledContents(True)
        panel.scroll_area.setBackgroundRole(gui.QPalette.Dark)
    panel.scroll_area.setWidget(panel.image_label)
    layout.addWidget(panel.scroll_area, 1)
    panel.status = gui.QLabel("Open reference artwork to inspect, zoom and print.", central)
    panel.status.setWordWrap(True)
    layout.addWidget(panel.status)
    if part == 3:
        panel.setCentralWidget(central)
        bar = panel.menuBar()
    else:
        bar = gui.QMenuBar(panel)
        layout.setMenuBar(bar)
    bar.setNativeMenuBar(False)
    definitions = [
        ("File", [("open", "Open", panel.open_file, "Ctrl+O"), ("print", "Print", panel.print_image, "Ctrl+P"), ("exit", "Exit", panel.close, "Ctrl+Q")]),
        ("View", [("zoom_in", "Zoom In (25%)", lambda: panel.zoom(1.25), "Ctrl++"), ("zoom_out", "Zoom Out (25%)", lambda: panel.zoom(.8), "Ctrl+-"), ("normal", "Normal Size", panel.normal, "Ctrl+S"), ("fit", "Fit to Window", panel.toggle_fit, "Ctrl+F")]),
        ("Help", [("about", "About", panel.about, "")]),
    ]
    if part == 3:
        definitions[-1][1].append(("about_qt", "About Qt", lambda: panel.message("About Qt", "Uses FontLab’s existing Qt runtime."), ""))
    for title, rows in definitions:
        menu = bar.addMenu(title)
        for key, text, call, shortcut in rows:
            action = gui.QAction(text, panel)
            panel.commands[key] = action
            if part == 3 and shortcut:
                action.setShortcut(gui.QKeySequence(shortcut))  # PythonQt accepts no str
            action.setCheckable(part == 3 and key == "fit")
            action.setEnabled(key in {"open", "exit", "about", "about_qt"})
            menu.addAction(action)
            owner = panel.closers if key == "exit" else panel.scope
            owner.connect(action.triggered, lambda *args, callback=call: callback(), closing=key == "exit", retry=key == "exit")
    panel.resize(*( (640, 460) if part == 2 else (500, 400) ))
