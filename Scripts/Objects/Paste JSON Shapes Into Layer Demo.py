# this_file: Scripts/Objects/Paste JSON Shapes Into Layer Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Paste JSON Shapes Into Layer: add shapes from object JSON to the current layer.

What: reads object JSON from the clipboard and adds its elements (shapes),
the shapes of its layers and its contours (joined into one new shape) to the
current layer of the current glyph with
``fontlabapp.objects.json_data.paste_shapes``. Glyph items are skipped; use
Paste JSON Glyphs Demo for those.
Use: copy shapes or contours with Copy Selection As JSON Demo, open the target
glyph in a Glyph window and run.
Safety: the pasted shapes are one Undo step. Nothing else in the glyph
changes. Needs FontLab 9.1 or later; on 9.0 it says so and changes nothing.
"""

TITLE = "Paste JSON Shapes Into Layer"


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
    """Paste the clipboard's shapes into the current layer and report."""
    import fly
    from fly.ap.core.history.glyphs import PartialWriteError, scan_auto_facts
    from fly.ap.core.scripting import current_package
    from fly.ap.objects import json_data

    if not json_data.available():
        notify(TITLE, json_data.NEEDS_91)
        return
    package = current_package()
    glyph, layer = (
        json_data.current_layer(fly.fl) if package is not None else (None, None)
    )
    if layer is None:
        notify(TITLE, "Open a glyph first. Nothing was changed.")
        return
    raw = json_data.read_clipboard()
    if raw is None:
        notify(TITLE, "The clipboard holds no object JSON. Nothing was changed.")
        return
    try:
        pasted = json_data.paste_shapes(
            layer, glyph, raw, facts=scan_auto_facts(package), title=TITLE
        )
    except PartialWriteError as error:
        notify(TITLE, json_data.PARTIAL_TEXT, str(error))
        return
    except (ValueError, RuntimeError) as error:
        notify(TITLE, f"Nothing was pasted: {error}")
        return
    lines = [f"Pasted: {item}" for item in pasted.created] + [
        f"Skipped: {item}" for item in pasted.skipped
    ]
    text = (
        f"{json_data.SHAPES_UNDO_TEXT}"
        if pasted.created
        else "No shapes to paste. Nothing was changed."
    )
    notify(TITLE, text, "\n".join(lines))


if __name__ == "__main__":
    main()
