# this_file: Scripts/Font Editors/Interpolation Preview Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Preview one glyph between two masters using designspace location controls.

What: Designspace location controls drive the existing read-only two-master
outline preview for an explicitly named glyph.

Use: Open a FontLab font and run this demo. Enter a glyph name, choose two
source masters, then move the axis controls or select a source/instance.
The existing two-master preview blends stored outlines in mapped design
coordinates. Locations outside the selected segment are refused visibly;
this is not a general multidimensional variable-font interpolator.

Safety: Capture the current font once. Refresh keeps that borrowed document
and never changes font data, selection, masters, history or pending edits.
Close releases only owned widgets and callbacks. Native PythonQt rendering,
complete font preservation and installed-artifact checks remain separate.
"""


def main():
    """Capture once at invocation and open the shared read-only preview."""
    from fly.fp.world import FontWorld

    from fly.ap.fontui.interpolation_preview import show

    return show(FontWorld().CurrentFont())


if __name__ == "__main__":
    main()
