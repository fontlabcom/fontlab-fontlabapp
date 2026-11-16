# this_file: Scripts/Kerning/Kerning Batch Window Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Kerning Batch: round, scale, remove small, clamp, copy masters and punctuation.

What: Opens the Kerning Batch window (fontlabapp.studios.kerning_batch) for
the current font. A TMetrics preview sits on top. Round snaps values to a step;
Scale multiplies them; Remove small deletes pairs near zero; Clamp limits every
pair to [-250, 100]; Copy masters copies one master's kerning to others;
Punctuation turns class pairs of selected glyphs into glyph exceptions.
Use: Open a font and run it. Set the options; each tab lists the exact pairs it
will change and counts them. Press the tab's button to apply that list.
Safety: Nothing changes until you press the button. It writes exactly the
listed pairs, as one named Undo step ("Kerning Batch: ..."), and refuses when
the kerning changed after the list was made; press Refresh then. With no font
open the window opens without a preview and says so.
"""

TITLE = "Kerning Batch Window Demo"


def main() -> None:
    """Open Kerning Batch, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.kerning_batch import show

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(qt, parent, TITLE, f"Kerning Batch did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
