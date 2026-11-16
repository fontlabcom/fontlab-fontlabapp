# this_file: Scripts/Names/Glyph Creation Explained Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Explain how App creates new glyphs, with a sample plan that is never executed.

What: Shows, in one message box, what fontlabapp.glyphs.creation sends to
FontLab's own Add Glyph command for a sample glyph "h.sc" with one component,
the Undo steps that result, the consent text for names that may rebuild
automatic glyphs, and how fontlabapp.glyphs.copies rounds the master widths it
plans for copied glyphs.
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is created. The sample glyph is a plain value that is printed,
not passed to create_glyphs, and no font, master, selection, history,
preference, Output or clipboard is touched.
"""

import json

TITLE = "Glyph Creation Explained Demo"
SAMPLE_WIDTH = 450.5  # a metric that needs rounding, as scaled small-cap widths do


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call (copied into every Names demo)."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def explanation_lines() -> list[str]:
    """Describe the plan for the sample glyph from the real creation and copies helpers."""
    from fly.ap.glyphs import copies, creation

    width = copies.half_up(SAMPLE_WIDTH)
    spec = creation.NewGlyph("h.sc", (("Regular", width),), (), (creation.Part("Regular", "h", 0, 0),))
    return [
        f"Master width {SAMPLE_WIDTH} rounds half up to {width} (copies.half_up).",
        "",
        "Data for the fontpr set_glyph(create=True) call:",
        json.dumps(creation.glyph_data(spec), indent=2),
        "",
        "Dotted segments of h.sc: " + ", ".join(sorted(creation.segments(spec.name))),
        "Undo with outlines: " + creation.undo_text(True),
        "Undo without outlines: " + creation.undo_text(False),
        "Automatic glyphs that may be rebuilt are created only after this tick: " + creation.REBUILD_LABEL,
        "Example note: " + creation.rebuild_note(["eacute.sc", "aacute.sc", "oacute.sc"]),
    ]


def main() -> None:
    """Show the explanation; no font is needed and nothing is created."""
    notify(TITLE, "Sample plan for one new glyph. Nothing was created.", "\n".join(explanation_lines()))


if __name__ == "__main__":
    main()
