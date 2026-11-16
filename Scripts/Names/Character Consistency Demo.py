# this_file: Scripts/Names/Character Consistency Demo.py
# SPDX-License-Identifier: Apache-2.0
# FLM: Names · Character Consistency
"""Open Character Consistency; controls, preview and actions share one owned window.

What: Review case counterparts, character coverage and instance style links.
Use: Open this demo, choose a task tab and review Preview Changes before Apply.
Safety: Use an owned test font. The preview is read-only; task writers retain
their original target and history guards. Native Undo/Redo and saved-font
acceptance remain separate from this demo.
Style Linker native instance-write qualification remains pending.
"""


def main():
    """Open the task studio in FontLab."""
    from fly.ap.studios.character_consistency.app import show
    return show()


if __name__ == "__main__":
    main()
