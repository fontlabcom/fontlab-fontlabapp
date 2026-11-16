# this_file: src/fontlabapp/proof/text_filter/controls.py
# SPDX-License-Identifier: Apache-2.0
"""Responsive owned native controls for the complete Text Simplifier panel."""

from typing import Any

from fontlabapp.glyphs.names.ui import QtCore, QtGui
from fontlabapp.proof.text_filter.model import SavedText


def build(dialog: Any) -> None:
    """Use responsive native layouts with accessible labels and source actions."""
    dialog.resize(660, 520)
    dialog.subtitle.setText(
        "Keep characters from a class such as A-Z or \\s. Simplify proof text for a work-in-progress font."
    )
    split = QtGui.QSplitter(QtCore.Qt.Horizontal)
    for name, label, readonly in (
        ("input_edit", "Input", False),
        ("output_edit", "Output", True),
    ):
        pane = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        edit, heading = QtGui.QPlainTextEdit(), QtGui.QLabel(label)
        edit.setReadOnly(readonly)
        edit.setAccessibleName(label)
        heading.setBuddy(edit)
        layout.addWidget(heading)
        layout.addWidget(edit)
        split.addWidget(pane)
        setattr(dialog, name, edit)
    dialog.root.addWidget(split, 3)
    label = QtGui.QLabel("Character set (regular-expression class)")
    dialog.characters_edit = QtGui.QPlainTextEdit(SavedText().characters)
    dialog.characters_edit.setAccessibleName("Character set")
    dialog.characters_edit.setMaximumHeight(110)
    label.setBuddy(dialog.characters_edit)
    dialog.root.addWidget(label)
    dialog.root.addWidget(dialog.characters_edit)
    dialog.new_tab = QtGui.QCheckBox("Open in a New Tab")
    dialog.root.addWidget(dialog.new_tab)
    dialog.status = QtGui.QLabel("Input and output are saved for the next session.")
    dialog.status.setWordWrap(True)
    dialog.root.addWidget(dialog.status)
    row = QtGui.QHBoxLayout()
    dialog.reset_button = QtGui.QPushButton("Reset")
    dialog.simplify_button = QtGui.QPushButton("Simplify")
    dialog.simplify_button.setDefault(True)
    dialog.close_button = QtGui.QPushButton("Close")
    for button in (dialog.reset_button, dialog.simplify_button, dialog.close_button):
        row.addWidget(button)
    dialog.root.addLayout(row)
    dialog._fill(SavedText())
