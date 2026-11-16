# this_file: Scripts/Reports/Open Contours Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Contours: open contours with a Select glyphs action.

What: Opens fontlabapp.fontui.open_contours, one shared App window with a read-only
report table (row and double-click glyph selection, red non-zero gaps) and Refresh.
Use: Read the report; Select glyphs selects each listed glyph.
Extension: fontlabapp.fontui.open_contours.show(parent=None) returns the shell.
Safety: Read-only except Select glyphs, which changes the selection only.
"""

TITLE = "Open Contours Demo"
DOMAIN = "fontlabapp.contours.open_contours"  # scan model and native owner behind the window
TABLE = "fontlabapp.fontui.glyph_row_table"  # shared glyph table tab: row selection, double-click, red gaps


def main() -> None:
    """Open the window, or say why it did not open."""
    import fly
    from fly.ap.fontui.open_contours import show
    from fly.ap.qt.dialogs import run_standard_message_box

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(qt, parent, TITLE, f"Open Contours did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
