# this_file: Scripts/Kerning/Kerning Proofs Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Preview App's four kerning proofs and open one in new tabs if you agree.

What: Reads the text of the four kerning proofs
(fontlabapp.kerning.proofs.proof_texts: hoefler-lowercase, hoefler-uppercase,
kernking and kernsym) and shows how many tab texts each has and the first
line of each. Then it asks whether to open the kernking proof with
fontlabapp.kerning.proofs.run, which creates one text tab per proof text.
Use: Run it with a font open. Read the summary under Show Details, then answer
the question. Yes opens the tabs on the current font and master; No opens none.
Safety: The proof texts come from a resource file shipped with App; the font
is not read for them. A tab opens only after you click Yes and is a visible
window, not a font change. Close it like any tab. While it creates each tab,
fontlabapp reads every glyph shape's on/off (active) state in the font and
writes back any state the tab creation changed. No other font data, selection,
history, preference, Output or clipboard is written. If creation fails, a new
tab may remain; close it. Without a font the demo shows the summary and opens
no tab.
"""

TITLE = "Kerning Proofs Demo"
OPEN_MODE = "kernking"


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def summary_lines(proofs) -> list[str]:
    """One line per proof mode: its text count, then the first line of its first text."""
    lines = []
    for mode in proofs.MODES:
        texts = proofs.proof_texts(mode)
        first = texts[0].splitlines()[0] if texts and texts[0].strip() else ""
        lines.append(f"{mode}: {len(texts)} tab text(s); starts with {first[:60]!r}")
    return lines


def main() -> None:
    """Show the summary, then open the confirmed proof."""
    import fly
    from fly.ap.core.scripting import current_package
    from fly.ap.kerning import proofs
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    package = current_package()
    summary = "Open a font to open a proof in tabs." if package is None else "The four kerning proofs are ready."
    notify(TITLE, summary, "\n".join(summary_lines(proofs)))
    if package is None:
        return
    count = len(proofs.proof_texts(OPEN_MODE))
    question = (
        f"Open the {OPEN_MODE} proof as {count} new text tab(s) on {package.master}? "
        "It snapshots and restores every shape's active flag."
    )
    if run_standard_message_box(qt, parent, TITLE, question, "Question", kind.Yes | kind.No, kind.No) != kind.Yes:
        return
    try:
        proofs.run(OPEN_MODE)
    except (ValueError, RuntimeError, TimeoutError) as error:
        run_standard_message_box(qt, parent, TITLE, f"The proof did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
