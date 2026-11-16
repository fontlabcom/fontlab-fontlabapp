# this_file: Scripts/Reports/Nodes Near Zones Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Nodes Near Zones: open contours with a Select glyphs action.

What: Opens fontlabapp.fontui.nodes_near_zones, one shared App window with a read-only
report and Refresh.
Use: Read the report; Select glyphs selects each listed glyph.
Extension: fontlabapp.fontui.nodes_near_zones.show(parent=None) returns the shell.
Safety: Read-only except Select glyphs, which changes the selection only.
"""

TITLE = "Nodes Near Zones Demo"
DOMAIN = "fontlabapp.contours.nodes_near_zones"  # scan model and native owner behind the window


def main() -> None:
    """Open the window, or say why it did not open."""
    import fly
    from fly.ap.fontui.nodes_near_zones import show
    from fly.ap.qt.dialogs import run_standard_message_box

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(qt, parent, TITLE, f"Nodes Near Zones did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
