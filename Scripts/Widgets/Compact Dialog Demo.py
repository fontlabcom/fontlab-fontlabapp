# this_file: Scripts/Widgets/Compact Dialog Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open a tiny dialog that uses FontLab's compact panel metrics.

What: Calls fontlabapp.qt.compact.compact_dialog to get a modeless QDialog whose layout uses the
6 px margin and 4 px spacing of FontLab's own panels instead of Qt's 11/6, then
adds a label and a Close button. This is the one-import way to build a script
window that matches native FontLab.
Use: Run it from the Scripts menu. Click Close to dismiss the dialog.
Safety: Reads and writes no font, master, selection, history, preference,
Output or clipboard. The only effect is one window owned by this script.
"""

TITLE = "Compact Dialog Demo"

_KEEP: list = []  # Keeps the modeless dialog alive after main() returns.


def main() -> None:
    """Show a compact dialog with a label and a Close button."""
    import fly
    from fly.ap.qt.compact import compact_dialog

    gui = fly.qt.QtGui
    dialog, layout = compact_dialog(TITLE)
    layout.addWidget(gui.QLabel("Margin 6 px, spacing 4 px, like FontLab panels."))
    close = gui.QPushButton("Close")
    close.clicked.connect(dialog.close)
    layout.addWidget(close)
    _KEEP[:] = [dialog]
    dialog.show()


if __name__ == "__main__":
    main()
