# this_file: Scripts/Reports/Font Reports Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open FontLab's read-only snapshot reports about the current font.

What: Opens four nonmodal report windows: glyph-set differences and composite
differences across the open fonts (fontlabapp.proof.crossfont.model.show),
the master node compatibility report and the SVG path commands dump of the
first selected layer (fontlabapp.proof.reports.specialized_ui).
Use: Run it with a font open (and glyphs selected for the last two). Read the
text, click Refresh to read the font again, and Close each window when done.
Safety: Read-only. The windows read the open fonts and the selection once when
they open and again when you click Refresh; they never change a font, master,
selection, history, preference or Output. Text in a window can be selected and
copied with the usual editing keys. If one report fails to open, the others
still do and a message lists what failed. With no font open nothing opens.
"""

TITLE = "Font Reports Demo"


def main() -> None:
    """Open each report on its own, then list any that failed."""
    import fly
    from fly.ap.core.scripting import current_package, show_script_dialog
    from fly.ap.proof.crossfont.model import show
    from fly.ap.proof.reports.specialized_ui import MasterNodeReportDialog, SvgPathCommandsDialog
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font first. These reports read the open fonts.", "Information", kind.Ok)
        return
    reports = (
        ("glyph set differences", show),
        ("composite differences", lambda: show(composites=True)),
        ("master node report", lambda: show_script_dialog(MasterNodeReportDialog, MasterNodeReportDialog.KEY)),
        ("SVG path commands", lambda: show_script_dialog(SvgPathCommandsDialog, SvgPathCommandsDialog.KEY)),
    )
    failures = []
    for label, opener in reports:
        try:
            opener()
        except (ValueError, RuntimeError, TimeoutError) as error:
            failures.append(f"{label}: {error}")
    if failures:
        run_standard_message_box(qt, parent, TITLE, "Some reports did not open:\n" + "\n".join(failures), "Warning", kind.Ok)


if __name__ == "__main__":
    main()
