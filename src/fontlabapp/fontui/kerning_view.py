# this_file: src/fontlabapp/fontui/kerning_view.py
# SPDX-License-Identifier: Apache-2.0
"""Original native composition for the explicit/effective pair editor."""

from typing import Any

from PythonQt import QtGui

from . import glyph_sequence


def build(owner: Any) -> None:
    """Build owned controls, leaving all pair validation/execution to Fontport."""
    owner.filter_control = QtGui.QLineEdit(owner.widget)
    owner.filter_control.setAccessibleName("Filter explicit kerning pairs")
    owner.filter_control.setPlaceholderText("Filter explicit pairs")
    owner.layout.addWidget(owner.filter_control)
    label = QtGui.QLabel("Explicit pairs: left | right | value", owner.widget)
    owner.pair_list = QtGui.QListWidget(owner.widget)
    owner.pair_list.setAccessibleName("Explicit kerning pairs")
    label.setBuddy(owner.pair_list)
    owner.layout.addWidget(label)
    owner.layout.addWidget(owner.pair_list)
    form = QtGui.QFormLayout()
    owner.layout.addLayout(form)
    for attr, text in (
        ("left_control", "&Left glyph or kerning group"),
        ("right_control", "&Right glyph or kerning group"),
        ("value_control", "Kerning &value"),
    ):
        control = QtGui.QLineEdit(owner.widget)
        control.setMaxLength(2147483647)
        control.setAccessibleName(text.replace("&", ""))
        caption = QtGui.QLabel(text, owner.widget)
        caption.setBuddy(control)
        form.addRow(caption, control)
        setattr(owner, attr, control)
    actions = QtGui.QHBoxLayout()
    owner.layout.addLayout(actions)
    owner.apply_button = QtGui.QPushButton("&Apply pair", owner.widget)
    owner.delete_button = QtGui.QPushButton("&Delete explicit pair", owner.widget)
    owner.reload_button = QtGui.QPushButton("R&eload", owner.widget)
    for control in (owner.apply_button, owner.delete_button, owner.reload_button):
        actions.addWidget(control)
    owner.diagnostic = QtGui.QLabel(owner.widget)
    owner.diagnostic.setWordWrap(True)
    owner.layout.addWidget(owner.diagnostic)
    owner.preview = glyph_sequence(owner.font, parent=owner.widget)
    owner.preview.mode_control.setCurrentIndex(1)
    owner.layout.addWidget(owner.preview.widget)
    note = QtGui.QLabel(
        "Group preview uses its first member. Toggle Apply kerning to compare.",
        owner.widget,
    )
    note.setWordWrap(True)
    owner.layout.addWidget(note)
