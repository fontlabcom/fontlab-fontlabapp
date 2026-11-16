# this_file: Scripts/Components/Component Audit Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Component Audit: composites, where used, missing bases, nested components, graph and brackets.

What: Opens the Component Audit window
(fontlabapp.studios.component_audit) for the current font. A read-only
TGlyph preview sits on the right. Composites lists every layer with
components (filter, Copy CSV, double-click opens the glyph); Where used
lists the composites that use one glyph; Missing bases lists components
whose base glyph or master layer is missing; Nested lists components whose
base is itself a composite and unnests them by one level; Graph opens the
movable component dependency graph; Brackets lists bracket-layer glyphs and
the glyphs that depend on them.
Use: Open a font and run it. Choose a row to see that glyph in the preview.
Safety: Every tab except Nested only reads; selecting, copying and opening
a glyph change nothing in the font. Nested lists exactly the layers it will
change; Unnest writes them as one named Undo step
("Component Audit: unnest components ...") and refuses when a glyph changed
after the list was made; press Reload selection then.
With no font open the window opens without a preview and says so.
"""

TITLE = "Component Audit Demo"


def main() -> None:
    """Open Component Audit, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.component_audit import show

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
            f"Component Audit did not open: {error}",
            "Warning",
            kind.Ok,
        )


if __name__ == "__main__":
    main()
