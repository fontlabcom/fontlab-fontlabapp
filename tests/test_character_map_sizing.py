# this_file: tests/test_character_map_sizing.py
"""Explicit child geometry survives a binding without virtual sizeHint dispatch."""

from types import SimpleNamespace

import pytest
from fontlabapp.glyphs.character_map.model import Glyph, Snapshot
from fontlabapp.glyphs.character_map.fonts import change
from fontlabapp.glyphs.character_map.ui import panel_type
from test_character_map_refresh import PaintObserver
from test_spacing_worksheet import APP, GUI, QtCore, drain, valid


class NonDispatchWidget(GUI.QWidget):
    """Model native adjustSize observing QWidget's invalid default size hint."""

    def adjustSize(self):
        self.resize(0, 0)


class NonDispatchScrollArea(GUI.QScrollArea):
    """Model setWidget's implicit hint lookup when size was not explicitly set."""

    def setWidget(self, widget):
        explicitly_sized = widget.testAttribute(QtCore.Qt.WA_Resized)
        super().setWidget(widget)
        if not explicitly_sized:
            widget.resize(0, 0)


class NonDispatchGui:
    QWidget = NonDispatchWidget
    QScrollArea = NonDispatchScrollArea

    def __getattr__(self, name):
        return getattr(GUI, name)


@pytest.fixture
def panel():
    gui = NonDispatchGui()
    facts = Snapshot((1, 2, "Regular"), (Glyph(1, "A", (65,)),))

    def no_clipboard(*args):
        raise AssertionError("Sizing must not use a clipboard")

    widget = panel_type(QtCore, gui, 3)(
        None, lambda: facts, SimpleNamespace(setText=no_clipboard)
    )
    observer = PaintObserver(widget.grid)
    widget.grid.installEventFilter(observer)
    yield widget, gui, observer
    if valid(widget):
        widget.close()
    drain()


def assert_variable_geometry(panel):
    grid = panel.grid
    assert grid.size() == QtCore.QSize(16 * grid.cell, 4096 * grid.cell)
    assert grid.minimumSize() == QtCore.QSize(0, 0)
    assert grid.maximumWidth() > grid.width()
    assert grid.maximumHeight() > grid.height()
    assert not panel.scroll_area.widgetResizable()


def test_initial_styles_grid_has_original_extent_and_natural_paint(panel):
    widget, _gui, observer = panel
    assert widget.grid.cell == 24
    assert_variable_geometry(widget)
    widget.show()
    for _ in range(3):
        APP.processEvents()
    assert observer.count > 0, "An exposed nonempty grid must paint without grab/render"
    assert widget.scroll_area.verticalScrollBar().maximum() > 0
    original_size = widget.grid.size()
    widget.resize(widget.width() + 100, widget.height() + 100)
    APP.processEvents()
    assert widget.grid.size() == original_size


@pytest.mark.parametrize("kind", ["family", "size", "style", "merging"])
def test_every_original_styles_update_applies_hint_without_fixing_size(panel, kind):
    widget, gui, observer = panel
    # Isolate later updates from the independent initial-attachment regression.
    widget.grid.resize(widget.grid.sizeHint())
    widget.show()
    APP.processEvents()
    cell = widget.grid.cell
    arguments = {
        "family": widget.family.currentText(),
        "size": "36",
        "style": widget.style_control.currentText(),
        "merging": False,
    }
    observer.count = 0
    change(widget, gui, kind, arguments[kind])
    assert_variable_geometry(widget)
    if kind == "merging":
        assert widget.grid.cell == cell
    else:
        assert widget.grid.cell == max(
            24, int(gui.QFontMetrics(widget.grid.display_font).xHeight()) * 3
        )
    for _ in range(3):
        APP.processEvents()
    assert observer.count > 0


def test_styles_can_grow_then_shrink_without_fixed_geometry(panel):
    widget, gui, _observer = panel
    sizes = []
    for size in (72, 6, 36):
        change(widget, gui, "size", str(size))
        assert_variable_geometry(widget)
        sizes.append(widget.grid.size())
    assert sizes[0].height() > sizes[1].height()
    assert sizes[2].height() > sizes[1].height()
