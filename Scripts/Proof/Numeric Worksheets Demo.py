# this_file: Scripts/Proof/Numeric Worksheets Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open both numeric worksheets for the selected glyphs of the current font.

What: Calls fontlabapp.proof.numeric.launcher.show and show_detailed. Each
captures the font's units per em, the selected glyph layers' advance widths
and every glyph's revision, twice to be sure nothing changed, and opens a
panel that calculates from those facts. The detailed panel adds special values
and historical revision ranges.
Use: Run it with a font open and some glyphs selected in a Font window. Use
each panel's own controls to read the figures, then close both panels.
Safety: Read-only. The launcher reads the current font, the selected layers
and the revision table, and no selection, metric, glyph, history, preference,
file, clipboard or Output writer is used. With no font open a message says so
and no panel opens. If the capture fails with a font open (for example, no
glyph is selected), each panel still opens and shows the error in its status
line; close it and select glyphs.
"""

TITLE = "Numeric Worksheets Demo"


def main() -> None:
    """Open both worksheets for the current font, or say that a font is needed."""
    import fly
    from fly.ap.core.scripting import current_package
    from fly.ap.proof.numeric.launcher import show, show_detailed
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font first. The worksheets read the current font.", "Information", kind.Ok)
        return
    failures = []
    for label, opener in (("worksheet", show), ("detailed worksheet", show_detailed)):
        try:
            opener()
        except (ValueError, RuntimeError, TimeoutError) as error:
            failures.append(f"The {label} did not open: {error}")
    if failures:
        run_standard_message_box(qt, parent, TITLE, "\n".join(failures), "Information", kind.Ok)


if __name__ == "__main__":
    main()
