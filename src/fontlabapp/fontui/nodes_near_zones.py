# this_file: src/fontlabapp/fontui/nodes_near_zones.py
# SPDX-License-Identifier: Apache-2.0
"""S66 Nodes Near Zones: a shell report tab with a tolerance control and Select glyphs.

The report lists on-curve nodes of the selected glyphs (all glyphs when none
is selected) that sit a few units off a vertical metric line. Changing the
tolerance rescans; Select glyphs selects each listed glyph once, in the font
the report was read from. It never edits outlines. A failed refresh clears
the report and disables selection.
"""

from typing import Any

from PythonQt import QtGui

from fontlabapp.contours.nodes_near_zones import model, native
from fontlabapp.qt import properties

from .glyph_row_table import STALE, GlyphTableTab  # noqa: F401
from .snapshot_audit import show_snapshots

ABOUT = (
    "Nodes Near Zones: on-curve nodes a few units off baseline, x-height, cap height, ascender or descender.\n"
    "Source: https://github.com/fontlabcom/fontlab-fontlabapp\n"
    "Menus: https://github.com/fontlabcom/fontlab-python-scriptmix\n"
    "Credits: FontLab App contributors (Apache-2.0)."
)
TOLERANCE_RANGE = (1, 30)
SCOPES = ("Selected glyphs (all if none)", "All glyphs")


class NodesNearZonesTab(GlyphTableTab):
    """Report text, a tolerance spin box and a Select glyphs button."""

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.tolerance = QtGui.QSpinBox()
        self.tolerance.setRange(*TOLERANCE_RANGE)
        self.tolerance.setValue(model.DEFAULT_TOLERANCE)
        self.tolerance.setSuffix(" units")
        self.scope = QtGui.QComboBox()
        self.scope.addItems(SCOPES)
        self.layout.addWidget(self.scope)
        self.layout.addWidget(self.tolerance)
        self._capture = lambda: native.capture(
            properties.value(self.tolerance, "value"), properties.value(self.scope, "currentIndex") == 1)
        self.connect(self.scope.currentIndexChanged, lambda *a: self.refresh())
        self.connect(self.tolerance.valueChanged, lambda *a: self.refresh())

    HEADERS = ("Glyph", "Master", "Zone", "Value", "X", "Y", "Offset")
    RED_COLUMN = None
    RIGHT_COLUMNS = (3, 4, 5, 6)

    def cells(self, row: tuple) -> list[str]:
        return [str(row[0]), str(row[1]), str(row[2]), f"{row[3]:g}", f"{row[4]:g}", f"{row[5]:g}", f"{row[5] - row[3]:+g}"]

    def pick(self, report: Any, names: list[str] | None) -> list:
        return native.select(report) if names is None else native.select(report, names)


def routes() -> tuple:
    """The single report route; capture is rebound per tab to read its tolerance."""
    return (("Nodes Near Zones",
             "On-curve nodes of the selected glyphs, or all glyphs, within a few units of a vertical metric.",
             lambda: native.capture(model.DEFAULT_TOLERANCE), model.render, model.summary),)


def show(*, parent: Any = None) -> Any:
    """Open Nodes Near Zones."""
    return show_snapshots("Nodes Near Zones", routes(), ABOUT, parent=parent, tab_type=NodesNearZonesTab)
