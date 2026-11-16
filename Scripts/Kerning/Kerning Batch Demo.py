# this_file: Scripts/Kerning/Kerning Batch Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Show the snapshot and the checks that App's kerning batch writer starts with.

What: Reads one complete kerning snapshot of the open font
(fontlabapp.kerning.batch.snapshot_kerning): masters, explicit pairs and
classes per master. Then it runs the batch writer's pair check,
fontlabapp.kerning.batch.validate_pair, on the first explicit pair and on a
pair with a glyph name that does not exist, to show what it accepts and what
it refuses before any write.
Use: Open a font and run it, then click Show Details.
Safety: Read-only. Only the snapshot and the pair check run; write_kerning is
never called, so no pair, class, history step or active master changes. No
font, master, selection, history, preference, Output or clipboard is written.
With no font open it says so.
"""

TITLE = "Kerning Batch Demo"
MISSING = "no.such.glyph"


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def check_line(batch, package, snapshot, master: str, pair: tuple) -> str:
    """The checked native sides of a pair, or the reason the batch writer refuses it."""
    try:
        sides = batch.validate_pair(package, master, pair, groups=snapshot.groups[master])
    except ValueError as error:
        return f"{pair} -> refused: {error}"
    return f"{pair} -> accepted as {sides}"


def main() -> None:
    """Snapshot the font and run the pair check; nothing is written."""
    from fly.ap.core.scripting import current_package
    from fly.ap.kerning import batch

    package = current_package()
    if package is None:
        notify(TITLE, "Open a font first. The snapshot reads its kerning.")
        return
    try:
        snapshot = batch.snapshot_kerning(package)
        lines = [f"{master}: {len(snapshot.pairs[master])} explicit pairs, {len(snapshot.groups[master])} classes" for master in snapshot.masters]
        master = package.master
        first = next(iter(snapshot.pairs[master]), None)
        lines.append("")
        if first is not None:
            lines.append(check_line(batch, package, snapshot, master, first))
        lines.append(check_line(batch, package, snapshot, master, (MISSING, MISSING)))
    except (ValueError, RuntimeError, TimeoutError) as error:
        notify(TITLE, f"The kerning could not be read: {error}")
        return
    notify(TITLE, f"Snapshot of {len(snapshot.masters)} master(s). Nothing was written.", "\n".join(lines))


if __name__ == "__main__":
    main()
