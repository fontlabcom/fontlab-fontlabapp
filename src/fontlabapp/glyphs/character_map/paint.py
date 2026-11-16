# this_file: src/fontlabapp/glyphs/character_map/paint.py
# SPDX-License-Identifier: Apache-2.0
"""Original damage-limited grid drawing, with a bounded native painter lifetime."""

from typing import Any
from unicodedata import category

from fontlabapp.qt.properties import value


def marker(grid: Any, painter: Any, gui: Any, row: int, column: int) -> None:
    """A tiny bottom-right square adds coverage without replacing source paint."""
    if grid.owner.facts is None:
        return
    x, y = (column + 1) * grid.cell - 5, (row + 1) * grid.cell - 5
    if row * 16 + column in grid.owner.assignments:
        painter.fillRect(x, y, 3, 3, gui.QColor("#146caa"))
    else:
        painter.setPen(gui.QColor("#6b6b6b"))
        painter.drawRect(x, y, 2, 2)


def draw(grid: Any, event: Any, core: Any, gui: Any) -> None:
    """Contain exceptions before they can escape a PythonQt paint callback."""
    painter = None
    try:
        painter = gui.QPainter(grid)
        painter.setFont(grid.display_font)
        rect, cell = value(event, "rect"), grid.cell
        first = max(0, value(rect, "top") // cell)
        last = min(4095, value(rect, "bottom") // cell)
        if grid.owner.part == 2:
            painter.fillRect(rect, core.Qt.white)
            for row in range(first, last + 1):
                for column in range(16):
                    box = core.QRect(column * cell, row * cell, cell, cell)
                    painter.setPen(gui.QColor("#c7ccd3"))
                    painter.drawRect(box)
                    char = chr(row * 16 + column)
                    if category(char) not in {"Cn", "Cs"}:
                        painter.setPen(gui.QColor("#253746"))
                        painter.drawText(box, core.Qt.AlignCenter, char)
                    marker(grid, painter, gui, row, column)
        else:
            painter.fillRect(rect, core.Qt.white)
            columns = range(
                max(0, value(rect, "left") // cell),
                min(15, value(rect, "right") // cell) + 1,
            )
            painter.setPen(gui.QColor(core.Qt.gray))
            for row in range(first, last + 1):
                for column in columns:
                    painter.drawRect(column * cell, row * cell, cell, cell)
            metrics = gui.QFontMetrics(grid.display_font)
            width = getattr(metrics, "width", None) or metrics.horizontalAdvance
            painter.setPen(gui.QColor(core.Qt.black))
            for row in range(first, last + 1):
                for column in columns:
                    code = row * 16 + column
                    painter.setClipRect(column * cell, row * cell, cell, cell)
                    if code == grid.last_key:
                        painter.fillRect(
                            column * cell + 1, row * cell + 1, cell, cell, core.Qt.red
                        )
                    if not 0xD800 <= code <= 0xDFFF:
                        char = chr(code)
                        painter.setPen(gui.QColor(core.Qt.black))
                        painter.drawText(
                            int(column * cell + cell / 2 - width(char) / 2),
                            row * cell + 4 + value(metrics, "ascent"),
                            char,
                        )
                    marker(grid, painter, gui, row, column)
    except Exception as error:  # noqa: BLE001 - native paint must never unwind through an active QPainter
        grid.owner.failure(error)
    finally:
        if painter is not None:
            try:
                if value(painter, "isActive"):
                    painter.end()
            except Exception as error:  # noqa: BLE001 - contain native painter finalization
                grid.owner.failure(error)
