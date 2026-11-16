# this_file: tests/test_character_map_contrast.py
"""Literal glyph/coverage paint remains readable under inherited dark/light palettes."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from fontlabapp.glyphs.character_map.model import Glyph, Snapshot
from fontlabapp.glyphs.character_map.ui import panel_type
from test_spacing_worksheet import APP, GUI, QtCore, drain, valid


def luminance(color):
    values = [color.redF(), color.greenF(), color.blueF()]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
    return sum(w * v for w, v in zip((.2126, .7152, .0722), linear))


def contrast(a, b):
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + .05) / (dark + .05)


@pytest.mark.parametrize('part', [2, 3])
@pytest.mark.parametrize('background', ['#242529', '#ffffff'])
def test_original_glyphs_and_coverage_readable_on_owned_palette(part, background):
    before = GUI.QPalette(APP.palette())
    parent = GUI.QWidget()
    palette = GUI.QPalette(parent.palette())
    palette.setColor(GUI.QPalette.Window, GUI.QColor(background))
    palette.setColor(GUI.QPalette.Base, GUI.QColor(background))
    parent.setPalette(palette)
    snapshot = Snapshot((7, 70, 'Regular'), (Glyph(1, 'A', (65,)),))
    panel = panel_type(QtCore, GUI, part)(parent, lambda: snapshot, NS(setText=Mock()))
    panel.grid.setPalette(palette)
    before_panel = GUI.QPalette(panel.palette())
    before_grid = GUI.QPalette(panel.grid.palette())
    try:
        panel.show()
        drain()
        cell = panel.grid.cell
        image = panel.grid.grab(QtCore.QRect(cell, 4 * cell, 2 * cell, cell)).toImage()
        ratio = image.devicePixelRatio()
        pixel = lambda x, y: image.pixelColor(round(x * ratio), round(y * ratio))
        ground = pixel(2, 2)
        assert ground.name() == '#ffffff', 'Hardcoded original dark glyph/marker colors need their own light canvas'
        glyph = GUI.QColor('#253746' if part == 2 else '#000000')
        assert sum(image.pixelColor(x, y) == glyph for x in range(round(cell * ratio)) for y in range(round(cell * ratio))) >= 3
        assert contrast(glyph, ground) >= 4.5
        assigned = pixel(cell - 4, cell - 4)
        missing = pixel(2 * cell - 5, cell - 5)
        assert assigned.name() == '#146caa' and missing.name() == '#6b6b6b'
        assert contrast(assigned, ground) >= 3 and contrast(missing, ground) >= 3
        assert panel.palette() == before_panel and panel.grid.palette() == before_grid and APP.palette() == before
        if part == 3:
            panel.grid.last_key = 65
            selected = panel.grid.grab(QtCore.QRect(cell, 4 * cell, cell, cell)).toImage()
            assert selected.pixelColor(round(2 * ratio), round(2 * ratio)).name() == '#ff0000'
        panel.text.setText('A😀B')
        assert panel.text.text() == 'A😀B' and panel.assignments == {65: ('A',)}
    finally:
        if valid(panel):
            panel.close()
        parent.deleteLater()
        drain()
    assert APP.palette() == before


def test_basic_background_fill_failure_is_contained_and_painter_always_ends(monkeypatch):
    import fontlabapp.glyphs.character_map.paint as paint
    error = RuntimeError('owned background fill failure')
    painter = NS(setFont=Mock(), fillRect=Mock(side_effect=error), isActive=lambda: True, end=Mock())
    failure = Mock()
    grid = NS(display_font=object(), cell=36, owner=NS(part=2, failure=failure))
    gui = NS(QPainter=lambda owner: painter)
    paint.draw(grid, NS(rect=QtCore.QRect(0, 0, 20, 20)), QtCore, gui)
    failure.assert_called_once_with(error)
    painter.end.assert_called_once_with()


@pytest.mark.parametrize('part', [2, 3])
def test_explicit_canvas_respects_the_native_damage_clip(part):
    import fontlabapp.glyphs.character_map.paint as paint
    cell = 36
    image = GUI.QImage(16 * cell, 6 * cell, GUI.QImage.Format_ARGB32)
    image.fill(GUI.QColor('#ff00ff'))
    damage = QtCore.QRect(cell, 4 * cell, 2 * cell, cell)
    painter = GUI.QPainter(image)
    painter.setClipRect(damage)
    errors = []
    owner = NS(part=part, facts=object(), assignments={65: ('A',)}, failure=errors.append)
    grid = NS(owner=owner, cell=cell, display_font=GUI.QFont('Helvetica', 14), last_key=-1)
    gui = NS(**vars(GUI))
    gui.QPainter = lambda target: painter
    paint.draw(grid, NS(rect=damage), QtCore, gui)
    assert not painter.isActive() and not errors
    assert image.pixelColor(0, 0).name() == '#ff00ff'
    assert image.pixelColor(2 * cell + 2, 4 * cell + 2).name() == '#ffffff'
    assert image.pixelColor(2 * cell - 4, 5 * cell - 4).name() == '#146caa'
    assert image.pixelColor(3 * cell - 5, 5 * cell - 5).name() == '#6b6b6b'
