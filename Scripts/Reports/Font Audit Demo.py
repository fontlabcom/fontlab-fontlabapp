# this_file: Scripts/Reports/Font Audit Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Font Audit: whole-font reports with a read-only TMetrics preview.

What: Opens the Font Audit window (fontlabapp.studios.font_audit) for the
current font. Overview shows the font cards, master metrics and mark-colour
and suffix groups; Glyph table exports a CSV; Unicode, Empty and
Unreferenced list blocks and glyphs; Case & small caps opens the Smallcap
Consistency report (Case Coverage needs the Scriptmix launcher's GlyphData).
Use: Click a row to show its glyphs in the preview; use the "Select ..."
buttons to select them in the Font window.
Extension: fontlabapp.studios.font_audit.practical.show(classify=callback)
adds source-named tabs, including fontlabapp.fontui.category_xml. Supply a
callback taking (name, unicode_hex_strings) and returning (category, subcategory)
from GlyphData; the pane renders the complete font as XML without changing its lib.
Safety: Read-only. It never edits the font or Undo history; it only selects
glyphs, writes the CSV file you choose and copies to the clipboard.
"""

TITLE = "Font Audit Demo"


def main() -> None:
    """Open Font Audit, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.font_audit import show

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(qt, parent, TITLE, f"Font Audit did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
