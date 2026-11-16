# this_file: Scripts/Font Editors/Font Info and Vertical Metrics Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Stage font information beside the captured font's vertical metrics report.

What: Edit the captured font's information in the shared Font Info editor and
explicitly Apply it, or Revert to reload stored values. The vertical metrics
report lists OS/2 typo, hhea and Windows ascent/descent values, keeping unset
values separate from explicit zero; Refresh re-reads it without discarding
staged edits.

Use: Open a FontLab font, then run this menu command. The window captures the
current font once; switching the active document does not retarget it. Close
the window when finished; this disconnects its callbacks and releases only its
owned controls, leaving the borrowed document open.

Safety: Writes happen only on Apply and are validated by the shared editor; the
report itself never writes, saves or closes fonts. Values are for the captured
font's current info source, not an all-master comparison. Native history and
saved/reopened behavior require separate host checks.
"""


def main():
    """Capture the current font once and return the shared window owner."""
    from fly.fp.world import FontWorld
    from fly.ap.fontui.font_info_metrics import show

    return show(FontWorld().CurrentFont())


if __name__ == "__main__":
    main()
