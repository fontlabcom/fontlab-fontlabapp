# this_file: tests/test_fontui_source_comparison.py
"""Stored source comparison preserves borrowed data and owns its signals."""
from types import SimpleNamespace as NS

import _cov_qt as fq
import pytest
from fontlabapp.fontui import source_comparison as module


@pytest.fixture
def scene(monkeypatch):
    monkeypatch.setattr(fq, "RECORDED_METHODS", fq.RECORDED_METHODS | {"setWindowTitle"})
    fq.install(monkeypatch)
    from fontlab_fontport.memory import UFOBackend
    from ufoLib2 import Font
    data = Font()
    data.newGlyph('A').width = 0
    data.layers.newLayer('Bold').newGlyph('A').width = 700.5
    backend = UFOBackend(data)
    font = NS(_backend=backend, _check=backend.check_open)
    yield font, data
    for owner in tuple(module._HANDLES):
        owner.close()
    fq.release()


def test_summary_when_two_sources_then_fractional_widths_and_structure(scene):
    font, data = scene
    assert 'advance 0' in module.summary(font, 'public.default', 'Bold', 'A')
    assert '700.5' in module.summary(font, 'public.default', 'Bold', 'A')
    pen = data.layers['Bold']['A'].getPen()
    pen.moveTo((0, 0))
    pen.lineTo((10, 10))
    pen.closePath()
    assert 'not compatible' in module.summary(font, 'public.default', 'Bold', 'A')


@pytest.mark.parametrize('case', ['layer', 'missing', 'nan', 'closed'])
def test_summary_when_source_unavailable_then_refuses(scene, case):
    font, data = scene
    left = 'public.default'
    if case == 'layer':
        left = 'gone'
    elif case == 'missing':
        del data.layers['Bold']['A']
    elif case == 'nan':
        data.layers['Bold']['A'].width = float('nan')
    else:
        font._backend.close()
    with pytest.raises((ValueError, RuntimeError)):
        module.summary(font, left, 'Bold', 'A')


def test_show_when_controls_refresh_and_close_then_report_and_disconnect(scene):
    font, data = scene
    owner = module.show(font)
    assert '700.5' in owner.report.toPlainText()
    data.layers['Bold']['A'].width = 12
    owner.refresh_button.clicked.emit()
    assert 'advance 12' in owner.report.toPlainText()
    owner.right.setCurrentIndex(0)
    assert 'advance 12' not in owner.report.toPlainText()
    font._backend.close()
    owner.refresh()
    assert 'closed' in owner.report.toPlainText().lower()
    owner.close()
    owner.refresh()
    owner.close()
    assert owner._close_complete and owner not in module._HANDLES


def test_show_when_no_font_then_visible_error(scene):
    owner = module.show(None)
    assert owner.report.toPlainText()
    owner.close()


def test_show_when_widget_show_fails_then_owner_is_released(scene, monkeypatch):
    font, _ = scene
    def broken(self):
        raise RuntimeError('show failed')
    monkeypatch.setattr(fq.FakeWidget, 'show', broken)
    with pytest.raises(RuntimeError, match='show failed'):
        module.show(font)
    assert not module._HANDLES


def test_show_when_parent_destroyed_then_disconnects(scene):
    font, _ = scene
    parent = fq.FakeWidget()
    owner = module.show(font, parent)
    parent.destroyed.emit()
    assert owner._close_complete and not owner.connections
    assert owner not in module._HANDLES


def test_summary_when_matching_geometry_then_maps_points_and_named_items(scene):
    from ufoLib2.objects import Anchor, Component
    font, data = scene
    for layer in data.layers:
        glyph = layer['A']
        pen = glyph.getPointPen()
        pen.beginPath()
        pen.addPoint((0, 0), segmentType='line')
        pen.addPoint((10, 10))
        pen.addPoint((20, 10))
        pen.addPoint((30, 0), segmentType='curve')
        pen.endPath()
        glyph.anchors.append(Anchor(10, 10, name='top'))
        glyph.components.append(Component('base'))
    assert 'A is compatible' in module.summary(font, 'public.default', 'Bold', 'A')
    data.layers['Bold']['A'].anchors[0].name = 'bottom'
    assert 'anchors differ' in module.summary(font, 'public.default', 'Bold', 'A')


def test_show_when_constructor_fails_then_owned_widget_is_cleaned(scene, monkeypatch):
    font, _ = scene
    def broken(self, *args):
        raise RuntimeError('construct failed')
    monkeypatch.setattr(fq.FakeWidget, 'setReadOnly', broken)
    with pytest.raises(RuntimeError, match='construct failed'):
        module.show(font)
    assert not module._HANDLES


