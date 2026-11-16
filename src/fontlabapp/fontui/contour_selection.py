# this_file: src/fontlabapp/fontui/contour_selection.py
# SPDX-License-Identifier: Apache-2.0
"""Three staged contour-selection tools sharing the existing guarded native writer.

Selection alone changes: no geometry, notification or history transaction.
The original Pedro Arilla selection policies remain in contours.selection.
"""
from time import monotonic
from typing import Any

from PythonQt import QtGui

import fontlabapp.fontui as fontui  # noqa: PLR0402 - native package lookup
from fontlabapp.contours.selection.model import plan
from fontlabapp.contours.selection.native import apply, capture
from fontlabapp.masters.layers import selection
from fontlabapp.qt.widgets import _cleanup_failure
from fontlabapp.studios import TabSpec

from .lifecycle import Owned

MODES = (("Select Contours", "contours"), ("Select Partial Contours", "partial"),
         ("Select Small Contours", "small"))


def selected() -> Any:
    """Capture the first explicit glyph/layer for the read-only preview."""
    source = selection.capture(monotonic() + 2)
    if not source.occurrences:
        raise ValueError("Select a glyph layer before opening Contour Selection.")
    return source.occurrences[0]


def _text(field: Any) -> str:
    value = field.text
    return str(value() if callable(value) else value)


class SelectionTab(Owned):
    """Keep a separate accepted selection plan per tab until Apply or Discard."""

    def __init__(self, shell: Any, mode: str, occurrence: Any):
        super().__init__(shell.widget)
        self.shell, self.mode, self.occurrence = shell, mode, occurrence
        self.source = self.target = None
        self.accepted_input = None
        self.layout.addWidget(QtGui.QLabel(
            "Preview the opening layer's selection. Apply changes selection only; "
            "geometry and other layers stay unchanged.", self.widget))
        self.limit = QtGui.QLineEdit(self.widget)
        self.limit.setText("100")
        self.limit.setAccessibleName("Area smaller than (square font units)")
        if mode == "small":
            self.layout.addWidget(QtGui.QLabel("Area smaller than (square font units)", self.widget))
            self.layout.addWidget(self.limit)
        else:
            self.limit.hide()
        self.table = fontui.glyph_table(("Glyph", "Layer", "Contour", "Selected before", "Selected after", "Area"), self.widget)
        self.layout.addWidget(shell.embed(self.table), 1)
        self.connect(self.table.row_selected, self.row_selected)
        discard = QtGui.QPushButton("Discard Preview", self.widget)
        self.layout.addWidget(discard)
        self.connect(discard.clicked, lambda *args: self.discard())
        shell.set_actions(self, refresh=self.refresh, preview=self.preview_changes,
                          apply=self.apply_changes, dirty=lambda: self.target is not None,
                          ready=self.ready, apply_label="Apply Selection")
        self.refresh()

    def row_selected(self, name: str, layer: str) -> None:
        try:
            self.shell.preview.load(name, layer)
        except Exception as error:  # noqa: BLE001 - contain native Qt callback failures
            self.shell.set_status(f"Preview unavailable: {error}")

    def refresh(self) -> None:
        """Capture only the originally bound occurrence; never silently rebind."""
        self.discard()
        current = selected()
        if (current.package_id, current.glyph_id, current.layer_id) != (
                self.occurrence.package_id, self.occurrence.glyph_id, self.occurrence.layer_id):
            raise ValueError("The selected font, glyph or layer changed; reopen Contour Selection.")
        self.source = capture(area=self.mode == "small")
        self.shell.preview.load(self.occurrence.glyph_name, self.occurrence.layer_name)
        self.shell.set_status("Captured opening layer. Preview Changes before Apply Selection.")

    def discard(self) -> None:
        self.target = self.accepted_input = None
        self.table.set_rows([])
        self.shell.preview.highlight(points=())

    def preview_changes(self) -> Any:
        """Plan without a setter and retain the exact reviewed inputs and source."""
        self.target = None
        if capture(area=self.mode == "small") != self.source:
            raise ValueError("Selection or geometry changed; discard the preview and Refresh.")
        value = _text(self.limit) if self.mode == "small" else None
        target = plan(self.source.paths, self.mode, value)
        name, layer = self.occurrence.glyph_name, self.occurrence.layer_name
        self.table.set_rows([
            (name, layer, (layer, number + 1, sum(path.selected), sum(nodes),
                           path.area if path.area is not None else ""))
            for number, (path, nodes) in enumerate(zip(self.source.paths, target.nodes))
        ])
        self.shell.preview.highlight(points=tuple(
            (ci, ni) for ci, nodes in enumerate(target.nodes)
            for ni, chosen in enumerate(nodes) if chosen))
        self.target, self.accepted_input = target, value
        self.shell.set_status(f"{target.paths} contours planned; selection has not changed.")
        return target

    def ready(self) -> bool:
        value = _text(self.limit) if self.mode == "small" else None
        return (self.target is not None and value == self.accepted_input
                and capture(area=self.mode == "small") == self.source)

    def apply_changes(self) -> int:
        if not self.ready():
            raise ValueError("Preview Changes first; inputs or selection changed.")
        count = apply(self.source, self.target)
        self.refresh()
        self.shell.set_status(f"{count} contours selected. Geometry was not changed.")
        return count


def show(parent: Any = None, *, font: Any = None, preview: Any = None) -> Any:
    """Open the three selection tabs with one captured, non-editing TGlyph."""
    occurrence = selected()
    shell = fontui.app_shell("Contour Selection", "tglyph", parent=parent,
                             package=lambda: occurrence.package)
    try:
        current_font = (font or fontui.current_font)()
        viewer = (preview or fontui.glyph_view)(
            current_font, shell.widget, name=occurrence.glyph_name,
            layer=occurrence.layer_name, controls=False, read_only=True)
        shell.set_preview(viewer)
        shell.selection_tabs = []
        for title, mode in MODES:
            tab = shell.add_tab(TabSpec(title, lambda owner, mode=mode: fontui._construct(SelectionTab, owner, mode, occurrence)))
            shell.selection_tabs.append(tab)
        shell.set_about(
            "Contour Selection\nExpand touched contours, fill stored-order partial spans, "
            "or select contours by analytic area. Small-contour selection clears other selected items.\n"
            "Independent adaptations after Pedro Arilla, glyphs-scripts (2018–2022), Apache-2.0.\n"
            "https://github.com/pedroarilla/glyphs-scripts\n"
            "Source and exact provenance: Scriptmix NOTICE and additional-tools.json."
        )
        shell.show()
    except BaseException as error:
        _cleanup_failure(shell, error)
        raise
    return shell
