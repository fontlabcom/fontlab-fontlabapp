# this_file: Scripts/Font Info/Style Names Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Try App's style-name rules (ShortNames and StyleLinker) on made-up styles.

What: Runs the naming rules of fontlabapp.fonts.style_names on sample styles
and prints the results: how a style splits into words, the abbreviated style
(shorten_style), the proposed PostScript name (propose_ps_name), the warnings
that prepare_names gives for bad or long names, and which base style, bold and
italic flags style_link finds for each style.
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is read from a font or written. The styles are plain values in
this script and no window opens. The rules only compute text: they do not
change family or style names or write any font, master, selection, history,
preference, Output or clipboard.
"""

TITLE = "Style Names Demo"
STYLES = ("Regular", "Bold Italic", "Semi Condensed Light", "ExtraBold", "Display Oblique", "")
AVAILABLE = ("Regular", "Bold", "Light")


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def lines() -> list[str]:
    """The sample results, one line each."""
    from fly.ap.fonts import style_names

    result = ["Styles, their words, abbreviation and PostScript name for family 'Sample Sans':"]
    for style in STYLES:
        words = style_names.split_style_words(style)
        result.append(f"  {style!r}: {list(words)} -> {style_names.shorten_style(style)} -> {style_names.propose_ps_name('Sample Sans', style)}")
    edits = style_names.prepare_names(("SampleSans-Rg", "SampleSans-Rg", "Sample", "SampleSansExtraLongFamily-BoldItalicCondensed"))
    result += ["", "prepare_names warnings:", *(f"  {problem}" for problem in edits.problems), "", f"style_link against {list(AVAILABLE)}:"]
    for style in ("Bold Italic", "Light Italic", "Black Italic", "Regular"):
        result.append(f"  {style!r}: {style_names.style_link(style, AVAILABLE)}")
    return result


def main() -> None:
    """Show the sample results; no font is needed."""
    notify(TITLE, "Sample style names. Nothing was read or written.", "\n".join(lines()))


if __name__ == "__main__":
    main()
