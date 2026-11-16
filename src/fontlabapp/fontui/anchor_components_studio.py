# this_file: src/fontlabapp/fontui/anchor_components_studio.py
# SPDX-License-Identifier: Apache-2.0
"""S27: retain the anchor/component inspection owner inside the shared shell."""

from typing import Any

from PythonQt import QtGui

import fontlabapp.fontui as fontui
from fontlabapp.fontui.anchor_components import AnchorComponentInspector
from fontlabapp.fontui.appshell import AppShell
from fontlabapp.fontui.lifecycle import Owned
from fontlabapp.fontui.table import GlyphRow
from fontlabapp.fontui.tglyph_model import default_layer
from fontlabapp.studios import TabSpec

_HANDLES: list[Any] = []
TITLE = "Anchor and Component Inspector"


class Shell(AppShell):
    """Keep the modeless shell reachable until its full close is acknowledged."""

    def close(self) -> None:
        super().close()
        if self in _HANDLES:
            _HANDLES.remove(self)


class Controller(AnchorComponentInspector):
    """Use the existing read/refresh/release contract with sortable tables."""

    def selected(self, font: Any, names: tuple[str, ...]) -> None:
        if self._closing:
            return
        if default_layer(self.font) != self.layer:
            self.anchor_rows = self.component_rows = ()
            self._fill(self.anchor_table, ())
            self._fill(self.component_table, ())
            self.canvas.load(None, self.layer)
            self.status.setText("The font's default layer changed. Close and reopen this inspector.")
            return
        super().selected(font, names)
        self.canvas.load(names[0] if font is self.font and names else None, self.layer)

    def _fill(self, table: Any, rows: tuple) -> None:
        table.set_rows([
            GlyphRow("—" if row[0] is None else str(row[0]), None, row[1:])
            for row in rows
        ])


class Panel(Owned):
    """Close the existing inspection before releasing its new table widgets."""

    def __init__(self, shell: Any, font: Any, qt: Any) -> None:
        super().__init__(shell.widget)
        self.controller = Controller(qt, font)
        self.controller.layer = default_layer(font)
        self.tables: list[Any] = []

    def build(self, canvas: Any) -> None:
        from fontlabapp.fontui.native import Browser

        owner = self.controller
        owner.canvas = canvas
        owner.anchor_table = fontui.glyph_table(("Anchor", "X", "Y"), self.widget)
        self.tables.append(owner.anchor_table)
        owner.component_table = fontui.glyph_table(("Base glyph", "Transformation"), self.widget)
        self.tables.append(owner.component_table)
        owner.status = QtGui.QLabel(self.widget)
        for table in self.tables:
            self.layout.addWidget(table.widget)
        self.layout.addWidget(owner.status)
        owner.browser = fontui._construct(
            Browser, owner.font, self.widget, None, False, True, owner.selected
        )
        owner.browser.preview.widget.hide()
        self.layout.addWidget(owner.browser.widget)

    def close(self) -> None:
        if not self.controller.release():
            raise RuntimeError("Anchor/component inspection cleanup is incomplete; retry Close")
        while self.tables:
            table = self.tables[-1]
            table.close()
            if not table._close_complete:
                raise RuntimeError("Inspection table cleanup is incomplete; retry Close")
            self.tables.pop()
        super().close()


def show(font: Any, parent: Any = None) -> Shell:
    """Open the captured font's read-only inspector without changing its owners."""
    from fontlabapp import _native

    shell = Shell(TITLE, "tglyph", parent=parent)
    _HANDLES.append(shell)
    try:
        panel = Panel(shell, font, _native("PythonQt"))
        shell.inspector = panel
        shell.children.append(panel)
        canvas = fontui.glyph_view(
            font, shell.widget, layer=panel.controller.layer, controls=False, read_only=True
        )
        shell.set_preview(canvas)
        panel.build(canvas)
        shell.add_tab(TabSpec("Anchors and Components", lambda app: panel.widget))
        shell.set_actions(panel, refresh=panel.controller.refresh)
        shell.set_about(
            "Inspect stored anchors and direct component transformations. "
            "Filter glyph names and select a glyph; sort table columns without changing records.\n"
            "Source: https://github.com/fontlabcom/fontlab-fontlabapp\n"
            "Credits: FontLab App contributors; Apache-2.0."
        )
        shell.show()
    except BaseException as error:
        pending = [error]
        while pending:
            failure = pending.pop()
            failed = getattr(failure, "owner", None)
            if isinstance(failed, Owned) and failed not in shell.children:
                shell.children.append(failed)
            if isinstance(failure, BaseExceptionGroup):
                pending.extend(failure.exceptions)
        try:
            shell.close()
        except BaseException as cleanup:
            error.add_note(f"Inspector cleanup is incomplete; retained owner: {cleanup}")
        raise
    return shell
