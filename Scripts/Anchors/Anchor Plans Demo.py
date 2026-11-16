# this_file: Scripts/Anchors/Anchor Plans Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Show what App's anchor writers plan, using sample anchors that are never written.

What: Builds two sample layers in memory and prints the plans that App's anchor
tools compute for them: Center (fontlabapp.anchors.coordinates.model), Round
to a grid, the anchor copy plan (fontlabapp.anchors.copy.model) and the preview
rows and Apply count of the shared writer (fontlabapp.anchors.writer). It also
names the modules that write after you press Apply in a real anchor panel
(fontlabapp.anchors.panel.model, fontlabapp.anchors.edit).
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is written. The sample layers are plain Python objects, no
panel opens, nothing is applied and no font, master, selection, history,
preference, Output or clipboard is touched. The panel base shared by App's
anchor writer scripts (fontlabapp.anchors.panel.model) is designed to write
only when you press its Apply button, as one Undo step; native Undo and Redo
are still to be accepted in FontLab.
"""

from types import SimpleNamespace

TITLE = "Anchor Plans Demo"
MODULES = (
    "fontlabapp.anchors.coordinates.model",
    "fontlabapp.anchors.copy.model",
    "fontlabapp.anchors.writer",
    "fontlabapp.anchors.panel.model",
    "fontlabapp.anchors.edit",
)


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def sample_layer(width: int, **anchors: tuple[int, int]) -> SimpleNamespace:
    """A plain stand-in for a layer: advance width and named anchors."""
    pins = [SimpleNamespace(name=name, point=SimpleNamespace(x=lambda x=x: x, y=lambda y=y: y)) for name, (x, y) in anchors.items()]
    return SimpleNamespace(isNull=False, autoLayer=False, advanceWidth=width, anchors=pins)


def explanation_lines() -> list[str]:
    """Plans for two sample layers, computed by the real App functions."""
    import fly.ap.anchors.writer as writer
    from fly.ap.anchors.coordinates import model as coordinates
    from fly.ap.anchors.copy import model as copy

    source = sample_layer(500, top=(183, 704), bottom=(262, -3))
    target = sample_layer(600, top=(100, 650))
    glyph = SimpleNamespace(name="a", findLayer=lambda master: source)
    names = ["top", "bottom"]

    def planner(_glyph, _master, layer) -> list:
        return [
            writer.Change(name, f"{old[0]}, {old[1]}", f"{new}, {old[1]}", ("set", name, (new, old[1])))
            for name, old, new in coordinates.center_plan(layer, names, "advance", 0.5, 0)
        ]

    plan = writer.collect([glyph], ["Regular"], planner)
    lines = ["Sample layer: advance 500, anchors top (183, 704) and bottom (262, -3).", "", "Center on the advance (coordinates.model.center_plan):"]
    lines += [f"  {label}: {change.name} {change.old} -> {change.new}" for label, change in plan.rows]
    lines.append(f"  Apply would write {writer.plural(plan.anchors, 'anchor')} on {writer.plural(len(plan.work), 'layer')} as one Undo step.")
    lines += ["", "Round to a 10 unit grid (coordinates.model.round_plan):"]
    lines += [f"  {name}: {old} -> {new}" for name, old, new in coordinates.round_plan(source, 10, True, True, [])]
    lines.append(f"  Half ties go up: snap(15, 10) = {coordinates.snap(15, 10)}, snap(-15, 10) = {coordinates.snap(-15, 10)}")
    lines += ["", "Copy anchors to a 600 unit wide glyph, scaled and replacing (copy.model.plan):"]
    lines += [f"  {name}: {old} -> {new}" for name, old, new in copy.plan(source, target, True, True)]
    lines += ["", f"FontLab cannot Redo an anchor moved to 0, 0, so writer.on_origin((0, 0)) is {writer.on_origin((0, 0))} and the tool refuses it."]
    lines += ["", "Modules behind the real panels: " + ", ".join(MODULES)]
    return lines


def main() -> None:
    """Show the sample plans; no font is needed and nothing is written."""
    notify(TITLE, "Sample anchor plans. Nothing was written.", "\n".join(explanation_lines()))


if __name__ == "__main__":
    main()
