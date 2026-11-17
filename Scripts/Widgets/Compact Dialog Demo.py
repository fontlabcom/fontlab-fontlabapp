# this_file: Scripts/Widgets/Compact Dialog Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open a compact dialog with a frameless glyph-style view above its controls.

What: Builds a modeless QDialog with fly.ap.qt.compact.compact_dialog, puts a
frameless graphics view (a large "A") in the top half with split_view and a
controls_box with a label and a Close button below it. Margins are 6 px and
spacing 4 px, like FontLab's own panels, instead of Qt's 11 and 6. Scripts
import the helpers through fly.ap; code inside fontlabapp may use the
fontlabapp.ui re-export of the same names.
Use: Run it from the Scripts menu. Click Close to dismiss the dialog.
Safety: Reads and writes no font, master, selection, history, preference,
Output or clipboard. The only effect is one window owned by this script.
"""

TITLE = "Compact Dialog Demo"

_KEEP: list = []  # Keeps the modeless dialog alive after main() returns.


def main() -> None:
    """Show a compact dialog with a label and a Close button."""
    import fly
    from fly.ap.qt.compact import compact_dialog, controls_box, split_view

    gui = fly.qt.QtGui
    dialog, layout = compact_dialog(TITLE)
    scene = gui.QGraphicsScene(dialog)
    scene.addText("A").setScale(8)
    view = gui.QGraphicsView(scene, dialog)
    controls, controls_layout = controls_box(dialog)
    controls_layout.addWidget(gui.QLabel("Margin 6 px, spacing 4 px, like FontLab panels."))
    close = gui.QPushButton("Close")
    close.clicked.connect(dialog.close)
    controls_layout.addWidget(close)
    split_view(layout, view, controls)
    _KEEP[:] = [dialog]
    dialog.show()


if __name__ == "__main__":
    main()
