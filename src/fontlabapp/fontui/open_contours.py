# this_file: src/fontlabapp/fontui/open_contours.py
# SPDX-License-Identifier: Apache-2.0
"""S65 Open Contours: a shell report tab with a Select glyphs action.

The report lists open contours of the current font on every master. Select
glyphs selects each listed glyph once, in the font the report was read from;
it never edits outlines. A failed refresh clears the report and disables
selection.
"""

from typing import Any

from fontlabapp.contours.open_contours import model, native

from .glyph_row_table import STALE, GlyphTableTab  # noqa: F401
from .snapshot_audit import show_snapshots

ABOUT = (
    "Open Contours: open contours on every master, with a Select glyphs action.\n"
    "Source: https://github.com/fontlabcom/fontlab-fontlabapp\n"
    "Menus: https://github.com/fontlabcom/fontlab-python-scriptmix\n"
    "Credits: original workflow by FontLab App contributors (Apache-2.0).\n"
)


class OpenContoursTab(GlyphTableTab):
    """Report text plus a Select glyphs button bound to the current report."""

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)

    HEADERS = ("Glyph", "Master", "Contour", "Nodes", "End gap")
    RED_COLUMN = 4
    RIGHT_COLUMNS = (3, 4)

    def cells(self, row: tuple) -> list[str]:
        return [str(row[0]), str(row[1]), f"#{row[2] + 1}", str(row[3]), str(row[4])]

    def is_red(self, row: tuple) -> bool:
        return row[4] > 0

    def pick(self, report: Any, names: list[str] | None) -> list:
        return native.select(report) if names is None else native.select(report, names)


def routes() -> tuple:
    """The single report route."""
    return (("Open Contours",
             "Open contours of every glyph on every master: node count and distance between the end nodes.",
             lambda: native.capture(), model.render, model.summary),)


def show(*, parent: Any = None) -> Any:
    """Open Open Contours."""
    return show_snapshots("Open Contours", routes(), ABOUT, parent=parent, tab_type=OpenContoursTab)
