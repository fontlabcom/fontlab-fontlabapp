# this_file: Scripts/Anchors/Anchors Inspect Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Summarise the anchors of the open font with App's read-only anchor inspectors.

What: Reads every glyph of the open font through
fontlabapp.anchors.inspect.model and shows four short sections in one message
box: the most common anchor names, how many glyphs are bases (plain anchors)
and marks (_anchors) on the current master, the glyphs whose anchor names
differ between masters, and where the first mark attaches to the first base.
The painters that draw this as clouds and attachment previews are
fontlabapp.anchors.inspect.views; the panel shell is
fontlabapp.anchors.inspect.ui.
Use: Open a font and run it. Click Show Details for the sections.
Safety: Read-only. It reads glyph names, layers and anchor positions and draws
nothing. It writes no font, master, selection, history, preference, Output or
clipboard. One failed section does not hide the others. With no font open it
only says so. At most 3000 glyphs are read.
"""

TITLE = "Anchors Inspect Demo"
MAX_GLYPHS = 3000
SHOWN = 10
PAINTERS = ("fontlabapp.anchors.inspect.ui", "fontlabapp.anchors.inspect.views")


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def sections(package, names: list[str]) -> list[tuple[str, list[str]]]:
    """Build each section on its own so that one failure keeps the others."""
    from fly.ap.anchors.inspect import model

    masters, master = list(package.masters), package.master

    def common() -> list[str]:
        glyphs = [glyph for glyph in (package.findName(name) for name in names) if glyph is not None]
        found = model.anchor_names(glyphs, masters)
        return [", ".join(found[:SHOWN]) + (" ..." if len(found) > SHOWN else "") or "No anchors"]

    def classes() -> list[str]:
        bases, marks = model.classify(package, names, master)
        return [f"{len(bases)} base glyphs, {len(marks)} mark glyphs on {master}"]

    def mismatches() -> list[str]:
        odd = [name for name, sets in model.anchor_sets(package, names, masters) if model.is_mismatch(sets)]
        return [f"{len(odd)} glyphs differ between masters: " + (", ".join(odd[:SHOWN]) or "none")]

    def attachment() -> list[str]:
        bases, marks = model.classify(package, names, master)
        if not bases or not marks:
            return ["Needs a glyph with plain anchors and a glyph with _anchors."]
        base, mark = bases[0], marks[0]
        shared = model.families(model.attachment_layer_of(package, base, master), model.attachment_layer_of(package, mark, master))
        if not shared:
            return [f"{mark} shares no anchor family with {base}."]
        dx, dy = model.attachment(model.attachment_layer_of(package, base, master), model.attachment_layer_of(package, mark, master), shared[0])
        return [f"{mark} attaches to {base} through '{shared[0]}' by moving {dx}, {dy}"]

    result = []
    for heading, build in (("Common anchor names", common), ("Bases and marks", classes), ("Master differences", mismatches), ("First attachment", attachment)):
        try:
            result.append((heading, build()))
        except (ValueError, RuntimeError) as error:
            result.append((heading, [f"Unavailable: {error}"]))
    return result


def main() -> None:
    """Summarise the open font, or say that a font is needed."""
    from fly.ap.core.scripting import current_package
    from fly.ap.masters.inspect.model import all_names

    package = current_package()
    if package is None:
        notify(TITLE, "Open a font first. This demo reads its anchors.")
        return
    names = all_names()[:MAX_GLYPHS]
    report = sections(package, names)
    lines = [f"{len(names)} glyphs read, masters: {', '.join(package.masters)}"]
    for heading, body in report:
        lines += ["", heading + ":", *("  " + line for line in body)]
    lines += ["", "Panel and painters behind the Fly menu scripts: " + ", ".join(PAINTERS)]
    notify(TITLE, "Anchor summary of the open font. Nothing was changed.", "\n".join(lines))


if __name__ == "__main__":
    main()
