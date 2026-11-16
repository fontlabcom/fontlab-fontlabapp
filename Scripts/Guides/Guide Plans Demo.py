# this_file: Scripts/Guides/Guide Plans Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Show how App plans glyph guides, with sample records that are never written.

What: Prints, for made-up guides, what the planning code of App's guide tools
returns: the guide grid records (fontlabapp.guides.inspect.model), how guide
records are filtered, scaled to another width and parsed from table rows
(fontlabapp.guides.records), and the guides that Perpendicular Guides would add
for three nodes and one component (fontlabapp.guides.perpendicular.model). It
names the modules that write guides in the real tools: the writers in
fontlabapp.guides.rewrite.model and the dialog shell in
fontlabapp.guides.rewrite.ui, whose Close and Apply buttons the shell itself creates.
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is written. The records are plain values in this script, no
panel opens, no guide is added, replaced or cleared and no font, master,
selection, history, preference, Output or clipboard is touched. Note that App's
real Perpendicular Guides action (fontlabapp.guides.perpendicular.model.run)
adds its guides at once from its menu entry, as one history step, with no
preview; this demo never calls it.
"""

import math

TITLE = "Guide Plans Demo"
NODES = ((1, 0.0, 0.0), (2, 100.0, 0.0), (3, 50.0, 80.0))
COMPONENTS = ((7, 200.0, 0.0, 100.0, 200.0),)
MODULES = ("fontlabapp.guides.rewrite.model", "fontlabapp.guides.rewrite.ui")


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def explanation_lines() -> list[str]:
    """Results of the real planners for the sample guides."""
    import fly.ap.guides.records as records
    from fly.ap.guides.inspect import model as guide_model
    from fly.ap.guides.perpendicular import model as perpendicular

    grid = guide_model.grid(0, 0, 250, 2)
    lines = ["Grid of 2 steps of 250 units (inspect.model.grid), as (x, y, angle, name):", *(f"  {record}" for record in grid), ""]
    lines.append("Filter 'Horizontal' with name text '2' keeps: " + str([record[3] for record in grid if records.matches(record, "Horizontal", "2")]))
    lines.append("Filter 'Vertical' keeps: " + str([record[3] for record in grid if records.matches(record, "Vertical", "")]))
    tilted = (50.0, 0.0, 45.0, "Slant")
    lines.append(f"Scaling to a glyph 1.2 times as wide (records.scaled): {records.scaled(grid[3], 1.2)} and {records.scaled(tilted, 1.2)} ({records.direction_of(tilted)})")
    lines.append("Table row parsed (180 degrees becomes 0 and x is zeroed): " + str(records.parse_row(["Regular", "12", "7", "180", " top "], 0)))
    try:
        records.parse_row(["Regular", "x", "7", "0", ""], 2)
    except ValueError as error:
        lines.append(f"A bad row is refused before any write: {error}")
    additions, messages = perpendicular.plan(NODES, COMPONENTS)
    lines += ["", "Perpendicular Guides for 3 nodes and 1 component (perpendicular.model.plan):"]
    lines += [f"  guide through ({x:g}, {y:g}) at {math.degrees(angle) % 180:.1f} degrees" for x, y, angle in additions]
    lines.append(f"  messages: {list(messages) or 'none'}; with one node only: {perpendicular.plan(NODES[:1], ())[1]}")
    lines += ["", "Write side, needs FontLab so not run here: " + ", ".join(MODULES)]
    return lines


def main() -> None:
    """Show the sample plans; no font is needed and nothing is written."""
    notify(TITLE, "Sample guide plans. Nothing was written.", "\n".join(explanation_lines()))


if __name__ == "__main__":
    main()
