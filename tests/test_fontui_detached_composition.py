# this_file: tests/test_fontui_detached_composition.py
"""Actual detached composition with complete source and owned-model preservation."""
from copy import deepcopy
import inspect
import sys

import pytest
from _detached_transform_fixture import (
    scene as _scene_fixture, capture, window, digest, LAYER, TARGET,
)

scene = _scene_fixture


@pytest.mark.parametrize('scene', [False], indirect=True)
def test_window_when_compact_then_host_margin_is_six_and_embedded_previews_are_zero(scene):
    owner = capture(scene)
    stage = owner.active
    margins = owner.layout.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (6, 6, 6, 6), (
        'the previews sit 6 px from the window edge, never against it')
    for peer in (stage.before, stage.after):
        inner = peer.widget.layout().contentsMargins()
        assert inner.left() == 0, 'an embedded preview adds no second margin'
    scene.check()


@pytest.mark.parametrize('scene', [False, True], indirect=True)
def test_capture_when_explicit_then_stored_closure_and_no_borrowed_binding_mutation(scene):
    owner = capture(scene)
    stage = owner.active
    assert list(stage.models[0].keys()) == ['B.base', 'M.middle', TARGET]
    assert len(stage.peers) == 3 and len(stage.fonts) == 2
    assert stage.models[0][TARGET].width == 600.25
    assert stage.models[0][TARGET].contours[0].points[0].x == 0
    assert stage.before.outlines[TARGET].bounds == (-5, 0, 100, 100)
    assert stage.before.run.glyphs[0].advance == 600.25
    assert stage.editor.glyph_control.currentText == TARGET
    assert not stage.editor.glyph_control.isEnabled()
    assert stage.before.text_control.isReadOnly() and stage.after.text_control.isReadOnly()
    assert owner.published_generation == owner.generation
    scene.check()


def test_show_when_none_empty_unselected_then_no_implicit_target(scene):
    from ufoLib2 import Font
    from fontlab_fontport.live import RFont
    from fontlab_fontport.memory import UFOBackend
    none = window(scene, font=None)
    assert 'No font' in none.target.text and not none.capture()
    empty = RFont(UFOBackend(Font()))
    try:
        owner = window(scene, font=empty)
        assert owner.font is empty and owner.layer_control.currentIndex == -1
        assert owner.glyph_control.currentIndex == -1 and owner.active is None
        assert not owner.capture() and 'No font' not in owner.target.text
        assert owner._release_now()
    finally:
        empty.close()
    normal = window(scene)
    assert normal.active is None and normal.layer_control.currentIndex == -1
    assert normal.glyph_control.currentIndex == -1 and not normal.capture()


def test_capture_when_other_layer_same_label_then_exact_identity_and_metadata(scene):
    owner = capture(scene, layer='Alternate', font_index=1)
    stage = owner.active
    assert owner.font is scene.fonts[1]
    assert stage.models[0][TARGET].width == 777.75
    assert stage.before.outlines[TARGET].bounds == (-5, 0, 150, 100)
    for model in stage.models:
        assert model[TARGET] == scene.sources[1].layers['Alternate'][TARGET]
        assert model.images['owned.png'] == scene.sources[1].images['owned.png']
        assert model.info.unitsPerEm == 1000
    assert stage.models[0][TARGET] is not stage.models[1][TARGET]
    assert stage.models[0]['B.base'] is not stage.models[1]['B.base']
    stage.models[1][TARGET].lib['owned'].append('owned-result-edit')
    stage.models[1]['B.base'].contours[0].points[0].x = -999
    scene.check()


# Literal decomposed points, derived from the fixture matrices independently.
POINTS = ((0, 0), (100, 0), (100, 100), (4, 5), (7, 9),
          (20, 30), (40, 40), (40, 60),
          (25, 39.5), (45, 49.5), (45, 59.5), (-5, 10), (5, 10), (7.5, 20))


@pytest.mark.parametrize('matrix,intensity', [((2, .25, .5, 3, 10, -5), 100),
                                           ((-1, 0, 0, 1, 0, 0), 100),
                                           ((1, 0, .5, 1, 0, 0), 25),
                                           ((1, 0, 0, 1, 25, 30), 100)])
