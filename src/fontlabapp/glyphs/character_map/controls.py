# this_file: src/fontlabapp/glyphs/character_map/controls.py
# SPDX-License-Identifier: Apache-2.0
"""Original reference-face controls plus current-font coverage and Refresh."""

from typing import Any

from fontlabapp.glyphs.character_map.fonts import connect
from fontlabapp.glyphs.character_map.grid import grid_type


def build(panel: Any, core: Any, gui: Any) -> None:
    central = gui.QWidget(panel) if panel.part == 3 else panel
    layout = gui.QVBoxLayout(central)
    panel.setWindowTitle(
        "Glyph Character Map" + (" — Styles" if panel.part == 3 else "")
    )
    panel.setAttribute(core.Qt.WA_QuitOnClose, False)
    panel.setAttribute(core.Qt.WA_DeleteOnClose, False)
    layout.addWidget(
        gui.QLabel(
            "Reference Font — installed face; FontLab coverage is reported separately.",
            central,
        )
    )
    panel.family = gui.QFontComboBox(central)
    panel.style_control = gui.QComboBox(central)
    panel.size_control = (
        gui.QSpinBox(central) if panel.part == 2 else gui.QComboBox(central)
    )
    panel.merging = gui.QCheckBox(
        "Font merging" if panel.part == 2 else "Automatic Font Merging", central
    )
    panel.merging.setChecked(True)
    if panel.part == 2:
        panel.style_control.addItems(["Regular", "Bold", "Italic"])
        panel.size_control.setRange(6, 72)
        panel.size_control.setValue(14)
        for widget in (
            panel.family,
            panel.style_control,
            panel.size_control,
            panel.merging,
        ):
            layout.addWidget(widget)
    else:
        controls = gui.QHBoxLayout()
        for title, widget in (
            ("Font:", panel.family),
            ("Size:", panel.size_control),
            ("Style:", panel.style_control),
        ):
            controls.addWidget(gui.QLabel(title, central))
            controls.addWidget(widget, 1)
        controls.addWidget(panel.merging, 1)
        controls.addStretch(1)
        layout.addLayout(controls)
    panel.text = gui.QLineEdit(central)
    panel.grid = grid_type(core, gui)(panel)
    panel.scroll_area = gui.QScrollArea(central)
    if panel.part == 3:
        panel.grid.resize(panel.grid.sizeHint())
    panel.scroll_area.setWidget(panel.grid)
    panel.copy_button = gui.QPushButton(
        "Copy selected text" if panel.part == 2 else "&To clipboard", central
    )
    if panel.part == 2:
        layout.addWidget(panel.text)
    layout.addWidget(panel.scroll_area, 1)
    if panel.part == 3:
        row = gui.QHBoxLayout()
        row.addWidget(panel.text, 1)
        row.addSpacing(12)
        row.addWidget(panel.copy_button)
        layout.addSpacing(4)
        layout.addLayout(row)
    else:
        layout.addWidget(panel.copy_button)
    panel.status = gui.QLabel("", central)
    panel.status.setWordWrap(True)
    layout.addWidget(
        gui.QLabel(
            "Cell corner: filled blue = covered in FontLab; hollow = missing. Hover for glyph names.",
            central,
        )
    )
    panel.output = gui.QPlainTextEdit(central)
    panel.output.setReadOnly(True)
    panel.output.setMaximumHeight(120)
    layout.addWidget(panel.status)
    layout.addWidget(panel.output)
    row = gui.QHBoxLayout()
    panel.refresh_button = gui.QPushButton("Refresh FontLab coverage", central)
    panel.close_button = gui.QPushButton("Close", central)
    row.addWidget(panel.refresh_button)
    row.addStretch(1)
    row.addWidget(panel.close_button)
    layout.addLayout(row)
    if panel.part == 3:
        panel.setCentralWidget(central)
    else:
        # Coverage controls need room beside the original grid: expose Latin rows.
        panel.resize(640, 700)
    connect(panel, gui)
    panel.scope.connect(panel.text.textChanged, lambda *args: panel.changed())
    panel.scope.connect(panel.copy_button.clicked, lambda *args: panel.copy())
    panel.scope.connect(panel.refresh_button.clicked, lambda *args: panel.refresh())
    panel.scope.connect(
        panel.close_button.clicked,
        lambda *args: panel.close(),
        closing=True,
        retry=True,
    )
