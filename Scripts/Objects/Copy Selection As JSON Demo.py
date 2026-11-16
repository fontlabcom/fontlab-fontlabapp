# this_file: Scripts/Objects/Copy Selection As JSON Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Copy Selection As JSON: put FontLab 9.1 object JSON on the clipboard.

What: in a Glyph window with selected shapes, copies those shapes of the
current layer; otherwise copies the glyphs selected in the Font window (or
the current glyph). Uses ``fontlabapp.objects.json_data.copy_objects``: it
puts the objects on the clipboard the way FontLab's own Copy does
(``flModelProducer.copyToClipboard``, FontLab's ``vic/objects`` formats
plus ``application/json``), so FontLab's Edit > Paste accepts them. A text
editor can still read the JSON.
Use: select glyphs or shapes and run. Then use Edit > Paste, or run Paste JSON
Glyphs Demo or Paste JSON Shapes Into Layer Demo, in this font or another one.
Safety: changes no font and records nothing for Undo. Needs FontLab 9.1 or
later; on 9.0 it says so and stops. Edit > Paste of copied glyphs was checked
live on 9.1.9812 (both masters, Font window and Glyph window); Paste of copied
shapes was not.
"""

TITLE = "Copy Selection As JSON"


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


def selection(fl, package) -> tuple[str, list]:
    """Return ``(label, objects)``: selected shapes of the current layer, else glyphs."""
    from fly.ap.core.scripting import names_selected_names
    from fly.ap.objects import json_data

    glyph, layer = json_data.current_layer(fl)
    shapes = [
        s
        for s in (layer.shapes if layer is not None else ())
        if getattr(s, "selected", False)
    ]
    if shapes:
        return f"selected shapes of {glyph.name}/{layer.name}", shapes
    glyphs = [
        g
        for g in (package.findName(n) for n in names_selected_names())
        if g is not None
    ]
    return "selected glyphs", glyphs


def main() -> None:
    """Copy the selection as object JSON and report what was copied."""
    import fly
    from fly.ap.core.scripting import current_package
    from fly.ap.objects import json_data

    if not json_data.available():
        notify(TITLE, json_data.NEEDS_91)
        return
    package = current_package()
    if package is None:
        notify(TITLE, "Open a font first. Nothing was copied.")
        return
    label, objects = selection(fly.fl, package)
    if not objects:
        notify(TITLE, "Select glyphs or shapes first. Nothing was copied.")
        return
    raw = json_data.copy_objects(package, objects)
    lines = json_data.describe(json_data.Envelope.parse(raw))
    notify(
        TITLE,
        f"Copied {len(objects)} {label} as object JSON ({len(raw)} bytes). Use Edit > Paste to paste them.",
        "\n".join(lines),
    )


if __name__ == "__main__":
    main()