def test_transform_when_affine_then_literal_geometry_spacing_and_no_accumulation(scene, matrix, intensity):
    owner = capture(scene); stage = owner.active
    for key, value in zip(stage.editor.matrix, matrix):
        stage.editor.matrix[key].setText(str(value))
    stage.editor.intensity_field.setText(str(intensity))
    f = intensity / 100
    a, b, c, d, x, y = ((1 + (matrix[0] - 1) * f), matrix[1] * f, matrix[2] * f,
                        (1 + (matrix[3] - 1) * f), matrix[4] * f, matrix[5] * f)
    expected = tuple((a * px + c * py + x, b * px + d * py + y) for px, py in POINTS)
    actual = tuple(point for operation, points in stage.after.outlines[TARGET].recording for point in points)
    assert actual == expected
    assert stage.after.run.glyphs[0].advance == a * 600.25
    assert stage.models[1][TARGET].height == d * 900.5
    before = digest(stage.models[1])
    assert stage.editor.update() and owner.valid
    assert digest(stage.models[1]) == before
    assert stage.before.outlines[TARGET].bounds == (-5, 0, 100, 100)


@pytest.mark.parametrize('route', ['disabled', 'zero', 'reset'])
def test_identity_when_requested_then_actual_after_is_before(scene, route):
    owner = capture(scene); stage = owner.active
    stage.editor.matrix['xx'].setText('2')
    if route == 'disabled':
        stage.editor.enabled_control.setChecked(False)
    elif route == 'zero':
        stage.editor.intensity_slider.setValue(0)
    else:
        stage.editor.buttons['reset'].click()
    assert owner.valid
    assert stage.after.outlines[TARGET].recording == stage.before.outlines[TARGET].recording
    assert stage.after.run.glyphs[0].advance == 600.25


@pytest.mark.parametrize('fault', ['missing_base', 'cycle', 'image', 'reader', 'target', 'layer', 'whitespace'])
def test_capture_when_incomplete_then_old_proof_clears_and_no_partial_stage(scene, monkeypatch, fault):
    from ufoLib2.objects import Component
    owner = capture(scene); old = owner.active
    source = scene.sources[0]
    backup = deepcopy(source.layers[LAYER])
    image = source.images['owned.png']
    try:
        with monkeypatch.context() as patch:
            if fault == 'missing_base':
                del source.layers[LAYER]['B.base']
            elif fault == 'cycle':
                source.layers[LAYER]['B.base'].components.append(Component(TARGET))
            elif fault == 'image':
                del source.images['owned.png']
            elif fault == 'reader':
                patch.setattr(scene.fonts[0]._backend, 'read_image', None)
            elif fault == 'target':
                del source.layers[LAYER][TARGET]
            elif fault == 'layer':
                del source.layers[LAYER]
            else:
                bad = source.layers[LAYER][TARGET].copy(name='bad name')
                source.layers[LAYER].insertGlyph(bad)
                owner.glyph_control.addItem('bad name')
                owner.glyph_control.setCurrentIndex(owner.glyph_control.findText('bad name'))
            assert not owner.capture()
            assert not owner.valid and owner.published_generation is None
            assert owner.active is None and old.after.run is None and old.before.run is None
            assert all(peer._close_complete for peer in old.peers)
            assert all(font._backend.closed for font in old.fonts)
            assert owner.status.text
    finally:
        if LAYER in source.layers:
            del source.layers[LAYER]
        restored = source.layers.newLayer(LAYER)
        for glyph in backup:
            restored.insertGlyph(deepcopy(glyph))
        # Preserve the original layer order and all attributes, not just glyph data.
        source.layers.layerOrder = scene.initial[0].layers.layerOrder
        source.images['owned.png'] = image


