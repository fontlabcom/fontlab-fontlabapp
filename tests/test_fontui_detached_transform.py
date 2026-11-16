# this_file: tests/test_fontui_detached_transform.py
"""Actual editor/Sequence behavior; no production method replacements."""
from copy import deepcopy
import hashlib
import importlib
import inspect
import json
import sys
from types import SimpleNamespace

import pytest

TARGET = 'Z.target'
LAYER = 'Display'
EXPECTED_RECORDING = (
    ('moveTo', ((10, -5),)), ('lineTo', ((210, -5),)),
    ('lineTo', ((210, 295),)), ('closePath', ()),
    ('moveTo', ((70, 115),)), ('lineTo', ((110, 115),)),
    ('lineTo', ((110, 205),)), ('closePath', ()),
)


def digest(value):
    from _feature_source_qt import freeze
    return hashlib.sha256(json.dumps(freeze(value), sort_keys=True).encode()).hexdigest()


def source_font(marker):
    from _feature_source_qt import font_fixture
    from ufoLib2.objects import Component
    font = font_fixture('languagesystem DFLT dflt;\n', marker)
    layer = font.layers.newLayer(LAYER)
    base = layer.newGlyph('A.base')
    base.width = 200
    pen = base.getPen()
    pen.moveTo((0, 0)); pen.lineTo((20, 0)); pen.lineTo((20, 30)); pen.closePath()
    root = layer.newGlyph(TARGET)
    root.width, root.height = 600.25, 900.5
    root.lib['marker'] = marker
    pen = root.getPen()
    pen.moveTo((0, 0)); pen.lineTo((100, 0)); pen.lineTo((100, 100)); pen.closePath()
    root.components.append(Component('A.base', (1, 0, 0, 1, 30, 40)))
    return font


def cache_state(font):
    return {
        name: {'layer': id(layer), 'valid': layer._valid,
               'bindings': {key: {'binding': id(binding), 'glyph': id(binding.glyph),
                                  'pending_geometry': binding.pending_geometry,
                                  'model': digest(binding.model.getDataForSerialization()),
                                  'accepted': digest(binding.accepted)}
                            for key, binding in layer._bindings.items()}}
        for name, layer in font._layers.items()
    }


def observation(state, phase):
    after, editor = state.after, state.editor
    return {'phase': phase, 'generation': state.generation, 'attempt': state.attempt,
            'callback_count': state.callbacks, 'publication_count': state.publications,
            'published_generation': state.published_generation,
            'target': TARGET, 'editor_result': editor.result is not None,
            'editor_diagnostic': editor.diagnostic.text,
            'after_run': after.run is not None,
            'after_names': [g.name for g in after.run.glyphs] if after.run is not None else [],
            'after_outlines': {k: {'recording': v.recording, 'bounds': v.bounds, 'width': v.width}
                               for k, v in after.outlines.items()},
            'after_selection': after.selected_index, 'after_diagnostic': after.diagnostic.text}


