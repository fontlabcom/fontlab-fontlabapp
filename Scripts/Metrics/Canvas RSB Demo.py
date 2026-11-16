# this_file: Scripts/Metrics/Canvas RSB Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Explain the right-sidebearing line overlay with sample geometry.

What: Shows, in one message box, what fontlabapp.metrics.canvas_rsb draws in a
Glyph window: a marker line at the right advance edge (or the left edge for
right-to-left text) and a small triangle, shifted by the italic angle.
fontlabapp.metrics.canvas_rsb.model.geometry computes sample lines for an
upright and an italic glyph so you can see the numbers.
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is drawn or opened. The overlay panel needs FontLab's
application object and paints into a Glyph window, so this demo only prints
the sample geometry; it reads and writes no font, master, selection, history,
preference, Output or clipboard.
"""

TITLE = "Canvas RSB Demo"
GLYPH = {"width": 500, "ascender": 750, "descender": -250, "x_height": 500}
CASES = (("upright, left to right", 0, 0), ("italic 12 degrees, left to right", 12, 0), ("upright, right to left", 0, 2))


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def explanation_lines() -> list[str]:
    """Sample marker geometry from the real model for an advance of 500 units."""
    from fly.ap.metrics.canvas_rsb.model import geometry

    lines = [f"Sample glyph: {GLYPH}", "Direction 0 marks the right edge, direction 2 the left edge.", ""]
    for label, angle, direction in CASES:
        line, triangle, stroke = geometry(*GLYPH.values(), angle, 1.0, direction)
        lines += [
            f"{label}:",
            "  line from (%.1f, %g) to (%.1f, %g)" % (line[0] + line[1]),
            "  triangle " + ", ".join("(%.1f, %.1f)" % point for point in triangle),
            f"  stroke width {stroke:g}",
        ]
    return lines


def main() -> None:
    """Show the explanation; no font or Glyph window is needed."""
    notify(TITLE, "Sample right-sidebearing marker geometry. Nothing was drawn.", "\n".join(explanation_lines()))


if __name__ == "__main__":
    main()
