# this_file: Scripts/Proof/Native Tabs Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Count the open glyph canvases and read the active text block, read-only.

What: Asks fontlabapp.core.native_tabs what text-tab tools ask before they
create a tab: canvases(native, workspace) lists the glyph canvases and
rendered_block(workspace) returns the active text block, or the first block
of the active canvas. A message box shows the canvas count and the glyph
names of that block (the first 40). FontLab 9.0.9804 raises TypeError from
the workspace's canvas list, so there canvases() reports only the active one.
Use: Run it with a Glyph window or text tab in front, then without any to see
the clean "nothing shown" report. A font is not required.
Safety: Read-only. It reads the workspace's canvas list, the active text
block and its glyph names. It creates no tab, sender or connection, and it
does not call the shape-activation helpers of the module. No font,
selection, history, preference, Output or clipboard is written.
"""

TITLE = "Native Tabs Demo"
SHOWN = 40  # glyph names listed from the block


def block_lines(block) -> list[str]:
    """The block's glyph names in order, or the reason there is no block."""
    if block is None:
        return ["No text block is shown: open a Glyph window or a text tab first."]
    names = [info.glyph.name for info in block.getAllGlyphs() or ()]
    more = f" ... (+{len(names) - SHOWN} more)" if len(names) > SHOWN else ""
    return [f"Active block: {len(names)} glyphs", " ".join(names[:SHOWN]) + more]


def notify(text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, TITLE, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(TITLE)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def main() -> None:
    """Report the canvases and the active block, or that FontLab has no workspace."""
    import fly
    from fly.ap.core.native_tabs import canvases, rendered_block

    native = fly.fl
    workspace = native.flWorkspace.instance()
    if workspace is None:
        notify("FontLab has no workspace to read.")
        return
    count = len(canvases(native, workspace))
    notify(f"Glyph canvases found: {count} (some builds list only the active one).", "\n".join(block_lines(rendered_block(workspace))))


if __name__ == "__main__":
    main()