@pytest.fixture
def linked(monkeypatch):
    from _feature_source_qt import owned_application, qt_namespace
    from PySide6 import QtCore, QtWidgets
    import shiboken6
    from ufoLib2 import Font
    from fontlab_fontport.live import RFont, RLayer
    from fontlab_fontport.memory import UFOBackend

    qt = qt_namespace()
    combo_base = qt.QtGui.QComboBox
    class Combo(combo_base):
        currentText = property(QtWidgets.QComboBox.currentText)
    class Slider(QtWidgets.QSlider):
        value = property(QtWidgets.QSlider.value)
    qt.QtGui.QComboBox, qt.QtGui.QSlider = Combo, Slider
    monkeypatch.setitem(sys.modules, 'PythonQt', qt)
    monkeypatch.setitem(sys.modules, 'fontlab', None)
    for name in ('transform', 'transform_view', 'lifecycle', 'sequence', 'sequence_canvas'):
        monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.' + name, raising=False)
    transform = importlib.import_module('fontlabapp.fontui.transform')
    sequence = importlib.import_module('fontlabapp.fontui.sequence')
    sources = [source_font(marker) for marker in ('first', 'second')]
    borrowed = [RFont(UFOBackend(model)) for model in sources]
    # Real held defcon notifications create uncommitted wrapper data; no method
    # replacement or fabricated pending flag. Fresh-layer reads must bypass it.
    cached = borrowed[0].getLayer(LAYER)[TARGET]
    cached.naked().holdNotifications()
    cached.width = 999
    assert sources[0].layers[LAYER][TARGET].width == 600.25
    source_before = [digest(model) for model in sources]
    cache_before = [cache_state(font) for font in borrowed]
    fresh = RLayer(borrowed[0], LAYER)
    closure = {}
    fresh._dependency_sources(TARGET, (), closure)
    assert list(closure) == ['A.base', TARGET]
    assert fresh not in borrowed[0]._layers.values()
    before_model = Font()
    before_model.info.unitsPerEm = 1000
    for glyph in closure.values():
        before_model.layers.defaultLayer.insertGlyph(deepcopy(glyph))
    after_model = deepcopy(before_model)
    before_digest = digest(before_model)
    owned_fonts = [RFont(UFOBackend(model)) for model in (before_model, after_model)]
    state = SimpleNamespace(ready=False, generation=1, attempt=0, callbacks=0,
                            publications=0, published_generation=None, valid=False, invalidations=0, held=[], owners=[],
                            borrowed=borrowed, sources=sources, models=[before_model, after_model],
                            fonts=owned_fonts, expected_before=before_digest)

    def publish(recipe, glyph):
        state.callbacks += 1
        if not state.ready:
            state.held.append((recipe, glyph))
            return
        assert state.generation == 1 and glyph.name == TARGET
        if state.after.closed:
            raise RuntimeError('The owned proof is closed')
        after_model.layers.defaultLayer.insertGlyph(deepcopy(glyph), overwrite=True)
        owned_fonts[1].refresh()
        state.after.refresh()
        assert state.after.run is not None and TARGET in state.after.outlines
        state.publications += 1
        state.published_generation = state.generation
        state.valid = True

    def invalidate():
        # Clear logical validity before the fallible peer/UI operation.
        state.invalidations += 1
        state.valid = False
        state.published_generation = None
        if state.ready:
            state.after.fail(RuntimeError("Transform preview is unavailable"))

    state.invalidate = invalidate

    def preserve():
        assert [digest(model) for model in sources] == source_before
        assert [cache_state(font) for font in borrowed] == cache_before
        assert cached.width == 999 and all(not font._backend.closed for font in borrowed)

    with owned_application() as app:
        parent = QtWidgets.QWidget()
        try:
            state.editor = transform.TransformEditor(before_model, name=TARGET, parent=parent, on_change=publish, on_invalidate=invalidate)
            state.owners.append(state.editor)
            state.parent = parent
            assert state.invalidations == 0
            assert state.editor.on_invalidate is invalidate
            state.editor.glyph_control.setEnabled(False)
            assert state.editor.glyph_control.currentText == TARGET
            for font in owned_fonts:
                peer = sequence.Sequence(font, parent=parent)
                state.owners.append(peer)
                peer.mode_control.setCurrentIndex(1)
                peer.text_control.setText('/' + TARGET)
                assert peer.run is not None and [g.name for g in peer.run.glyphs] == [TARGET]
            state.before, state.after = state.owners[1:]
            assert state.callbacks == 1 and len(state.held) == 1 and state.publications == 0
            state.ready = True
            state.held.clear()
            for name, value in [('xx', '2'), ('yy', '3'), ('dx', '10'), ('dy', '-5')]:
                state.editor.matrix[name].setText(value)
            assert state.callbacks == 5 and state.publications == 4
            assert state.editor.result.recording == EXPECTED_RECORDING
            assert state.after.outlines[TARGET].recording == EXPECTED_RECORDING
            assert state.after.outlines[TARGET].bounds == (10, -5, 210, 295)
            assert state.after.run.glyphs[0].advance == 1200.5
            assert after_model[TARGET].height == 2701.5
            assert digest(before_model) == before_digest
            assert state.before.outlines[TARGET].bounds == (0, 0, 100, 100)
            assert state.after.select_key(QtCore.Qt.Key_Home) is True
            assert state.after.selected_index == 0
            preserve()
            state.prime = observation(state, 'nonidentity-prime')
            yield state
        finally:
            state.ready = False
            for owner in reversed(state.owners):
                owner.close()
                assert owner._close_complete
            QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            assert all(not shiboken6.isValid(owner.widget) for owner in state.owners)
            parent.deleteLater()
            QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            assert not shiboken6.isValid(parent)
            for font in owned_fonts:
                if not font._backend.closed:
                    font.close()
                assert font._backend.closed
            preserve()
            assert QtWidgets.QApplication.instance() is app
    # Test-fixture cleanup restores only our own held wrapper edit after its
    # preservation oracle; releasing equal-to-accepted data causes no write.
    cached.width = 600.25
    cached.naked().releaseHeldNotifications()
    assert [digest(model) for model in sources] == source_before


