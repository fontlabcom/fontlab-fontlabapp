# this_file: src/fontlabapp/anchors/duplicates/controls.py
# SPDX-License-Identifier: Apache-2.0
"""Complete original four-column duplicate-anchor UI and explicit refresh."""

from typing import Any

from fontlabapp.anchors.duplicates.model import TITLE, plan, rows
from fontlabapp.guides.inspect.model import affected_auto_layers
from fontlabapp.qt.properties import value


def build(owner: Any, core: Any, gui: Any) -> None:
    """Finish every control and Close before any fallible font capture."""
    owner.setWindowTitle(TITLE)
    owner.setMinimumWidth(580)
    owner.setAttribute(core.Qt.WA_QuitOnClose, False)
    palette = value(owner, "palette")
    for group in (gui.QPalette.Active, gui.QPalette.Inactive):
        base = gui.QColor(palette.color(group, gui.QPalette.Base)).lightness()
        ink = max(
            (
                gui.QColor(palette.color(group, role))
                for role in (gui.QPalette.Text, gui.QPalette.WindowText)
            ),
            key=lambda color: abs(color.lightness() - base),
        )
        palette.setColor(group, gui.QPalette.Text, ink)
    owner.setPalette(palette)
    root = gui.QVBoxLayout(owner)
    root.setContentsMargins(20, 18, 20, 16)
    root.setSpacing(12)
    heading = gui.QLabel(TITLE)
    font = value(heading, "font")
    font.setPointSizeF(font.pointSizeF() * 1.35)
    font.setBold(True)
    heading.setFont(font)
    root.addWidget(heading)
    owner.subtitle = gui.QLabel()
    owner.subtitle.setWordWrap(True)
    owner.subtitle.setTextFormat(core.Qt.PlainText)
    root.addWidget(owner.subtitle)
    bar = gui.QHBoxLayout()
    bar.setSpacing(10)
    owner.scope = gui.QComboBox()
    owner.scope.addItems(
        ["Whole font, all masters", "Selected glyphs (0), all masters"]
    )
    owner.coincident = gui.QCheckBox("Also remove coincident anchors (keep the first)")
    bar.addWidget(owner.scope)
    bar.addStretch(1)
    bar.addWidget(owner.coincident)
    root.addLayout(bar)
    owner.table = gui.QTableWidget(0, 4)
    owner.table.setHorizontalHeaderLabels(
        ["Glyph · master", "Finding", "Anchors", "Fix"]
    )
    owner.table.verticalHeader().setVisible(False)
    owner.table.setEditTriggers(gui.QAbstractItemView.NoEditTriggers)
    owner.table.setSelectionMode(gui.QAbstractItemView.NoSelection)
    owner.table.setAlternatingRowColors(True)
    owner.table.setShowGrid(False)
    owner.table.setWordWrap(False)
    owner.table.horizontalHeader().setSectionResizeMode(gui.QHeaderView.Stretch)
    owner.table.horizontalHeader().setSectionResizeMode(
        0, gui.QHeaderView.ResizeToContents
    )
    owner.table.setHorizontalScrollBarPolicy(core.Qt.ScrollBarAlwaysOff)
    owner.table.setMinimumHeight(260)
    root.addWidget(owner.table, 1)
    owner.warning = gui.QLabel()
    owner.warning.setTextFormat(core.Qt.PlainText)
    owner.warning.setWordWrap(True)
    root.addWidget(owner.warning)
    footer = gui.QHBoxLayout()
    owner.status = gui.QLabel()
    owner.status.setTextFormat(core.Qt.PlainText)
    footer.addWidget(owner.status, 1)
    owner.refresh_button, owner.close_button, owner.apply_button = (
        gui.QPushButton(label) for label in ("Refresh", "Close", "Fix")
    )
    for button in (owner.refresh_button, owner.close_button, owner.apply_button):
        footer.addWidget(button)
    owner.apply_button.setDefault(True)
    root.addLayout(footer)
    for signal, callback in (
        (owner.scope.currentIndexChanged, owner.refresh),
        (owner.coincident.toggled, owner.changed),
        (owner.refresh_button.clicked, owner.refresh),
        (owner.apply_button.clicked, owner.apply),
    ):
        owner.signals.connect(signal, lambda *args, callback=callback: callback())
    owner.signals.connect(
        owner.close_button.clicked,
        lambda *args: owner.close(),
        closing=True,
        retry=True,
    )


def render(owner: Any, gui: Any) -> None:
    """Preserve stable duplicate-first display independently of writer ordering."""
    facts = owner.facts
    if facts is None:
        owner.subtitle.setText("Open a font first.")
        owner.table.setRowCount(0)
        owner.apply_button.setEnabled(False)
        owner.warning.setText("")
        owner.status.setText("Nothing to fix")
        return
    selected = int(value(owner.scope, "currentIndex")) == 1
    coincident = owner.coincident.isChecked()
    found = rows(facts, selected)
    dupes = sum(finding.kind == "duplicate name" for _, finding in found)
    owner.subtitle.setText(
        f"{dupes} duplicate-name finding{'s' if dupes != 1 else ''} and {len(found) - dupes} coincident group{'s' if len(found) - dupes != 1 else ''}."
    )
    owner.scope.setItemText(1, f"Selected glyphs ({len(facts.selection)}), all masters")
    palette = value(owner, "palette")
    ink = gui.QColor(palette.color(gui.QPalette.WindowText))
    dim = gui.QColor(ink)
    dim.setAlpha(130)
    accent, error = gui.QColor(palette.color(gui.QPalette.Link)), gui.QColor("#d33")
    owner.table.setRowCount(len(found))
    for index, (layer, finding) in enumerate(
        sorted(found, key=lambda row: row[1].kind != "duplicate name")
    ):
        active = not layer.auto and (finding.kind != "coincident" or coincident)
        names = {pin.identity: pin.name for pin in layer.pins}
        fix = (
            "auto layer, kept"
            if layer.auto
            else "remove " + ", ".join(names[key] for key in finding.extras)
            if active
            else "kept"
        )
        for column, text in enumerate(
            (
                f"{layer.name} · {layer.master}",
                finding.kind,
                ", ".join(finding.names),
                fix,
            )
        ):
            item = gui.QTableWidgetItem(text)
            color = (
                error
                if column == 1 and finding.kind == "duplicate name"
                else dim
                if column == 1
                else accent
                if column == 3 and active
                else dim
                if column == 3
                else ink
            )
            item.setForeground(gui.QBrush(color))
            owner.table.setItem(index, column, item)
    work = plan(facts, coincident, selected)
    blocked = affected_auto_layers(
        facts.dependencies, {layer.name for layer, _ in work}
    )
    pending = sum(len(extras) for _, extras in work)
    owner.warning.setText(
        "Cannot safely undo changes to automatic dependants: " + ", ".join(blocked)
        if blocked
        else ""
    )
    owner.warning.setVisible(bool(blocked))
    owner.apply_button.setEnabled(pending > 0 and not blocked)
    owner.status.setText(
        "Fix unavailable"
        if blocked
        else f"{pending} anchor{'s' if pending != 1 else ''} to remove"
        if pending
        else "Nothing to fix"
    )
