# this_file: Scripts/Font Editors/Core PythonQt Labs Demo.py
# SPDX-License-Identifier: Apache-2.0
"""What: Open Model Filtering Lab and compare its seven distinct lesson profiles.

Setup: matching WP09 App candidate and fontlab-python-lessons in FontLab 9.
Use: open a font, filter or sort its names, then preview the matching glyphs.
The public fontlabapp.studios.core_pythonqt_labs route composes the retained
fontlabapp.fontui.core_pythonqt_labs profiles with a read-only TMetrics preview.
Safety: The preview is read-only; selection actions retain their active
Font-window safety checks.
"""


def main():
    """Open the filtering lab through the same route used by Examples."""
    from fly.ap.studios.core_pythonqt_labs import show

    return show("E01")


if __name__ == "__main__":
    main()
