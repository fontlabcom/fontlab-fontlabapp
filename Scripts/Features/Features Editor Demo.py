# this_file: Scripts/Features/Features Editor Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Preview suffix-based feature code for the open font in App's feature panel.

What: Opens a nonmodal panel built on FeaturesDialog
(fontlabapp.features.editor.ui), the shell of App's feature tools. Type a
feature tag (such as ss01) and a glyph-name suffix (such as .ss01); the panel
reads the font's glyph names, pairs each base glyph with its suffixed
alternate (suffix_pairs in fontlabapp.features.code) and shows the generated
substitution block (feature_text).
Use: Open a font and run it. Edit the tag or suffix and the preview updates;
a bad tag shows its error in the status line. Close ends it.
Safety: Read-only. The panel reads the font's glyph names, and no font feature
code is read or changed. The shell's Apply button is kept disabled and
relabelled, and its handler only reports that nothing was written. The panel
has no Copy button, so the shell's copy_text, which would write the clipboard,
is never called. No font, feature, master, selection, history, preference,
Output or clipboard is written. With no font open nothing opens.
"""

TITLE = "Features Editor Demo"


def panel_class() -> type:
    """Build the read-only preview panel on the shared feature-panel shell."""
    import fly
    from fly.ap.features import code
    from fly.ap.features.editor.ui import FeaturesDialog

    gui = fly.qt.QtGui

    class FeaturePreview(FeaturesDialog):
        """Generated substitutions for one tag and suffix; Apply never writes."""

        KEY = "features_editor_demo"

        def __init__(self, parent=None) -> None:
            super().__init__(parent, title=TITLE, subtitle="Suffix pairs and the feature code they give. Read-only: nothing here changes the font.", key=self.KEY)

        def setup(self) -> None:
            """Create the tag and suffix fields and the preview box."""
            body = self.prepare()
            self.apply_button.setText("Apply (demo: no write)")
            self.tag_edit, self.suffix_edit = gui.QLineEdit("ss01"), gui.QLineEdit(".ss01")
            form = gui.QFormLayout()
            form.addRow("Feature tag", self.tag_edit)
            form.addRow("Glyph suffix", self.suffix_edit)
            body.addLayout(form)
            self.preview = gui.QPlainTextEdit()
            self.preview.setReadOnly(True)
            body.addWidget(self.preview, 1)
            for edit in (self.tag_edit, self.suffix_edit):
                self._connect(edit.textChanged, lambda *args: self.refresh())

        def refresh(self) -> None:
            """Generate the block for the typed tag and suffix; a bad tag clears the preview and shows its error."""
            self.ensure_font()
            self._preview_valid = False
            self.apply_button.setEnabled(False)
            self.preview.clear()
            pairs = code.suffix_pairs(self.names, self.suffix_edit.text)
            self.preview.setPlainText(code.feature_text(self.tag_edit.text, pairs))
            self.status.setText(f"{len(pairs)} suffix pairs among {len(self.names)} glyphs. Nothing changed.")

        def apply(self) -> None:
            """Replace the writing Apply: state that nothing was written."""
            self.status.setText("Demo only: nothing was written. Close the panel.")

    return FeaturePreview


def main() -> None:
    """Open the panel on the current font, or say that a font is needed."""
    import fly
    from fly.ap.core.scripting import current_package, show_script_dialog
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font first. The panel previews feature code for its glyphs.", "Information", kind.Ok)
        return
    try:
        panel = panel_class()
        show_script_dialog(panel, panel.KEY)
    except (ValueError, RuntimeError, TimeoutError) as error:
        run_standard_message_box(qt, parent, TITLE, f"The panel did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
