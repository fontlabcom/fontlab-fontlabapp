# this_file: Scripts/Metrics/Vertical Metrics & Zones Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Vertical Metrics & Zones: master metrics, calculated font metrics, zones, italic angle and a diagram.

What: Opens the Vertical Metrics & Zones window
(fontlabapp.studios.vertical_metrics) for the current font. A read-only
TMetrics preview sits on top. Metrics table edits each master's ascender,
descender, x-height and cap height; Calculate sets hhea, Win and (optionally)
typo metrics that enclose every glyph and compares the stored metrics of
every open font; Zones edits alignment zones per master and suggests them
from the overshoots of H, O, x and o; Italic angle sets each master's angle;
Diagram draws H, x, b and p against every master's lines and lists nodes
that sit just off them.
Use: Open a font and run it. Set the values; each edit tab lists exactly the
master values it will change. Press its Set button.
Safety: Diagram, Nodes Near Zones and the font comparison only read. Nothing
changes until you press Set. It writes exactly the listed values as one named
Undo step ("Vertical Metrics: ..."), and refuses when a value changed after
the list was made; press Refresh then. With no font open the window opens
without a preview and says so.
"""

TITLE = "Vertical Metrics & Zones Demo"


def main() -> None:
    """Open Vertical Metrics & Zones, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.vertical_metrics import show

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(
            qt,
            parent,
            TITLE,
            f"Vertical Metrics & Zones did not open: {error}",
            "Warning",
            kind.Ok,
        )


if __name__ == "__main__":
    main()
