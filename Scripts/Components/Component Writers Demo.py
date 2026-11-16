# this_file: Scripts/Components/Component Writers Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Show how App plans component edits, using a sample layer that is never written.

What: Builds two sample glyphs with three components in memory and prints the
preview rows and the Apply count that App's shared component writer
(fontlabapp.components.writer) computes when a script nudges every plain
component 10 units to the right: a scaled component is blocked, the offsets
are formatted for the table, and an eject is described as "contours +
components". It also shows the component description that the creation helper
(fontlabapp.components.creation) takes and names the panel base the real
scripts use (fontlabapp.components.panel.model).
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is written. The sample layer is made of plain Python objects,
no panel opens, nothing is applied or created and no font, master, selection,
history, preference, Output or clipboard is touched. The panel base shared by
App's component writer scripts is designed to write only when you press its
Apply button, as one Undo step; native Undo and Redo are still to be accepted
in FontLab.
"""

from types import SimpleNamespace

TITLE = "Component Writers Demo"
STEP = 10


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def sample_shape(number: int, base: str, dx: float, dy: float, scale: float = 1.0) -> SimpleNamespace:
    """A plain stand-in for a component shape with a translation and a uniform scale."""
    matrix = SimpleNamespace(
        m11=lambda: scale, m22=lambda: scale, m12=lambda: 0.0, m21=lambda: 0.0,
        dx=lambda: dx, dy=lambda: dy, isAffine=lambda: True,
    )
    return SimpleNamespace(id=number, isComponent=True, shapeData=SimpleNamespace(componentGlyph=base), transform=matrix)


def explanation_lines() -> list[str]:
    """Rows and counts computed by the real writer for the sample layer."""
    import fly.ap.components.writer as writer
    from fly.ap.components.creation import NewComponent

    def glyph_of(name: str, *shapes: SimpleNamespace) -> SimpleNamespace:
        layer = SimpleNamespace(isNull=False, autoLayer=False, name="Regular", shapes=list(shapes))
        return SimpleNamespace(name=name, findLayer=lambda master: layer)

    glyphs = [
        glyph_of("aacute", sample_shape(1, "acute", 120, 600), sample_shape(2, "dotaccent", -40, 0)),
        glyph_of("ccedilla", sample_shape(3, "cedilla", 30, -10, scale=0.5)),
    ]

    def planner(_glyph, _master, current) -> list:
        rows = []
        for shape in writer.components(current):
            x, y = writer.offset(shape)
            new = f"{writer.fmt(x + STEP)}, {writer.fmt(y)}"
            if writer.plain_move(shape):
                rows.append(writer.Change(writer.base_of(shape), writer.offset_text((x, y)), new, (shape.id, (x + STEP, y))))
            else:
                rows.append(writer.Change(writer.base_of(shape), writer.offset_text((x, y)), new, problem="scaled or turned, not a plain move"))
        return rows

    plan = writer.collect(glyphs, ["Regular"], planner)
    lines = [f"Two sample glyphs; the plan moves each plain component by {STEP} units (components.writer.collect):"]
    lines += [f"  {label}: {change.name} {change.old} -> {change.new}" + (f"  [blocked: {change.problem}]" if change.problem else "") for label, change in plan.rows]
    lines.append(f"  Layers to write: {len(plan.work)}. A blocked row keeps its whole layer out of the work list; problems: {plan.problems or 'none'}.")
    lines += ["", "Eject one level of a component (Decompose, Nested Finder) would give " + writer.parts_text(3, 1) + " and " + writer.parts_text(1, 0) + "."]
    lines += ["", "Creation helper input, built but never used to create anything: " + repr(NewComponent("acute", "Regular", 120, 600))]
    lines.append("Real scripts call components.creation.build_components before the Undo step and add_component inside it.")
    lines.append("Panel base of the real scripts: fontlabapp.components.panel.model.panel_type")
    return lines


def main() -> None:
    """Show the sample plan; no font is needed and nothing is written."""
    notify(TITLE, "Sample component plan. Nothing was written.", "\n".join(explanation_lines()))


if __name__ == "__main__":
    main()
