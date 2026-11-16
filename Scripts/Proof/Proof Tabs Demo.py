# this_file: Scripts/Proof/Proof Tabs Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Build sample proofs in memory, then open them in new text tabs if you agree.

What: Makes a seeded random proof (fontlabapp.proof.random.generate) and two
context proofs (fontlabapp.proof.context.proof_lines) from made-up glyph
names, and shows them in a message box. Then it asks twice whether to open
them: the random words with fontlabapp.proof.tabs.text.open_text_tab, and the
context rows with fontlabapp.proof.tabs.named.open_named_tab.
Use: Run it with a font open. Read the sample under Show Details, then answer
each question. Yes opens one new text tab on the current font; No opens none.
Glyph names the font lacks show as missing slots in the second tab.
Safety: The proofs come from sample text and fixed names; the selection and
the font are not read for them. A new tab opens only after you click Yes and
is a visible window, not a font change. Close it like any tab. While it
creates the tab, fontlabapp reads every glyph shape's on/off (active) state
in the font and writes back any state the tab creation changed. No other
font data, selection, history, preference, Output or clipboard is written.
If creation fails, a new tab may remain; close it. Without a font the demo
shows the samples and opens no tab.
"""

import random

TITLE = "Proof Tabs Demo"
SEED = 208  # the same sample every run
MODE = "lowercase-words"
CONTEXT = (("HHOHH", ("n", "o")), ("lining", ("H",)))  # (mode, selected names)
PREVIEW_ROWS = 3


def context_text(rows: tuple) -> str:
    """Join glyph-name rows into readable lines, a blank row for an empty one."""
    return "\n".join(" ".join(row) for row in rows)


def sample_lines(generate, proof_lines) -> list[str]:
    """The seeded random proof and the first rows of each context proof."""
    lines = [f"random {MODE}: {generate(MODE, rng=random.Random(SEED)).strip()}"]
    for mode, names in CONTEXT:
        rows = proof_lines(mode, names)
        lines.append(f"context {mode} for {', '.join(names)}: {len(rows)} rows")
        lines += [f"    {context_text((row,))}" for row in rows[:PREVIEW_ROWS]]
    return lines


def main() -> None:
    """Show the samples and open the confirmed tabs."""
    import fly
    from fly.ap.core.scripting import current_package
    from fly.ap.proof.context import proof_lines
    from fly.ap.proof.random import generate
    from fly.ap.proof.tabs.named import open_named_tab
    from fly.ap.proof.tabs.text import open_text_tab
    from fly.ap.qt.dialogs import create_message_box, run_message_box, run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    text = generate(MODE, rng=random.Random(SEED))
    package = current_package()
    summary = "Open a font to open sample tabs." if package is None else "Sample proofs are ready."
    box = create_message_box(qt.QtGui, TITLE, summary, "Information", (parent,), detail="\n".join(sample_lines(generate, proof_lines)))
    box.setWindowTitle(TITLE)
    run_message_box(box, kind.Ok)
    if package is None:
        return
    choices = (
        ("the seeded random words", lambda: open_text_tab(text, expected_id=package.id)),
        (
            "the context rows for n and o",
            lambda: open_named_tab(
                proof_lines(*CONTEXT[0]), expected_id=package.id, master=package.master
            ),
        ),
    )
    for label, opener in choices:
        question = (
            f"Open {label} in a new text tab on {package.master}? "
            "It snapshots and restores every shape's active flag."
        )
        if run_standard_message_box(qt, parent, TITLE, question, "Question", kind.Yes | kind.No, kind.No) != kind.Yes:
            continue
        try:
            opener()
        except (ValueError, RuntimeError, TimeoutError, TypeError, ExceptionGroup) as error:
            run_standard_message_box(qt, parent, TITLE, f"No tab for {label}: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
