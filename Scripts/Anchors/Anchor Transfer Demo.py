# this_file: Scripts/Anchors/Anchor Transfer Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Anchor Transfer: copy anchors from a glyph, between masters, between fonts, from components or from a CSV file.

What: Opens the Anchor Transfer window (fontlabapp.studios.anchor_transfer)
for the current font, with a TGlyph preview. From glyph copies the anchors
of a named glyph into the selected glyphs; Between masters copies them from
one master into others; Between fonts copies them from one open font into
another; From components recovers missing base anchors from positioned mark
components; CSV import reads anchors from a UTF-8 CSV file.
Use: Open a font, select glyphs in the Font window and run it. Set the
options; each tab lists the exact anchor edits it will make. Press the
tab's button (Copy, Mirror, Copy Anchors, Derive or Import).
Safety: Nothing changes until you press that button. It writes exactly the
listed edits, as one named Undo step ("Anchor Transfer: ..."), and refuses
when the font changed after the list was made; press Refresh then. Between
fonts refuses the same font on both sides and writes one Undo step in the
destination font. With no font open the window opens without a preview and
says so.
"""

TITLE = "Anchor Transfer Demo"


def main() -> None:
    """Open Anchor Transfer, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.anchor_transfer import show

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(qt, parent, TITLE, f"Anchor Transfer did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
