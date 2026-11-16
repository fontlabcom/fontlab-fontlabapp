# this_file: Scripts/Components/Component Studio Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Component Studio: build, replace, decompose, copy offsets, set locations and lock components.

What: Opens the Component Studio window
(fontlabapp.studios.component_studio) for the current font. A read-only
TGlyph preview sits on the right. Build checks one-line recipes with
FontLab's builder and builds them (Dump from selection lists the recipes of
the selected glyphs); Replace swaps a component's base glyph in place;
Decompose turns all, one named or Serif* components into outlines; Offsets
copies component offsets from one master to others; Locations sets or resets
component source locations; Locks locks or unlocks components.
Use: Open a font, select glyphs in the Font window and run it. Each tab lists
exactly the layers and values it will change. Press its Apply button.
Safety: Dump from selection and the lock listing only read. Nothing in the
font changes until you press a tab's Apply button. Each Apply writes exactly
the listed values as one named Undo step ("Component Studio: ..."), and
refuses when a glyph changed after the list was made; press Reload selection
then. Build's own builder steps keep FontLab's Undo.
With no font open the window opens without a preview and says so.
"""

TITLE = "Component Studio Demo"


def main() -> None:
    """Open Component Studio, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.component_studio import show

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
            f"Component Studio did not open: {error}",
            "Warning",
            kind.Ok,
        )


if __name__ == "__main__":
    main()
