# this_file: Scripts/Names/Glyph Catalog Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Sort and filter a snapshot of glyph names, Unicode values and modification dates.

What: Opens two modeless panels from fontlabapp.glyphs.catalog: the custom view
(own matcher, OR fields, inclusive dates, sort keys) and the official view with
typed dates and native regular expressions. The Basic variants live in the same
module.
Use: Run it with a font open, type into the filter fields and click column
headers. Refresh reads the font again. Close each panel when done.
Safety: Read-only. The panels read the current font and keep their own state in
owned windows. No font, master, selection, history, preference, Output or
clipboard is written, and no menu action is triggered. Cells are read-only.
"""

TITLE = "Glyph Catalog Demo"


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
    from fly.ap.glyphs.catalog.model import show_custom, show_official_custom

    if current_package() is None:
        notify(TITLE, "Open a font first. These panels read the current font.")
        return
    failures = []
    for label, opener in (("show_custom", show_custom), ("show_official_custom", show_official_custom)):
        try:
            opener()
        except (RuntimeError, ValueError, TimeoutError) as error:
            failures.append(f"{label} did not open: {error}")
    if failures:
        notify(TITLE, "\n".join(failures))


if __name__ == "__main__":
    main()
