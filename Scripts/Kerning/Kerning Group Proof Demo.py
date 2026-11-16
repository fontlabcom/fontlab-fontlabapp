# this_file: Scripts/Kerning/Kerning Group Proof Demo.py
# SPDX-License-Identifier: Apache-2.0
"""List the glyphs that share a kerning group with the selected glyph.

What: Reads the first selected glyph and every glyph's left and right kerning
group (fontlabapp.kerning.group_proof.native.capture), builds the proof rows
with fontlabapp.kerning.group_proof.model.build and shows them in one message
box: the glyph, its left-group peers (L:) and its right-group peers (R:).
Use: Open a font, select a glyph in a Font window and run it, then click Show
Details. With no selection or ambiguous groups the box says why.
Safety: Read-only and no proof tab is opened. The demo reads the selection,
the glyph order and the kerning classes of the current master, twice, and
refuses a change in between. It never switches the master or writes a font,
selection, history, preference, Output or clipboard. The real proof command
(model.run) would also open a new tab; this demo does not call it.
"""

from time import monotonic

TITLE = "Kerning Group Proof Demo"
SECONDS = 2.0


def notify(title: str, text: str, details: str = "", icon: str = "Information") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, icon, (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def proof_lines(proof) -> list[str]:
    """The proof rows as they would read in a tab: label, then peer names."""
    return [prefix + " ".join(names) for prefix, names in proof.rows]


def main() -> None:
    """Capture the selected glyph's groups and show the peers, or say why not."""
    from fly.ap.kerning.group_proof import native
    from fly.ap.kerning.group_proof.model import build

    try:
        source = native.capture(monotonic() + SECONDS)
        proof = build(source.rows, source.current_id)
    except (ValueError, RuntimeError, TimeoutError) as error:
        notify(TITLE, str(error), icon="Warning")
        return
    if not proof.has_peers:
        notify(TITLE, f"{proof.current} has no other left or right kerning-group members.")
        return
    summary = f"{proof.current}: {len(proof.left)} left-group and {len(proof.right)} right-group peers. No tab was opened."
    notify(TITLE, summary, "\n".join(proof_lines(proof)))


if __name__ == "__main__":
    main()
