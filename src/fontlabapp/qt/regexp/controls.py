# this_file: src/fontlabapp/qt/regexp/controls.py
# SPDX-License-Identifier: Apache-2.0
"""Build the complete pattern laboratory controls with injected native Qt widgets."""

from typing import Any


def build(owner: Any, core: Any, gui: Any) -> None:
    """Retain editable native combo histories and the original four syntax choices."""
    owner.setWindowTitle("Glyph Name Pattern Lab")
    owner.setAttribute(core.Qt.WA_QuitOnClose, False)
    owner.resize(760, 540)
    layout = gui.QVBoxLayout(owner)
    summary = gui.QLabel(
        "Author and test Qt 5 glyph-name patterns. Captured names are a snapshot. "
        "Refresh after font changes. Drafts and results change no font data."
    )
    summary.setWordWrap(True)
    layout.addWidget(summary)
    for name, label, text in (
        ("pattern", "Pattern", r"(s\w+)"),
        ("input", "Test text", "small stones"),
    ):
        edit = gui.QComboBox(owner)
        edit.setEditable(True)
        edit.addItem(text)
        title = gui.QLabel(label)
        title.setBuddy(edit)
        layout.addWidget(title)
        layout.addWidget(edit)
        setattr(owner, name, edit)
        owner.scope.connect(edit.editTextChanged, lambda *args: owner.changed())
    owner.syntax = gui.QComboBox(owner)
    owner.syntax.addItems(
        ["Regular expression", "Regular expression 2", "Wildcard", "Fixed string"]
    )
    layout.addWidget(owner.syntax)
    owner.scope.connect(owner.syntax.currentIndexChanged, lambda *args: owner.changed())
    owner.case = gui.QCheckBox("Case sensitive", owner)
    owner.minimal = gui.QCheckBox("Minimal match", owner)
    for item in (owner.case, owner.minimal):
        layout.addWidget(item)
        owner.scope.connect(item.toggled, lambda *args: owner.changed())
    row = gui.QHBoxLayout()
    owner.glyphs = gui.QComboBox(owner)
    owner.glyphs.setToolTip("Choose a captured glyph name as the local test text.")
    owner.glyphs.setEnabled(False)
    row.addWidget(owner.glyphs)
    owner.refresh_button = gui.QPushButton("Refresh Glyph Names", owner)
    owner.close_button = gui.QPushButton("Close", owner)
    row.addWidget(owner.refresh_button)
    row.addWidget(owner.close_button)
    layout.addLayout(row)
    owner.scope.connect(owner.glyphs.activated, owner.choose)
    owner.scope.connect(owner.refresh_button.clicked, lambda *args: owner.refresh())
    owner.scope.connect(
        owner.close_button.clicked,
        lambda *args: owner.close(),
        closing=True,
        retry=True,
    )
    owner.output = gui.QTextEdit(owner)
    owner.output.setReadOnly(True)
    layout.addWidget(owner.output)
    owner.status = gui.QLabel()
    owner.status.setWordWrap(True)
    layout.addWidget(owner.status)
