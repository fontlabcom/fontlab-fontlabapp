# this_file: Scripts/Objects/Import Glyphs From JSON File Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Import Glyphs From JSON File: create new glyphs from an object JSON file.

What: reads a file written by Export Glyphs To JSON File Demo (or any FontLab
object JSON) with ``fontlabapp.objects.json_data.load_file`` and creates its
glyphs as new glyphs with ``json_data.paste_glyphs``: taken names get
``.1``, ``.2``, ..., widths and outlines come from the JSON layer named like
each master. Existing glyphs are never changed.
Use: open the target font, run and choose the file.
Safety: each new glyph is its own Undo step (FontLab's Add Glyph) and the
outlines are one more Undo step. A file that is not object JSON changes
nothing. Needs FontLab 9.1 or later; on 9.0 it says so and changes nothing.
"""

TITLE = "Import Glyphs From JSON File"
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
    """Ask for a file and create its glyphs in the current font."""
    import fly
    from fly.ap.core.history.glyphs import PartialWriteError, scan_auto_facts
    from fly.ap.core.scripting import current_package
    from fly.ap.objects import json_data

    if not json_data.available():
        notify(TITLE, json_data.NEEDS_91)
        return
    package = current_package()
    if package is None:
        notify(TITLE, "Open a font first. Nothing was changed.")
        return
    path = fly.qt.QtGui.QFileDialog.getOpenFileName(
        fly.fl.MainWindow(), TITLE, "", FILTER
    )
    if not path:
        return
    try:
        raw = json_data.load_file(str(path))
        pasted = json_data.paste_glyphs(
            package, raw, facts=scan_auto_facts(package), title=TITLE
        )
    except PartialWriteError as error:
        notify(TITLE, json_data.PARTIAL_TEXT, str(error))
        return
    except (OSError, ValueError, RuntimeError) as error:
        notify(TITLE, f"Nothing was imported: {error}")
        return
    lines = ["Created: " + (", ".join(pasted.created) or "nothing")]
    lines += [f"Note: {n}" for n in pasted.notes] + [
        f"Skipped: {s}" for s in pasted.skipped
    ]
    notify(
        TITLE,
        f"Created {len(pasted.created)} glyphs. {json_data.GLYPHS_UNDO_TEXT}",
        "\n".join(lines),
    )


if __name__ == "__main__":
    main()
