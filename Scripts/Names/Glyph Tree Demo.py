# this_file: Scripts/Names/Glyph Tree Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Browse the current font as a read-only tree of glyphs, Unicode values and dates.

What: Opens two modeless panels from fontlabapp.glyphs.tree: the outline with
row and column status, and the expandable tree. Each glyph lists every Unicode
assignment and its local modification date.
Use: Run it with a font open, expand a glyph and click rows. Close each panel
when done.
Safety: Read-only. The panels read the current font and keep their own state in
owned windows. No font, master, selection, history, preference, Output or
clipboard is written, and no menu action is triggered.
"""

TITLE = "Glyph Tree Demo"


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
    from fly.ap.glyphs.tree.model import show_outline, show_tree

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
