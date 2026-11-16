# this_file: Scripts/Contours/Align & Nudge Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Align & Nudge: align, distribute, nudge, overlap and simplify nodes.

What: Opens the Align & Nudge window (fontlabapp.studios.align_nudge) for the
current font. A TGlyph preview sits on top. Align & distribute lines up or
spaces selected contours, nodes and components; Interpolated nudge moves
selected on-curve nodes and scales neighbouring handles; Overlap nodes moves
corner nodes onto selected tips along each master's italic angle; Simplify
removes alternate selected nodes across compatible masters.
Use: Open a font, select nodes in the glyph, type glyph names or use the font
selection, then press a Preview button to see the planned rows and a ghost
outline, or the action button to write.
Safety: Writes go to the explicit layer of the selected preview master (or every
master), one named Undo step ("Align & Nudge: ..."), and are read back; a
change FontLab rounds away is reported as "Partly applied". Auto layers are
skipped; hinted layers are refused unless you tick "Edit hinted layers anyway"
or remove PostScript hints. Previews never write. With no font open the window
says so.
"""

TITLE = "Align & Nudge Demo"


def main() -> None:
    """Open Align & Nudge, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.align_nudge import show

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
            f"Align & Nudge did not open: {error}",
            "Warning",
            kind.Ok,
        )


if __name__ == "__main__":
    main()
