# this_file: Scripts/Names/Glyph Calendar Demo.py
# SPDX-License-Identifier: Apache-2.0
"""See on which days the glyphs of the current font were modified.

What: Opens two modeless panels from fontlabapp.glyphs.calendar: the standard
calendar with a read-only report for the chosen day, and the official one with
locales, week start, header style and date format.
Use: Run it with a font open, pick a day and read the glyph list. Close each
panel when done.
Safety: Read-only. The panels read the current font and keep their own state in
owned windows. No font, master, selection, history, preference, Output or
clipboard is written, and no menu action is triggered.
"""

TITLE = "Glyph Calendar Demo"


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
    from fly.ap.glyphs.calendar.model import show, show_official

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
