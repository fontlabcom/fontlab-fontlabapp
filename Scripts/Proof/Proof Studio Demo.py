# this_file: Scripts/Proof/Proof Studio Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Proof Studio: pattern strings and kerning proofs with a TMetrics preview.

What: Opens the Proof Studio window (fontlabapp.studios.proof_studio) for the
current font. A TMetrics preview sits on top. Pattern strings puts each
selected glyph between lowercase, uppercase, lining or oldstyle figures, or
surrounds it with H, HHOHH, I or nnonn. Kerning proofs shows the Hoefler
lowercase/uppercase, KernKing and KernSym texts.
Use: Select glyphs in the Font window (or a Glyph window), pick a generator
and source, then read the preview, press Copy, or press "Open in FontLab
Glyph tab" for the same new tab(s) the original Proof scripts open.
Safety: Read-only. It never edits the font or Undo history; Open uses the
current selection and master, as the scripts do.
"""

TITLE = "Proof Studio Demo"


def main() -> None:
    """Open Proof Studio, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.proof_studio import show

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(qt, parent, TITLE, f"Proof Studio did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
