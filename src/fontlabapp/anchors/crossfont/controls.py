# this_file: src/fontlabapp/anchors/crossfont/controls.py
# SPDX-License-Identifier: Apache-2.0
"""All original two-font copy controls with explicit PythonQt property reads."""

from typing import Any

from fontlabapp.anchors.crossfont.model import ALL_MASTERS, Options
from fontlabapp.qt.properties import value


def radios(
    dialog: Any,
    gui: Any,
    layout: Any,
    row: int,
    label: str,
    names: tuple[str, str],
    keys: tuple[str, str],
    checked: int,
) -> None:
    """Own each original independent exclusive radio pair, never merge groups."""
    layout.addWidget(gui.QLabel(label), row, 0)
    group = gui.QButtonGroup(dialog)
    dialog.groups.append(group)
    for index, (name, key) in enumerate(zip(names, keys, strict=True)):
        button = gui.QRadioButton(name)
        setattr(dialog, key, button)
        group.addButton(button, index)
        layout.addWidget(button, row, index + 1)
        button.setChecked(index == checked)


def selectors(dialog: Any, gui: Any, side: str, layout: Any) -> None:
    """Keep separate font and layer refresh actions for both original sides."""
    font, layer = gui.QComboBox(), gui.QComboBox()
    setattr(dialog, side + "_font", font)
    setattr(dialog, side + "_layer", layer)
    layout.addWidget(font, 0, 0, 1, 3)
    for row, kind in ((0, "font"), (1, "layer")):
        button = gui.QPushButton("<<")
        button.setToolTip("Refresh " + kind + " list")
        if kind == "layer":
            button.setMaximumWidth(30)
        setattr(dialog, side + "_" + kind + "_refresh", button)
        layout.addWidget(button, row, 3)
        callback = (
            dialog.refresh_fonts
            if kind == "font"
            else lambda side=side: dialog.refresh_layers(side)
        )
        dialog.signals.connect(
            button.clicked, lambda *args, callback=callback: callback()
        )
    layout.addWidget(
        gui.QLabel("Source Layer:" if side == "source" else "Destination Layer:"), 1, 0
    )
    layout.addWidget(layer, 1, 1, 1, 2)


def build(dialog: Any, core: Any, gui: Any) -> None:
    """Construct every source control, original defaults and useful error output."""
    dialog.groups = []
    outer = gui.QVBoxLayout(dialog)
    source, destination = gui.QGroupBox("Source"), gui.QGroupBox("Destination")
    a, b = gui.QGridLayout(source), gui.QGridLayout(destination)
    selectors(dialog, gui, "source", a)
    selectors(dialog, gui, "destination", b)
    radios(
        dialog,
        gui,
        a,
        2,
        "Copy from:",
        ("All glyphs", "Selected glyphs"),
        ("all_glyphs", "selected_glyphs"),
        0,
    )
    radios(
        dialog,
        gui,
        a,
        3,
        "Which anchors:",
        ("All anchors", "Specific anchors"),
        ("all_anchors", "specific_anchors"),
        0,
    )
    dialog.anchor_names = gui.QLineEdit()
    dialog.anchor_names.setPlaceholderText("Comma separated list of anchors: top, left")
    a.addWidget(gui.QLabel("Anchors list:"), 4, 0)
    a.addWidget(dialog.anchor_names, 4, 1, 1, 3)
    radios(
        dialog,
        gui,
        b,
        2,
        "Location:",
        ("Absolute", "Relative"),
        ("absolute", "relative"),
        0,
    )
    radios(
        dialog,
        gui,
        b,
        3,
        "Handle Collision:",
        ("Overwrite", "Rename"),
        ("overwrite", "rename"),
        1,
    )
    radios(
        dialog,
        gui,
        b,
        4,
        "Collision rename:",
        ("Incoming", "Destination"),
        ("incoming", "rename_destination"),
        1,
    )
    dialog.suffix = gui.QLineEdit(".bak")
    dialog.suffix.setPlaceholderText("Examples: .new, .bak, .1")
    b.addWidget(gui.QLabel("Addon suffix:"), 5, 0)
    b.addWidget(dialog.suffix, 5, 1, 1, 3)
    dialog.italic = gui.QCheckBox("Use italic angle")
    dialog.angle = gui.QSpinBox()
    dialog.angle.setRange(0, 20)
    dialog.angle.setValue(10)
    dialog.angle.setSuffix("°")
    b.addWidget(gui.QLabel("Italic:"), 6, 0)
    b.addWidget(dialog.italic, 6, 1)
    b.addWidget(dialog.angle, 6, 2, 1, 2)
    outer.addWidget(source)
    outer.addWidget(destination)
    outer.addStretch()
    dialog.status = gui.QLabel()
    dialog.status.setWordWrap(True)
    outer.addWidget(dialog.status)
    dialog.details = gui.QPlainTextEdit()
    dialog.details.setReadOnly(True)
    dialog.details.setMaximumHeight(140)
    dialog.details.hide()
    outer.addWidget(dialog.details)
    dialog.copy_button = gui.QPushButton("Copy Anchors")
    outer.addWidget(dialog.copy_button)
    dialog.close_button = gui.QPushButton("Close")
    outer.addWidget(dialog.close_button)
    dialog.signals.connect(dialog.copy_button.clicked, lambda *args: dialog.copy())
    dialog.signals.connect(
        dialog.close_button.clicked,
        lambda *args: dialog.close(),
        closing=True,
        retry=True,
    )
    dialog.setWindowTitle("TR | Copy Anchors 2.3")
    dialog.setGeometry(300, 300, 200, 300)
    dialog.setWindowFlags(core.Qt.Window | core.Qt.WindowStaysOnTopHint)
    dialog.setModal(False)


def options(dialog: Any) -> Options:
    """Read callable or property profiles; isChecked is a captured native method."""
    return Options(
        dialog.relative.isChecked(),
        dialog.italic.isChecked(),
        int(value(dialog.angle, "value")),
        dialog.rename.isChecked(),
        dialog.rename_destination.isChecked(),
        str(value(dialog.suffix, "text")),
        str(value(dialog.anchor_names, "text"))
        if dialog.specific_anchors.isChecked()
        else None,
    )


def reset_layers(combo: Any) -> None:
    """Font Refresh restores exactly the original All-only layer choice."""
    combo.clear()
    combo.addItem(ALL_MASTERS)
