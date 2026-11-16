# this_file: Scripts/Names/Glyph Names Report Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Report on glyph names: duplicate Unicode values, unreferenced glyphs and the selection.

What: Reads the current font once and shows four sections in one message box.
fontlabapp.glyphs.names scans every glyph. fontlabapp.glyphs.unicode.duplicates
lists code points that several glyphs share and the glyph it would keep.
fontlabapp.glyphs.unreferenced lists unencoded glyphs that no feature or
component uses. The current selection is read with fontlabapp.core.scripting.
A last section runs the fontlabapp.glyphs.selection planner on sample marks to
show which glyphs the Select Different Colours tool would add; the demo itself
selects nothing.
Use: Run it with a font open and click Show Details. Without a font a message
says so.
Safety: Read-only; a section that fails shows an error line and the others
stay. No glyph is renamed, no Unicode value is removed, no glyph is
selected and no font, master, history, preference, Output or clipboard is
written.
The Duplicate Unicodes writer (unicode.duplicates.show) is not opened.
"""

TITLE = "Glyph Names Report Demo"
SAMPLE_MARKS = ((0, "A", 10, True), (1, "B", 10, False), (2, "C", 20, False), (3, "D", 0, False))
SHOWN = 20  # names listed per section before the count summary


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call (copied into every Names demo)."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def preview(names: list[str]) -> str:
    """The first ``SHOWN`` names, then how many more there are."""
    more = f", ... ({len(names) - SHOWN} more)" if len(names) > SHOWN else ""
    return ", ".join(names[:SHOWN]) + more if names else "none"


def duplicate_lines(facts) -> list[str]:
    """Group the shared Unicode values of a names scan; nothing is removed."""
    from fly.ap.glyphs.unicode.duplicates.model import Glyph, groups

    glyphs = tuple(
        Glyph(int(entry.record.id), int(entry.glyph.id), name, tuple(entry.record.unicodes), (), ())
        for name, entry in facts.entries.items()
    )
    found = groups(glyphs)
    return [f"U+{group.code:04X}: {', '.join(group.names)} (keeps {group.keeper})" for group in found] or ["none"]


def selection_lines() -> list[str]:
    """Read the current selection (the current glyph when nothing is selected)."""
    from fly.ap.core.scripting import names_selected_names

    return [preview(names_selected_names())]


def plan_lines() -> list[str]:
    """Plan a different-colour selection over sample marks and name the glyphs it would add."""
    from fly.ap.glyphs.selection.mark_colors import GlyphMark, plan

    marks = tuple(GlyphMark(*row) for row in SAMPLE_MARKS)
    added = [marks[index].name for index in plan(marks)]
    return [f"Sample: A (colour 10) is selected; the tool would add {', '.join(added)}"]


def main() -> None:
    """Scan the current font and show the four sections."""
    from fly.ap.core.scripting import current_package
    from fly.ap.glyphs.names.model import scan
    from fly.ap.glyphs.unreferenced import unreferenced

    package = current_package()
    if package is None:
        notify(TITLE, "Open a font first. This report reads the current font.")
        return
    try:
        facts, scan_error = scan(), None  # scan and unreferenced raise only ValueError: neither has a deadline
    except ValueError as error:
        facts, scan_error = None, error

    def duplicates() -> list[str]:
        if facts is None:  # only this section needs the scan; the others still run
            raise scan_error
        return duplicate_lines(facts)

    count = "unavailable" if facts is None else len(facts.entries)
    lines = [f"Glyphs: {count}"]
    sections = (
        ("Duplicate Unicodes", duplicates),
        ("Unreferenced glyphs", lambda: [preview([n + (f" ({m})" if m else "") for n, m in unreferenced(package)])]),
        ("Current selection", selection_lines),
        ("Selection planner", plan_lines),
    )
    for heading, build in sections:
        try:
            lines += ["", heading + ":"] + build()
        except (ValueError, TimeoutError) as error:  # keep the sections already built
            lines += ["", heading + ":", "error: " + str(error)]
    summary = "The glyph scan failed; the other sections follow." if facts is None else f"{count} glyphs read."
    notify(TITLE, summary, "\n".join(lines))


if __name__ == "__main__":
    main()
