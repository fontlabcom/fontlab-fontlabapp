# this_file: Scripts/Font Info/Font Info Panel Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Browse the Font Info of the current master in App's Font Info panel shell.

What: Opens a nonmodal panel built on FontInfoDialog
(fontlabapp.fonts.info.ui), the shell of App's six Font Info tools, and fills
its table with the family and style names, the vertical metrics, the OS/2 and
hhea ascenders and descenders and the version numbers of the current master.
Use: Open a font and run it. The table shows the master that was current when
the panel opened; close the panel and run the demo again after switching.
Safety: Read-only. The panel reads the listed Font Info fields of the current
master and the font's identity; it never switches a master. The shell's Apply
button is kept disabled and relabelled, and the handler behind it only
reports that nothing was written: scripting.write_font_info, the writer the
real tools use, is never called. No font, master, selection, history,
preference, Output or clipboard is written, and the panel has no Copy button.
With no font open nothing opens.
"""

TITLE = "Font Info Panel Demo"
FIELDS = (
    "familyName", "styleName", "ascender", "descender", "xHeight", "capHeight",
    "openTypeOS2TypoAscender", "openTypeOS2TypoDescender", "openTypeHheaAscender",
    "openTypeHheaDescender", "versionMajor", "versionMinor",
)  # fmt: skip


def panel_class() -> type:
    """Build the read-only panel class on the shared Font Info shell."""
    from fly.ap.fonts.info.ui import FontInfoDialog

    class InfoViewer(FontInfoDialog):
        """A table of Font Info values; Apply never writes."""

        KEY = "font_info_panel_demo"

        def __init__(self, parent=None) -> None:
            super().__init__(parent, title=TITLE, subtitle="Font Info of the current master. Read-only: nothing here changes the font.", key=self.KEY)

        def setup(self) -> None:
            """Relabel Apply so that it is clear it writes nothing."""
            self.apply_button.setText("Apply (demo: no write)")

        def refresh(self) -> None:
            """Fill the table with the current master's values and keep Apply disabled."""
            self.ensure_font()
            info = self.package.info
            self.rows(("Field", "Value"), [(field, "" if getattr(info, field) is None else getattr(info, field)) for field in FIELDS])
            self.apply_button.setEnabled(False)
            self.status.setText(f"{len(FIELDS)} fields of master {self.package.master}. Nothing changed.")

        def apply(self) -> None:
            """Replace the writing Apply: state that nothing was written."""
            self.status.setText("Demo only: nothing was written. Close the panel.")

    return InfoViewer


def main() -> None:
    """Open the panel on the current font, or say that a font is needed."""
    import fly
    from fly.ap.core.scripting import current_package, show_script_dialog
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font first. The panel lists its Font Info.", "Information", kind.Ok)
        return
    try:
        panel = panel_class()
        show_script_dialog(panel, panel.KEY)
    except (ValueError, RuntimeError, TimeoutError) as error:
        run_standard_message_box(qt, parent, TITLE, f"The panel did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