def attempt(state, route, path):
    """Call a real entry directly; a selected path is owned by the test."""
    editor = state.editor
    if route == 'update':
        return editor.update()
    if route == 'sync':
        return editor._sync(True)
    if route == 'reset':
        return editor.reset_transform()
    return editor.load_settings(str(path))


def trace_operations(state, action):
    """Observe real code before its first fallible operations, without replacing it."""
    from fontlab_fontport.recipe import Recipe
    editor_type = type(state.editor)
    markers = {
        '_sync': 'target = self.intensity_field',
        'reset_transform': 'self._show(Recipe())',
        'load_settings': 'self._show(Recipe.load(path))',
        'update': 'name = self.glyph_control.currentText',
    }
    points = {}
    for name, marker in markers.items():
        function = getattr(editor_type, name)
        lines, start = inspect.getsourcelines(function)
        line = next(start + i for i, text in enumerate(lines) if marker in text)
        points[function.__code__, line] = name
    calls = {editor_type.recipe.__code__: 'recipe',
             Recipe.load.__func__.__code__: 'Recipe.load',
             importlib.import_module('fontlab_fontport.operations').transform_glyph.__code__: 'transform_glyph'}
    events = []
    previous = sys.gettrace()

    def trace(frame, event, arg):
        name = points.get((frame.f_code, frame.f_lineno)) if event == 'line' else None
        if event == 'call':
            name = calls.get(frame.f_code)
        if name:
            events.append({'operation': name, 'result': state.editor.result,
                           'valid': state.valid, 'generation': state.published_generation,
                           'run': state.after.run, 'outlines': dict(state.after.outlines),
                           'selection': state.after.selected_index})
        return trace if frame.f_code in calls or any(code is frame.f_code for code, _ in points) else None

    try:
        sys.settrace(trace)
        result = action()
    finally:
        sys.settrace(previous)
        state.operations = events
    return result


def assert_unavailable(state):
    assert not state.valid and state.published_generation is None
    assert state.after.run is None and not state.after.outlines
    assert state.after.selected_index is None


def assert_early(state):
    assert state.operations, 'The real entry operation must have been reached'
    for event in state.operations:
        assert event['result'] is None
        assert not event['valid'] and event['generation'] is None
        assert event['run'] is None and not event['outlines']
        assert event['selection'] is None


def test_prime_when_nonidentity_then_independent_geometry_and_two_sequences(linked):
    assert linked.prime['after_selection'] == 0
    assert linked.prime['publication_count'] == 4
    assert linked.valid and linked.published_generation == 1


@pytest.mark.parametrize('boundary', ['temporal', 'final'])
def test_matrix_when_invalid_then_signal_and_direct_attempt_clear_proof(linked, boundary):
    trace_operations(linked, lambda: linked.editor.matrix['xx'].setText('invalid'))
    assert_early(linked)
    assert_unavailable(linked)
    assert trace_operations(linked, linked.editor.update) is False
    assert_early(linked)
    assert_unavailable(linked)
    assert linked.editor.result is None
    assert linked.editor.diagnostic.text == "xx: not a number: 'invalid'"
    assert linked.callbacks == 5 and linked.publications == 4


@pytest.mark.parametrize('selected_load', [False, True])
@pytest.mark.parametrize('boundary', ['temporal', 'final'])
def test_target_when_missing_then_clear_before_read_and_keep_source(linked, tmp_path, selected_load, boundary):
    from fontlab_fontport.recipe import Recipe
    path = tmp_path / 'valid.json'
    Recipe(matrix=(1, 0, 0, 1, 25, 30)).save(path)
    target = deepcopy(linked.models[0][TARGET])
    del linked.models[0][TARGET]
    try:
        action = (lambda: linked.editor._dialog(lambda *args: str(path), linked.editor.load_settings)) if selected_load else linked.editor.update
        result = trace_operations(linked, action)
        assert result is None if selected_load else result is False
        assert_early(linked)
        assert_unavailable(linked)
        assert linked.editor.result is None
        assert linked.editor.diagnostic.text == "'Z.target'"
        assert linked.callbacks == 5 and linked.publications == 4
        if selected_load:
            assert linked.editor.matrix['dx'].text == '25'
            assert any(e['operation'] == 'Recipe.load' for e in linked.operations)
    finally:
        linked.models[0].layers.defaultLayer.insertGlyph(target)
        assert digest(linked.models[0]) == linked.expected_before


