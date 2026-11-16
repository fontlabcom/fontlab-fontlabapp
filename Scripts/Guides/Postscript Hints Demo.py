# this_file: Scripts/Guides/Postscript Hints Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Count the PostScript stem hints of the selected glyphs, master by master.

What: Reads the selected glyphs (or the current glyph) and, for every master
layer, shows how many horizontal and vertical PostScript hints it has
(fontlabapp.hints.postscript.hint_counts, which counts a hint by its role, as
FontLab's own remove-hints does). Plain guidelines are not counted.
Use: Open a font, select glyphs in a Font window and run it. Click Show Details
for the table. At most 20 glyphs are listed.
Safety: Read-only. It reads the guide lists of the selected layers and writes
no hint, guide, font, master, selection, history, preference, Output or
clipboard. With no font open, or with nothing selected, it only says so.

The separate hint-editing mini-app uses fontlabapp.studios.hint_tools for
its actions and fontlabapp.fontui.hint_tools for the window. Its original
panels are retained in fontlabapp.fontui.hint_autohint and
fontlabapp.fontui.hint_removal. This demo only describes that relationship;
it does not open those panels or run their editing actions.
"""

TITLE = "Postscript Hints Demo"
MAX_GLYPHS = 20


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def count_lines(package, glyphs: list) -> list[str]:
    """One line per glyph and master layer with its horizontal and vertical hints."""
    from fly.ap.hints.postscript import hint_counts

    lines = []
    for glyph in glyphs[:MAX_GLYPHS]:
        for master in package.masters:
            layer = glyph.findLayer(master)
            if layer is None or layer.isNull:
                continue
            try:
                horizontal, vertical = hint_counts(layer)
                lines.append(f"{glyph.name} / {master}: {horizontal} horizontal, {vertical} vertical")
            except (ValueError, RuntimeError) as error:
                lines.append(f"{glyph.name} / {master}: unreadable ({error})")
    return lines


def main() -> None:
    """Count the hints of the selection, or say what is missing."""
    from fly.ap.components.inspect.model import selected_glyphs
    from fly.ap.core.scripting import current_package

    package = current_package()
    if package is None:
        notify(TITLE, "Open a font and select glyphs first. This demo reads their hints.")
        return
    try:
        glyphs = selected_glyphs(package)
    except (ValueError, RuntimeError) as error:
        notify(TITLE, f"The selection could not be read: {error}")
        return
    if not glyphs:
        notify(TITLE, "Select glyphs in a Font window first. This demo reads their hints.")
        return
    notify(TITLE, f"Hint counts of {min(len(glyphs), MAX_GLYPHS)} glyphs. Nothing was changed.", "\n".join(count_lines(package, glyphs)))


if __name__ == "__main__":
    main()
