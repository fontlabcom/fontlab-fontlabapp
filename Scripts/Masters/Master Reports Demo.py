# this_file: Scripts/Masters/Master Reports Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Show App's per-master node report and point counter on made-up masters.

What: Feeds sample masters to the report builders of two App tools and prints
their text: the Master Node Report, which compares every master with the first
one path by path and node by node (fontlabapp.masters.node_report.model), and
the Master Point Counter, which lists points, handles, nodes and paths of each
master layer (fontlabapp.masters.point_counts.model).
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is read from a font or written. The masters are plain values
in this script, no window opens and no panel (node_report.show,
point_counts.show) or native reader is called. No font, master, selection,
history, preference, Output or clipboard is touched.
"""

TITLE = "Master Reports Demo"


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def node_report() -> str:
    """Regular matches Light; Bold has a curve where Light has a line, and lacks a path."""
    from fly.ap.masters.layers.compatibility.model import GlyphLayers, Layer
    from fly.ap.masters.node_report import model

    square = ("line", "line", "line", "line")
    rounded = ("line", "curve", "offcurve", "offcurve", "line", "line")
    group = GlyphLayers(
        "o",
        (
            Layer("Light", (square, square[:3])),
            Layer("Regular", (square, square[:3])),
            Layer("Bold", (rounded,)),
        ),
    )
    return model.render((group,))


def point_counter() -> str:
    """Three master layers of one glyph; Bold has one curve more."""
    from fly.ap.contours.point_counts.model import Counts, LayerCount
    from fly.ap.masters.point_counts import model

    rows = (
        LayerCount("Light", Counts(4, 8, 16, 2)),
        LayerCount("Regular", Counts(4, 8, 16, 2)),
        LayerCount("Bold", Counts(4, 9, 18, 2)),
    )
    return model.render(rows)


def main() -> None:
    """Show the sample reports; no font is needed."""
    lines = []
    for heading, build in (("Master Node Report", node_report), ("Master Point Counter", point_counter)):
        lines += [heading + ":", build().rstrip(), ""]
    notify(TITLE, "Sample master reports. Nothing was read or written.", "\n".join(lines))


if __name__ == "__main__":
    main()
