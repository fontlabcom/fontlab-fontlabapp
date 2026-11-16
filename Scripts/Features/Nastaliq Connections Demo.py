# this_file: Scripts/Features/Nastaliq Connections Demo.py
# SPDX-License-Identifier: Apache-2.0
# FLM: Features · Nastaliq Connections
"""Open Nastaliq Connections; controls, preview and actions share one owned window.

What: Review the retained Nastaliq connection editor beside a glyph preview.
Use: Open this demo, choose a task tab and review Preview Changes before Apply.
Safety: Use an owned test font. The preview is read-only; task writers retain
their original target and history guards. Native Undo/Redo and saved-font
acceptance remain separate from this demo.
"""


def main():
    """Open the task studio in FontLab."""
    from fly.ap.studios.nastaliq_connections.app import show
    return show()


if __name__ == "__main__":
    main()
