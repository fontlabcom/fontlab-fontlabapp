# this_file: Scripts/Masters/Layer Manager Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Layer Manager: copy between masters, twins, backups, intermediate layers, clean-up and delivery.

What: Opens the Layer Manager window (fontlabapp.studios.layer_manager)
for the current font. A control-less TGlyph preview sits on the right.
Copy between masters replaces chosen master layers from one source master;
Twins copies contours, components, anchors or metrics from one master to
another; Backups backs up the current layer, restores a backup or uses a
layer as the master; Intermediate adds interpolated layers at a location;
Clean-up deletes ticked extra layers or empty layers; Deliver copies glyphs
or mapped layers from another open font into the current one.
Use: Open a font, select glyphs in the Font window and run it. Every tab
lists its plan first; choose a row to see that glyph and layer in the
preview.
Safety: Opening the window, changing a control and choosing a row change
nothing in the font. Apply checks the font again and refuses a plan that
differs from the list on screen. Each Apply is one named Undo step
("Layer Manager: ..."); Deliver adds each missing glyph with FontLab's Add
Glyph first, one Undo step per glyph. The source font of Deliver is only
read. With no font open the window opens without a preview and says so.
"""

TITLE = "Layer Manager Demo"


def main() -> None:
    """Open Layer Manager, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.layer_manager import show

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(
            qt,
            parent,
            TITLE,
            f"Layer Manager did not open: {error}",
            "Warning",
            kind.Ok,
        )


if __name__ == "__main__":
    main()