@pytest.mark.parametrize('route', ['slider', 'field', 'reset', 'reset_button', 'load', 'enabled'])
def test_route_when_valid_then_clear_before_work_and_publish_once(linked, tmp_path, route):
    from fontlab_fontport.recipe import Recipe
    editor = linked.editor
    path = tmp_path / 'valid.json'
    Recipe(matrix=(1, 0, 0, 1, 25, 30)).save(path)
    actions = {
        'slider': lambda: editor.intensity_slider.setValue(50),
        'field': lambda: editor.intensity_field.setText('25'),
        'reset': editor.reset_transform,
        'reset_button': editor.buttons['reset'].click,
        'load': lambda: editor._dialog(lambda *args: str(path), editor.load_settings),
        'enabled': lambda: editor.enabled_control.setChecked(False),
    }
    expected = {
        'slider': ((5, -2.5, 155, 197.5), 900.375, 1801.0),
        'field': ((2.5, -1.25, 127.5, 148.75), 750.3125, 1350.75),
        'reset': ((0, 0, 100, 100), 600.25, 900.5),
        'reset_button': ((0, 0, 100, 100), 600.25, 900.5),
        'load': ((25, 30, 125, 130), 600.25, 900.5),
        'enabled': ((0, 0, 100, 100), 600.25, 900.5),
    }
    trace_operations(linked, actions[route])
    assert_early(linked)
    assert sum(e['operation'] == 'transform_glyph' for e in linked.operations) == 1
    assert linked.callbacks == 6 and linked.publications == 5
    assert linked.valid and linked.published_generation == 1
    bounds, advance, height = expected[route]
    assert linked.after.outlines[TARGET].bounds == bounds
    assert linked.after.run.glyphs[0].advance == advance
    assert linked.models[1][TARGET].height == height
    assert linked.after.selected_index is None


@pytest.mark.parametrize('kind', ['invalid', 'missing'])
@pytest.mark.parametrize('boundary', ['temporal', 'final'])
def test_selected_file_when_unreadable_then_attempt_is_unavailable(linked, tmp_path, kind, boundary):
    path = tmp_path / 'selected.json'
    if kind == 'invalid':
        path.write_text('{invalid JSON\n')
    trace_operations(linked, lambda: linked.editor._dialog(lambda *args: str(path), linked.editor.load_settings))
    assert_early(linked)
    assert_unavailable(linked)
    assert linked.editor.result is None
    assert linked.callbacks == 5 and linked.publications == 4
    assert not any(e['operation'] in ('update', 'recipe', 'transform_glyph') for e in linked.operations)
    assert ('Expecting property name' if kind == 'invalid' else 'No such file') in linked.editor.diagnostic.text


def test_chooser_when_cancelled_then_valid_proof_and_models_are_unchanged(linked):
    before = observation(linked, 'cancel')
    models = [digest(model) for model in linked.models]
    invalidations = linked.invalidations
    assert trace_operations(linked, lambda: linked.editor._dialog(lambda *args: '', linked.editor.load_settings)) is None
    assert linked.operations == [] and linked.invalidations == invalidations
    assert observation(linked, 'cancel') == before
    assert [digest(model) for model in linked.models] == models


@pytest.mark.parametrize('failure', ['backend', 'target', 'retired'])
def test_publication_when_refused_then_update_success_is_not_proof(linked, failure):
    if failure == 'backend':
        linked.fonts[1].close()
        action = linked.editor.update
    elif failure == 'retired':
        linked.generation = 2
        action = linked.editor.update
    else:
        assert not linked.editor.glyph_control.isEnabled()
        action = lambda: linked.editor.glyph_control.setCurrentIndex(0)
    trace_operations(linked, action)
    assert_early(linked)
    assert_unavailable(linked)
    assert linked.editor.result is not None
    assert linked.callbacks == 6 and linked.publications == 4
    assert linked.editor.diagnostic.text.startswith('Callback failed:')


@pytest.mark.parametrize('text', ['bad', 'nan', 'inf', '-inf'])
def test_intensity_when_invalid_then_no_calculation_or_publication(linked, text):
    trace_operations(linked, lambda: linked.editor.intensity_field.setText(text))
    assert_early(linked)
    assert_unavailable(linked)
    assert linked.editor.result is None and linked.callbacks == 5
    assert not any(e['operation'] == 'transform_glyph' for e in linked.operations)


