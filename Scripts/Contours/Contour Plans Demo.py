# this_file: Scripts/Contours/Contour Plans Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Preview App's Angularizzle, Raise Ascender and Node Duplicator plans on samples.

What: Runs the detached planners behind three App contour tools on made-up
data and prints what each would do: Angularizzle turns a rounded path into
straight segments (fontlabapp.contours.angularizzle.model), Raise Ascender moves
the nodes above the x-height of every repeated layer occurrence
(fontlabapp.contours.raise_ascender.model) and Node Duplicator copies selected
nodes in three profiles (fontlabapp.contours.nodes.duplicator.model).
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is edited. The paths, layers and nodes are plain values in this
script; the real tools (and the settings Angularizzle saves when you press its
Process button) are not opened, so no font, master, selection, history,
preference, Output or clipboard is touched.
"""

TITLE = "Contour Plans Demo"
PLANE = 20
AMOUNT = 20


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def angularizzle_lines() -> list[str]:
    """A square with one rounded corner, sampled at minimum plane 20."""
    from fly.ap.contours.angularizzle import model

    segments = (model.Segment(((0, 0), (100, 0))), model.Segment(((100, 0), (100, 60), (60, 100), (0, 100))), model.Segment(((0, 100), (0, 0))))
    path = model.Path(segments)
    full = model.angularize((path,), PLANE)[0]
    lean = model.angularize((path,), PLANE, keep_detail=False)[0]
    return [f"Path length {full.length:.1f}: {len(full.points)} samples with detail, {len(lean.points)} without; {len(model.line_nodes(full))} straight nodes would be drawn."]


def raise_lines() -> list[str]:
    """One layer seen twice: the second occurrence starts from the raised nodes."""
    from fly.ap.contours.raise_ascender import model

    layer = model.Layer("Regular", 500, (model.Point(0, 700), model.Point(10, 520), model.Point(20, 400)))
    steps = model.plan((layer, layer), AMOUNT)
    return [f"Step {number}: {step.changed} nodes move, y values {[point.y for point in step.before]} -> {[point.y for point in step.after]}" for number, step in enumerate(steps, 1)]


def duplicator_lines() -> list[str]:
    """Duplicate the last node of a triangle in the three profiles."""
    from fly.ap.contours.nodes.duplicator import model

    nodes = tuple(model.Node(key, x, y, "line", 0, "", ()) for key, (x, y) in enumerate(((0, 0), (100, 0), (100, 100)), 1))
    layer = model.Layer(10, 1, (model.Path(1, nodes, True),))
    source = model.Source((layer,), (10,), ((0, 2),), True)
    lines = []
    for mode in ("current", "handles", "all"):
        result = model.plan(source, mode)
        lines.append(f"{mode}: {result.inserted} insertions " + str([(op.index, op.node.kind) for op in result.operations]))
    return lines


def explanation_lines() -> list[str]:
    """The three planners, run on fixed sample data that they accept."""
    lines = []
    for heading, build in (("Angularizzle", angularizzle_lines), ("Raise Ascender by 20 above x-height 500", raise_lines), ("Node Duplicator on the third node", duplicator_lines)):
        lines += [heading + ":", *("  " + line for line in build()), ""]
    return lines


def main() -> None:
    """Show the sample plans; no font is needed and nothing is edited."""
    notify(TITLE, "Sample contour tool plans. Nothing was edited.", "\n".join(explanation_lines()))


if __name__ == "__main__":
    main()
