# this_file: Scripts/Kerning/Kerning Selection Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Find kerning exceptions and look up typed text pairs, without changing any.

What: For the current master it uses fontlabapp.kerning.selection.find to list
glyph pairs that override a broader class pair (an exception) and
text_values to read the effective kerning of the adjacent pairs of a sample
text, marking each value as explicit or inherited. It also reports how many
deletions the exception editor would stage if you selected every exception.
Use: Open a font and run it, then click Show Details.
Safety: Read-only. It reads the explicit pairs, the classes and the effective
kerning of the current master without switching it. The deletion plan is only
counted, never sent to the writer; no font, master, selection, history,
preference, Output or clipboard is written. With no font open it says so.
"""

TITLE = "Kerning Selection Demo"
SAMPLE_TEXT = "AV To"
MAX_ROWS = 12


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def report(selection, package) -> tuple[str, list[str]]:
    """Summary text and detail lines for the current master."""
    master = package.master
    rows = selection.find(package, [master])
    deletions = sum(len(pairs) for pairs in selection.exception_plan(rows).values())
    lines = [f"Master {master}: {len(rows)} exception(s); {deletions} deletion(s) would be staged."]
    for _, pair, value, broader, broader_value in rows[:MAX_ROWS]:
        lines.append(f"  {pair[0]} {pair[1]} = {value:g} overrides {broader[0]} {broader[1]} = {broader_value:g}")
    if len(rows) > MAX_ROWS:
        lines.append(f"  ... {len(rows) - MAX_ROWS} more")
    pairs = selection.adjacent_pairs(selection.parse_words(SAMPLE_TEXT, package))
    values = selection.text_values(package, [master], pairs)
    lines += ["", f"Adjacent pairs of {SAMPLE_TEXT!r}:"]
    for pair in pairs:
        value, explicit = values[pair, master]
        lines.append(f"  {pair[0]} {pair[1]} = {value:g} ({'explicit' if explicit else 'inherited or none'})")
    return f"{len(rows)} exception(s) in {master}. Nothing was changed.", lines


def main() -> None:
    """Report on the current font, or say that a font is needed."""
    from fly.ap.core.scripting import current_package
    from fly.ap.kerning import selection

    package = current_package()
    if package is None:
        notify(TITLE, "Open a font first. The report reads its kerning.")
        return
    try:
        summary, lines = report(selection, package)
    except (ValueError, RuntimeError) as error:
        notify(TITLE, f"The kerning could not be read: {error}")
        return
    notify(TITLE, summary, "\n".join(lines))


if __name__ == "__main__":
    main()
