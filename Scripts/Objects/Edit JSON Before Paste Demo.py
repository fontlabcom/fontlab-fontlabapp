# this_file: Scripts/Objects/Edit JSON Before Paste Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Edit JSON Before Paste Demo: change object JSON in Python, then create glyphs.

What: writes the selected glyphs as object JSON, then edits the JSON with
``fontlabapp.objects.json_data`` helpers before FontLab reads it: every
glyph is renamed with a ``.json`` suffix (``rename_glyphs``), Unicode values
are dropped (``drop_unicodes``) and every layer width is set to 600
(``set_advance_width``). Then ``json_data.paste_glyphs`` creates the edited
copies as new glyphs, with ``.1``, ``.2``, ... if a name is still taken.
Use: select a few glyphs and run; compare ``o`` with the new ``o.json``.
Safety: the selected glyphs do not change. Each new glyph is its own Undo
step (FontLab's Add Glyph) and the outlines are one more Undo step. Needs
FontLab 9.1 or later; on 9.0 it says so and changes nothing.
"""

TITLE = "Edit JSON Before Paste Demo"
SUFFIX = ".json"
WIDTH = 600


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


def edited(json_data, raw: bytes):
    """Return the envelope with renamed glyphs, no Unicode values and width ``WIDTH``."""
    envelope = json_data.only_glyphs(json_data.Envelope.parse(raw))
    envelope = json_data.rename_glyphs(envelope, lambda name: name + SUFFIX)
    envelope = json_data.drop_unicodes(envelope)
    return json_data.set_advance_width(envelope, WIDTH)


def main() -> None:
    """Export the selection, edit the JSON and paste the edited glyphs."""
    from fly.ap.core.history.glyphs import PartialWriteError, scan_auto_facts
    from fly.ap.core.scripting import current_package, names_selected_names
    from fly.ap.objects import json_data

    if not json_data.available():
        notify(TITLE, json_data.NEEDS_91)
        return
    package = current_package()
    if package is None:
        notify(TITLE, "Open a font first. Nothing was changed.")
        return
    glyphs = [
        g
        for g in (package.findName(n) for n in names_selected_names())
        if g is not None
    ]
    if not glyphs:
        notify(TITLE, "Select glyphs first. Nothing was changed.")
        return
    envelope = edited(json_data, json_data.export(package, glyphs))
    lines = ["Edited JSON:"] + ["  " + line for line in json_data.describe(envelope)]
    try:
        pasted = json_data.paste_glyphs(
            package, envelope, facts=scan_auto_facts(package), title=TITLE
        )
    except PartialWriteError as error:
        notify(TITLE, json_data.PARTIAL_TEXT, str(error))
        return
    except (ValueError, RuntimeError) as error:
        notify(TITLE, f"Nothing was pasted: {error}", "\n".join(lines))
        return
    lines += ["", "Created: " + (", ".join(pasted.created) or "nothing")]
    lines += [f"Note: {n}" for n in pasted.notes] + [
        f"Skipped: {s}" for s in pasted.skipped
    ]
    notify(
        TITLE,
        f"Created {len(pasted.created)} edited glyphs. {json_data.GLYPHS_UNDO_TEXT}",
        "\n".join(lines),
    )


if __name__ == "__main__":
    main()
