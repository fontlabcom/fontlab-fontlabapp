# this_file: src/fontlabapp/masters/background/clear/controls.py
# SPDX-License-Identifier: Apache-2.0
"""Whole-font ordered background table and explicit complete-object Clear action."""
from time import monotonic
from typing import Any

from fontlabapp.masters.background.clear.model import plan, automatic_dependants
from fontlabapp.masters.background.clear.capture import check


def build(owner: Any, core: Any, gui: Any) -> None:
    """Build all recovery and Close controls before the first native capture."""
    title = "Clear Master Backgrounds" if owner.masters else "Clear All Layer Backgrounds"
    owner.setWindowTitle(title)
    owner.setAttribute(core.Qt.WA_QuitOnClose, False)
    owner.resize(680, 460)
    root = gui.QVBoxLayout(owner)
    description = gui.QLabel("Scan every glyph in the current font. Clear removes each entire background, including its outlines, anchors, guides and other content. "
                            + ("Only declared master layers are included." if owner.masters else "All mapped layer backgrounds are included."))
    description.setWordWrap(True)
    description.setTextFormat(core.Qt.PlainText)
    root.addWidget(description)
    owner.table = gui.QTableWidget(0, 4)
    owner.table.setHorizontalHeaderLabels(["Glyph", "Layer", "Background", "Action"])
    owner.table.setEditTriggers(gui.QAbstractItemView.NoEditTriggers)
    owner.table.setSelectionBehavior(gui.QAbstractItemView.SelectRows)
    owner.table.horizontalHeader().setSectionResizeMode(gui.QHeaderView.Stretch)
    root.addWidget(owner.table, 1)
    owner.status = gui.QLabel()
    owner.status.setTextFormat(core.Qt.PlainText)
    owner.status.setWordWrap(True)
    root.addWidget(owner.status)
    footer = gui.QHBoxLayout()
    footer.addStretch(1)
    owner.refresh_button, owner.close_button, owner.apply_button = (
        gui.QPushButton(label) for label in ("Refresh", "Close", "Clear backgrounds")
    )
    for button in (owner.refresh_button, owner.close_button, owner.apply_button):
        footer.addWidget(button)
    root.addLayout(footer)
    for signal, callback in ((owner.refresh_button.clicked, owner.refresh),
                             (owner.apply_button.clicked, owner.apply)):
        owner.signals.connect(signal, lambda *args, callback=callback: callback())
    owner.signals.connect(owner.close_button.clicked, lambda *args: owner.close(),
                          closing=True, retry=True)


def render(owner: Any, gui: Any) -> None:
    """Render complete detached facts; no partial table can remain actionable."""
    deadline = monotonic() + 2
    owner.table.setRowCount(0)
    owner.apply_button.setEnabled(False)
    if owner.facts is None:
        owner.status.setText("Open a font, then Refresh.")
        return
    removals = plan(owner.facts, owner.masters, deadline)
    check(deadline)
    by_id = {row.identity: row for row in owner.facts.layers}
    owner.table.setRowCount(len(removals))
    for index, item in enumerate(removals):
        check(deadline)
        labels = (item.glyph, ", ".join(by_id[identity].name for identity in item.foreground_ids),
                  item.mask_name, "Remove entire background")
        for column, text in enumerate(labels):
            owner.table.setItem(index, column, gui.QTableWidgetItem(text))
    check(deadline)
    auto = automatic_dependants(owner.facts, {item.glyph for item in removals}, deadline)
    owner.status.setText("Automatic layers/dependants prevent clearing this scan."
                        if auto else f"{len(removals)} backgrounds across {len({item.glyph_id for item in removals})} glyphs.")
    owner.apply_button.setEnabled(bool(removals) and not auto)