def test_refresh_when_source_changes_then_new_snapshot_not_other_same_label_font(scene):
    owner = capture(scene); old = owner.active
    source = scene.sources[0].layers[LAYER][TARGET]
    try:
        source.width = 701.5
        owner.refresh_button.click()
        assert owner.valid and owner.font is scene.fonts[0]
        assert owner.active.models[0][TARGET].width == 701.5
        assert owner.active.generation > old.generation
        assert all(peer._close_complete for peer in old.peers)
        assert all(font._backend.closed for font in old.fonts)
        assert old.models[0][TARGET].width == 600.25
    finally:
        source.width = 600.25


@pytest.mark.parametrize('route', ['matrix', 'singular', 'nonfinite', 'intensity', 'out_of_range', 'glyph'])
def test_update_when_invalid_then_temporal_and_final_proof_unavailable(scene, route):
    owner = capture(scene); stage = owner.active
    stage.editor.matrix['xx'].setText('2')
    lines, start = inspect.getsourcelines(type(stage.editor).update)
    boundary = next(start + index for index, text in enumerate(lines) if 'name = self.glyph_control.currentText' in text)
    events = []
    previous = sys.gettrace()
    def trace(frame, event, arg):
        if frame.f_code is type(stage.editor).update.__code__:
            if event == 'line' and frame.f_lineno == boundary:
                events.append((owner.valid, owner.published_generation, stage.editor.result,
                               stage.after.run, dict(stage.after.outlines)))
            return trace
        return None
    try:
        sys.settrace(trace)
        if route in ('matrix', 'singular', 'nonfinite'):
            stage.editor.matrix['xx'].setText({'matrix': 'bad', 'singular': '0', 'nonfinite': 'inf'}[route])
        elif route in ('intensity', 'out_of_range'):
            stage.editor.intensity_field.setText('bad' if route == 'intensity' else '1000')
        else:
            stage.editor.glyph_control.setCurrentIndex(0)
    finally:
        sys.settrace(previous)
    assert events and all(event == (False, None, None, None, {}) for event in events)
    assert not owner.valid and owner.published_generation is None
    assert stage.after.run is None and not stage.after.outlines


def test_settings_when_saved_loaded_bad_or_cancelled_then_no_font_write(scene, tmp_path):
    owner = capture(scene); stage = owner.active
    stage.editor.matrix['xx'].setText('2')
    path = tmp_path / 'recipe.json'
    stage.editor.save_settings(str(path))
    data = path.read_bytes()
    with pytest.raises(FileExistsError):
        stage.editor.save_settings(str(path))
    assert path.read_bytes() == data
    stage.editor.reset_transform()
    stage.editor._dialog(lambda *args: str(path), stage.editor.load_settings)
    assert owner.valid and stage.after.run.glyphs[0].advance == 1200.5
    before = digest(stage.models[1]), owner.published_generation, stage.after.run
    stage.editor._dialog(lambda *args: '', stage.editor.load_settings)
    assert (digest(stage.models[1]), owner.published_generation, stage.after.run) == before
    script = stage.editor.show_script()
    assert isinstance(script, str) and 'transform' in script
    path.write_text('{not JSON')
    stage.editor._dialog(lambda *args: str(path), stage.editor.load_settings)
    assert not owner.valid and stage.editor.result is None and stage.after.run is None
    path.unlink()
    stage.editor._dialog(lambda *args: str(path), stage.editor.load_settings)
    assert not owner.valid and stage.after.run is None


