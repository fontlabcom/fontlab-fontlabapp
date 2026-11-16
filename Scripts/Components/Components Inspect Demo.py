# this_file: Scripts/Components/Components Inspect Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Summarise the components of the open font with App's read-only inspectors.

What: Reads every glyph of the open font through
fontlabapp.components.inspect.model and shows four short sections in one
message box: how many layers use components (with the first rows as CSV),
the bases used most often, missing bases, and the glyphs whose component
list differs between masters. The badge painters are
fontlabapp.components.inspect.views; the panel shell is
fontlabapp.components.inspect.ui.
Use: Open a font and run it. Click Show Details for the sections.
Safety: Read-only. It reads glyph names, layers and component lists and draws
nothing. It writes no font, master, selection, history, preference, Output or
clipboard. One failed section does not hide the others. With no font open it
only says so. At most 3000 glyphs are read.
"""

TITLE = "Components Inspect Demo"
MAX_GLYPHS = 3000
SHOWN = 5
PAINTERS = ("fontlabapp.components.inspect.ui", "fontlabapp.components.inspect.views")


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
    from fly.ap.components.inspect import model

    masters = list(package.masters)

    def layers() -> list[str]:
        rows = model.report(package, names, masters)
        return [f"{len(rows)} layers carry components"] + model.to_csv(rows[:SHOWN]).splitlines()

    def bases() -> list[str]:
        used = model.usage_index(package, names, masters)
        top = sorted(used, key=lambda base: (-len(used[base]), base))[:SHOWN]
        return [f"{base}: used by {len(used[base])} glyphs" for base in top] or ["No component bases"]

    def gaps() -> list[str]:
        groups = model.missing(package, names, masters)
        return [f"{base}: {len(rows)} layers (first: {rows[0][0]}, {rows[0][1]}, {rows[0][2]})" for base, rows in groups.items()][:SHOWN] or ["No missing bases"]

    def differences() -> list[str]:
        odd = [name for name, lists in model.component_lists(package, names, masters) if model.odd_masters(lists, masters)]
        return [f"{len(odd)} glyphs differ between masters: " + (", ".join(odd[:SHOWN * 2]) or "none")]

    result = []
    for heading, build in (("Layers with components", layers), ("Most used bases", bases), ("Missing bases", gaps), ("Master differences", differences)):
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
        notify(TITLE, "Open a font first. This demo reads its components.")
        return
    names = all_names()[:MAX_GLYPHS]
    lines = [f"{len(names)} glyphs read, masters: {', '.join(package.masters)}"]
    for heading, body in sections(package, names):
        lines += ["", heading + ":", *("  " + line for line in body)]
    lines += ["", "Panel and painters behind the Fly menu scripts: " + ", ".join(PAINTERS)]
    notify(TITLE, "Component summary of the open font. Nothing was changed.", "\n".join(lines))


if __name__ == "__main__":
    main()
