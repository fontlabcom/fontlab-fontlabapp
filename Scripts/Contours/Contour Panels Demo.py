# this_file: Scripts/Contours/Contour Panels Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Explain what App's contour selection, transform and writer panels plan.

What: Shows, for made-up contours, what the plans of App's contour panels
contain before anything is applied: which nodes the three selection actions
would select (fontlabapp.contours.selection.model), the area of a contour,
the outline before and after a slant and the preview scale that the transform
panel uses (fontlabapp.contours.transform.model), and the number format of the
shared writer (fontlabapp.contours.writer). It also names the panel and copy
modules that need FontLab (fontlabapp.contours.panel.model,
fontlabapp.contours.selection.panel.model, fontlabapp.contours.copy).
Use: Run it from the Scripts menu and click Show Details. No font is needed.
The area line needs the fontTools package; without it that line says so.
Safety: Nothing is selected, transformed or written. The contours are plain
values in this script, no panel opens and no font, master, selection, history,
preference, Output or clipboard is touched. The panel base shared by App's
contour writer scripts (fontlabapp.contours.panel.model) and the selection
panel base (fontlabapp.contours.selection.panel.model, used by Shadow Copy,
Outline Effect and the hint scripts) are designed to write the font only when
you press their action button, as one Undo step (native Undo and Redo are
still to be accepted in FontLab). Select Small Contours
(fontlabapp.contours.selection.native) changes only the node selection.
"""

from types import SimpleNamespace

TITLE = "Contour Panels Demo"
SQUARE = [(0, 0, True), (100, 0, True), (100, 100, True), (0, 100, True)]
SLANT = (1.0, 0.0, 0.2, 1.0, 0.0, 0.0)
MODULES = (
    "fontlabapp.contours.panel.model",
    "fontlabapp.contours.selection.panel.model",
    "fontlabapp.contours.selection.native",
    "fontlabapp.contours.copy",
)


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def selection_lines() -> list[str]:
    """The three selection plans for three sample contours (True means selected)."""
    from fly.ap.contours.selection import model

    paths = (model.Path((False, True, False)), model.Path((False, False)), model.Path((True, False, False)))
    lines = ["Selected nodes now, per contour (x is selected): " + "; ".join("".join("x" if on else "." for on in path.selected) for path in paths)]
    for mode in ("contours", "partial"):
        plan = model.plan(paths, mode)
        lines.append(f"  {mode}: " + "; ".join("".join("x" if on else "." for on in row) for row in plan.nodes) + f" ({plan.paths} contours chosen)")
    small = model.plan((model.Path((False,) * 3, 90.0), model.Path((False,) * 2, 4000.0)), "small", "100")
    lines.append(f"  small, below 100 square units: {small.nodes}; other selection cleared: {small.clear_other}")
    try:
        square = tuple((SQUARE[i][:2], SQUARE[(i + 1) % 4][:2]) for i in range(4))
        lines.append(f"  Area of the 100 x 100 square: {model.unsigned_area(square):g}")
    except RuntimeError as error:
        lines.append(f"  Area unavailable: {error}")
    try:
        model.threshold("lots")
    except ValueError as error:
        lines.append(f"  Bad input is refused: {error}")
    return lines


def transform_lines() -> list[str]:
    """A slanted square and the preview scale of a 120 x 120 widget."""
    import fly.ap.contours.writer as writer
    from fly.ap.contours.transform import model

    slanted = model.mapped([SQUARE], SLANT)[0]
    box = SimpleNamespace(x=lambda: 0, y=lambda: 0, width=lambda: 100, height=lambda: 100)
    scale, _b, _c, _d, dx, dy = model.fit(box, 120, 120)
    return [
        "Slant of 0.2 maps the square corners to " + ", ".join(f"({writer.fmt(x)}, {writer.fmt(y)})" for x, y, _ in slanted),
        f"Preview scale in a 120 x 120 widget: {scale:g}, offset {dx:g}, {dy:g}",
    ]


def explanation_lines() -> list[str]:
    """Selection and transform sections, then the modules that need FontLab."""
    lines = ["Selection plans (selection.model.plan):", *selection_lines(), ""]
    lines += ["Transform preview (transform.model.mapped and fit):", *transform_lines(), ""]
    return lines + ["Needs FontLab, so not run here: " + ", ".join(MODULES)]


def main() -> None:
    """Show the sample plans; no font is needed and nothing is applied."""
    notify(TITLE, "Sample contour panel plans. Nothing was applied.", "\n".join(explanation_lines()))


if __name__ == "__main__":
    main()