@pytest.mark.parametrize('fault', ['install', 'readback', 'missing_after_base', 'closed_peer'])
def test_publication_when_fallible_then_refuse_and_retry_from_before(scene, monkeypatch, fault):
    from ufoLib2.objects import Layer
    owner = capture(scene); stage = owner.active
    stage.editor.matrix['xx'].setText('2')
    base = deepcopy(stage.models[1]['B.base'])
    try:
        with monkeypatch.context() as patch:
            if fault == 'install':
                original = Layer.insertGlyph
                def refused(layer, *args, **kwargs):
                    if layer is stage.models[1].layers.defaultLayer:
                        raise OSError('owned install refusal')
                    return original(layer, *args, **kwargs)
                patch.setattr(Layer, 'insertGlyph', refused)
            elif fault == 'readback':
                def refused(*args):
                    raise OSError('owned readback refusal')
                patch.setattr(stage.fonts[1]._backend, 'check_open', refused)
            elif fault == 'missing_after_base':
                del stage.models[1]['B.base']
            else:
                stage.after.close()
            assert stage.editor.update() is True  # Legacy success callback error policy.
            assert not owner.valid and owner.published_generation is None
            assert stage.editor.diagnostic.text.startswith('Callback failed:')
            if fault != 'closed_peer':
                assert stage.after.run is None and not stage.after.outlines
        if fault == 'missing_after_base':
            stage.models[1].layers.defaultLayer.insertGlyph(base)
        if fault == 'closed_peer':
            assert owner.capture()
            stage = owner.active
            stage.editor.matrix['xx'].setText('2')
        else:
            assert stage.editor.update()
        assert owner.valid and stage.after.run.glyphs[0].advance == 1200.5
    finally:
        if 'B.base' not in stage.models[1]:
            stage.models[1].layers.defaultLayer.insertGlyph(base)


def test_retire_when_peer_diagnostic_raises_then_old_target_is_fenced(scene, monkeypatch):
    owner = capture(scene); old = owner.active
    with monkeypatch.context() as patch:
        def fail(*args):
            raise OSError('owned diagnostic refusal')
        patch.setattr(old.after.diagnostic, 'setText', fail)
        assert not owner.capture()
        assert not owner.valid and owner.published_generation is None
        assert owner.active is None
        assert old.retired and all(peer.closed for peer in old.peers)
    assert owner.capture()


@pytest.mark.parametrize('peer_index', [0, 1, 2])
@pytest.mark.parametrize('kind', ['false', 'exception', 'base'])
def test_release_when_actual_ui_close_faults_then_three_ACK_before_backend_close(scene, monkeypatch, peer_index, kind):
    owner = capture(scene); stage = owner.active
    peer = stage.peers[peer_index]
    error = KeyboardInterrupt('owned UI interrupt') if kind == 'base' else OSError('owned UI refusal')
    with monkeypatch.context() as patch:
        def fail():
            if kind == 'false':
                return False
            raise error
        patch.setattr(peer.widget, 'hide', fail)
        assert not owner.release()
        scene.app.processEvents()
        assert not owner._released and stage in owner.retired
        assert not peer._close_complete
        assert all(not font._backend.closed for font in stage.fonts)
        assert not owner.valid and all(child.closed for child in stage.peers)
        assert not owner.capture()
    assert owner._release_now() and owner.release()
    assert all(child._close_complete for child in stage.peers)
    assert all(font._backend.closed for font in stage.fonts)


@pytest.mark.parametrize('backend_index', [0, 1])
@pytest.mark.parametrize('kind', ['false', 'exception', 'base'])
def test_release_when_backend_refuses_then_retained_retry_no_duplicate_close(scene, monkeypatch, backend_index, kind):
    owner = capture(scene); stage = owner.active
    backend = stage.fonts[backend_index]._backend
    error = KeyboardInterrupt('owned backend interrupt') if kind == 'base' else OSError('owned backend refusal')
    calls = []
    with monkeypatch.context() as patch:
        def fail():
            calls.append(tuple(peer._close_complete for peer in stage.peers))
            if kind == 'false':
                return False
            raise error
        patch.setattr(backend, 'close', fail)
        assert not owner.release()
        scene.app.processEvents()
        assert calls == [(True, True, True)]
        assert not backend.closed and not owner._released and stage in owner.retired
    assert owner._release_now()
    assert all(font._backend.closed for font in stage.fonts)


