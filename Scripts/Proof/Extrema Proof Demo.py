# this_file: Scripts/Proof/Extrema Proof Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Find the highest and lowest glyphs of the current font and proof them.

What: After you confirm, calls fontlabapp.proof.extrema.model.show_all. It
scans every foreground master and auxiliary layer of the current font, opens
the Highest & Lowest Glyphs panel with the winning coordinates, and opens a
new Glyph tab that shows both winning layers.
Use: Run it with a font open and click Yes. Read the coordinates in the panel.
Run Again in the panel scans again and opens another new tab; Close ends it.
Safety: It reads the font. The one change is a new tab, a visible window you
can close, opened after you click Yes and again by each Run Again. While it
creates the tab, fontlabapp reads every glyph shape's on/off (active) state
and writes back any state the tab creation changed. If the tab fails to open,
the panel still shows the coordinates and a new tab may remain; close it.
Selection, history, preferences, Output and clipboard are untouched. Without
a font, or if you click No, nothing is opened.
"""

TITLE = "Extrema Proof Demo"
QUESTION = (
    "Scan every layer of the current font and open a new Glyph tab with its "
    "highest and lowest glyphs? It snapshots and restores every shape's active flag."
)


def main() -> None:
    """Confirm, then open the extrema panel and its proof tab."""
    import fly
    from fly.ap.core.scripting import current_package
    from fly.ap.proof.extrema.model import show_all
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font first. This demo scans the current font.", "Information", kind.Ok)
        return
    if run_standard_message_box(qt, parent, TITLE, QUESTION, "Question", kind.Yes | kind.No, kind.No) != kind.Yes:
        return
    try:
        show_all()
    except (ValueError, RuntimeError, TimeoutError) as error:
        run_standard_message_box(qt, parent, TITLE, f"The extrema proof could not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
