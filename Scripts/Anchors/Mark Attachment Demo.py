# this_file: Scripts/Anchors/Mark Attachment Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Mark Attachment: preview mark attachment, align components by anchor, add cursive anchors.

What: Opens the Mark Attachment window
(fontlabapp.studios.mark_attachment) for the current font. A read-only
TMetrics preview sits on top. Mark preview draws a mark attached to a base
by a shared anchor on every master; Align by anchor moves mark components
onto their base glyph's anchors; Cursive saves an entry/exit sample from one
layer and adds the missing entry and exit anchors it fits.
Use: Open a font, select glyphs in the Font window and run it. Each edit tab
lists exactly the layers and values it will change. Press Align or Add.
Safety: Mark preview only reads; Get sample writes only a new sample file.
Nothing in the font changes until you press Align or Add. It writes exactly
the listed values as one named Undo step ("Mark Attachment: ..."), and
refuses when a glyph changed after the list was made; press Refresh then.
With no font open the window opens without a preview and says so.
"""

TITLE = "Mark Attachment Demo"


def main() -> None:
    """Open Mark Attachment, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.mark_attachment import show

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
            f"Mark Attachment did not open: {error}",
            "Warning",
            kind.Ok,
        )


if __name__ == "__main__":
    main()
