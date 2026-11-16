# this_file: src/fontlabapp/fontui/features_view.py
# SPDX-License-Identifier: Apache-2.0
"""Original composition for the staged feature-code editor."""

from typing import Any

from PythonQt import QtGui


def build(owner: Any) -> None:
    """Create owned controls; staging and validation live elsewhere."""
    from PythonQt import QtCore
    from types import SimpleNamespace
    from .feature_source import create_source_input

    row = QtGui.QHBoxLayout()
    owner.layout.addLayout(row)
    caption = QtGui.QLabel("&Block", owner.widget)
    owner.block_control = QtGui.QComboBox(owner.widget)
    owner.block_control.setAccessibleName("Feature block")
    caption.setBuddy(owner.block_control)
    owner.tag_control = QtGui.QLineEdit(owner.widget)
    owner.tag_control.setAccessibleName("New feature tag")
    owner.tag_control.setPlaceholderText("tag, e.g. liga")
    owner.add_button = QtGui.QPushButton("A&dd feature", owner.widget)
    owner.remove_button = QtGui.QPushButton("Re&move feature", owner.widget)
    for item in (
        caption,
        owner.block_control,
        owner.tag_control,
        owner.add_button,
        owner.remove_button,
    ):
        row.addWidget(item)
    owner.text_control = create_source_input(
        SimpleNamespace(QtCore=QtCore, QtGui=QtGui), owner.widget,
        is_closed=lambda: owner.closed,
        on_change=lambda: owner._mark(),
        on_diagnostic=lambda text: owner.diagnostic.setText(text),
    )
    owner.text_control.setAccessibleName("Feature code (stored, not compiled)")
    owner.layout.addWidget(owner.text_control)
    owner.status = QtGui.QLabel(owner.widget)
    owner.layout.addWidget(owner.status)
    actions = QtGui.QHBoxLayout()
    owner.layout.addLayout(actions)
    owner.apply_button = QtGui.QPushButton("&Apply to font", owner.widget)
    owner.revert_button = QtGui.QPushButton("Re&vert to font", owner.widget)
    actions.addWidget(owner.apply_button)
    actions.addWidget(owner.revert_button)
    owner.diagnostic = QtGui.QLabel(owner.widget)
    owner.diagnostic.setWordWrap(True)
    owner.layout.addWidget(owner.diagnostic)
