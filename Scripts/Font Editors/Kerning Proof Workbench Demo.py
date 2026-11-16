# this_file: Scripts/Font Editors/Kerning Proof Workbench Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Inspect and edit kerning alongside a glyph sequence in one retained window.

What: Show explicit pairs, their effective group fallback and a linked proof.
Use: Open a font, run this demo and select a pair or type its glyph/group names.
Apply writes the typed value; Delete removes an explicit pair. Reload reads the
same captured font. The sequence can also show independently typed glyph names.
Safety: Apply and Delete are writers. Use an owned test font. The native backend
uses the captured font's current master and can refuse unsupported history data.
Changing the active font does not retarget this window; closing it leaves the
borrowed font open. Native Undo/Redo and saved-font acceptance remain separate.
"""


def main():
    """Capture the current borrowed font once and return the retained owner."""
    from fly.ap.fontui.kerning_proof import show
    from fly.fp.world import FontWorld

    font = FontWorld().CurrentFont()
    return show(None if font is None else font)


if __name__ == "__main__":
    main()
