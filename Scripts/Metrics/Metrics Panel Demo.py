# this_file: Scripts/Metrics/Metrics Panel Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Preview rounding the selected glyphs' advances in App's Metrics panel.

What: Opens a nonmodal panel built on the shared Metrics panel base
(fontlabapp.metrics.panel.model.panel_type) that every App metrics script
uses. This subclass plans "round each advance to the nearest 10 units" and
shows the old and new advance of each selected layer in the preview table,
for the current master or all masters.
Use: Open a font, select glyphs in a Font window and run it. Switch between
Current master and All masters, click Use selection after changing the
selection and Close when done.
Safety: Preview only. The panel normally has an Apply button that writes the
font as one Undo step; this demo replaces Apply, so clicking it only says that
nothing was written, and the writer (metrics.panel.model.commit) is never
called. The panel reads the selected glyphs, their layers and the font's
component facts; it writes no font, master, selection, history, preference,
Output or clipboard. With no font open nothing opens.
"""

TITLE = "Metrics Panel Demo"
STEP = 10


def rounded(width: float) -> int:
    """The advance rounded half up to a multiple of STEP."""
    from fly.ap.metrics.panel.model import unit

    return unit(width / STEP) * STEP


def panel_class() -> type:
    """Build the preview-only panel class on the shared Metrics panel base."""
    from fly.ap.metrics.panel.model import make_plan, panel_type

    class RoundPreviewPanel(panel_type()):
        """Round advances to the nearest 10 units, preview only."""

        TITLE = "Round Advances (preview only)"
        KEY = "metrics_panel_demo"
        HEADERS = ("Advance", "Rounded")
        ACCENT = (2,)

        def build(self) -> None:
            """No extra controls; relabel Apply so it is clear it writes nothing."""
            self.apply_button.setText("Apply (demo: no write)")

        def subtitle_hint(self) -> str:
            """Say what the preview computes."""
            return f"Rounds each advance to the nearest {STEP} units. This demo never writes."

        def planner(self, package, glyphs):
            """Plan the rounded advance of one layer; the outline never moves."""

            def plan(layer, master):
                width = layer.advanceWidth
                return make_plan(layer, 0, rounded(width), (f"{width:g}", f"{rounded(width)}"))

            return plan

        def apply(self) -> None:
            """Replace the writing Apply: state that nothing was written."""
            self.status.setText("Demo only: nothing was written. Close the panel.")

    return RoundPreviewPanel


def main() -> None:
    """Open the preview panel on the current font, or say that a font is needed."""
    import fly
    from fly.ap.core.scripting import current_package, show_script_dialog
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font and select glyphs first. The panel previews their advances.", "Information", kind.Ok)
        return
    try:
        panel = panel_class()
        show_script_dialog(panel, panel.KEY)
    except (ValueError, RuntimeError, TimeoutError) as error:
        run_standard_message_box(qt, parent, TITLE, f"The panel did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
