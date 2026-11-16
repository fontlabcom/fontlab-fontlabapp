# this_file: Scripts/Font Editors/Representation and Notification Explorer Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Select a glyph and inspect its representations and observed scripting changes.

What: The report shows cached area and fresh decomposed bounds and outlines.

Use: Open a font and run once. Select a glyph in the captured font's browser.
Refresh rereads that view. Actual Glyph.Changed callbacks update the report and
count observed events; no synthetic changes are posted.

Safety: Representation reads may populate caches but never invalidate borrowed caches or discard unfinished edits.
External native changes are not verified by this scripting observer. Close releases
observers and widgets without editing, saving or closing the borrowed font.
"""


def main():
    """Capture the current font once and retain its owned explorer."""
    from fly.fp.world import FontWorld

    from fly.ap.fontui.representation_notifications import show

    return show(FontWorld().CurrentFont())


if __name__ == "__main__":
    main()
