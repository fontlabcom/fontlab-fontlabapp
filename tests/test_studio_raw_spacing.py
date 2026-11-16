# this_file: tests/test_studio_raw_spacing.py
# SPDX-License-Identifier: Apache-2.0
"""The embedded raw-spacing inspector on real Qt controls and captured font data."""

import importlib
import sys
from types import SimpleNamespace as NS

import pytest
from issue205_panels import Combo, Edit, panels as panels, legacy_qt as legacy_qt, owned as owned  # noqa: F401
from issue205_painting import QtGui, render


@pytest.fixture
def raw(panels, monkeypatch):  # noqa: F811 - imported fixture
    panels.qt.gui.QLineEdit = Edit
    panels.qt.gui.QComboBox = Combo
    for name in ('fontlabapp.proof.inspectors.views', 'fontlabapp.studios.spacing_studio.raw'):
        monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module('fontlabapp.studios.spacing_studio.raw')
    path = QtGui.QPainterPath()
    path.addRect(10, 20, 200, 400)
    for glyph in (panels.glyph, panels.mark):
        for layer in glyph.layers:
            contour = NS(closed=True, nodes=lambda: [NS(x=10, y=20, isOn=lambda: True)])
            layer.shapes = [NS(isComponent=False, shapeData=None, contours=[contour],
                               closedPath=path, openedPath=QtGui.QPainterPath(), transform=QtGui.QTransform())]
    def create():
        return panels.own(module.SpacingPreview(None))
    return NS(module=module, host=panels, create=create)


def test_raw_spacing_captures_real_paths_master_advances_and_optional_labels(raw):
    panel = raw.create()
    panel.text.setText('/A /acute /A')
    assert panel._snapshot_valid, panel.last_error
    assert [row[:3] for row in panel.rows] == [('A', 0, 600), ('acute', 600, 600), ('A', 1200, 600)]
    assert panel.show_boxes.isChecked() and panel.show_numbers.isChecked()
    result = render(panel.canvas)
    assert len(result.paths) == 3 and len(result.labels) == 6
    assert not result.paths[0].isEmpty()
    panel.show_numbers.setChecked(False)
    panel.show_boxes.setChecked(False)
    assert render(panel.canvas).labels == []
    panel.master.setCurrentIndex(1)
    assert panel.chosen_master() == 'Bold' and raw.host.package.master == 'Regular'
    assert 'no kerning' in panel.subtitle.text()
    assert panel.path('A') is panel.paths[('A', 'Bold')]
    panel.close()
    assert not panel._connections


def test_raw_spacing_empty_and_no_font_show_distinct_clean_canvas_messages(raw):
    panel = raw.create()
    panel.text.setText('')
    assert panel.rows == [] and panel._snapshot_valid
    assert render(panel.canvas).labels == ['Type characters or /glyphname tokens above.']
    panel.close()
    raw.host.state.package = None
    empty = raw.create()
    assert not empty._snapshot_valid and empty.package is None
    assert empty.chosen_master() == ''
    assert render(empty.canvas).labels == ['Open a font first.']


@pytest.mark.parametrize('fault', ['switched', 'closed', 'create', 'draw', 'end', 'inactive', 'hook'])
def test_raw_spacing_paint_failure_invalidates_without_repaint_loop_and_recovers(raw, monkeypatch, fault):
    from issue205_painting import Painter

    panel = raw.create()
    panel.text.setText('/A')
    pending, painters = [True], []
    monkeypatch.setattr(panel.canvas, 'update', lambda: pending.append(True))
    original = raw.host.package
    image = QtGui.QImage(800, 600, QtGui.QImage.Format_ARGB32)
    class ObservedPainter(Painter):
        def __init__(self):
            super().__init__(image)
            self.ends = 0
        def isActive(self):
            return False if fault == 'inactive' else super().isActive()
        def end(self):
            self.ends += 1
            result = super().end()
            return False if fault == 'end' else result
    def painter(widget):
        if fault == 'create':
            raise RuntimeError('persistent create')
        result = ObservedPainter()
        painters.append(result)
        return result
    painter.Antialiasing = QtGui.QPainter.Antialiasing
    with monkeypatch.context() as broken:
        broken.setattr(raw.host.qt.gui, 'QPainter', painter)
        if fault in ('switched', 'closed'):
            raw.host.state.package = None if fault == 'closed' else NS(id=999, isNull=False)
        if fault in ('draw', 'hook'):
            broken.setattr(panel.canvas, 'draw', lambda p: (_ for _ in ()).throw(ValueError('persistent draw')))
        if fault == 'hook':
            broken.setattr(panel.canvas, 'on_error', lambda text: (_ for _ in ()).throw(RuntimeError('hook failed')))
        frames = 0
        while pending and frames < 7:
            pending.pop()
            panel.canvas.paintEvent(None)
            frames += 1
        assert frames < 7 and not pending, 'Failed paint must not schedule itself forever'
        assert panel.canvas.paint_error and not panel._snapshot_valid
        assert panel.rows == [] and panel.paths == {} and panel.package is None
        assert all(p.ends == 1 for p in painters)
    raw.host.state.package = original
    panel.refresh()
    assert panel._snapshot_valid and not panel.last_error
    assert len(render(panel.canvas).paths) == 1
    panel.close()
    assert not panel._connections


@pytest.mark.parametrize('drift', ['advance', 'closure', 'masters'])
def test_raw_spacing_rejects_changed_captured_sources_before_drawing(raw, drift):
    panel = raw.create()
    panel.text.setText('/A')
    if drift == 'advance':
        raw.host.layer.advanceWidth += 0.1
    elif drift == 'closure':
        raw.host.layer.shapes[0].contours[0].closed = False
    else:
        raw.host.package.masters.reverse()
    with pytest.raises(ValueError, match='changed'):
        panel.ensure_snapshot()
    assert not panel._snapshot_valid and panel.paths == {} and panel.package is None
