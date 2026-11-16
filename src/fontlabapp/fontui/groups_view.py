# this_file: src/fontlabapp/fontui/groups_view.py
# SPDX-License-Identifier: Apache-2.0
"""Native widget composition for the original groups editor."""

from typing import Any

from PythonQt import QtGui

from . import glyph_preview


def build(owner: Any) -> None:
    """Populate one Owned handle; no font mutation or model callbacks."""
    lists = QtGui.QHBoxLayout()
    owner.layout.addLayout(lists)
    owner.group_list, owner.member_list = (
        QtGui.QListWidget(owner.widget),
        QtGui.QListWidget(owner.widget),
    )
    owner.group_list.setAccessibleName("Groups")
    owner.member_list.setAccessibleName("Group members")
    owner.member_list.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
    for text, control in (("Groups", owner.group_list), ("Members", owner.member_list)):
        column = QtGui.QVBoxLayout()
        label = QtGui.QLabel(text, owner.widget)
        label.setBuddy(control)
        column.addWidget(label)
        column.addWidget(control)
        lists.addLayout(column)
    owner.name_control, owner.members_control = (
        QtGui.QLineEdit(owner.widget),
        QtGui.QLineEdit(owner.widget),
    )
    for text, control in (
        ("Group &name (add or rename)", owner.name_control),
        ("&Glyph names to add (space separated)", owner.members_control),
    ):
        label = QtGui.QLabel(text, owner.widget)
        label.setBuddy(control)
        control.setAccessibleName(text.replace("&", ""))
        control.setMaxLength(2147483647)
        owner.layout.addWidget(label)
        owner.layout.addWidget(control)
    actions = QtGui.QHBoxLayout()
    owner.layout.addLayout(actions)
    owner.buttons = {}
    for action, label in (
        ("add", "&Add empty group"),
        ("rename", "&Rename"),
        ("delete", "&Delete group"),
        ("add_members", "Add &members"),
        ("remove_members", "Remove &selected"),
    ):
        button = QtGui.QPushButton(label, owner.widget)
        owner.buttons[action] = button
        actions.addWidget(button)
        owner.connect(button.clicked, lambda *args, a=action: owner.edit(a))
    owner.reload_button = QtGui.QPushButton("Re&load", owner.widget)
    actions.addWidget(owner.reload_button)
    owner.diagnostic = QtGui.QLabel(owner.widget)
    owner.diagnostic.setWordWrap(True)
    owner.layout.addWidget(owner.diagnostic)
    owner.preview = glyph_preview(owner.font, parent=owner.widget)
    owner.layout.addWidget(owner.preview.widget)
