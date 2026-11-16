# this_file: Scripts/Kerning/Kerning Cutoff Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Show which kerning pairs the cutoff filter would clamp, without clamping.

What: Plans the Kerning Cutoff filter (fontlabapp.kerning.cutoff.plan) on a
sample of pairs and, with a font open, on every explicit pair of every master
(fontlabapp.kerning.batch.snapshot_kerning). The filter would clamp values
below -250 to -250 and above 100 to 100; the demo lists how many pairs per
master it would change.
Use: Run it from the Scripts menu and click Show Details. A font is optional;
with one open the real counts follow the sample.
Safety: A dry run. The plan is printed and never passed to the writer, so no
kerning changes. The font read is a snapshot of pairs, classes and master
names that never switches the master. No font, master, selection, history,
preference, Output or clipboard is written; cutoff.apply and cutoff.run are
not called.
"""

TITLE = "Kerning Cutoff Demo"
SAMPLE = {"Regular": {("A", "V"): -300, ("T", "o"): -90, ("@O_left", "@O_right"): 140, ("L", "y"): 100}}


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def count_lines(cutoff, pairs: dict) -> list[str]:
    """For each master, how many pairs the filter would clamp, from the real plan."""
    edits = cutoff.plan(pairs)
    return [f"{master}: {len(changes)} of {len(pairs[master])} pairs would change" for master, changes in edits.items()]


def main() -> None:
    """Show the sample plan and, with a font open, the plan for the real kerning."""
    from fly.ap.core.scripting import current_package
    from fly.ap.kerning import cutoff

    lines = [f"Limits: {cutoff.LOWER} to {cutoff.UPPER} (inclusive).", f"Sample pairs: {SAMPLE}"]
    lines += ["Sample result: " + str(cutoff.plan(SAMPLE)), *count_lines(cutoff, SAMPLE)]
    summary = "Sample plan only. Open a font to count its pairs. Nothing was changed."
    package = current_package()
    if package is not None:
        from fly.ap.kerning.batch import snapshot_kerning

        try:
            snapshot = snapshot_kerning(package, typed=True)
            lines += ["", "Current font:", *count_lines(cutoff, snapshot.pairs)]
            summary = "Planned the cutoff for the current font. Nothing was changed."
        except (ValueError, RuntimeError, TimeoutError) as error:
            summary = f"The font's kerning could not be read: {error}"
    notify(TITLE, summary, "\n".join(lines))


if __name__ == "__main__":
    main()