@pytest.mark.parametrize('signal', ['release', 'finished', 'destroyed'])
@pytest.mark.parametrize('dispatch', ['update', 'selection'])
def test_close_when_nested_dispatch_then_fenced_and_deferred(scene, signal, dispatch):
    from PySide6.QtCore import Qt
    owner = capture(scene); stage = owner.active
    seen = []
    def stop(*args):
        if signal == 'release':
            assert not owner.release()
        elif signal == 'finished':
            owner.owned.content.finished.emit(0)
        else:
            owner._destroyed()
        seen.append((tuple(peer.closed for peer in stage.peers),
                     tuple(peer._close_complete for peer in stage.peers),
                     tuple(font._backend.closed for font in stage.fonts)))
    if dispatch == 'update':
        stage.after.on_update = stop
        stage.editor.update()
    else:
        stage.after.on_select = stop
        assert stage.after.select_key(Qt.Key_Home)
    assert seen == [((True, True, True), (False, False, False), (False, False))]
    assert not owner.valid
    scene.app.processEvents()
    assert owner._released
    assert all(peer._close_complete for peer in stage.peers)


@pytest.mark.parametrize('kind', ['ordinary', 'base'])
def test_owned_model_constructor_failure_when_backend_created_then_resource_retained_for_cleanup(scene, monkeypatch, kind):
    from fontlab_fontport import live
    owner = window(scene)
    owner.layer_control.setCurrentIndex(owner.layer_control.findText(LAYER))
    owner.glyph_control.setCurrentIndex(owner.glyph_control.findText(TARGET))
    original = live.RFont
    created = []
    error = ValueError('owned model constructor') if kind == 'ordinary' else KeyboardInterrupt('owned model constructor')
    def fail(backend):
        font = original(backend)
        created.append(font)
        raise error
    with monkeypatch.context() as patch:
        patch.setattr(live, 'RFont', fail)
        if kind == 'ordinary':
            assert not owner.capture()
        else:
            with pytest.raises(KeyboardInterrupt) as caught:
                owner.capture()
            assert caught.value is error
    assert created and all(font._backend.closed for font in created)
    assert any(problem is error for problem in owner.problems)
    assert owner.capture()


@pytest.mark.parametrize('scene', [False], indirect=True)
def test_source_when_closed_then_detached_edit_remains_useful_but_refresh_refuses(scene):
    owner = capture(scene); stage = owner.active
    scene.fixture_closers[0]()  # Explicit fixture-only external closure, not a tool action.
    scene.expected_closed[0] = True
    stage.editor.matrix['xx'].setText('2')
    assert owner.valid and stage.after.run.glyphs[0].advance == 1200.5
    assert 'Detached snapshot' in owner.status.text
    assert not owner.capture()
    assert owner.active is None and not owner.valid and owner.published_generation is None
    assert 'closed' in owner.status.text.lower()
    assert all(peer._close_complete for peer in stage.peers)
    assert scene.fonts[1]._backend.closed is False


def test_generation_when_old_callback_arrives_then_current_target_not_overwritten(scene):
    owner = capture(scene); old = owner.active
    old_callback = old.editor.on_change
    recipe = old.editor.recipe()
    glyph = deepcopy(old.models[0][TARGET])
    owner.layer_control.setCurrentIndex(owner.layer_control.findText('Alternate'))
    assert owner.active is None and old.retired and not owner.valid
    owner.glyph_control.setCurrentIndex(owner.glyph_control.findText(TARGET))
    assert owner.capture()
    before = digest(owner.active.models[1]), owner.published_generation
    old_callback(recipe, glyph)
    assert (digest(owner.active.models[1]), owner.published_generation) == before
    assert owner.active.models[1][TARGET].width == 777.75


