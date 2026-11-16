# this_file: Scripts/Components/Component Recipes Demo.py
# SPDX-License-Identifier: Apache-2.0
"""List the component recipes of the selected glyphs in a read-only report.

What: Opens the nonmodal Dump Component Recipes report
(fontlabapp.components.recipes.ui.ComponentRecipesDialog). It prints one
"base+base=glyph" line for every selected layer that has components, in the
order of the selection and of the components; positions and transforms are not
part of a recipe. fontlabapp.components.recipes.model builds the lines.
Use: Open a font, select glyphs in a Font window (or a Glyph window) and run
it. Click Refresh after you change the selection or the font and Close when
done.
Safety: Read-only. The report reads the selected layers' component names when
it opens and on Refresh, never their outlines, and it writes no font, master,
selection, history, preference, Output or clipboard. Text in the window can be
selected and copied with the usual editing keys. With no font open nothing
opens.
"""

TITLE = "Component Recipes Demo"


def main() -> None:
    """Open the report on the current font, or say that a font is needed."""
    import fly
    from fly.ap.components.recipes.ui import ComponentRecipesDialog
    from fly.ap.core.scripting import current_package, show_script_dialog
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font and select glyphs first. The report reads their components.", "Information", kind.Ok)
        return
    try:
        show_script_dialog(ComponentRecipesDialog, ComponentRecipesDialog.KEY)
    except (ValueError, RuntimeError, TimeoutError) as error:
        run_standard_message_box(qt, parent, TITLE, f"The report did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
