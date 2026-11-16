# this_file: tests/test_character_map_layout.py
"""The coverage adaptation must leave useful initial BMP rows in the viewport."""

from types import SimpleNamespace

import pytest
from fontlabapp.glyphs.character_map.model import Glyph, Snapshot
from fontlabapp.glyphs.character_map.ui import panel_type
from test_spacing_worksheet import GUI, QtCore, drain, valid


@pytest.fixture
def panel():
    facts = Snapshot((1, 2, "Regular"), (Glyph(1, "A", (65,)),))
    widget = panel_type(QtCore, GUI, 2)(
        None, lambda: facts, SimpleNamespace(setText=lambda *args: None)
    )
    widget.show()
    drain()
    yield widget
    if valid(widget):
        widget.close()
    drain()


def test_default_view_exposes_printable_latin_without_scroll(panel):
    viewport = panel.scroll_area.viewport()
    assert viewport.height() >= 6 * panel.grid.cell, (
        "Coverage UI must leave six full BMP rows at the default size"
    )
    assert panel.scroll_area.verticalScrollBar().value() == 0
    assert viewport.rect().contains(
        panel.grid.mapTo(
            viewport, QtCore.QPoint(2 * panel.grid.cell, 5 * panel.grid.cell - 1)
        )
    )
    assert panel.height() == 700


def test_original_controls_and_complete_coverage_remain_visible(panel):
    controls = (
        panel.family,
        panel.style_control,
        panel.size_control,
        panel.merging,
        panel.text,
        panel.scroll_area,
        panel.copy_button,
        panel.status,
        panel.output,
        panel.refresh_button,
        panel.close_button,
    )
    for widget in controls:
        assert widget.isVisible() and panel.rect().contains(widget.geometry()), type(
            widget
        ).__name__
    assert panel.output.isReadOnly() and "1 glyphs" in panel.output.toPlainText()
    assert panel.text.maxLength() == 32767
    assert (
        panel.size_control.minimum(),
        panel.size_control.maximum(),
        panel.size_control.value(),
    ) == (6, 72, 14)


def test_user_resize_keeps_original_scroll_and_grid_extent(panel):
    original = panel.grid.size()
    panel.resize(panel.width(), 560)
    drain()
    assert panel.height() == 560, (
        "Initial height must not become a fixed/minimum window constraint"
    )
    assert panel.grid.size() == original
    scrollbar = panel.scroll_area.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())
    drain()
    assert panel.grid.height() == 4096 * panel.grid.cell
    assert (
        panel.scroll_area.viewport().height() + scrollbar.value() == panel.grid.height()
    )


def test_typography_keeps_original_geometry_and_does_not_resize_window(panel):
    height = panel.height()
    for size in (6, 72, 14):
        panel.size_control.setValue(size)
        drain()
        assert panel.grid.cell == max(20, size * 2 + 8)
        assert panel.grid.size() == QtCore.QSize(
            16 * panel.grid.cell, 4096 * panel.grid.cell
        )
        assert panel.height() == height
