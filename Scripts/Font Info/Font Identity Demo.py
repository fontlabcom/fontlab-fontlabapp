# this_file: Scripts/Font Info/Font Identity Demo.py
# SPDX-License-Identifier: Apache-2.0
# FLM: Font Info · Font Identity
"""Open Font Identity; controls, preview and actions share one owned window.

Retained task models: fontlabapp.fonts.identity_tools.

What: Review font versions, names and credits, and trial-font naming.
Use: Open this demo, choose a task tab and review Preview Changes before Apply.
Safety: Use an owned test font. The preview is read-only; task writers retain
their original target and history guards. Native Undo/Redo and saved-font
acceptance remain separate from this demo.
"""


def main():
    """Open the task studio in FontLab."""
    from fly.ap.studios.font_identity.app import show
    return show()


if __name__ == "__main__":
    main()
