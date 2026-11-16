# this_file: Scripts/Kerning/Kerning Browser Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Kerning Browser: pairs, classes, exceptions, missing pairs, masters and energy.

What: Opens the Kerning Browser window (fontlabapp.studios.kerning_browser) for
the current font. A TMetrics preview sits on top. Pairs lists and filters one
master's pairs and exports them as CSV; Classes shows each kerning class with
its members and values on every master; Exceptions lists glyph exceptions to
class pairs; Missing lists unkerned combinations of two glyph lists; Masters
compares every pair across masters and flags sign changes, gaps and jumps;
Energy sums kerning per selected glyph and suggests sidebearing changes.
Use: Open a font and run it. Pick a row to preview its pair on its master.
Select class members, copy the missing list or open the Energy report.
Safety: Every tab is read-only except Exceptions, which removes only the
exceptions you tick, as one named Undo step ("Kerning Browser: Remove ..."),
and refuses when the kerning changed after the scan. With no font open the
window opens without a preview and says so.
"""

TITLE = "Kerning Browser Demo"


def main() -> None:
    """Open Kerning Browser, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.kerning_browser import show

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(qt, parent, TITLE, f"Kerning Browser did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
