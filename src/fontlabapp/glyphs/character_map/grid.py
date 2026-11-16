# this_file: src/fontlabapp/glyphs/character_map/grid.py
# SPDX-License-Identifier: Apache-2.0
"""BMP reference grid with distinct original mouse, tooltip and insertion rules."""

from html import escape
from typing import Any
from unicodedata import name

from fontlabapp.glyphs.character_map.model import codepoint_at, selectable
from fontlabapp.glyphs.character_map.paint import draw
from fontlabapp.qt.properties import value


def grid_type(core: Any, gui: Any) -> type:
    class Grid(gui.QWidget):
        def __init__(self, owner: Any) -> None:
            gui.QWidget.__init__(self, owner)
            self.owner, self.display_font = owner, gui.QFont()
            self.cell, self.last_key = 24, -1
            self.setMouseTracking(True)

        def sizeHint(self) -> Any:
            return core.QSize(16 * self.cell, 4096 * self.cell)

        def tooltip(self, code: int) -> str:
            if self.owner.part == 2:
                text = f"U+{code:04X} {name(chr(code), 'Unassigned')}"
            else:
                char = (
                    "Surrogate: not a Unicode scalar"
                    if 0xD800 <= code <= 0xDFFF
                    else escape(chr(code))
                )
                family = escape(value(self.display_font, "family"), quote=True)
                text = f'<p>Character: <span style="font-size: 24pt; font-family: {family}">{char}</span><p>Value: 0x{code:x}'
            if self.owner.facts is None:
                detail = "FontLab coverage unavailable — Refresh"
            else:
                names = self.owner.assignments.get(code, ())
                detail = "FontLab: " + (", ".join(names) if names else "missing")
            return text + (
                "\n" + detail if self.owner.part == 2 else "<p>" + escape(detail)
            )

        def mouseMoveEvent(self, event: Any) -> None:
            if self.owner.closed:
                return
            try:
                point = (
                    self.mapFromGlobal(event.globalPos())
                    if self.owner.part == 3
                    else event.pos()
                )
                code = codepoint_at(
                    self.owner.part, value(point, "x"), value(point, "y"), self.cell
                )
                if code is not None:
                    gui.QToolTip.showText(event.globalPos(), self.tooltip(code), self)
            except Exception as error:  # noqa: BLE001 - native mouse callback boundary
                self.owner.failure(error)

        def mousePressEvent(self, event: Any) -> None:
            if self.owner.closed:
                return
            try:
                if self.owner.part == 3 and event.button() != core.Qt.LeftButton:
                    gui.QWidget.mousePressEvent(self, event)
                    return
                code = codepoint_at(
                    self.owner.part, value(event, "x"), value(event, "y"), self.cell
                )
                if code is None:
                    return
                if self.owner.part == 3:
                    self.last_key = code
                    self.update()
                    if 0xD800 <= code <= 0xDFFF:
                        self.owner.failure(
                            ValueError(
                                "Surrogate code points cannot be inserted as characters."
                            )
                        )
                        return
                if self.owner.part == 2 and not selectable(2, code):
                    return
                member = (
                    True
                    if self.owner.part == 3
                    else gui.QFontMetrics(self.display_font).inFontUcs4(code)
                )
                if selectable(self.owner.part, code, member):
                    if self.owner.part == 2:
                        self.owner.text.setText(
                            value(self.owner.text, "text") + chr(code)
                        )
                    else:
                        self.owner.text.insert(chr(code))
                    self.last_key = code
            except Exception as error:  # noqa: BLE001 - native mouse callback boundary
                self.owner.failure(error)

        def paintEvent(self, event: Any) -> None:
            if not self.owner.closed:
                draw(self, event, core, gui)

    return Grid
