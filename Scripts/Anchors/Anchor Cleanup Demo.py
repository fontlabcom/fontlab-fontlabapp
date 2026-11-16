# this_file: Scripts/Anchors/Anchor Cleanup Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Explain the duplicate-anchor finder and the cross-font anchor copy with samples.

What: Shows, in one message box, what App's duplicate-anchor finder
(fontlabapp.anchors.duplicates.model.findings) reports for a made-up layer
and what the cross-font anchor copy (fontlabapp.anchors.crossfont.model)
would do for two made-up fonts: which layers pair up and which anchors it
adds, renames or removes.
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is removed, copied or opened. The sample anchors are plain
values; the real windows (fontlabapp.anchors.duplicates.ui and
fontlabapp.anchors.crossfont.ui) are not opened, and no font, master,
selection, history, preference, Output or clipboard is touched.
"""

TITLE = "Anchor Cleanup Demo"
WINDOWS = ("fontlabapp.anchors.duplicates.ui", "fontlabapp.anchors.crossfont.ui")


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def explanation_lines() -> list[str]:
    """Findings and a copy simulation computed by the real App models."""
    from fly.ap.anchors.crossfont import model as crossfont
    from fly.ap.anchors.duplicates import model as duplicates

    layer = (
        duplicates.Pin(1, "top", 100, 700),
        duplicates.Pin(2, "top.1", 100, 700),
        duplicates.Pin(3, "bottom", 50, 0),
        duplicates.Pin(4, "ogonek", 50.2, 0.3),
    )
    lines = ["Sample layer: top (100, 700), top.1 (100, 700), bottom (50, 0), ogonek (50.2, 0.3).", "Duplicate finder (duplicates.model.findings); only the extras would be removed:"]
    lines += [f"  {found.kind}: {', '.join(found.names)} -> remove anchor ids {list(found.extras)}" for found in duplicates.findings(layer)]
    pairs = crossfont.layer_pairs(("Regular", "Bold"), ("Regular", "Black"), crossfont.ALL_MASTERS, crossfont.ALL_MASTERS)
    lines += ["", f"Cross-font layer pairs, All masters to All masters: {list(pairs)}"]
    source = (crossfont.Pin(10, "top", 200, 700, ()), crossfont.Pin(11, "bottom", 250, 0, ()))
    destination = (crossfont.Pin(20, "top", 10, 10, ()),)
    result = crossfont.copy_layer(source, destination, 500, 600, crossfont.Options(relative=True))
    lines.append(f"Copy 500 wide Regular anchors to a 600 wide layer, relative to width (crossfont.model.copy_layer): {result.copied} copied")
    lines += [f"  {edit.action} {edit.pin.name} at x {edit.pin.x:g}" for edit in result.edits]
    return [*lines, "", "The real windows, not opened here: " + ", ".join(WINDOWS)]


def main() -> None:
    """Show the sample results; no font is needed and nothing is changed."""
    notify(TITLE, "Sample anchor cleanup and copy results. Nothing was changed.", "\n".join(explanation_lines()))


if __name__ == "__main__":
    main()
