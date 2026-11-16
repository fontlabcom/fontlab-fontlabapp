# this_file: Scripts/Contours/Outline Doctor Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Outline Doctor: scan glyph outlines for problems and fix them.

What: Opens the Outline Doctor window (fontlabapp.studios.outline_doctor) for
the current font. A TGlyph preview sits on top. The Scan tab reports open
contours, near-miss angles, stems and metrics, and dangerous off-curve
handles; the Handles, Points, Segments and Overlaps tabs fix zero or
retractable handles, missing extremes, close points, fractional coordinates,
short or chosen curves and lines, overlaps, and small or duplicate contours.
Near-miss stems and metrics come from fontpr's per-master font info
(fontlabapp.core.outline), so scanning never switches the current master.
A base glyph used by components is scanned and fixed like any other; only
outline data that FontLab shares beyond those components is kept
(fontlabapp.core.sharing).
Use: Open a font, type glyph names or use the font selection, choose a check,
then press Scan or Preview to see the rows and a before/after ghost, or
"Apply to chosen glyphs" to write.
Safety: Scan and Preview never write. A fix writes the explicit layers it
planned, as one named Undo step ("Outline Doctor: ..."), and reads them back.
Structural fixes keep masters compatible by default: a change some masters
would not get is held back. Auto layers are skipped; hinted layers are refused
unless you tick "Edit hinted layers anyway" or remove PostScript hints. With no
font open the window says so.

Related outline mini-apps use fontlabapp.fontui.outline_editing for reviewed
changes, fontlabapp.fontui.outline_routes for the original editing operations,
and fontlabapp.fontui.outline_simplify for the cleanup controls. Contour order
and selection are composed in fontlabapp.fontui.outline_order and
fontlabapp.fontui.contour_selection. Compatibility inspection and conversion
live in fontlabapp.fontui.outline_compatibility with its original inspector
adapters in fontlabapp.fontui.outline_compatibility_routes. These are related
source references; this demo opens only Outline Doctor.
"""

TITLE = "Outline Doctor Demo"


def main() -> None:
    """Open Outline Doctor, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.outline_doctor import show

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(
            qt,
            parent,
            TITLE,
            f"Outline Doctor did not open: {error}",
            "Warning",
            kind.Ok,
        )


if __name__ == "__main__":
    main()
