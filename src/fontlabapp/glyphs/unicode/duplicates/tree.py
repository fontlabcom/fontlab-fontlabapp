# this_file: src/fontlabapp/glyphs/unicode/duplicates/tree.py
# SPDX-License-Identifier: Apache-2.0
"""Expanded source-order duplicate groups and their owned native item objects."""

from typing import Any

from fontlabapp.glyphs.unicode.duplicates.model import groups


def populate(qt: Any, tree: Any, facts: Any) -> dict:
    """Build the literal source pair dictionary; Qt tree owns all created items."""
    core, gui = qt.QtCore, qt.QtGui
    items = {}
    tree.blockSignals(True)
    try:
        for group in groups(facts.glyphs) if facts is not None else ():
            char = chr(group.code)
            char = char if char.isprintable() and not char.isspace() else ""
            top = gui.QTreeWidgetItem(
                [f"U+{group.code:04X}  {char}   {len(group.names)} glyphs", ""]
            )
            font = top.font(0)
            font.setBold(True)
            top.setFont(0, font)
            tree.addTopLevelItem(top)
            for name in group.names:
                item = gui.QTreeWidgetItem([name, ""])
                item.setFlags(item.flags() | core.Qt.ItemIsUserCheckable)
                item.setCheckState(
                    0,
                    core.Qt.Unchecked if name == group.keeper else core.Qt.Checked,
                )
                top.addChild(item)
                items[name, group.code] = item
            top.setExpanded(True)
    finally:
        tree.blockSignals(False)
    return items


def update(qt: Any, tree: Any, items: dict, palette: Any) -> None:
    """Refresh the source keep/remove action labels with paired signal blocking."""
    core, gui = qt.QtCore, qt.QtGui
    tree.blockSignals(True)
    try:
        for (_, code), item in items.items():
            checked = item.checkState(0) == core.Qt.Checked
            item.setText(1, f"remove U+{code:04X}" if checked else "keeps it")
            item.setForeground(
                1,
                gui.QBrush(
                    gui.QColor("#d33") if checked else palette.color(gui.QPalette.Link)
                ),
            )
    finally:
        tree.blockSignals(False)


def publish_result(dialog: Any, result: dict) -> None:
    """Rescan after a successful complete removal, then show the original status."""
    dialog.reload()
    dialog.last_result = result
    count = len(result["changed"])
    dialog.status.setText(f"Updated {count} glyph{'s' if count != 1 else ''}")
