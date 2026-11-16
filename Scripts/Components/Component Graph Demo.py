# this_file: Scripts/Components/Component Graph Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open App's two elastic component dependency graphs of the current master.

What: Opens two nonmodal windows that draw which glyph is built from which
(fontlabapp.components.graph.model.show and show_official). The glyphs are
nodes on a small spring simulation; the second window uses degree-weighted
forces and double arrows. fontlabapp.components.graph.native reads the
component names and fontlabapp.components.graph.elastic.ui draws them.
Use: Open a font and run it. Drag nodes to feel the springs, click Shuffle or
Stop Motion, choose "Original Nine-node Graph" in the list to see the fixed
sample graph instead of your font, click Refresh after font changes and Close
each window when done. A large font may take a moment to read.
Safety: Read-only. The windows read the glyph names and component bases of the
current master once when they open and again on Refresh, and moving a node
changes only the window's own drawing. They write no font, master, selection,
history, preference, Output or clipboard. If one graph fails to open, the other
still does and a message lists what failed. With no font open nothing opens.
"""

TITLE = "Component Graph Demo"


def main() -> None:
    """Open each graph on its own, then list any that failed."""
    import fly
    from fly.ap.components.graph.model import show, show_official
    from fly.ap.core.scripting import current_package
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font first. The graphs read its components.", "Information", kind.Ok)
        return
    failures = []
    for label, opener in (("clipped-force graph", show), ("degree-weighted graph", show_official)):
        try:
            opener()
        except (ValueError, RuntimeError, TimeoutError) as error:
            failures.append(f"{label}: {error}")
    if failures:
        run_standard_message_box(qt, parent, TITLE, "Some graphs did not open:\n" + "\n".join(failures), "Warning", kind.Ok)


if __name__ == "__main__":
    main()
