# this_file: Scripts/Masters/Master Text Demo.py
# SPDX-License-Identifier: Apache-2.0
"""See how App's Master Text Comparison turns words into rows, on a made-up font.

What: Runs the pure parts of Master Text Comparison on a made-up character map
and two masters and prints the results: how Unicode aliases resolve
(font_maps in fontlabapp.masters.text.model), how a comma-separated text
becomes one row per word and master side by side or stacked (analyze), which
characters or /glyph-name tokens are dropped, and how custom text beats the
preset list (select_text), using the four built-in presets of
fontlabapp.masters.text.settings.
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is read from a font or written. The font is a few plain
values in this script. The panel and launcher (fontlabapp.masters.text.ui and
fontlabapp.masters.text.controller) are not opened: they bind to the opening
font, store window settings and open a new proof tab. No preset file is read.
No font, master, selection, history, preference, Output or clipboard is
touched.
"""

TITLE = "Master Text Demo"
FACTS = (("H", (72,)), ("a", (97,)), ("a.alt", (97,)), ("space", (32,)), ("Aacute", (193,)))
MASTERS = ("Light", "Bold")


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
    from fly.ap.masters.text import model, settings

    cmap, names, aliases = model.font_maps(FACTS)
    result = [f"Unicode aliases: {[(f'U+{code:04X}', kept, ignored) for code, kept, ignored in aliases]}"]
    for text, layout, mode in (("Ha,Hz,xyz", 1, "characters"), ("Ha,Hz,xyz", 0, "characters"), ("/Aacute /a.alt,/nope", 1, "names")):
        found = model.analyze(text, cmap, names, MASTERS, layout, mode=mode)
        result += [
            f"analyze({text!r}, {'side by side' if layout else 'stacked'}, {mode}): {len(found.words)} words, {sum(len(row) for row in found.rows)} slots",
            f"  preview: {found.preview!r}",
            f"  dropped: {[(d.word, d.offset, d.text, d.kind) for d in found.dropped]}; empty fields: {list(found.empty_words)}",
        ]
    try:
        model.analyze("xyz", cmap, names, MASTERS)
    except model.NoUsableGlyphs as error:
        result.append(f"analyze('xyz') refused: {error}")
    presets = settings.FALLBACKS
    result += [
        f"select_text('', presets, 1) -> {model.select_text('', presets, 1)[:30]}...",
        f"select_text('Hamburg', presets, 1) -> {model.select_text('Hamburg', presets, 1)}",
        f"select_text('Hamburg', presets, 1, immediate=3) -> {model.select_text('Hamburg', presets, 1, immediate=3)}",
    ]
    return result


def main() -> None:
    """Show the sample results; no font is needed."""
    notify(TITLE, "Sample master text comparison. Nothing was read or written.", "\n".join(lines()))


if __name__ == "__main__":
    main()
