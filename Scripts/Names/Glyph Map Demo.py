# this_file: Scripts/Names/Glyph Map Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open the glyph map (character map): Unicode coverage of the current font.

What: Opens two modeless panels from fontlabapp.glyphs.character_map: the
fixed-style map with a size spin box and an append-at-end picker, and the
official map with database styles, sizes and a cursor-aware picker.
Use: Run it with a font open, click a cell to see which glyphs carry that code
point, and close each panel when done. The panel's Copy selected text and To
clipboard buttons put text on the system clipboard only when you click them.
Without a font a message says so.
Safety: Read-only. The panels read the current font and keep their own state in
owned windows. The demo itself writes nothing: no font, master, selection,
history, preference, Output or clipboard, and no menu action is triggered. The
only writes are the clipboard copies you start with the panel's own buttons.
"""

TITLE = "Glyph Map Demo"


def notify(title: str, text: str) -> None:
    """Show one modal message box owned by this call (copied into every Names demo)."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),))
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def main() -> None:
    """Open the panels for the current font, or say that a font is needed."""
    from fly.ap.core.scripting import current_package
    from fly.ap.glyphs.character_map.model import show, show_official

    if current_package() is None:
        notify(TITLE, "Open a font first. These panels read the current font.")
        return
    failures = []
    for label, opener in (("show", show), ("show_official", show_official)):
        try:
            opener()
        except (RuntimeError, ValueError, TimeoutError) as error:
            failures.append(f"{label} did not open: {error}")
    if failures:
        notify(TITLE, "\n".join(failures))


if __name__ == "__main__":
    main()
