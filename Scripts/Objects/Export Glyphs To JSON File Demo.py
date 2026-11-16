# this_file: Scripts/Objects/Export Glyphs To JSON File Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Export Glyphs To JSON File: save the selected glyphs as object JSON.

What: writes the glyphs selected in the Font window (or the current glyph)
with ``fontlabapp.objects.json_data.export`` and saves them, pretty-printed
UTF-8, with ``json_data.save_file`` to a file you choose.
Use: select glyphs, run, choose a file name. Import Glyphs From JSON File Demo
reads the file back into this font or another one.
Safety: changes no font and records nothing for Undo; only the chosen file
is written. Needs FontLab 9.1 or later; on 9.0 it says so and stops.
"""

TITLE = "Export Glyphs To JSON File"
FILTER = "Object JSON (*.json);;All files (*)"


def notify(title: str, text: str, details: str = "") -> None:
    """Show a modal report box."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(
        qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details
    )
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def main() -> None:
    """Ask for a file and save the selected glyphs to it."""
    import fly
    from fly.ap.core.scripting import current_package, names_selected_names
    from fly.ap.objects import json_data

    if not json_data.available():
        notify(TITLE, json_data.NEEDS_91)
        return
    package = current_package()
    if package is None:
        notify(TITLE, "Open a font first. Nothing was saved.")
        return
    glyphs = [
        g
        for g in (package.findName(n) for n in names_selected_names())
        if g is not None
    ]
    if not glyphs:
        notify(TITLE, "Select glyphs first. Nothing was saved.")
        return
    path = fly.qt.QtGui.QFileDialog.getSaveFileName(
        fly.fl.MainWindow(), TITLE, "glyphs.json", FILTER
    )
    if not path:
        return
    saved = json_data.save_file(str(path), json_data.export(package, glyphs))
    lines = json_data.describe(json_data.Envelope.parse(saved.read_bytes()))
    notify(TITLE, f"Saved {len(glyphs)} glyphs to {saved.name}.", "\n".join(lines))


if __name__ == "__main__":
    main()
