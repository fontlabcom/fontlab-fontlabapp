# this_file: Scripts/Reports/Font Revision Comparison Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Font Revision Comparison: composite and glyph-set difference reports between open fonts in one window.

What: Opens fontlabapp.fontui.font_revision_comparison, one shared App window with a read-only
report tab per original menu report, each with Refresh. Every tab keeps the
original capture and render code, so the text matches the separate menu report.
Use: Pick a tab, read the report, press Refresh after changing the selection.
Extension: fontlabapp.fontui.font_revision_comparison.show(only=None, parent=None) returns the shell;
only= opens a single named report.
Safety: Read-only. It never edits the font, selection or Undo history.
"""

TITLE = "Font Revision Comparison Demo"


def main() -> None:
    """Open the window, or say why it did not open."""
    import fly
    from fly.ap.fontui.font_revision_comparison import show
    from fly.ap.qt.dialogs import run_standard_message_box

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(qt, parent, TITLE, f"Font Revision Comparison did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
