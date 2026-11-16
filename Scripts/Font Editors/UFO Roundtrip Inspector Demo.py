# this_file: Scripts/Font Editors/UFO Roundtrip Inspector Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Inspect an owned temporary UFO export/import without overwriting the source.

What: Compare all readable UFO semantic families and report adapter losses.
Use: Open a font and press Inspect owned UFO roundtrip. The complete report
remains in the window; temporary files and the detached import are cleaned up.
The window uses fontlabapp.fontui.ufo_roundtrip_editor.RoundtripEditor for
owned staging and semantic comparison.

Safety: No source save, mutation or close. Native conversion has listed losses;
ordinary tests do not establish native preservation or history acceptance.
"""


def main():
    """Capture the current font once and retain the inspector window."""
    from fly.fp.world import FontWorld

    from fly.ap.fontui.ufo_roundtrip import show

    return show(FontWorld().CurrentFont())


if __name__ == '__main__':
    main()
