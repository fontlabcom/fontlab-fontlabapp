# this_file: Scripts/Kerning/Kerning Identity Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Show how App names the sides of a kerning pair, legacy and typed.

What: Decodes sample sides with fontlabapp.kerning.identity.native_side and
converts sample pairs with pair_key in both forms: legacy keys, where a class
is written @name, and typed keys, which keep (name, mode) and so can tell a
class from a glyph whose own name starts with @. With a font open it also reads
the first explicit pairs of the current master with read_pairs.
Use: Run it from the Scripts menu and click Show Details. A font is optional.
Safety: Read-only. The samples are plain strings; the font read only lists the
explicit pairs of the current master without switching it. No font, master,
selection, history, preference, Output or clipboard is written.
"""

TITLE = "Kerning Identity Demo"
SIDES = ("A", "@O_left", ("@odd", "glyphMode"), ("O_left", "groupMode"))
PAIRS = (("A", "@O_right"), (("@odd", "glyphMode"), "V"))
MAX_PAIRS = 5


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def pair_line(identity, pair: tuple, typed: bool) -> str:
    """One pair in the requested form, or the reason that form cannot hold it."""
    try:
        return f"  {'typed' if typed else 'legacy'}: {identity.pair_key(pair, typed=typed)}"
    except ValueError as error:
        return f"  {'typed' if typed else 'legacy'}: refused: {error}"


def sample_lines(identity) -> list[str]:
    """Decoded sides and both pair forms for the samples."""
    lines = [f"native_side({side!r}) = {identity.native_side(side)}" for side in SIDES]
    for pair in PAIRS:
        lines += ["", f"pair {pair!r}", pair_line(identity, pair, False), pair_line(identity, pair, True)]
    return lines


def main() -> None:
    """Show the samples and, with a font open, its first typed pairs."""
    from fly.ap.core.scripting import current_package
    from fly.ap.kerning import identity

    lines = sample_lines(identity)
    summary = "Sample pair sides. Open a font to see its pairs too."
    package = current_package()
    if package is not None:
        try:
            pairs = identity.read_pairs(package, package.master, typed=True)
            lines += ["", f"First {MAX_PAIRS} of {len(pairs)} explicit pairs of {package.master} (typed):"]
            lines += [f"  {pair} = {value:g}" for pair, value in list(pairs.items())[:MAX_PAIRS]]
            summary = f"Sample pair sides and the pairs of {package.master}."
        except (ValueError, RuntimeError) as error:
            summary = f"The font's pairs could not be read: {error}"
    notify(TITLE, summary, "\n".join(lines))


if __name__ == "__main__":
    main()
