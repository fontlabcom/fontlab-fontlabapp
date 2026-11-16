# this_file: Scripts/Font Info/Revisions Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Compare two open fonts, or two masters, field by field in App's revision panel.

What: With a font open, opens the Compare Open Font Revisions panel
(fontlabapp.fonts.revisions.ui, RevisionCompareDialog): choose a font and a
master on each side and it lists the glyphs whose presence, advance width,
contour and node geometry, anchors or components differ. Without a font it
shows what the comparison reports on two made-up snapshots
(fontlabapp.fonts.revisions.model.compare).
Use: Open one or two fonts and run it. Choose both sides, click Compare, select
a row for the details. Refresh Font List re-reads the open fonts; Close ends it.
Safety: Read-only. Refresh Font List, Compare, the search box and Close only
read: the panel lists the open fonts and their masters and reads every glyph of
the two chosen masters (layers, node coordinates and flags, transforms,
anchors, components). It activates no font or master and has no Apply, Copy or
save control, so nothing is written to a font, master, selection, history,
preference, Output or clipboard. The raw node flags it compares include
selection state. The sample comparison uses numbers in this script.
"""

TITLE = "Revisions Demo"


def sample_lines() -> list[str]:
    """Compare two made-up snapshots of font masters that differ in one advance and one glyph."""
    from fly.ap.fonts.revisions import model

    font = model.FontChoice(1, 1, "Sample", ("Regular",), "")

    def record(name: str, advance: float) -> object:
        return model.GlyphRecord(name, 1, 1, "present", advance, (), (), (), ())

    def snapshot(glyphs: tuple) -> object:
        return model.RevisionSnapshot(font, "Regular", True, glyphs, (font,), True)

    left = snapshot((record("a", 500), record("b", 520)))
    right = snapshot((record("a", 500), record("b", 540), record("c", 480)))
    return [f"{d.glyph or '(font)'}: {', '.join(d.fields)}" for d in model.compare(left, right)]


def main() -> None:
    """Open the comparison panel when a font is open; otherwise show the sample comparison."""
    import fly
    from fly.ap.core.scripting import current_package, show_script_dialog
    from fly.ap.qt.dialogs import create_message_box, run_message_box, run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        box = create_message_box(qt.QtGui, TITLE, "Open a font first. Sample comparison of two made-up snapshots is in the details.", "Information", (parent,), detail="\n".join(sample_lines()))
        box.setWindowTitle(TITLE)
        run_message_box(box, kind.Ok)
        return
    try:
        from fly.ap.fonts.revisions.ui import RevisionCompareDialog

        show_script_dialog(RevisionCompareDialog, RevisionCompareDialog.KEY)
    except (ValueError, RuntimeError, TimeoutError) as error:
        run_standard_message_box(qt, parent, TITLE, f"The panel did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