@pytest.mark.parametrize('route', ['update', 'sync', 'reset', 'load'])
def test_entry_when_closed_then_refuse_without_work(linked, tmp_path, route):
    linked.editor.close()
    assert linked.editor._close_complete
    calls = linked.invalidations
    result = trace_operations(linked, lambda: attempt(linked, route, tmp_path / 'missing.json'))
    assert result is False if route == 'update' else result is None
    assert linked.operations == [] and linked.invalidations == calls
    assert linked.callbacks == 5 and not linked.editor._invalidating


@pytest.mark.parametrize('route', ['update', 'sync', 'reset', 'load'])
def test_notification_when_reentrant_then_refuse_nested_entries_only(linked, tmp_path, route):
    from fontlab_fontport.recipe import Recipe
    path = tmp_path / 'valid.json'
    Recipe().save(path)
    nested = []

    def notify():
        linked.invalidate()
        assert linked.editor._invalidating
        nested.append([attempt(linked, name, tmp_path / 'must-not-open.json')
                       for name in ('update', 'sync', 'reset', 'load')])

    linked.editor.on_invalidate = notify
    result = trace_operations(linked, lambda: attempt(linked, route, path))
    assert result is True if route == 'update' else result is None
    assert nested and all(row == [False, None, None, None] for row in nested)
    assert not linked.editor._invalidating
    assert_early(linked)
    assert sum(e['operation'] == 'transform_glyph' for e in linked.operations) == 1
    assert linked.callbacks == 6 and linked.publications == 5


@pytest.mark.parametrize('route', ['update', 'sync', 'reset', 'load'])
@pytest.mark.parametrize('kind', ['exception', 'base', 'close', 'close_exception', 'arbitrary_exception'])
def test_notification_when_refused_then_restore_fence_and_stop(linked, tmp_path, route, kind):
    error = KeyboardInterrupt('owned stop') if kind == 'base' else ValueError('owned refusal')

    def notify():
        if kind != 'arbitrary_exception':
            linked.invalidate()
        if kind.startswith('close'):
            linked.editor.close()
            assert linked.editor._close_complete
        if kind != 'close':
            raise error

    linked.editor.on_invalidate = notify
    action = lambda: attempt(linked, route, tmp_path / 'must-not-open.json')
    if kind == 'base':
        with pytest.raises(KeyboardInterrupt) as caught:
            trace_operations(linked, action)
        assert caught.value is error
    else:
        result = trace_operations(linked, action)
        assert result is False if route == 'update' else result is None
    assert linked.operations == []
    assert linked.editor.result is None and not linked.editor._invalidating
    assert linked.callbacks == 5 and linked.publications == 4
    if kind == 'arbitrary_exception':
        # The helper cannot clear an arbitrary external peer on the consumer's behalf.
        assert linked.valid and linked.after.run is not None
    else:
        assert_unavailable(linked)
    if kind in ('exception', 'arbitrary_exception'):
        assert linked.editor.diagnostic.text == 'owned refusal'


@pytest.mark.parametrize('factory', [False, True])
@pytest.mark.parametrize('initial_good', [False, True])
@pytest.mark.parametrize('callback_raises', [False, True])
def test_constructor_when_callback_supplied_then_register_after_legacy_update(linked, factory, initial_good, callback_raises):
    from fontlabapp.fontui import transform_editor
    calls, successes = [], []

    def notify():
        calls.append('invalidate')
        if callback_raises:
            raise ValueError('subsequent refusal')

    construct = transform_editor if factory else type(linked.editor)
    owner = construct(linked.models[0] if initial_good else None, TARGET, linked.parent,
                      lambda recipe, glyph: successes.append((recipe, glyph)), notify)
    linked.owners.append(owner)
    assert calls == [] and owner.on_invalidate is notify
    assert (owner.result is not None) == initial_good
    assert len(successes) == int(initial_good)
    result = owner.update()
    assert calls == ['invalidate'] and not owner._invalidating
    assert result == (initial_good and not callback_raises)
    assert len(successes) == int(initial_good) * (1 if callback_raises else 2)
    if callback_raises:
        assert owner.diagnostic.text == 'subsequent refusal'


def test_bridge_when_peer_closed_then_logical_validity_clears_before_ui(linked):
    linked.after.close()
    assert linked.after._close_complete
    assert linked.editor.update() is True
    assert not linked.valid and linked.published_generation is None
    assert linked.publications == 4 and linked.callbacks == 6
    assert linked.editor.diagnostic.text.startswith('Callback failed:')

