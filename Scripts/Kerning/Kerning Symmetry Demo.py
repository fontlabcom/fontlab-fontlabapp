# this_file: Scripts/Kerning/Kerning Symmetry Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Dry-run the Kerning Symmetry plan and report what it would change.

What: Reads the explicit kerning and class order of every master
(fontlabapp.kerning.symmetry.native.capture), plans the symmetric values for
the configured target glyphs (fontlabapp.kerning.symmetry.model.plan) and
shows, per master, the number of comparisons, mismatches and keys that would
change, plus the first mismatches.
Use: Open a font that has the target glyphs (a.sc, v.sc, w.sc, y.sc, t.sc,
x.sc, o.sc and AVWYUX80TOovwx:!*|`.-) and run it, then click Show Details. A
missing target glyph is reported by name.
Safety: A dry run. The plan is computed and printed; the writer is never
called, so kerning stays as it is. The demo does not call the tool's own
run or show functions because those apply the plan at once. It reads pairs and
classes of each master without switching it and writes no font, master,
selection, history, preference, Output or clipboard.
"""

from time import monotonic

TITLE = "Kerning Symmetry Demo"
SECONDS = 2.5
MAX_ROWS = 6


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def plan_lines(report: dict) -> list[str]:
    """Per-master counts and the first mismatches from the plan description."""
    lines = []
    for master in report["masters"]:
        lines.append(f"{master['master']}: {master['comparisons']} comparisons, {master['mismatch_count']} mismatches, {master['net_changed_keys']} keys would change.")
        for row in master["mismatches"][:MAX_ROWS]:
            lines.append(f"    {row['glyph_pair'][0]} / {row['glyph_pair'][1]}: before {row['before']}, would {row['operation']} at {row['requested_value']:g}")
    if report["skipped_masters"]:
        lines.append("Skipped masters: " + ", ".join(report["skipped_masters"]))
    return lines


def main() -> None:
    """Capture, plan and describe; nothing is written."""
    from fly.ap.core.scripting import current_package
    from fly.ap.kerning.symmetry.model import plan
    from fly.ap.kerning.symmetry.native import capture, describe

    package = current_package()
    if package is None:
        notify(TITLE, "Open a font first. The dry run reads its kerning.")
        return
    end = monotonic() + SECONDS

    def check() -> None:
        if monotonic() >= end:
            raise TimeoutError("The dry run took too long; nothing was written.")

    try:
        before = capture(package, check)
        result = plan(before.kerning, tuple(name for _, _, name in before.bindings), check=check)
    except (ValueError, RuntimeError, TimeoutError) as error:
        notify(TITLE, f"No plan could be made: {error}")
        return
    report = describe(result, False)
    changes = sum(master["net_changed_keys"] for master in report["masters"])
    notify(TITLE, f"Dry run: {changes} key(s) would change. Nothing was written.", "\n".join(plan_lines(report)))


if __name__ == "__main__":
    main()
