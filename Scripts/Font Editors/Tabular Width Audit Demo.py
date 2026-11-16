# this_file: Scripts/Font Editors/Tabular Width Audit Demo.py
# SPDX-License-Identifier: Apache-2.0
"""What: Compare selected glyph advances with the first selected row.

Use: Choose an open font, select glyphs and refresh when open fonts change.
Safety: Borrows fonts for read-only inspection. No font data, selections,
masters, history or preferences are changed. Close the window to release
its controls; refused cleanup retains its owner for a later retry.
"""

handle = None


def main():
    """Retain a nonmodal audit over one genuine open-font world."""
    from fly.ap.fontui.tabular_audit import show
    from fly.fp.world import FontWorld

    global handle
    handle = show(FontWorld())
    return handle


if __name__ == "__main__":
    main()
