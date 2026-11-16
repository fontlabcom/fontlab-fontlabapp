# this_file: Scripts/Contours/Derived Glyphs Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Derived Glyphs: small caps, sups and subs, tabular and default figures, unicase and placeholders.

What: Opens the Derived Glyphs window (fontlabapp.studios.derived_glyphs)
for the current font. A read-only TMetrics preview sits on top. Small caps
makes scaled .sc copies of the selected capitals; Sups & subs makes scaled,
shifted .sups or .subs copies of the selected figures; Tabular figures makes
centred .tf copies with one shared width per master; Default figures makes
the ten default digit cells components of one figure family; Unicase makes
uppercase cells components of their lowercase; Placeholders makes empty
glyphs from typed names or characters.
Use: Open a font, select glyphs in the Font window where a tab asks for a
selection, and run it. Every tab lists its plan first; choose a row to see
the source and the target in the preview.
Safety: Opening the window, changing a control and choosing a row change
nothing in the font. Apply checks the font again and refuses a plan that
differs from the list on screen. Each new glyph is its own Undo step
(FontLab's Add Glyph); outlines and components are one more named Undo step
("Derived Glyphs: ..."). Unicase asks before it replaces drawings. Rows that
may make FontLab rebuild automatic glyphs are skipped unless you tick
"Create even if FontLab may rebuild these auto glyphs".
With no font open the window opens without a preview and says so.

Shape-generation collaborators are catalogued in
fontlabapp.studios.shape_generators and composed by
fontlabapp.fontui.outline_generators. They are related source references;
this demo opens only Derived Glyphs.
"""

TITLE = "Derived Glyphs Demo"


def main() -> None:
    """Open Derived Glyphs, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.derived_glyphs import show

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
            f"Derived Glyphs did not open: {error}",
            "Warning",
            kind.Ok,
        )


if __name__ == "__main__":
    main()
