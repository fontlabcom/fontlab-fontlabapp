# this_file: tests/test_character_map_refresh.py
"""Coverage refresh schedules actual visible paints without forced rendering."""

from types import SimpleNamespace

import pytest
from fontlabapp.glyphs.character_map.model import Glyph, Snapshot
from fontlabapp.glyphs.character_map.ui import panel_type
from test_spacing_worksheet import APP, GUI, QtCore, drain, valid


class PaintObserver(QtCore.QObject):
    def __init__(self, grid):
        super().__init__(grid)
        self.count = 0

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.Paint:
            self.count += 1
        return False


@pytest.mark.parametrize("part", (2, 3))
@pytest.mark.parametrize("failed", (False, True), ids=("success", "failure"))
def test_refresh_repaints_visible_coverage_without_geometry_change(part, failed):
    state = {"code": 65, "fail": False}

    def capture():
        if state["fail"]:
            raise ValueError("Coverage unavailable")
        return Snapshot((1, 2, "Regular"), (Glyph(1, "A", (state["code"],)),))

    def forbid_copy(*args):
        raise AssertionError("Refresh must not access the clipboard")

    panel = panel_type(QtCore, GUI, part)(
        None, capture, SimpleNamespace(setText=forbid_copy)
    )
    observer = PaintObserver(panel.grid)
    panel.grid.installEventFilter(observer)
    try:
        panel.show()
        panel.scroll_area.ensureVisible(panel.grid.cell + 2, 4 * panel.grid.cell + 2)
        panel.text.setText("AB")
        if failed:
            # Pre-set error labels so relayout cannot accidentally repaint the grid.
            panel.status.setText("Coverage unavailable")
            panel.output.setPlainText(
                "FontLab coverage unavailable. Reference-font selection remains available."
            )
        for _ in range(3):
            APP.processEvents()
        assert panel.isVisible() and observer.count > 0
        geometry, reference_font = panel.grid.geometry(), GUI.QFont(panel.grid.display_font)
        observer.count = 0
        state.update(code=66, fail=failed)
        panel.refresh_button.click()
        for _ in range(3):
            APP.processEvents()
        assert panel.assignments == ({} if failed else {66: ("A",)})
        assert (panel.facts is None) == failed
        assert panel.grid.geometry() == geometry
        assert panel.text.text() == "AB" and panel.grid.display_font == reference_font
        assert observer.count > 0, "Changed coverage must schedule an actual grid paint"
    finally:
        if valid(panel):
            panel.close()
        drain()
