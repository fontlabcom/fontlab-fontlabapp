# this_file: Scripts/Metrics/Advance Widths Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Advance Widths: width table, round and scale, tabular widths, zero-width marks and width chart.

What: Opens the Advance Widths window (fontlabapp.studios.advance_widths) for
the current font. A read-only TMetrics preview sits on top. Table lists the
advance of the selected glyphs in every master and flags mixed progressions;
Round & scale rounds advances to a step of 1 to 100 units or scales them by a
percentage; Tabular gives figures one shared, centred width and checks the
widths of the selected layers; Marks sets the advance of combining marks to 0;
Chart draws the advances across masters.
Use: Select glyphs in the Font window, open a font and run it. Set the
options; each edit tab lists the exact layers it will change. Press Apply.
Safety: Table, Chart and Check only read. Nothing changes until you press
Apply. It writes exactly the listed layers, as one named Undo step
("Advance Widths: ..."), and refuses when a listed layer changed after the
list was made; press Refresh then. With no font open the window opens without
a preview and says so.
"""

TITLE = "Advance Widths Demo"


def main() -> None:
    """Open Advance Widths, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.advance_widths import show

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(qt, parent, TITLE, f"Advance Widths did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
