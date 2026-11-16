# this_file: Scripts/Objects/Object JSON Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Object JSON Demo: a read-only tour of FontLab 9.1 object JSON.

What: writes the selected glyphs, the current layer, its first shape and its
first contour as object JSON with ``fontlabapp.objects.json_data.export``,
then lists what each JSON holds, its size in bytes and whether FontLab reads
it back (``json_data.decode``) into the same number of objects.
Use: open a font, select glyphs (or open one in a Glyph window) and run.
Safety: changes nothing and records nothing for Undo; decoded objects are
detached copies. Needs FontLab 9.1 or later; on 9.0 it says so and stops.
"""

TITLE = "Object JSON Demo"


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


def samples(fl, package) -> list[tuple[str, list]]:
    """Return ``(label, objects)`` pairs to export: glyphs, layer, shape, contour."""
    from fly.ap.core.scripting import names_selected_names
    from fly.ap.objects import json_data

    glyphs = [
        g
        for g in (package.findName(n) for n in names_selected_names())
        if g is not None
    ]
    found = [("Selected glyphs", glyphs)] if glyphs else []
    glyph, layer = json_data.current_layer(fl)
    if glyph is None and glyphs:
        glyph = glyphs[0]
        layer = glyph.activeLayer  # flGlyph property, not a method
    if layer is not None:
        found.append((f"Layer {glyph.name}/{layer.name}", [layer]))
        shapes = list(layer.shapes)
        if shapes:
            found.append(("First shape", shapes[:1]))
            contours = list(shapes[0].contours)
            if contours:
                found.append(("First contour", contours[:1]))
    return found


def report(fl, package, json_data) -> list[str]:
    """Export each sample, describe it and check that FontLab reads it back."""
    lines = []
    for label, objects in samples(fl, package):
        raw = json_data.export(package, objects)
        envelope = json_data.Envelope.parse(raw)
        back = json_data.decode(raw)
        same = (
            "yes"
            if len(back) == len(objects)
            else f"no ({len(back)} of {len(objects)})"
        )
        lines += [
            f"{label}: {len(raw)} bytes, kinds {', '.join(envelope.kinds()) or 'none'}"
        ]
        lines += ["  " + line for line in json_data.describe(envelope)]
        lines += [f"  Read back by FontLab: {same}", ""]
    return lines


def main() -> None:
    """Run the read-only tour and show one report."""
    import fly
    from fly.ap.core.scripting import current_package
    from fly.ap.objects import json_data

    if not json_data.available():
        notify(TITLE, json_data.NEEDS_91)
        return
    package = current_package()
    if package is None:
        notify(TITLE, "Open a font first. Nothing was changed.")
        return
    lines = report(fly.fl, package, json_data)
    if not lines:
        notify(TITLE, "Select glyphs or open a glyph first. Nothing was changed.")
        return
    notify(TITLE, "Object JSON tour. Nothing was changed.", "\n".join(lines))


if __name__ == "__main__":
    main()
