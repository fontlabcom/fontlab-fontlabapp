# this_file: tests/_detached_transform_fixture.py
"""Actual product composition, owned Qt/models and complete preservation oracles."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from _feature_source_qt import font_fixture, freeze, owned_application, qt_namespace
from test_fontui_detached_transform import digest

ROOT = Path(__file__).resolve().parent
TARGET = 'Z.root'
LAYER = 'Display'


def cache_state(font):
    """Keep exact defcon serial data, including its str-derived Color values."""
    return {name: {'identity': id(layer), 'valid': layer._valid,
                   'bindings': {key: (id(binding), id(binding.glyph),
                                      binding.pending_geometry,
                                      deepcopy(binding.model.getDataForSerialization()),
                                      deepcopy(binding.accepted))
                                for key, binding in layer._bindings.items()}}
            for name, layer in font._layers.items()}


def rich_font(marker):
    from ufoLib2.objects import Component, Anchor, Guideline
    font = font_fixture('languagesystem DFLT dflt;\n', marker)
    layer = font.layers.newLayer(LAYER)
    base = layer.newGlyph('B.base')
    pen = base.getPen()
    pen.moveTo((0, 0)); pen.lineTo((10, 0)); pen.lineTo((10, 10)); pen.closePath()
    middle = layer.newGlyph('M.middle')
    pen = middle.getPen()
    pen.moveTo((0, 0)); pen.lineTo((20, 0)); pen.lineTo((20, 20)); pen.closePath()
    middle.components.append(Component('B.base', (2, 0, 0, 1, 5, 7), 'nested'))
    root = font['A'].copy(name=TARGET)
    root.components = [Component('M.middle', (1, .5, 0, 1, 20, 30), 'middle'),
                       Component('B.base', (1, 0, .25, 1, -5, 10), 'shared')]
    root.contours[0].identifier = 'root-contour'
    root.contours[0].points[0].identifier = 'root-point'
    root.anchors = [Anchor(10.5, 50.25, 'top', identifier='root-anchor')]
    root.guidelines = [Guideline(25, 0, 90, 'guide', identifier='root-guide')]
    root.image.color = '0.1,0.2,0.3,0.4'
    pen = root.getPen(); pen.moveTo((4, 5)); pen.lineTo((7, 9)); pen.endPath()
    layer.insertGlyph(root)
    other = font.layers.newLayer('Alternate')
    for glyph in layer:
        other.insertGlyph(deepcopy(glyph))
    other[TARGET].width = 777.75
    other[TARGET].contours[0].points[1].x = 150
    return font


@pytest.fixture
def scene(request, monkeypatch, tmp_path):
    from PySide6 import QtCore, QtWidgets
    import shiboken6
    from fontlab_fontport.live import RFont
    from fontlab_fontport.memory import UFOBackend

    qt = qt_namespace()
    class Combo(qt.QtGui.QComboBox):
        currentText = property(QtWidgets.QComboBox.currentText)
    class Slider(QtWidgets.QSlider):
        value = property(QtWidgets.QSlider.value)
    qt.QtGui.QComboBox, qt.QtGui.QSlider = Combo, Slider
    monkeypatch.setitem(sys.modules, 'PythonQt', qt)
    monkeypatch.setitem(sys.modules, 'fontlab', None)
    names = ['fontlabapp.fontui.' + name for name in
             ('transform', 'transform_view', 'lifecycle', 'sequence', 'sequence_canvas', 'detached_transform')]
    names.append('fly.ap.fontui.detached_transform')
    saved = {name: sys.modules.get(name) for name in names}
    for name in names:
        monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module('fontlabapp.fontui.detached_transform')
    assert Path(module.__file__).resolve() == ROOT.parent / 'src/fontlabapp/fontui/detached_transform.py'
    sources = [rich_font(marker) for marker in ('first', 'second')]
    fonts = [RFont(UFOBackend(source)) for source in sources]
    fixture_closers = [font._backend.close for font in fonts]
    expected_closed = [False, False]
    initial = deepcopy(sources)
    serialized = [json.dumps(freeze(source), sort_keys=True) for source in sources]
    warm = getattr(request, 'param', True)
    held = None
    if warm:
        held = fonts[0].getLayer(LAYER)[TARGET]
        held.naked().holdNotifications()
        held.width = 999
        held[0].points[0].x = 888
        assert sources[0].layers[LAYER][TARGET].width == 600.25
        assert sources[0].layers[LAYER][TARGET].contours[0].points[0].x == 0
    caches = [cache_state(font) for font in fonts]
    forbidden = []
    for font in fonts:
        for name in dir(font._backend):
            if name.startswith(('set_', 'write_', 'new_', 'remove_', 'rename_', 'edit_')) or name in ('save', 'save_options', 'close'):
                if not callable(getattr(font._backend, name)):
                    continue
                def refuse(*args, _name=name, **kwargs):
                    forbidden.append(_name)
                    raise AssertionError('Borrowed mutation: ' + _name)
                monkeypatch.setattr(font._backend, name, refuse)
        for name in ('refresh', 'save', 'close'):
            def refuse(*args, _name=name, **kwargs):
                forbidden.append('RFont.' + _name)
                raise AssertionError('Borrowed wrapper mutation: ' + _name)
            monkeypatch.setattr(font, name, refuse)
    before_models = []
    previous_profile = sys.getprofile()
    def profile(frame, event, value):
        if frame.f_code is module._snapshot.__code__ and event == 'return' and isinstance(value, tuple):
            before_models.append((value[0], digest(value[0])))
    sys.setprofile(profile)
    state = SimpleNamespace(module=module, fonts=fonts, sources=sources, initial=initial,
                            owners=[], parents=[], before_models=before_models, held=held,
                            expected_closed=expected_closed, fixture_closers=fixture_closers)
    def check():
        assert not forbidden
        assert [json.dumps(freeze(source), sort_keys=True) for source in sources] == serialized
        assert sources == initial
        assert [cache_state(font) for font in fonts] == caches
        assert [font._backend.closed for font in fonts] == expected_closed
        assert all(font._backend.saved_path is None for font in fonts)
        if held is not None:
            assert held.width == 999 and held[0].points[0].x == 888
        # M1: common final complete before-model oracle for EVERY composition case.
        assert all(digest(model) == expected for model, expected in before_models)
    state.check = check
    with owned_application() as app:
        state.app = app
        try:
            yield state
        finally:
            sys.setprofile(previous_profile)
            check()  # All temporary source/model faults must already be restored.
            peers, owned_fonts = [], []
            owners = list(dict.fromkeys([*state.owners, *module._HANDLES]))
            for owner in owners:
                for stage in ([owner.active] if owner.active is not None else []) + owner.retired:
                    peers.extend(stage.peers); owned_fonts.extend(stage.fonts)
                assert owner._release_now()
                assert owner._released
            assert all(peer._close_complete for peer in peers)
            assert all(font._backend.closed for font in owned_fonts)
            QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            assert all(not shiboken6.isValid(peer.widget) for peer in peers)
            for parent in state.parents:
                if shiboken6.isValid(parent):
                    parent.deleteLater()
            QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            assert all(not shiboken6.isValid(parent) for parent in state.parents)
            assert QtWidgets.QApplication.instance() is app
            check()
            receipt = {
                'common_final_before_model_digests': len(before_models),
                'both_sources_and_cache_pending_edits_exact': True,
                'all_owned_peers_ack_and_widgets_deleted': True,
                'all_owned_backends_closed_after_peers': True,
                'deliberate_fixture_source_closure': expected_closed,
                'borrowed_mutator_calls': forbidden, 'application_alive': True}
            (tmp_path / 'cleanup.json').write_text(json.dumps(receipt) + '\n')
            request.node.user_properties.append(('detached_cleanup', json.dumps(receipt)))
    if held is not None:
        held.width = 600.25
        held[0].points[0].x = 0
        held.naked().releaseHeldNotifications()
    for name in names:
        sys.modules.pop(name, None)
        if saved[name] is not None:
            sys.modules[name] = saved[name]


def window(scene, font_index=0, font='default'):
    from PySide6.QtWidgets import QWidget
    parent = QWidget(); scene.parents.append(parent)
    owner = scene.module.show(scene.fonts[font_index] if font == 'default' else font, parent)
    scene.owners.append(owner)
    return owner


def capture(scene, layer=LAYER, name=TARGET, font_index=0):
    owner = window(scene, font_index)
    owner.layer_control.setCurrentIndex(owner.layer_control.findText(layer))
    assert owner.glyph_control.currentIndex == -1
    owner.glyph_control.setCurrentIndex(owner.glyph_control.findText(name))
    assert owner.capture()
    assert owner.valid and owner.active is not None
    return owner


