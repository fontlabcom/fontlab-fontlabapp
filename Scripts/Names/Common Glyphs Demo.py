# this_file: Scripts/Names/Common Glyphs Demo.py
# SPDX-License-Identifier: Apache-2.0
"""List the glyphs that every open font has, with characters, names and Unicode values.

What: Opens the fontlabapp.glyphs.common report panel. It reads every open font,
keeps the glyph names they share (or all glyphs of a single font), and shows the
characters, the nice names and the production names. This demo has no GlyphData
database, so every production name is reported as unknown on purpose.
Use: Run it with one or more fonts open, read the report and close the panel. The
Copy Characters and Copy Original Report buttons put text on the system clipboard
only when you click them. Without a font a message says so.
Safety: Read-only. The panel reads the open fonts and keeps its report in its own
window. Its optional all-font label action is not implemented, so no font, master,
selection, history, preference or Output is written by this demo, and it writes
the clipboard only through those buttons when you click them.
"""

TITLE = "Common Glyphs Demo"


def notify(title: str, text: str) -> None:
    """Show one modal message box owned by this call (copied into every Names demo)."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),))
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def unknown_production(name: str, checkpoint=None):
    """Production metadata of a demo without a database: every mapping is unknown."""
    from fly.ap.glyphs.common.model import Production

    return Production(None, "unknown")


def main() -> None:
    """Open the report panel, or explain why FontLab refused to build the report."""
    from fly.ap.glyphs.common.controller import show

    try:
        show(unknown_production)
    except (ValueError, TimeoutError) as error:
        notify(TITLE, "The report could not be built: " + str(error))


if __name__ == "__main__":
    main()
