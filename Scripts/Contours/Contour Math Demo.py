# this_file: Scripts/Contours/Contour Math Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Try App's outline math on sample numbers: transforms, extremes, reflect, nodes.

What: Prints the results of four small App helpers for made-up outlines: affine
transforms such as a slant (fontlabapp.contours.affine), the true vertical
extent of a curve, which can differ from its node positions
(fontlabapp.contours.extent), the reflect plan for selected points and
components (fontlabapp.contours.reflect) and the distance and angle between
selected nodes (fontlabapp.contours.nodes.coordinates).
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is read from a font or written. The numbers are plain values in
this script and no font, master, selection, history, preference, Output or
clipboard is touched.
"""

TITLE = "Contour Math Demo"
SLANT = (1.0, 0.0, 0.2, 1.0, 0.0, 0.0)  # x grows by 0.2 per unit of y
CUBIC = (0, 100, 100, 0)  # y values of a cubic whose handles sit at 100
NODES = [(0, 0, 0.0, 0.0, True), (0, 1, 30.0, 40.0, False), (1, 0, 100.5, 40.0, True)]


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def explanation_lines() -> list[str]:
    """Results of the real helpers for the sample numbers."""
    import fly.ap.contours.affine as affine
    import fly.ap.contours.extent as extent
    import fly.ap.contours.reflect as reflect
    from fly.ap.contours.nodes import coordinates

    inverse = affine.invert(SLANT)
    corner = affine.apply(SLANT, 0, 100)
    lines = [
        f"Slant {SLANT}: point (0, 100) moves to {corner}; the inverse brings it back to {affine.apply(inverse, *corner)}.",
        f"Rotating (1, 0) by 0.5 radians gives {tuple(round(v, 4) for v in affine.apply(affine.rotation(0.5), 1, 0))}; the identity leaves {affine.apply(affine.IDENTITY, 7, 9)}.",
        "",
    ]
    contour = [((0, 0), extent.ON), ((0, 100), extent.CURVE), ((100, 100), extent.CURVE), ((100, 0), extent.ON)]
    peak = max(extent.contour_ys(contour, True))
    lines += [f"A cubic with handles at y 100 only reaches y {peak:g} (extent.contour_ys); its turning point is {extent.cubic_extremes(*CUBIC)}.", ""]
    elements = (reflect.Element("point", (10, 20)), reflect.Element("component", (60, 0), scale=(1.0, 1.0)), reflect.Element("anchor", (500, 700), selected=False))
    plan = reflect.plan(elements, (0, 0, 100, 100), "horizontal")
    lines.append("Reflect horizontally in the box 0, 0, 100 x 100 (reflect.plan):")
    lines += [f"  {old.kind}: {old.position} -> {new.position}" + (f", scale {new.scale}" if new.scale else "") + ("" if old.selected else " (not selected)") for old, new in zip(elements, plan.elements)]
    lines += ["", "Distances between consecutive selected nodes (nodes.coordinates.measures):"]
    lines += [f"  {label}: dx {coordinates.number(dx)}, dy {coordinates.number(dy)}, length {coordinates.number(length)}, angle {angle:.1f} degrees" for label, dx, dy, length, angle in coordinates.measures(NODES)]
    return lines


def main() -> None:
    """Show the sample results; no font is needed."""
    notify(TITLE, "Sample outline math. Nothing was read or written.", "\n".join(explanation_lines()))


if __name__ == "__main__":
    main()
