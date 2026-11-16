# this_file: Scripts/Contours/Contour Reports Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open App's three read-only contour reports for the selected glyphs.

What: Opens three nonmodal report windows: the Point Counter, which counts
lines, curves and off-curve points of every foreground layer
(fontlabapp.contours.point_counts.ui.PointCountsDialog); Close But No Cigar,
which lists nodes and segments that miss an angle or metric by a hair
(fontlabapp.contours.near_miss.model.show); and the SVG path commands of the
first selected layer (fontlabapp.contours.svg_path.model.show).
Use: Open a font, select glyphs in a Font window and run it. Read the text,
click Refresh after you change the selection or the outlines and Close each
window when done.
Safety: Read-only. The windows read the selected glyphs' own contours when they
open and again on Refresh; they never change a font, master, selection,
history, preference, Output or clipboard. Text in a window can be selected and
copied with the usual editing keys. If one report fails to open, the others
still do and a message lists what failed. With no font open nothing opens.
"""

TITLE = "Contour Reports Demo"


def main() -> None:
    """Open each report on its own, then list any that failed."""
    import fly
    from fly.ap.contours.near_miss.model import show as show_near_miss
    from fly.ap.contours.point_counts.ui import PointCountsDialog
    from fly.ap.contours.svg_path.model import show as show_svg_path
    from fly.ap.core.scripting import current_package, show_script_dialog
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font and select glyphs first. These reports read their contours.", "Information", kind.Ok)
        return
    reports = (
        ("point counter", lambda: show_script_dialog(PointCountsDialog, PointCountsDialog.KEY)),
        ("close but no cigar", show_near_miss),
        ("SVG path commands", show_svg_path),
    )
    failures = []
    for label, opener in reports:
        try:
            opener()
        except (ValueError, RuntimeError, TimeoutError) as error:
            failures.append(f"{label}: {error}")
    if failures:
        run_standard_message_box(qt, parent, TITLE, "Some reports did not open:\n" + "\n".join(failures), "Warning", kind.Ok)


if __name__ == "__main__":
    main()
