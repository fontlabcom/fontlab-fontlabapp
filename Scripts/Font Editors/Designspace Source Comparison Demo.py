# this_file: Scripts/Font Editors/Designspace Source Comparison Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Compare captured-font source layers or explicitly open a designspace.

What: Choose reference and comparison layers and a glyph to inspect advance
widths and structural compatibility (ordered contour/node types and anchor and
component name sets). Open designspace reads the selected external file and its
referenced UFOs to report source metrics, advances and missing glyphs. Structural
compatibility does not certify interpolation or variable-font export.

Use: Open a FontLab font, then run this menu command. Refresh repeats the read
of the captured font without switching masters. Changing the host's current
font does not retarget the window. Open designspace shows a distinct external
report; cancel or read failure preserves the previous complete report.

Safety: Both comparisons are read-only. Captured-font reads exclude unfinished
edits held in another scripting wrapper. The borrowed FontLab document is never
edited, saved or closed. Closing the window disconnects its owned callbacks.
Cooperative deadline and closure checks run between external reads; blocking I/O
cannot be preempted. Native lifetime and whole-font preservation still require
separate host checks.
"""


def main():
    """Capture the current font once and return the shared window owner."""
    from fly.fp.world import FontWorld
    from fly.ap.fontui.source_comparison import show

    return show(FontWorld().CurrentFont())


if __name__ == "__main__":
    main()
