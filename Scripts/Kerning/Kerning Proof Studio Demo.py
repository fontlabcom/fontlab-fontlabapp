# this_file: Scripts/Kerning/Kerning Proof Studio Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Kerning Proof with text pairs, symmetry and a live text preview.

What: Show fontlabapp.studios.kerning_proof in the shared studio shell.
Use: Open a font, enter proof text and choose a tab. Review pair rows and the
TMetrics preview; Preview Changes stages a symmetry plan before Apply Changes.
Safety: Text Preview only reads the captured font. Pairs From Text and Symmetry
apply reviewed edits through the shared writer and refuse stale targets. Native
Undo/Redo, saved-font preservation and window lifetime remain to be qualified.
"""

TITLE = "Kerning Proof Studio Demo"


def main() -> None:
    """Open Kerning Proof, or show one owned warning if launch is refused."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    try:
        from fly.ap.studios.kerning_proof import show

        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(qt, parent, TITLE, f"Kerning Proof did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
