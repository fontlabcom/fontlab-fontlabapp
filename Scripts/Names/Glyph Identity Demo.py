# this_file: Scripts/Names/Glyph Identity Demo.py
# SPDX-License-Identifier: Apache-2.0
# FLM: Names · Glyph Identity
"""Open Glyph Identity; controls, preview and actions share one owned window.

Shared assembly: fontlabapp.fontui.identity_tools.
Retained task models: fontlabapp.glyphs.identity_tools.

What: Preview batch renames, suffix changes and Unicode assignments or removals.
Use: Open this demo, choose a task tab and review Preview Changes before Apply.
Safety: Use an owned test font. The preview is read-only; task writers retain
their original target and history guards. Native Undo/Redo and saved-font
acceptance remain separate from this demo.
"""


def main():
    """Open the task studio in FontLab."""
    from fly.ap.studios.glyph_identity.app import show
    return show()


if __name__ == "__main__":
    main()