@pytest.mark.parametrize('factory,index', [('transform_editor', 1), ('glyph_sequence', 1), ('glyph_sequence', 2)])
@pytest.mark.parametrize('kind', ['ordinary', 'group', 'base'])
def test_partial_factory_when_real_owner_then_original_error_and_retry_survive(scene, monkeypatch, factory, index, kind):
    from fontlabapp import fontui
    owner = window(scene)
    owner.layer_control.setCurrentIndex(owner.layer_control.findText(LAYER))
    owner.glyph_control.setCurrentIndex(owner.glyph_control.findText(TARGET))
    original = getattr(fontui, factory)
    error = KeyboardInterrupt('original factory') if kind == 'base' else ValueError('original factory')
    partial, calls = [], []
    with monkeypatch.context() as patch:
        def failed_factory(*args, **kwargs):
            child = original(*args, **kwargs)  # Always actual construction, never dummy success.
            calls.append(child)
            if len(calls) != index:
                return child
            partial.append(child)
            def refuse():
                raise RuntimeError('owned partial hide refusal')
            patch.setattr(child.widget, 'hide', refuse)
            error.owner = child
            if kind == 'group':
                raise ExceptionGroup('actual partial factory', [error])
            raise error
        patch.setattr(fontui, factory, failed_factory)
        if kind == 'base':
            with pytest.raises(KeyboardInterrupt) as caught:
                owner.capture()
            assert caught.value is error
        else:
            assert not owner.capture()
        assert partial and owner.active is None and owner.retired
        stage = owner.retired[0]
        assert partial[0] in stage.peers and partial[0].closed and not partial[0]._close_complete
        assert all(not backend.closed for backend in stage.backends)
        assert any(problem is error or (isinstance(problem, ExceptionGroup) and error in problem.exceptions)
                   for problem in owner.problems)
    assert owner.capture()
    assert all(child._close_complete for child in calls)
    assert all(backend.closed for backend in stage.backends)


@pytest.mark.parametrize('position', [1, 2, 3])
@pytest.mark.parametrize('kind', ['ordinary', 'base'])
def test_layout_when_real_child_install_fails_then_owned_objects_close(scene, monkeypatch, position, kind):
    owner = window(scene)
    owner.layer_control.setCurrentIndex(owner.layer_control.findText(LAYER))
    owner.glyph_control.setCurrentIndex(owner.glyph_control.findText(TARGET))
    add = owner.layout.addWidget
    seen = []
    error = KeyboardInterrupt('owned layout') if kind == 'base' else ValueError('owned layout')
    with monkeypatch.context() as patch:
        def fail(widget):
            add(widget)
            seen.append(widget)
            if len(seen) == position:
                raise error
        patch.setattr(owner.layout, 'addWidget', fail)
        if kind == 'base':
            with pytest.raises(KeyboardInterrupt) as caught:
                owner.capture()
            assert caught.value is error
        else:
            assert not owner.capture()
    assert seen and not owner.valid and owner.active is None and not owner.retired
    assert any(problem is error for problem in owner.problems)
    assert owner.capture()


@pytest.mark.parametrize('kind', ['ordinary', 'base'])
def test_show_when_outer_construction_fails_then_original_exception_preserved(scene, monkeypatch, kind):
    from PySide6.QtWidgets import QWidget
    from PythonQt import QtGui
    parent = QWidget(); scene.parents.append(parent)
    original = QtGui.QLabel.setText
    error = KeyboardInterrupt('owned outer construction') if kind == 'base' else ValueError('owned outer construction')
    def fail(widget, text):
        if 'Owned same label' in text:
            raise error
        return original(widget, text)
    with monkeypatch.context() as patch:
        patch.setattr(QtGui.QLabel, 'setText', fail)
        with pytest.raises(type(error)) as caught:
            scene.module.show(scene.fonts[0], parent)
        assert caught.value is error
    assert not scene.module._HANDLES


def test_capture_when_reentrant_peer_notification_then_no_recompute_or_model_swap(scene):
    owner = capture(scene); stage = owner.active
    attempts = []
    stage.after.on_update = lambda peer: attempts.append(owner.capture())
    stage.editor.matrix['xx'].setText('2')
    assert attempts == [False, False]
    assert owner.active is stage and owner.valid
    assert stage.after.run.glyphs[0].advance == 1200.5


def test_resource_when_upm_absent_then_documented_fallback_without_source_write(scene):
    scene.sources[0].info.unitsPerEm = None
    try:
        owner = capture(scene)
        assert owner.active.models[0].info.unitsPerEm is None
        assert owner.active.editor.view(300, 200)[0] > 0
    finally:
        scene.sources[0].info.unitsPerEm = 1000


