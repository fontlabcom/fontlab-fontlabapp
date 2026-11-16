# this_file: Scripts/Contours/Transform Studio Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Transform Studio: transform, slant, rotate and reflect glyph outlines.

What: Opens the Transform Studio window (fontlabapp.studios.transform_studio)
for the current font. A TGlyph preview sits on top. Transform scales, skews,
rotates and moves whole layers about a chosen origin; Slant shears about a
pivot height, or uses smart slant with optional sidebearing compensation;
Rotate & reflect turns or mirrors the selected nodes or components.
Use: Open a font, type glyph names or use the font selection, then press a
Preview button to see the planned rows and a ghost outline, or the action
button to write.
Safety: Writes go to the explicit layer of the selected preview master (or every
master), one named Undo step ("Transform Studio: ..."), and are read back; a
change FontLab rounds away is reported as "Partly applied". Auto layers are
skipped; hinted layers are refused unless you tick "Edit hinted layers anyway"
or remove PostScript hints. Previews never write. With no font open the window
says so.

Related transform tabs are composed by fontlabapp.fontui.outline_studios;
fontlabapp.fontui.raise_ascender supplies its ascender controls and
fontlabapp.fontui.superaligner preserves the original alignment operation.
These are source references, not additional operations run by this demo.
"""

TITLE = "Transform Studio Demo"


def main() -> None:
    """Open Transform Studio, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.transform_studio import show

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
            f"Transform Studio did not open: {error}",
            "Warning",
            kind.Ok,
        )


if __name__ == "__main__":
    main()
