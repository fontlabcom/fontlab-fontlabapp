# this_file: Scripts/Reports/Snapshot Audit Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Snapshot Audit: shared report window used by Geometry Audit.

What: Opens fontlabapp.fontui.snapshot_audit, one shared App window with a read-only
report tab per original menu report, each with Refresh. Every tab keeps the
original capture and render code, so the text matches the separate menu report.
Use: Pick a tab, read the report, press Refresh after changing the selection.
Extension: fontlabapp.fontui.snapshot_audit.show_snapshots(title, routes, about) builds such a window from (title, capture, render, status) routes.
Safety: Read-only. It never edits the font, selection or Undo history.
"""

TITLE = "Snapshot Audit Demo"


def main() -> None:
    """Open the window, or say why it did not open."""
    import fly
    from fly.ap.fontui.geometry_audit import show
    from fly.ap.qt.dialogs import run_standard_message_box

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(qt, parent, TITLE, f"Snapshot Audit did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
