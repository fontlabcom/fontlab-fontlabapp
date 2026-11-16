# this_file: Scripts/Masters/Background Samples Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Show App's background-layer maths and clearing plan on made-up layers.

What: Runs the pure parts of App's background tools on sample values and
prints the results: the Scale and Shift of node coordinates and component
matrices (Transform in fontlabapp.masters.background.model), the path-selection
rule (selected_paths), the numeric field check (numeric) and what Clear
Backgrounds would remove from a small made-up font in its all-layers and
masters-only scopes (plan in fontlabapp.masters.background.clear.model).
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is read from a font or written. The layers are plain values in
this script, no window opens and no background is created, changed or
removed. The native adapters and the panels (the Backend classes, run(),
show() and the Apply and Clear buttons of their panels) are never called. No
font, master, selection, history, preference, Output or clipboard is touched.
"""

TITLE = "Background Samples Demo"
POINTS = ((100.0, 200.0), (400.0, 650.0))
MATRIX = (1, 0, 0, 0, 1, 0, 50, 20, 1)  # an affine component placement at (50, 20)


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def transforms() -> list[str]:
    """Scale to 50 percent and Shift by 30 on two nodes and one component matrix."""
    from fly.ap.masters.background import model

    lines = []
    for mode, value in (("scale", 50), ("shift", 30)):
        operation = model.Transform(mode, value)
        lines.append(f"{mode} {value}: nodes {POINTS} -> {operation.points(POINTS)}; component x 50 -> {operation.component(MATRIX)[6]:g}")
    lines.append(f"Scale applied twice (repeat=2) to the first node: {model.Transform('scale', 50).points(POINTS[:1], repeat=2)}")
    lines.append(f"selected_paths((all, some, none, all)) -> {model.selected_paths(((True, True), (True, False), (False,), (True,)))}")
    for text in ("12.5", "twelve"):
        try:
            lines.append(f"numeric({text!r}) -> {model.numeric(text):g}")
        except ValueError as error:
            lines.append(f"numeric({text!r}) refused: {error}")
    return lines


def clearing() -> list[str]:
    """Glyph A has a master layer and an auxiliary layer, each with its own background."""
    from fly.ap.masters.background.clear import model

    def fore(identity: int, name: str, master: bool, background: int) -> object:
        return model.Layer(1, "A", identity, name, master, False, False, False, background)

    def mask(identity: int, name: str) -> object:
        return model.Layer(1, "A", identity, name, False, True, True, False, None)

    layers = (fore(1, "Regular", True, 2), mask(2, "Regular background"), fore(3, "Regular trial", False, 4), mask(4, "trial background"))
    source = model.Snapshot(("sample",), ("Regular",), layers, ())
    lines = []
    for scope, masters in (("All layers", False), ("Masters only", True)):
        removals = model.plan(source, masters)
        lines.append(f"{scope}: {', '.join(f'{r.glyph} / {r.mask_name} (owners {list(r.foreground_ids)})' for r in removals) or 'nothing'}")
    return lines


def main() -> None:
    """Show the sample results; no font is needed."""
    lines = []
    for heading, build in (("Scale and Shift", transforms), ("Clear Backgrounds plan", clearing)):
        lines += [heading + ":", *build(), ""]
    notify(TITLE, "Sample background results. Nothing was read or written.", "\n".join(lines))


if __name__ == "__main__":
    main()
