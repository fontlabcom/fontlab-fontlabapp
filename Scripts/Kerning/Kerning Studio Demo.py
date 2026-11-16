# this_file: Scripts/Kerning/Kerning Studio Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Kerning Studio: pairs from text, glyph pairs, kerning groups and tightening.

What: Opens the Kerning Studio window (fontlabapp.studios.kerning_studio) for
the current font. A TMetrics preview sits on top. Text pairs lists every
adjacent pair of a typed text with its value on each master; Glyph pairs lists
the records that involve one glyph; Groups shows the glyphs that share its
kerning groups; Tighten measures two unkerned gaps at a height and matches the
first pair to the second.
Use: Open a font and run it. Type text or a glyph name, pick a row, then use the
buttons: set a value, set every master's cell, nudge by 1, 5 or 10, Kern To
Max, delete a pair on all masters, or apply the matched kerning. The status
line names the masters that were changed.
Safety: Reads cover every master. Writes go to the selected preview master
(the grid and delete cover every master), one named Undo step each
("Kerning Studio: ..."), and are read back. Groups and the measuring steps are read-only. With no font open the
window opens without a preview and says so.
"""

TITLE = "Kerning Studio Demo"


def main() -> None:
    """Open Kerning Studio, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.kerning_studio import show

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(qt, parent, TITLE, f"Kerning Studio did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
