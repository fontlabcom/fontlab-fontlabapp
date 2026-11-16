# this_file: src/fontlabapp/glyphs/identity_tools/glyph_labels/different_colours.py
# SPDX-License-Identifier: Apache-2.0
"""Preview additive mark-colour selection using the existing native transport."""
from PythonQt import QtGui

from fontlabapp import _native
from fontlabapp.core.scripting import current_package
from fontlabapp.fontui.lifecycle import Owned
from fontlabapp.glyphs.selection._mark_colors_native import _capture
from fontlabapp.glyphs.selection.mark_colors import plan, select_different_mark_colours


class Panel(Owned):
    """Keep a captured selection; refuse changed marks before the native action."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.status = QtGui.QLabel(self.widget)
        self.status.setWordWrap(True)
        self.layout.addWidget(self.status)
        self.before = ()
        self.package_id = None
        self.refresh()

    def refresh(self):
        package = current_package()
        if package is None:
            raise ValueError("Open a font and activate its Font window.")
        self.package_id = package.id
        self.before = _capture(_native("FL").fl)
        indices = set(plan(self.before))
        names = [glyph.name for glyph in self.before if glyph.index in indices]
        self.status.setText(
            "Keep the initial selection and add displayed glyphs with other colours. "
            "Filtered-out glyphs stay untouched.\nCandidates: " + (", ".join(names) or "None")
        )

    def apply(self):
        if current_package(self.package_id) is None or _capture(_native("FL").fl) != self.before:
            raise ValueError("Font, marks or selection changed; refresh and preview again.")
        names = select_different_mark_colours()
        self.refresh()
        self.status.setText("Added: " + (", ".join(names) or "None"))
        return names
