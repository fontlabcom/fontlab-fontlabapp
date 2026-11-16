# this_file: Scripts/Kerning/Kerning Persistence Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Audit which explicit kerning pairs FontLab would clip when it reloads a font.

What: Opens the nonmodal Kerning Persistence Audit
(fontlabapp.kerning.persistence.ui.KerningPersistenceDialog). It lists every
explicit pair of the current master, or of all masters, with its value and
whether the value lies outside plus or minus twice the units per em.
Use: Open a font and run it. Switch between Current master and All masters,
type in the search box to filter, click Refresh after changes and Close when
done.
Safety: Read-only. The audit reads the explicit pairs, the units per em and
the master names; it never switches the master or writes a font, selection,
history, preference, Output or clipboard. Its status line ends with "No
changes made". With no font open nothing opens.
"""

TITLE = "Kerning Persistence Demo"


def main() -> None:
    """Open the audit on the current font, or say that a font is needed."""
    import fly
    from fly.ap.core.scripting import current_package, show_script_dialog
    from fly.ap.kerning.persistence.ui import KerningPersistenceDialog
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font first. The audit reads its kerning.", "Information", kind.Ok)
        return
    try:
        show_script_dialog(KerningPersistenceDialog, KerningPersistenceDialog.KEY)
    except (ValueError, RuntimeError, TimeoutError) as error:
        run_standard_message_box(qt, parent, TITLE, f"The audit did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