@pytest.mark.parametrize('tuple_result', [False, True])
def test_open_when_real_designspace_then_complete_distinct_report(scene, tmp_path, monkeypatch, tuple_result):
    from test_fontui_designspace_sources import fixture
    path = fixture(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    monkeypatch.setattr(fq.FakeFileDialog, 'path', (str(path), '*.designspace') if tuple_result else str(path))
    owner = module.show(scene[0])
    owner.open_button.clicked.emit()
    text = owner.report.toPlainText()
    assert text.startswith(f'External designspace: {path}')
    assert 'UPM' in text and '800' in text and '600.5' in text
    assert 'Missing: left; extra: right' in text
    assert 'compatible' in text and 'not comparable' in text
    assert before == {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    owner.refresh_button.clicked.emit()
    assert 'advance 700.5' in owner.report.toPlainText()
    assert 'External designspace:' not in owner.report.toPlainText()


@pytest.mark.parametrize('result', ['', ('', '*.designspace')])
def test_open_when_cancelled_then_report_unchanged(scene, monkeypatch, result):
    owner = module.show(scene[0])
    before = owner.report.toPlainText()
    monkeypatch.setattr(fq.FakeFileDialog, 'path', result)
    owner.open_button.clicked.emit()
    assert owner.report.toPlainText() == before


@pytest.mark.parametrize('problem', ['file', 'chooser', 'optional'])
def test_open_when_failure_then_preserves_report_and_shows_error(scene, monkeypatch, problem):
    owner = module.show(scene[0])
    before = owner.report.toPlainText()
    monkeypatch.setattr(fq.FakeFileDialog, 'path', '/missing.designspace')
    if problem == 'chooser':
        def fail(*args):
            raise RuntimeError('chooser unavailable')
        monkeypatch.setattr(fq.FakeFileDialog, 'getOpenFileName', fail)
    elif problem == 'optional':
        import builtins
        original = builtins.__import__
        def missing(name, *args, **kwargs):
            if name == 'fontlab_fontport.designspace':
                raise ModuleNotFoundError('optional Fontport missing')
            return original(name, *args, **kwargs)
        monkeypatch.setattr(builtins, '__import__', missing)
    owner.open_button.clicked.emit()
    assert owner.report.toPlainText() == before
    assert 'Open designspace failed:' in owner.status.text


def test_open_when_closed_during_chooser_then_ignores_result(scene, monkeypatch):
    owner = module.show(scene[0])
    before = owner.report.toPlainText()
    def choose(*args):
        owner.close()
        return '/late.designspace'
    monkeypatch.setattr(fq.FakeFileDialog, 'getOpenFileName', choose)
    owner.open_designspace()
    assert owner.report.toPlainText() == before
    assert owner._close_complete and owner not in module._HANDLES
    assert scene[0]._backend.layer_names()


def test_open_when_read_overruns_then_preserves_report(scene, tmp_path, monkeypatch):
    from test_fontui_designspace_sources import fixture
    path = fixture(tmp_path)
    owner = module.show(scene[0])
    before = owner.report.toPlainText()
    monkeypatch.setattr(fq.FakeFileDialog, 'path', str(path))
    times = iter([0.0, 4.0])
    monkeypatch.setattr(module, 'monotonic', lambda: next(times))
    owner.open_designspace()
    assert owner.report.toPlainText() == before
    assert 'deadline' in owner.status.text


def test_open_when_real_qt_then_button_report_and_cleanup(monkeypatch, tmp_path):
    import sys
    from _feature_source_qt import owned_application, qt_namespace
    from PySide6 import QtWidgets
    from test_fontui_designspace_sources import fixture
    from fontlab_fontport.memory import UFOBackend
    from ufoLib2 import Font

    qt = qt_namespace()
    class Combo(QtWidgets.QComboBox):
        currentText = property(QtWidgets.QComboBox.currentText)
    qt.QtGui.QComboBox = Combo
    monkeypatch.setitem(sys.modules, 'PythonQt', qt)
    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.lifecycle', raising=False)
    path = fixture(tmp_path)
    monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', lambda *args: (str(path), '*.designspace'))
    data = Font()
    data.newGlyph('A').width = 500
    backend = UFOBackend(data)
    with owned_application() as app:
        owner = module.show(NS(_backend=backend, _check=backend.check_open))
        try:
            owner.open_button.click()
            assert 'External designspace:' in owner.report.toPlainText()
            assert '600.5' in owner.report.toPlainText()
            assert owner.status.text.startswith('External designspace:')
            owner.refresh_button.click()
            assert 'advance 500' in owner.report.toPlainText()
        finally:
            owner.close()
            app.processEvents()
        assert owner._close_complete and not owner.connections


def test_show_when_optional_reader_missing_then_current_font_still_works(scene, monkeypatch):
    import builtins
    original = builtins.__import__
    def missing(name, *args, **kwargs):
        if name in ('fontlabapp.fontui.designspace_sources', 'fontlab_fontport.designspace'):
            raise ModuleNotFoundError('optional reader missing')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', missing)
    owner = module.show(scene[0])
    owner.refresh_button.clicked.emit()
    assert 'advance 700.5' in owner.report.toPlainText()


def test_open_when_closed_during_read_then_no_publish_and_font_stays_open(scene, monkeypatch):
    from fontlabapp.fontui import designspace_sources
    owner = module.show(scene[0])
    before = owner.report.toPlainText()
    monkeypatch.setattr(fq.FakeFileDialog, 'path', '/selected.designspace')
    def read(path, publish, *, check):
        owner.close()
        check()
        publish('late report')
    monkeypatch.setattr(designspace_sources, 'refresh', read)
    owner.open_designspace()
    assert owner.report.toPlainText() == before
    assert owner._close_complete and scene[0]._backend.layer_names()
