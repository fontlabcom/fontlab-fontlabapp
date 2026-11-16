# this_file: Scripts/Features/Feature Code Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Generate OpenType feature code from glyph-name suffixes, on made-up names.

What: Runs the host-free generators of fontlabapp.features.code on a made-up
glyph list: safe_name (which names may appear unescaped in feature code),
suffix_pairs (base and alternate glyphs that both exist) and feature_text (a
complete substitution block), including the refusal of a bad feature tag.
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is read from a font or written. The glyph names are plain
values in this script and no window opens. The generated text is shown only;
it is never compiled or stored, and no feature, font, master, selection,
history, preference, Output or clipboard is touched.
"""

TITLE = "Feature Code Demo"
NAMES = ("a", "a.ss01", "b", "b.ss01", "c.ss01", "f_i", "f_i.ss01", "bad name.ss01", "bad name")


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
    from fly.ap.features import code

    pairs = code.suffix_pairs(NAMES, ".ss01")
    result = [f"Glyphs: {list(NAMES)}", "", "safe_name: " + ", ".join(f"{name!r} {code.safe_name(name)}" for name in ("a.ss01", "f_i", "1a", "bad name")), ""]
    result += [f"suffix_pairs(names, '.ss01') -> {pairs}", "  (c.ss01 has no base glyph and the names with a space are unsafe, so they are skipped)", "", "feature_text('ss01', pairs):", code.feature_text("ss01", pairs), ""]
    try:
        code.feature_text("ss1", pairs)
    except ValueError as error:
        result.append(f"feature_text('ss1', pairs) refused: {error}")
    return result


def main() -> None:
    """Show the sample results; no font is needed."""
    notify(TITLE, "Sample feature code. Nothing was read or written.", "\n".join(lines()))


if __name__ == "__main__":
    main()
