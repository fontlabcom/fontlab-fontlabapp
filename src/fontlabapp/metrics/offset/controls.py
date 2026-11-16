# this_file: src/fontlabapp/metrics/offset/controls.py
# SPDX-License-Identifier: Apache-2.0
"""All original editors plus captured FontLab spacing preview and owned Close."""

from typing import Any

from fontlabapp.qt.slider.profiles import group, wire


def build(owner: Any, core: Any, gui: Any) -> None:
    owner.setWindowTitle(
        "Glyph Spacing Offset" + (" — Stacked" if owner.part == 3 else "")
    )
    owner.resize(760, 600)
    root = gui.QVBoxLayout(owner)
    root.addWidget(
        gui.QLabel(
            "Preview geometric sidebearings for captured selected layers. Font data is unchanged."
        )
    )
    editors = gui.QGridLayout()
    root.addLayout(editors)
    owner.controls = {}
    for row, (key, label, initial) in enumerate(
        (
            ("minimum", "Minimum offset:", 0),
            ("maximum", "Maximum offset:", 20),
            ("value", "Offset editor:", 5),
        )
    ):
        editor = gui.QSpinBox(owner)
        editor.setRange(-100, 100)
        editor.setSingleStep(1)
        if owner.part == 2:
            editor.setValue(initial)
        owner.controls[key] = editor
        editors.addWidget(gui.QLabel(label), row, 0)
        editors.addWidget(editor, row, 1)
    orientation = gui.QComboBox(owner)
    orientation.addItems(["Horizontal", "Vertical"])
    owner.controls["orientation"] = orientation
    editors.addWidget(orientation, 3, 0, 1, 2)
    for row, key, label in (
        (0, "appearance", "Invert appearance"),
        (1, "keys", "Invert key bindings"),
    ):
        box = gui.QCheckBox(label, owner)
        owner.controls[key] = box
        editors.addWidget(box, row, 2)
    if owner.part == 2:
        owner.groups = (group(owner, core, gui),)
        for control in owner.groups[0]:
            root.addWidget(control)
    else:
        owner.stack = gui.QStackedWidget(owner)
        root.addWidget(owner.stack)
        owner.groups = tuple(
            group(owner, core, gui, direction)
            for direction in (core.Qt.Horizontal, core.Qt.Vertical)
        )
        for title, direction, controls in zip(
            ("Horizontal", "Vertical"),
            (gui.QBoxLayout.TopToBottom, gui.QBoxLayout.LeftToRight),
            owner.groups,
            strict=True,
        ):
            page = gui.QGroupBox(title, owner)
            layout = gui.QBoxLayout(direction, page)
            for control in controls:
                layout.addWidget(control)
            owner.stack.addWidget(page)
    owner.output = gui.QPlainTextEdit(owner)
    owner.output.setReadOnly(True)
    root.addWidget(owner.output, 1)
    owner.status = gui.QLabel("", owner)
    owner.status.setWordWrap(True)
    root.addWidget(owner.status)
    buttons = gui.QHBoxLayout()
    root.addLayout(buttons)
    for key, label, call in (
        ("refresh", "Refresh Selection", owner.refresh),
        ("close", "Close", owner.close),
    ):
        button = gui.QPushButton(label, owner)
        owner.controls[key] = button
        buttons.addWidget(button)
        owner.scope.connect(
            button.clicked,
            lambda *args, call=call: call(),
            closing=key == "close",
            retry=key == "close",
        )
    wire(owner, core)
