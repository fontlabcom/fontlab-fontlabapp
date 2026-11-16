# this_file: Scripts/Anchors/Anchor Studio Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Anchor Studio: place, align, rename, clean up and inspect anchors.

What: Opens the Anchor Studio window (fontlabapp.studios.anchor_studio) for
the current font. A TGlyph preview sits on top. Place puts top/bottom/_top/
_bottom anchors at the ink edges; Align centres, snaps to a metric, rounds to a
grid or centres "top" optically; Rename & delete renames by text or regular
expression and deletes ticked names; Clean-up removes duplicate and extraneous
anchors; Overlays shows an anchor cloud and rings around stacked anchors.
Use: Open a font, type glyph names or use the font selection, then press a
Preview button to see the planned rows, or the action button to write.
Safety: Writes go to the explicit layer of the selected preview master (or every
master), one named Undo step ("Anchor Studio: ..."), and are read back; a move
FontLab rounds away is reported as "Partly applied". Auto and hinted layers
are skipped until you remove PostScript hints. Overlays are read-only. With no
font open the window says so.
"""

TITLE = "Anchor Studio Demo"


def main() -> None:
    """Open Anchor Studio, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.anchor_studio import show

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(qt, parent, TITLE, f"Anchor Studio did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
