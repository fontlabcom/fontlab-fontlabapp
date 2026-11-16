# this_file: Scripts/Metrics/Spacing Worksheet Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open the spacing worksheet that compares four candidate advance widths.

What: Opens the nonmodal spacing worksheet (fontlabapp.metrics.worksheet.model.show).
It reads the advance of every selected glyph layer and prints four local
candidates, each the advance times a factor pair that you can edit.
Use: Open a font, select glyphs in a Font window and run it. Edit the factor
cells, click Refresh to read the selection again, Reset Factors to restore the
defaults, and Close when done.
Safety: Read-only. The window reads the selected layers' advance widths when
it opens and again on Refresh. Factors live only in the window and the
candidates are text; no font, master, selection, history, preference, Output
or clipboard is written. FontLab may finish loading a layer it had not read
yet. Closing discards your factors. With no font open nothing opens.
"""

TITLE = "Spacing Worksheet Demo"


def main() -> None:
    """Open the worksheet on the current font, or say that a font is needed."""
    import fly
    from fly.ap.core.scripting import current_package
    from fly.ap.metrics.worksheet.model import show
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font and select glyphs first. The worksheet reads their advances.", "Information", kind.Ok)
        return
    try:
        show()
    except (ValueError, RuntimeError, TimeoutError) as error:
        run_standard_message_box(qt, parent, TITLE, f"The worksheet did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
