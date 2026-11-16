# this_file: Scripts/Metrics/Spacing Offset Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Preview how a sidebearing offset would move the selected glyphs' ink.

What: Opens the nonmodal spacing offset window
(fontlabapp.metrics.offset.model.show) with its three slider controls. It
reads the selected layers' left and right margins and shows the margins that
an offset from -100 to 100 units would give: left plus the offset, right minus
the offset, advance unchanged.
Use: Open a font, select glyphs in a Font window and run it. Move the
sliders, click Refresh to read the selection again and Close when done.
Safety: Read-only. The sliders change only numbers in the window. The window
reads each selected layer's advance and bounding box when it opens and on
Refresh (FontLab may fill its bounding-box cache) and never writes a font,
master, selection, history, preference, Output or clipboard. With no font
open nothing opens.
"""

TITLE = "Spacing Offset Demo"


def main() -> None:
    """Open the offset preview on the current font, or say that a font is needed."""
    import fly
    from fly.ap.core.scripting import current_package
    from fly.ap.metrics.offset.model import show
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font and select glyphs first. The preview reads their margins.", "Information", kind.Ok)
        return
    try:
        show()
    except (ValueError, RuntimeError, TimeoutError) as error:
        run_standard_message_box(qt, parent, TITLE, f"The preview did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
