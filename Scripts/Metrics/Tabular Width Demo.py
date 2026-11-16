# this_file: Scripts/Metrics/Tabular Width Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Check whether the selected glyphs share one advance width.

What: Opens the nonmodal Check Tabular Widths report
(fontlabapp.metrics.tabular_width.ui.TabularWidthDialog). The first selected
glyph is the reference; each other glyph is marked as the same width or not.
Use: Open a font, select glyphs in a Font window and run it. Read the report,
click Refresh after you change the font or selection and Close when done.
Safety: Read-only. The report reads the advance width of each selected glyph
layer when it opens and on Refresh (FontLab may finish loading a layer it had
not read yet). It never writes a font, master, selection, history,
preference, Output or clipboard. With no font open nothing opens.
"""

TITLE = "Tabular Width Demo"


def main() -> None:
    """Open the report on the current font, or say that a font is needed."""
    import fly
    from fly.ap.core.scripting import current_package, show_script_dialog
    from fly.ap.metrics.tabular_width.ui import TabularWidthDialog
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font and select glyphs first. The report reads their widths.", "Information", kind.Ok)
        return
    try:
        show_script_dialog(TabularWidthDialog, TabularWidthDialog.KEY)
    except (ValueError, RuntimeError, TimeoutError) as error:
        run_standard_message_box(qt, parent, TITLE, f"The report did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
