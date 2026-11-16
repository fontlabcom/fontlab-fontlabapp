# this_file: Scripts/Names/Glyph Name Entry Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Type glyph names with completion and test name patterns against the current font.

What: Opens three modeless panels: two completion drafts from
fontlabapp.glyphs.completion (alphabetic triggers; punctuation triggers with a
popup) and the pattern lab from fontlabapp.glyphs.pattern, which tries four
regular-expression syntaxes on the glyph names.
Use: Run it with a font open, type a few letters in a completion draft and
enter a pattern in the lab. Close each panel when done.
Safety: Read-only. The panels read the current font and keep their own state in
owned windows. No font, master, selection, history, preference, Output or
clipboard is written, and no menu action is triggered. Draft text stays in the
panels.
"""

TITLE = "Glyph Name Entry Demo"


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
    from fly.ap.glyphs.completion.model import show, show_official
    from fly.ap.glyphs.pattern import show as show_pattern

    if current_package() is None:
        notify(TITLE, "Open a font first. These panels read the current font.")
        return
    failures = []
    for label, opener in (("show", show), ("show_official", show_official), ("show_pattern", show_pattern)):
        try:
            opener()
        except (RuntimeError, ValueError, TimeoutError) as error:
            failures.append(f"{label} did not open: {error}")
    if failures:
        notify(TITLE, "\n".join(failures))


if __name__ == "__main__":
    main()