def test_before_model_when_temporarily_missing_then_failed_update_and_restored_final_digest(scene):
    owner = capture(scene); stage = owner.active
    glyph = deepcopy(stage.models[0][TARGET])
    del stage.models[0][TARGET]
    try:
        assert not stage.editor.update()
        assert not owner.valid and stage.after.run is None
    finally:
        stage.models[0].layers.defaultLayer.insertGlyph(glyph)
    assert stage.editor.update() and owner.valid


def test_owned_after_font_when_closed_then_open_peer_clears_and_capture_retries(scene):
    owner = capture(scene); stage = owner.active
    stage.fonts[1].close()  # Deliberate owned-fixture failure; peer stays open.
    assert not stage.after.closed
    assert stage.editor.update()
    assert not owner.valid and stage.after.run is None and not stage.after.outlines
    assert stage.editor.diagnostic.text.startswith('Callback failed:')
    assert owner.capture() and owner.valid


@pytest.mark.parametrize('which', ['editor', 'before'])
def test_peer_when_closing_during_publication_then_not_marked_current(scene, which):
    owner = capture(scene); stage = owner.active
    def close_during_publication(peer):
        if peer.run is not None:
            getattr(stage, which).close()
    stage.after.on_update = close_during_publication
    stage.editor.update()
    assert getattr(stage, which)._close_complete
    assert not owner.valid and owner.published_generation is None
    assert stage.after.run is None and not stage.after.outlines


def test_refresh_when_close_during_invalidation_then_no_new_source_read(scene, monkeypatch):
    owner = capture(scene); stage = owner.active
    reads = []
    backend = scene.fonts[0]._backend
    original = backend.read_glyph
    def read(*args):
        reads.append(args)
        return original(*args)
    monkeypatch.setattr(backend, 'read_glyph', read)
    stage.after.on_update = lambda peer: owner.release()
    assert not owner.capture()
    assert owner._closing and not owner.valid
    assert reads == []
    scene.app.processEvents()
    assert owner._released


def test_actual_parent_deletion_when_live_then_children_ack_before_owned_backends_close(scene):
    from PySide6 import QtCore
    owner = capture(scene); stage = owner.active
    scene.parents[0].deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    scene.app.processEvents()
    assert owner._released
    assert all(peer._close_complete for peer in stage.peers)
    assert all(backend.closed for backend in stage.backends)


@pytest.mark.parametrize('boundary', ['old_hide', 'first_layout'])
def test_capture_when_cleanup_or_acquisition_releases_then_no_later_factory(scene, monkeypatch, boundary):
    import fontlabapp.fontui as ui
    owner = capture(scene); old = owner.active
    reads, factories = [], []
    backend = scene.fonts[0]._backend
    read = backend.read_glyph
    def observed_read(*args):
        reads.append(owner._closing)
        return read(*args)
    codes = {ui.transform_editor.__code__, ui.glyph_sequence.__code__}
    previous = sys.getprofile()
    def profile(frame, event, value):
        if event == 'call' and frame.f_code in codes:
            factories.append(owner._closing)
        if previous is not None:
            previous(frame, event, value)
    with monkeypatch.context() as patch:
        patch.setattr(backend, 'read_glyph', observed_read)
        if boundary == 'old_hide':
            hide = old.editor.widget.hide
            def stop():
                result = hide()
                owner.release()
                return result
            patch.setattr(old.editor.widget, 'hide', stop)
        else:
            add = owner.layout.addWidget
            def stop(widget):
                result = add(widget)
                owner.release()
                return result
            patch.setattr(owner.layout, 'addWidget', stop)
        try:
            sys.setprofile(profile)
            assert not owner.capture()
        finally:
            sys.setprofile(previous)
    assert owner._closing and not owner.valid and owner.active is None
    assert True not in factories, 'A new peer factory began after the owner was fenced'
    if boundary == 'old_hide':
        assert reads == [] and factories == []
    scene.app.processEvents()
    assert owner._released
    assert all(peer._close_complete for peer in old.peers)
    assert all(backend.closed for backend in old.backends)


