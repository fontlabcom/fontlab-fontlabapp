# this_file: Scripts/Anchors/Anchor Rings Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Explain the duplicate-anchor rings drawn in a Glyph window, with sample anchors.

What: Shows, in one message box, which anchor pairs App circles in a Glyph
window and how big the rings are. fontlabapp.anchors.canvas_rings.model.rings
finds every pair of anchors closer than one unit and sizes the ring for the
handle size (5, 8 or 12) and the zoom, using made-up anchor positions.
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is drawn or opened. The real overlay
(fontlabapp.anchors.canvas_rings.ui.CanvasAnchorRingsDialog) paints into a
Glyph window and never edits the font; this demo only prints the sample
numbers and reads and writes no font, master, selection, history, preference,
Output or clipboard.
"""

TITLE = "Anchor Rings Demo"
POINTS = ((0.0, 0.0), (0.4, 0.3), (250.0, 700.0), (250.0, 700.0), (250.0, 700.0), (300.0, 0.0))
CASES = ((8, 1.0), (8, 0.25), (12, 0.25), (5, 4.0))
OVERLAY = "fontlabapp.anchors.canvas_rings.ui.CanvasAnchorRingsDialog"


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def explanation_lines() -> list[str]:
    """Rings of the sample anchors for each handle size and zoom."""
    from fly.ap.anchors.canvas_rings.model import rings

    lines = [f"Sample anchors: {list(POINTS)}", "A pair closer than 1 unit gets one ring; three coincident anchors give three rings.", ""]
    for handle, scale in CASES:
        found = rings(POINTS, scale, handle_size=handle)
        lines.append(f"Handle size {handle}, zoom {scale:g}: {len(found)} rings")
        lines += [f"  anchors {ring.pair} at {ring.center}: diameter {ring.diameter:.1f}, outer stroke {ring.outer:.1f}, inner stroke {ring.inner:.1f}" for ring in found]
    return [*lines, "", "The overlay itself, not opened here: " + OVERLAY]


def main() -> None:
    """Show the sample rings; no font or Glyph window is needed."""
    notify(TITLE, "Sample duplicate-anchor rings. Nothing was drawn.", "\n".join(explanation_lines()))


if __name__ == "__main__":
    main()
