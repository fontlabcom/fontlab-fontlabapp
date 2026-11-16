# this_file: Scripts/Contours/Contour Samples Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Show the contour reports of App on made-up outlines, without a font.

What: Feeds sample outlines to the pure report builders behind App's contour
reports and prints their text: Close But No Cigar
(fontlabapp.contours.near_miss.model), the Point Counter
(fontlabapp.contours.point_counts.model), the SVG path dump
(fontlabapp.contours.svg_path.model) and Dangerous Offcurves
(fontlabapp.contours.dangerous_offcurves.model), which finds handles that sit
almost on their own curve.
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Dangerous Offcurves needs the fontTools package; without it that section says
so and the others still show.
Safety: Nothing is read from a font or written. The outlines are plain values
in this script, no window opens and no font, master, selection, history,
preference, Output or clipboard is touched.
"""

TITLE = "Contour Samples Demo"
CUBIC = ((140, 170), (140, 30), (140, 150), (150, 0))  # a handle almost on its curve


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def near_miss() -> str:
    """One glyph whose bottom edge is 1 degree off the horizontal and a node 1 unit above x-height."""
    from fly.ap.contours.near_miss import model

    nodes = tuple(model.Node(point, False) for point in ((0, 0), (300, 5), (300, 501), (0, 700)))
    return model.render((model.Glyph("H", "Regular", "Regular", (750, 700, 500, -250), (80,), (90,), (nodes,)),))


def point_counts() -> str:
    """Three layers; the last one has a different point count and gets the marker."""
    from fly.ap.contours.point_counts import model

    layers = (
        model.LayerCount("Regular", model.Counts(4, 8, 16, 2)),
        model.LayerCount("Bold", model.Counts(4, 8, 16, 2)),
        model.LayerCount("Light", model.Counts(4, 9, 18, 2)),
    )
    return model.render((model.GlyphCount("a", layers),))


def svg_path() -> str:
    """One contour of a line and a cubic."""
    from fly.ap.contours.svg_path import model

    return model.render(((((0, 0), (100, 0)), ((100, 0), (100, 50), (50, 100), (0, 100))),))


def dangerous() -> str:
    """One layer whose first handle lies on the curve."""
    from fly.ap.contours.dangerous_offcurves import model

    path = tuple(model.Node(x, y, off) for (x, y), off in zip(CUBIC, (False, True, True, False)))
    return model.render(model.analyse((model.Layer((1, 1), "o", "Regular", (path,)),)))


def explanation_lines() -> list[str]:
    """Each report on its own, so that a missing optional package keeps the others."""
    lines = []
    for heading, build in (("Close But No Cigar", near_miss), ("Point Counter", point_counts), ("SVG path commands", svg_path), ("Dangerous Offcurves", dangerous)):
        try:
            lines += [heading + ":", build().rstrip(), ""]
        except ImportError as error:  # only Dangerous Offcurves needs the optional fontTools
            lines += [heading + ":", f"Unavailable: {error}", ""]
    return lines


def main() -> None:
    """Show the sample reports; no font is needed."""
    notify(TITLE, "Sample contour reports. Nothing was read or written.", "\n".join(explanation_lines()))


if __name__ == "__main__":
    main()
