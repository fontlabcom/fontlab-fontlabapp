# this_file: Scripts/Features/Feature Categories Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Export the open font's glyph categories as a UFO lib fragment, in a read-only panel.

What: Opens the Categories to XML Lib Key panel
(fontlabapp.features.categories, built by model.show) with a simple category
policy of this script: a glyph is a Mark when its Unicode value lies in the
Combining Diacritical Marks block (U+0300 to U+036F) or its name ends in
comb; every other glyph is a base. The panel lists all glyphs in font order as
the public.openTypeCategories fragment for a UFO lib dictionary.
Use: Open a font and run it. Select the text you want and copy it yourself;
Refresh reads the font again and Close ends it.
Safety: Read-only. The panel reads every glyph's id, name and Unicode values
(several times, to be sure the font did not change meanwhile) and applies the
policy in this script; its only buttons are Refresh and Close, and its text
box is read-only. It writes no font, master, selection, history, preference,
Output or clipboard and no file. With no font open nothing opens.
"""

TITLE = "Feature Categories Demo"
COMBINING = (0x0300, 0x036F)


def classify(name: str, codes: list[str]) -> tuple[str | None, str | None]:
    """The policy: (category, subcategory) with Mark for combining marks, else Base."""
    if name.endswith("comb") or any(COMBINING[0] <= int(code, 16) <= COMBINING[1] for code in codes):
        return "Mark", None
    return "Base", None


def main() -> None:
    """Open the categories panel on the current font, or say that a font is needed."""
    import fly
    from fly.ap.core.scripting import current_package
    from fly.ap.features.categories import model
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font first. The panel lists its glyph categories.", "Information", kind.Ok)
        return
    try:
        model.show(classify)
    except (ValueError, RuntimeError, TimeoutError) as error:
        run_standard_message_box(qt, parent, TITLE, f"The panel did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
