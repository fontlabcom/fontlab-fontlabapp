# this_file: Scripts/Metrics/Spacing Studio Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Spacing Studio: sidebearings, reference copies, italic spacing and spacing strings.

What: Opens the Spacing Studio window (fontlabapp.studios.spacing_studio) for
the current font. A TMetrics preview sits on top. Sidebearings sets, adds to or
scales LSB/RSB, equalizes them or centres the ink in the advance; Reference
copies metrics from a reference glyph, syncs sidebearings from a reference
master and compares layer measurements; Italic changes sidebearings measured on
the de-slanted outline; Strings shows spacing strings, an offset preview and
the standalone TMetrics window.
Use: Open a font, type glyph names or use the font selection, then press a
button. Each result row shows the change; choosing a row shows the glyph.
Safety: Writes go to the explicit layer of the selected preview master (or every
master), one named Undo step each ("Spacing Studio: ..."), and are read back.
Bases move before composites; a composite whose base moves is not shifted again.
Auto, metrics-linked and hinted layers are skipped. The comparison, offset
preview and strings are read-only. With no font open the window says so.
"""

TITLE = "Spacing Studio Demo"


def main() -> None:
    """Open Spacing Studio, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.spacing_studio import show

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(qt, parent, TITLE, f"Spacing Studio did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
