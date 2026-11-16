# this_file: Scripts/Reports/Metric Reports Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Metric Reports: the vertical metrics report for every open font in one window.

What: Opens fontlabapp.fontui.metric_reports, one shared App window with a read-only
report tab per original menu report, each with Refresh. Every tab keeps the
original capture and render code, so the text matches the separate menu report.
Use: Pick a tab, read the report, press Refresh after changing the selection.
Extension: fontlabapp.fontui.metric_reports.show(only=None, parent=None) returns the shell;
only= opens a single named report.
Safety: Read-only. It never edits the font, selection or Undo history.
"""

TITLE = "Metric Reports Demo"


def main() -> None:
    """Open the window, or say why it did not open."""
    import fly
    from fly.ap.fontui.metric_reports import show
    from fly.ap.qt.dialogs import run_standard_message_box

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(qt, parent, TITLE, f"Metric Reports did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
