# this_file: src/fontlabapp/fontui/outline_routes/simplify_selected_nodes.py
# SPDX-License-Identifier: Apache-2.0
"""Remove alternate selected nodes from straight contours.

What: Keep the first selected node, remove the second, and repeat in contour
order. Open endpoints stay. Closed polygons keep at least three nodes.
How: Preview the removals on each master. Delete by descending stored index.
Curves are kept; use FontLab Contour > Simplify for curve reduction. Shared or transformed outlines are also kept.
Why: Restrict this operation to polygons so deletion cannot break cubic topology.
Use: Select polygon nodes, run the tool, choose masters and press Simplify.
Benefit: A repeatable reduction with matching selected indices applied across compatible masters.
The change is recorded as one Undo step. Automatic layers are kept; leave the
automatic-base consent off to keep their bases too.

Independent behaviour rewrite after Pedro Arilla, glyphs-scripts,
Paths/Simplify selection.py, Apache-2.0.
Repository: https://github.com/pedroarilla/glyphs-scripts . No source code copied.
"""

from typing import Any

import fontlabapp.contours.panel.model as panel
import fontlabapp.contours.writer as writer  # noqa: PLR0402 - native package lookup
import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - native package lookup
from fontlabapp.fontui.outline_simplify import (
    SimplifyEditor,
    changes,
    removals,
)

TITLE = "Simplify Selected Nodes"
KEY = "contours_simplify_selected_nodes"


class SimplifyPanel(panel.panel_type()):
    """Reuse the master scope and structural-compatibility preview."""

    TITLE, KEY, ACTION, DONE, UNIT = TITLE, KEY, "Simplify", "Simplified", "contour"
    STRUCTURAL = True
    HEADERS = ("Glyph · master", "Polygon", "Nodes", "After")

    def planner(self) -> writer.Planner:
        return lambda glyph, master, layer: changes(
            layer, glyph.findLayer(self.current_master)
        )

    def editor(self) -> writer.Editor:
        return SimplifyEditor()


def main() -> Any:
    """Show the non-modal polygon reduction panel."""
    try:
        return scripting.show_script_dialog(SimplifyPanel, KEY)
    except (ValueError, RuntimeError, TimeoutError) as error:
        import PythonQt as qt

        import fontlabapp as ap
        from fontlabapp.qt.dialogs import run_standard_message_box

        run_standard_message_box(
            qt, ap.fontlab.MainWindow(), TITLE, str(error), "Warning", qt.QtGui.QMessageBox.Ok
        )
        return None


if __name__ == "__main__":
    main()

__all__ = ['SimplifyEditor', 'changes', 'main', 'removals']
