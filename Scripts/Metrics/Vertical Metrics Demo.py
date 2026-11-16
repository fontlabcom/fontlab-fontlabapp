# this_file: Scripts/Metrics/Vertical Metrics Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Compare the stored vertical metrics of every master in every open font.

What: Opens the nonmodal Vertical Metrics Reporter
(fontlabapp.metrics.vertical.ui.VerticalMetricsDialog). It lists eight stored
values per master: typo and hhea ascender, descender and line gap, and the
Windows ascent and descent. An unset hhea value shows as None, not zero.
Use: Open one or more fonts and run it. Read the report, click Refresh after
changing a font and Close when done.
Safety: Read-only. The report reads stored metadata through FontLab's
metadata-only font API; it never switches a master or writes a font,
selection, history, preference, Output or clipboard. Values FontLab derives on
export are not part of it. With no font open nothing opens.
"""

TITLE = "Vertical Metrics Demo"


def main() -> None:
    """Open the report, or say that a font is needed."""
    import fly
    from fly.ap.core.scripting import current_package, show_script_dialog
    from fly.ap.metrics.vertical.ui import VerticalMetricsDialog
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font first. The report reads its masters.", "Information", kind.Ok)
        return
    try:
        show_script_dialog(VerticalMetricsDialog, VerticalMetricsDialog.KEY)
    except (ValueError, RuntimeError, TimeoutError) as error:
        run_standard_message_box(qt, parent, TITLE, f"The report did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