@pytest.mark.parametrize('selector', ['layer', 'glyph'])
@pytest.mark.parametrize('notification', ['invalidate', 'publish'])
def test_target_when_changed_from_sequence_then_no_superseded_publication(scene, selector, notification):
    owner = capture(scene); old = owner.active
    changed = []
    def select(peer):
        if changed or (notification == 'publish' and peer.run is None):
            return
        changed.append(True)
        control = owner.layer_control if selector == 'layer' else owner.glyph_control
        control.setCurrentIndex(control.findText('Alternate' if selector == 'layer' else 'B.base'))
    old.after.on_update = select
    old.editor.update()
    assert changed and not owner.valid and owner.published_generation is None
    scene.app.processEvents()
    assert owner.active is None and old.retired and old.after.run is None
    if selector == 'layer':
        assert owner.layer_control.currentText == 'Alternate'
        assert owner.glyph_control.currentIndex == -1
        owner.glyph_control.setCurrentIndex(owner.glyph_control.findText(TARGET))
    else:
        assert owner.glyph_control.currentText == 'B.base'
    assert owner.capture()
    stage = owner.active
    assert stage.layer == ('Alternate' if selector == 'layer' else LAYER)
    assert stage.name == (TARGET if selector == 'layer' else 'B.base')
    assert stage.after.run.glyphs[0].name == stage.name
    if selector == 'layer':
        assert stage.after.run.glyphs[0].advance == 777.75
    assert owner.valid and stage.generation > old.generation


@pytest.mark.parametrize('selector', ['layer', 'glyph'])
@pytest.mark.parametrize('route', ['ordinary', 'capture_notification'])
def test_target_when_ordinary_or_capture_signal_then_explicit_next_capture_matches(scene, monkeypatch, selector, route):
    owner = capture(scene); old = owner.active
    changed = []
    def select(*args):
        if changed:
            return
        changed.append(True)
        control = owner.layer_control if selector == 'layer' else owner.glyph_control
        control.setCurrentIndex(control.findText('Alternate' if selector == 'layer' else 'B.base'))
    if route == 'ordinary':
        select()
    else:
        add = owner.layout.addWidget
        def install(widget):
            result = add(widget)
            stage = owner.active
            if stage.after is not None and widget is stage.after.widget:
                stage.after.on_update = select
            return result
        with monkeypatch.context() as patch:
            patch.setattr(owner.layout, 'addWidget', install)
            assert not owner.capture()
    assert changed and not owner.valid and owner.published_generation is None
    scene.app.processEvents()
    assert owner.active is None
    if selector == 'layer':
        assert owner.layer_control.currentText == 'Alternate'
        assert owner.glyph_control.currentIndex == -1
        owner.glyph_control.setCurrentIndex(owner.glyph_control.findText(TARGET))
    else:
        assert owner.glyph_control.currentText == 'B.base'
    assert owner.capture()
    assert owner.active.layer == ('Alternate' if selector == 'layer' else LAYER)
    assert owner.active.name == (TARGET if selector == 'layer' else 'B.base')
    assert owner.valid and owner.active.generation > old.generation


def test_capture_when_source_callback_releases_then_no_owned_stage_acquired(scene, monkeypatch):
    import fontlabapp.fontui as ui
    owner = capture(scene); old = owner.active
    backend = scene.fonts[0]._backend
    original = backend.read_glyph
    calls = []
    def read(*args):
        value = original(*args)
        owner.release()
        return value
    previous = sys.getprofile()
    codes = {ui.transform_editor.__code__, ui.glyph_sequence.__code__}
    def profile(frame, event, value):
        if event == 'call' and frame.f_code in codes:
            calls.append(frame.f_code.co_name)
        if previous is not None:
            previous(frame, event, value)
    with monkeypatch.context() as patch:
        patch.setattr(backend, 'read_glyph', read)
        try:
            sys.setprofile(profile)
            assert not owner.capture()
        finally:
            sys.setprofile(previous)
    assert owner._closing and owner.active is None and not owner.valid
    assert calls == []
    scene.app.processEvents()
    assert owner._released and all(peer._close_complete for peer in old.peers)
