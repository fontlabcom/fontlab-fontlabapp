# this_file: src/fontlabapp/studios/component_audit/brackets.py
# SPDX-License-Identifier: Apache-2.0
"""Brackets tab: the Scriptmix "Bracket Layers and Components" (Scripts/Reports/Bracket Layers and Components.py).

The original opened the shared App "Bracket Layer Report": every glyph
with a layer name holding both [ and ], plus every glyph that depends on
one through components, as read-only text with Refresh. This tab shows the
same capture (``brackets.native.report``) and text (``brackets.model.render``)
with the same status line; Refresh scans again. A failed scan clears the text
and shows the reason (no partial result). Read-only: no history, selection,
Output or glyph is touched.
Adapted from Reset Type Studio's Report Glyphs containing BL.py.
Copyright 2025 Fernando Díaz & Reset Type Studio. See NOTICE and additional-tools.json.
"""

from typing import Any

from PythonQt import QtGui

from .._kerning_ui import button
from ._shared import AuditPanel, backends, hline

DESCRIPTION = (
    "Scan the current font for layer names containing both [ and ], plus glyphs that depend "
    "on them through components."
)


class BracketsPanel(AuditPanel):
    def build_controls(self) -> None:
        self.output = QtGui.QPlainTextEdit(self.widget)
        self.output.setReadOnly(True)
        self.layout.addWidget(self.output, 1)
        buttons = hline(self.layout)
        self.refresh_button = button(self.widget, buttons, "Refresh", self.reload_view)
        self.report: Any = None

    def clear_view(self) -> None:
        self.report = None
        self.output.clear()

    def refresh(self) -> None:
        self.clear()
        if self.tool.package is None:
            self.subtitle.setText("Open a font first.")
            self.note("")
            return
        self.subtitle.setText(DESCRIPTION)
        found = backends()
        report = found.bracket_report()
        self.output.setPlainText(found.brackets.render(report))
        self.report = report
        self.note(
            f"Scanned glyphs: {report.glyph_count}. Distinct affected glyphs: {report.total}. Refresh after changes."
        )

    def failed(self, error: BaseException) -> None:
        super().failed(error)
        self.note(str(error))


__all__ = ["DESCRIPTION", "BracketsPanel"]
