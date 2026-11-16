# this_file: Scripts/Names/Editable Glyph Tree Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Edit a local draft of the glyph tree: insert rows and columns without touching the font.

What: Opens two modeless panels from fontlabapp.glyphs.tree.editable: the
outline with before-row and append-column editing, and the full tree with
keyboard, menu and selection policies.
Use: Run it with a font open and edit rows. Edits change only the draft held by
the panel; close the panel to discard it.
Safety: Read-only. The panels read the current font and keep their own state in
owned windows. No font, master, selection, history, preference, Output or
clipboard is written, and no menu action is triggered. Edits stay in the
panel's local tree.
"""

TITLE = "Editable Glyph Tree Demo"


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
    from fly.ap.glyphs.tree.editable.model import show_outline, show_tree

    if current_package() is None:
        notify(TITLE, "Open a font first. These panels read the current font.")
        return
    failures = []
    for label, opener in (("show_outline", show_outline), ("show_tree", show_tree)):
        try:
            opener()
        except (RuntimeError, ValueError, TimeoutError) as error:
            failures.append(f"{label} did not open: {error}")
    if failures:
        notify(TITLE, "\n".join(failures))


if __name__ == "__main__":
    main()
