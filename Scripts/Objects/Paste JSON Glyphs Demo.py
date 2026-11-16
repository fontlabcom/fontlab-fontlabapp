# this_file: Scripts/Objects/Paste JSON Glyphs Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Paste JSON Glyphs: create new glyphs from object JSON on the clipboard.

What: reads object JSON from the clipboard (``json_data.read_clipboard``)
and creates its glyphs in the current font with
``fontlabapp.objects.json_data.paste_glyphs``. Names already in the font
get ``.1``, ``.2``, ... (renamed glyphs lose their Unicode values). Each
master gets the width and outlines of the JSON layer with the same name;
JSON from a one-master font fills every master. Existing glyphs are never
changed.
Use: run Copy Selection As JSON Demo (or put object JSON on the clipboard), open
the target font and run.
Safety: each new glyph is its own Undo step (FontLab's Add Glyph) and the
outlines are one more Undo step. Bad data is rejected before any change.
Needs FontLab 9.1 or later; on 9.0 it says so and changes nothing.
"""

TITLE = "Paste JSON Glyphs"


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


def pasted_lines(pasted) -> list[str]:
    """Report lines for a ``json_data.Pasted`` result."""
    lines = ["Created: " + (", ".join(pasted.created) or "nothing")]
    lines += [f"Note: {note}" for note in pasted.notes]
    lines += [f"Skipped: {item}" for item in pasted.skipped]
    return lines


def main() -> None:
    """Paste the clipboard's glyphs as new glyphs and report the result."""
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
    raw = json_data.read_clipboard()
    if raw is None:
        notify(TITLE, "The clipboard holds no object JSON. Nothing was changed.")
        return
    try:
        pasted = json_data.paste_glyphs(
            package, raw, facts=scan_auto_facts(package), title=TITLE
        )
    except PartialWriteError as error:
        notify(TITLE, json_data.PARTIAL_TEXT, str(error))
        return
    except (ValueError, RuntimeError) as error:
        notify(TITLE, f"Nothing was pasted: {error}")
        return
    notify(
        TITLE,
        f"Created {len(pasted.created)} glyphs. {json_data.GLYPHS_UNDO_TEXT}",
        "\n".join(pasted_lines(pasted)),
    )


if __name__ == "__main__":
    main()
