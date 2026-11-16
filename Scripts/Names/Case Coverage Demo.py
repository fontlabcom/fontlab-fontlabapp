# this_file: Scripts/Names/Case Coverage Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Check upper/lower case partners and small-cap consistency of the current font.

What: Runs two read-only reports and shows them in one message box. The
fontlabapp.glyphs.case_coverage report lists capitals without a lowercase glyph
and the reverse for the current font. The fontlabapp.glyphs.smallcaps report
counts small caps, capitals and lowercase glyphs and lists missing partners and kerning mismatches.
Glyph categories come from Python's unicodedata, not from a GlyphData database,
so unencoded glyphs are reported as unknown mappings instead of guessed.
Use: Run it with a font open and click Show Details. Without a font a message
says so.
Safety: Read-only. No proof tab is opened, no case-coverage option is saved and
no font, master, selection, history, preference, Output or clipboard is written.
"""

import unicodedata

TITLE = "Case Coverage Demo"
SUBCATEGORY = {"Lu": "Uppercase", "Ll": "Lowercase"}  # every other category stays "Other"
SMALLCAP_KEYS = (
    "missing_lowercase_smallcaps",
    "missing_uppercase_smallcaps",
    "orphan_smallcaps",
    "kerning_mismatches",
)


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call (copied into every Names demo)."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def metadata(name: str, codes: tuple, checkpoint=None) -> tuple:
    """Return (subcategory, character) from the first Unicode value; unencoded is unknown."""
    if not codes:
        return None, None
    text = chr(codes[0])
    return SUBCATEGORY.get(unicodedata.category(text), "Other"), text


def preferred(mapped: str, checkpoint=None):
    """No canonical-name policy: the first glyph that encodes the partner wins."""
    return None


def case_lines(report: dict) -> list[str]:
    """Summarise one case-coverage report: status counts, then glyphs that need a partner."""
    counts: dict[str, int] = {}
    for row in report["rows"]:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    lines = [f"{status}: {count}" for status, count in sorted(counts.items())]
    lines.append("all clear" if report["all_clear"] else "needs attention: " + ", ".join(dict.fromkeys(report["proof"])))
    return lines


def smallcap_lines(report: dict) -> list[str]:
    """Summarise the small-cap report: case counts, then the number of glyphs in each problem list."""
    lines = [f"{case}: {count}" for case, count in report["counts"].items()]
    lines += [f"{key.replace('_', ' ')}: {len(report[key])}" for key in SMALLCAP_KEYS]
    return lines


def main() -> None:
    """Build both reports for the current font and show them."""
    from fly.ap.glyphs.case_coverage.controller import run
    from fly.ap.glyphs.case_coverage.model import Options
    from fly.ap.glyphs.smallcaps.capture import current_report

    try:
        snapshot = run(Options(allFonts=False), metadata, preferred, proof=lambda *args, **kwargs: None)
        smallcaps = current_report()
    except (ValueError, TimeoutError) as error:
        notify(TITLE, "The reports could not be built: " + str(error))
        return
    lines = []
    for font in snapshot.fonts:
        lines += [f"Case coverage: {font.label} ({font.master})"] + case_lines(font.report) + [""]
    lines += ["Small caps: " + smallcaps["family"] + f" ({smallcaps['master']})"] + smallcap_lines(smallcaps)
    notify(TITLE, "Case coverage and small caps read for the current font.", "\n".join(lines))


if __name__ == "__main__":
    main()
