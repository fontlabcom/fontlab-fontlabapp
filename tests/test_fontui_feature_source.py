# this_file: tests/test_fontui_feature_source.py
# SPDX-License-Identifier: Apache-2.0
"""Actual editor/build/state and two complete RFont/UFO fonts at every boundary."""
from copy import deepcopy
import importlib
import sys
from types import SimpleNamespace

import pytest
from _feature_source_qt import owned_application, qt_namespace, font_fixture, freeze, snapshot

TAIL = 'feature liga {\n  sub A B by A;\n} liga;\nfeature kern {\r\n  pos A B -25;\r\n} kern;\r\n'


@pytest.fixture
def real_source(monkeypatch):
    from fontlab_fontport.live import RFont
    from fontlab_fontport.memory import UFOBackend
    from fontlab_fontport.fontdata import RFeatures
    from PySide6 import QtCore
    import shiboken6

    names = ['fontlabapp.fontui.'+n for n in ('features', 'features_view', 'lifecycle', 'sequence', 'sequence_canvas')]
    saved = {name: sys.modules.get(name) for name in names}
    for name in names:
        monkeypatch.delitem(sys.modules, name, raising=False)
    qt = qt_namespace()
    monkeypatch.setitem(sys.modules, 'PythonQt', qt)
    monkeypatch.setitem(sys.modules, 'fontlab', None)
    with owned_application() as app:
        module = importlib.import_module('fontlabapp.fontui.features')
        models = [font_fixture('# original\n'+TAIL, marker) for marker in ('A', 'B')]
        backends = [UFOBackend(model) for model in models]
        fonts = [RFont(backend) for backend in backends]
        expected = deepcopy(models)
        owners, logical, writes, callbacks, forbidden = [], [], [], [], []
        original = RFeatures.set_blocks
        def set_blocks(self, values, **kwargs):
            logical.append((self, deepcopy(values)))
            return original(self, values, **kwargs)
        monkeypatch.setattr(RFeatures, 'set_blocks', set_blocks)
        for backend in backends:
            setter = backend.set_features
            def write(text, *, _backend=backend, _setter=setter, **kwargs):
                writes.append((_backend, text))
                return _setter(text, **kwargs)
            monkeypatch.setattr(backend, 'set_features', write)
            for name in ('close', 'save', 'save_options', 'write_glyph', 'set_info', 'set_info_many', 'set_groups', 'set_kerning', 'set_lib', 'new_glyph', 'remove_glyph'):
                def refuse(*args, _name=name, **kwargs):
                    forbidden.append(_name)
                    raise AssertionError('Unexpected borrowed mutation: '+_name)
                monkeypatch.setattr(backend, name, refuse)
        state = SimpleNamespace(app=app, qt=qt, module=module, fonts=fonts, models=models, backends=backends,
                                expected=expected, owners=owners, logical=logical, writes=writes, callbacks=callbacks)
        def check():
            assert not forbidden
            for model, before, backend in zip(models, expected, backends):
                assert freeze(model) == freeze(before)
                assert not backend.closed and backend.saved_path is None
        state.check = check
        yield state
        for owner in reversed(owners):
            if hasattr(owner, '_release_now'):
                assert owner._release_now()
            else:
                owner.close()
                assert owner._close_complete
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        for owner in owners:
            if hasattr(owner, 'widget'):
                assert not shiboken6.isValid(owner.widget)
        for owner in owners:
            parent = getattr(owner, '_test_parent', None)
            if parent is not None and shiboken6.isValid(parent):
                shiboken6.delete(parent)
        check()
    for name in names:
        sys.modules.pop(name, None)
        if saved[name] is not None:
            sys.modules[name] = saved[name]


def editor_for(state, prefix='# original\n'):
    state.models[0].features.text = prefix+TAIL
    state.expected[0].features.text = prefix+TAIL
    editor = state.module.FeaturesEditor(state.fonts[0], on_apply=lambda *args: state.callbacks.append(args))
    state.owners.append(editor)
    return editor


def test_failed_switch_when_mixed_eol_draft_then_retains_native_draft_and_selection(real_source):
    from PySide6.QtGui import QTextCursor
    state = real_source
    editor = editor_for(state, '# one\r\n# two\n')
    editor.block_control.setCurrentIndex(1)
    editor.text_control.moveCursor(QTextCursor.End)
    editor.text_control.insertPlainText('# sibling\n')
    editor.block_control.setCurrentIndex(0)
    staged = deepcopy(editor.state.staged)
    editor.text_control.moveCursor(QTextCursor.End)
    editor.text_control.insertPlainText('# mixed draft\n')
    cursor = editor.text_control.textCursor()
    cursor.setPosition(1); cursor.setPosition(5, QTextCursor.KeepAnchor)
    editor.text_control.setTextCursor(cursor)
    before = snapshot(editor.text_control)
    editor.block_control.setCurrentIndex(2)
    assert snapshot(editor.text_control) == before
    assert editor.key == 'Prefix' and editor.block_control.currentIndex == 0
    assert editor.state.staged == staged
    assert 'Mixed' in editor.diagnostic.text
    assert not state.logical and not state.writes and not state.callbacks
    state.check()


@pytest.mark.parametrize('ending', ['\n', '\r\n', '\r'])
@pytest.mark.parametrize('scalar', ['\u00a0', '\u2028', '日本 e\u0301 😀'])
def test_source_when_noop_edit_and_switch_then_exact_blocks_and_one_write(real_source, ending, scalar):
    from PySide6.QtGui import QTextCursor
    state = real_source
    prefix = '# A'+scalar+'B'+ending+'# end'+ending
    tail = TAIL
    if ending == '\r':
        prefix = '# prefix\n'
        tail = TAIL.replace('feature kern {\r\n  pos A B -25;\r\n} kern;\r\n',
                            'feature kern {\r  # A'+scalar+'B\r  pos A B -25;\r} kern;\r')
    editor = editor_for(state, prefix)
    if ending == '\r':
        state.models[0].features.text = state.expected[0].features.text = prefix+tail
        assert editor.refresh()
    assert not editor.dirty and not editor.apply()
    for row in (1, 2, 0):
        editor.block_control.setCurrentIndex(row)
    assert not editor.dirty and not editor.apply()
    assert not state.logical and not state.writes and not state.callbacks
    if ending == '\r':
        editor.block_control.setCurrentIndex(2)
        wanted = prefix+tail+'# added\r'
        assert editor.state.raw('kern') == tail[tail.index('feature kern'):]
    else:
        wanted = prefix+'# added'+ending+tail
        assert editor.state.raw('Prefix') == prefix
    editor.text_control.moveCursor(QTextCursor.End)
    assert editor.text_control.insertPlainText('# added\n')
    state.expected[0].features.text = wanted
    assert editor.apply(), editor.diagnostic.text
    assert len(state.logical) == len(state.writes) == len(state.callbacks) == 1
    assert state.callbacks[0] == (state.fonts[0], wanted)
    assert not editor.apply()
    state.check()


@pytest.mark.parametrize('command', ['Undo', 'Redo'])
def test_original_ps_when_noop_history_then_inspect_only_and_sibling_editable(real_source, command):
    from PySide6 import QtCore, QtGui
    state = real_source
    prefix = '# A\u2029B\n'
    editor = editor_for(state, prefix)
    widget = editor.text_control
    assert widget.isReadOnly() and not editor.dirty
    before = snapshot(widget)
    binding = QtGui.QKeySequence.keyBindings(getattr(QtGui.QKeySequence, command))[0][0]
    event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, binding.key(), binding.keyboardModifiers(), '')
    QtCore.QCoreApplication.sendEvent(widget, event)
    assert snapshot(widget) == before and not editor.apply()
    assert not widget.insertPlainText('X')
    editor.block_control.setCurrentIndex(1)
    assert not widget.isReadOnly()
    widget.moveCursor(QtGui.QTextCursor.End)
    assert widget.insertPlainText('# sibling\n')
    state.expected[0].features.text = prefix+TAIL.replace('} liga;\n','} liga;\n# sibling\n')
    assert editor.apply()
    assert len(state.logical) == len(state.writes) == len(state.callbacks) == 1
    state.check()


@pytest.mark.parametrize('route', ['setter', 'insert', 'mime', 'key', 'ime'])
def test_unsupported_ingress_when_selected_then_refusal_before_loss(real_source, route):
    from PySide6 import QtCore, QtGui
    state = real_source
    editor = editor_for(state)
    w = editor.text_control
    cursor = w.textCursor(); cursor.setPosition(1); cursor.setPosition(5, QtGui.QTextCursor.KeepAnchor); w.setTextCursor(cursor)
    before = snapshot(w)
    if route == 'setter':
        assert not w.setPlainText('x\u2029y')
    elif route == 'insert':
        assert not w.insertPlainText('x\u2029y')
    elif route == 'mime':
        mime = QtCore.QMimeData(w); mime.setText('x\u2029y')
        assert not w.insertFromMimeData(mime)
    elif route == 'key':
        QtCore.QCoreApplication.sendEvent(w, QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_unknown, QtCore.Qt.NoModifier, 'x\u2029y'))
    else:
        event = QtGui.QInputMethodEvent(); event.setCommitString('x\u2029y'); QtCore.QCoreApplication.sendEvent(w,event)
    assert snapshot(w) == before
    assert not editor.apply() and not editor.dirty
    assert not state.logical and not state.writes and not state.callbacks
    state.check()


@pytest.mark.parametrize('route', ['document', 'base', 'foreign'])
def test_opaque_mutation_when_apply_switch_external_then_retained_until_revert(real_source, route):
    from PySide6 import QtGui, QtWidgets
    state = real_source
    editor = editor_for(state)
    w = editor.text_control
    foreign = None
    if route == 'document':
        w.document().setPlainText('opaque\u2029draft')
    elif route == 'base':
        QtWidgets.QPlainTextEdit.setPlainText(w, 'opaque\u2029draft')
    else:
        foreign = QtGui.QTextDocument(w)
        foreign.setDocumentLayout(QtWidgets.QPlainTextDocumentLayout(foreign))
        foreign.setPlainText('opaque\u2029draft'); w.setDocument(foreign)
    before = snapshot(w)
    assert editor.dirty
    assert not editor.apply() and snapshot(w) == before
    editor.block_control.setCurrentIndex(1)
    assert editor.key == 'Prefix' and editor.block_control.currentIndex == 0
    assert snapshot(w) == before
    editor._changed()
    assert snapshot(w) == before and 'staged edits kept' in editor.diagnostic.text
    assert editor.refresh() and editor.text_control is w
    assert w.source_text() == '# original\n'
    if foreign is not None:
        import shiboken6
        assert shiboken6.isValid(foreign) and foreign.toRawText() == 'opaque\u2029draft'
    assert not state.logical and not state.writes and not state.callbacks
    state.check()


@pytest.mark.parametrize('revert', [False, True])
def test_external_change_when_draft_then_warning_and_explicit_overwrite_or_revert(real_source, revert):
    state = real_source
    editor = editor_for(state)
    assert editor.text_control.setPlainText('# draft\n')
    state.models[0].features.text = '# external\n'+TAIL
    state.expected[0].features.text = '# external\n'+TAIL
    before = snapshot(editor.text_control)
    editor._changed()
    assert snapshot(editor.text_control) == before and 'staged edits kept' in editor.diagnostic.text
    if revert:
        assert editor.refresh() and editor.text_control.source_text() == '# external\n'
        assert not editor.apply() and not state.writes
    else:
        state.expected[0].features.text = '# draft\n'+TAIL
        assert editor.apply() and len(state.writes) == 1
    state.check()


@pytest.mark.parametrize('mode', ['before', 'ignored', 'partial'])
def test_apply_when_backend_failure_then_no_callback_or_automatic_replay(real_source, monkeypatch, mode):
    state = real_source
    editor = editor_for(state)
    assert editor.text_control.setPlainText('# draft\n')
    calls = []
    def fail(text, **kwargs):
        calls.append(text)
        if mode == 'partial':
            state.models[0].features.text = '# known partial\n'
        if mode != 'ignored':
            raise OSError('owned backend refusal')
    monkeypatch.setattr(state.backends[0], 'set_features', fail)
    if mode == 'partial':
        state.expected[0].features.text = '# known partial\n'
    assert not editor.apply()
    assert calls == ['# draft\n'+TAIL] and not state.callbacks
    assert editor.text_control.source_text() == '# draft\n'
    state.check()


def test_add_remove_and_malformed_storage_when_staged_then_original_validation(real_source):
    state = real_source
    editor = editor_for(state)
    editor.tag_control.setText('calt')
    assert editor.add_feature() and editor.key == 'calt'
    assert editor.remove_feature() and not editor.dirty
    assert not editor.apply() and not state.logical
    editor.tag_control.setText('bad tag')
    assert editor.add_feature()
    assert not editor.apply() and not state.writes and not state.callbacks
    state.check()


@pytest.mark.parametrize('prior', [False, True])
def test_show_when_guarded_load_refuses_then_key_and_selector_not_committed(real_source, monkeypatch, prior):
    state = real_source
    editor = editor_for(state)
    editor.block_control.blockSignals(prior)
    monkeypatch.setattr(editor.text_control, 'load_source', lambda text: False)
    assert editor._show('liga') is False
    assert editor.key == 'Prefix' and editor.block_control.currentIndex == 0
    assert editor.block_control.signalsBlocked() is prior
    assert editor.refresh() is False
    state.check()


def test_close_when_cleanup_fails_then_live_source_is_fenced(real_source, monkeypatch):
    state = real_source
    editor = editor_for(state)
    hide = editor.widget.hide
    monkeypatch.setattr(editor.widget, 'hide', lambda: False)
    with pytest.raises(RuntimeError, match='hide'):
        editor.close()
    before = snapshot(editor.text_control)
    assert editor.closed and not editor._close_complete
    assert not editor.text_control.insertPlainText('X') and not editor.apply()
    assert snapshot(editor.text_control) == before and not state.writes
    monkeypatch.setattr(editor.widget, 'hide', hide)
    state.check()


def test_unfaithful_cr_split_when_supported_sibling_edited_then_untouched_source_not_rewritten(real_source):
    import json
    import os
    from pathlib import Path
    state=real_source
    source='# prefix\nfeature liga {\n sub A B by A;\n} liga;\nfeature kern {\r pos A B -25;\r} kern;\r'
    state.models[0].features.text=state.expected[0].features.text=source
    editor=state.module.FeaturesEditor(state.fonts[0],on_apply=lambda *args: state.callbacks.append(args))
    state.owners.append(editor)
    initial=deepcopy(editor.state.loaded)
    editor.block_control.setCurrentIndex(1)
    editor.text_control.setPlainText('feature liga {\n sub B A by A;\n} liga;\n')
    result=editor.apply()
    receipt={'source':source,'initial_get_blocks':initial,'apply':result,
             'stored':state.models[0].features.text,'logical':len(state.logical),
             'backend_writes':len(state.writes),'callbacks':len(state.callbacks),
             'diagnostic':editor.diagnostic.text}
    if os.environ.get('FEATURE_TEST_OUT'):
        (Path(os.environ['FEATURE_TEST_OUT'])/'CR-sibling-observation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    wanted = '# prefix\nfeature liga {\n sub B A by A;\n} liga;\nfeature kern {\r pos A B -25;\r} kern;\r'
    state.expected[0].features.text = wanted
    assert initial == {'prefix': '# prefix\n', 'features': [
        ('liga', 'feature liga {\n sub A B by A;\n} liga;\n'),
        ('kern', 'feature kern {\r pos A B -25;\r} kern;\r'),
    ]}
    assert result and state.models[0].features.text == wanted, receipt
    assert len(state.logical) == len(state.writes) == len(state.callbacks) == 1
    assert state.callbacks[0] == (state.fonts[0], wanted)
    assert not editor.apply()
    assert len(state.logical) == len(state.writes) == len(state.callbacks) == 1
    state.check()


def test_switch_when_reentrant_load_cannot_ack_then_old_row_and_observed_draft_retained(real_source):
    state=real_source
    editor=editor_for(state)
    widget=editor.text_control
    notices=[]
    def changed(message):
        notices.append(message)
        assert widget.insertPlainText('X')
    widget.on_diagnostic=changed
    editor.block_control.setCurrentIndex(1)
    assert editor.key=='Prefix' and editor.block_control.currentIndex==0
    assert widget.document().toRawText().startswith('Xfeature liga')
    assert widget.quarantined and notices
    assert not editor.apply() and not state.writes
    state.check()


@pytest.mark.parametrize('key',['Key_Return','Key_Enter'])
def test_safe_enter_when_actual_native_key_then_exact_source_and_one_write(real_source,key):
    from PySide6 import QtCore,QtGui
    state=real_source
    editor=editor_for(state,'# left right\n')
    widget=editor.text_control
    cursor=widget.textCursor();cursor.setPosition(6);widget.setTextCursor(cursor)
    QtCore.QCoreApplication.sendEvent(widget,QtGui.QKeyEvent(QtCore.QEvent.KeyPress,getattr(QtCore.Qt,key),QtCore.Qt.NoModifier,'\r'))
    assert widget.source_text()=='# left\n right\n'
    state.expected[0].features.text='# left\n right\n'+TAIL
    assert editor.apply() and len(state.writes)==len(state.logical)==len(state.callbacks)==1
    assert not editor.apply()
    state.check()


@pytest.mark.parametrize('action', ['apply', 'add', 'remove'])
def test_duplicates_when_inspected_then_complete_source_and_no_writes(real_source, action):
    state = real_source
    editor = editor_for(state)
    source = '# é\nfeature liga {\r sub A B by A;\r} liga;\rfeature aalt {} aalt;feature liga {???} liga;'
    state.models[0].features.text = state.expected[0].features.text = source
    assert editor.refresh()
    reason = 'Duplicate feature tags cannot be edited by occurrence; inspect only.'
    assert editor.state.loaded == {'prefix': source, 'features': []}
    assert editor.text_control.source_text() == source.replace('\r', '\n')
    assert editor.text_control.isReadOnly() and not editor.editable
    assert not editor.apply_button.isEnabled() and not editor.add_button.isEnabled()
    assert not editor.remove_button.isEnabled() and not editor.tag_control.isEnabled()
    assert editor.diagnostic.text == reason
    if action == 'add':
        editor.tag_control.setText('calt')
        assert editor.add_feature()
    elif action == 'remove':
        assert not editor.remove_feature()
    assert not editor.apply() and editor.diagnostic.text == reason
    assert not state.logical and not state.writes and not state.callbacks
    state.check()


@pytest.mark.parametrize('destination', ['unique', 'no_api', 'read_error', 'closed'])
def test_duplicate_reason_when_refreshed_then_resets_before_every_path(real_source, monkeypatch, destination):
    state = real_source
    editor = editor_for(state)
    duplicate = 'feature liga {} liga;feature liga {???} liga;'
    state.models[0].features.text = state.expected[0].features.text = duplicate
    assert editor.refresh() and not editor.editable
    if destination == 'unique':
        state.models[0].features.text = state.expected[0].features.text = '# original\n' + TAIL
        assert editor.refresh() and editor.editable and not editor.text_control.isReadOnly()
        assert editor.diagnostic.text == 'Edits are staged until Apply.'
        assert editor.text_control.setPlainText('# unique\n')
        state.expected[0].features.text = '# unique\n' + TAIL
        assert editor.apply()
        assert state.callbacks == [(state.fonts[0], '# unique\n' + TAIL)]
    elif destination == 'no_api':
        editor.font = SimpleNamespace(features=SimpleNamespace(text='read only'))
        assert editor.refresh() and not editor.editable
        assert not editor.apply() and editor.diagnostic.text == state.module.READ_ONLY
    elif destination == 'read_error':
        def fail():
            raise OSError('owned read refusal')
        monkeypatch.setattr(state.backends[0], 'get_feature_blocks', fail)
        assert not editor.refresh() and editor.diagnostic.text == 'owned read refusal'
        assert not editor.apply() and editor.diagnostic.text == state.module.READ_ONLY
    else:
        editor.close()
        assert not editor.refresh()
    assert editor._read_only_reason == state.module.READ_ONLY
    expected_calls = 1 if destination == 'unique' else 0
    assert len(state.logical) == len(state.writes) == len(state.callbacks) == expected_calls
    state.check()


@pytest.mark.parametrize('source,wanted', [
    ('feature liga {\n sub A B by A;\n} liga;', 'feature liga { sub ;'),
    ('feature liga {\r???\r} liga;', 'feature liga {\r???\u00a0日本\r} liga;'),
    ('feature liga {\r\n???\r\n} liga;', 'feature liga {\r\n???\u00a0é\r\n} liga;'),
])
def test_real_named_malformed_body_when_applied_then_stored_without_compilation(real_source, source, wanted):
    state = real_source
    editor = editor_for(state)
    state.models[0].features.text = state.expected[0].features.text = source
    assert editor.refresh()
    editor.block_control.setCurrentIndex(1)
    assert editor.text_control.setPlainText(wanted.replace('\r\n', '\n').replace('\r', '\n'))
    state.expected[0].features.text = wanted
    assert editor.apply(), editor.diagnostic.text
    assert state.models[0].features.text == wanted
    assert len(state.logical) == len(state.writes) == len(state.callbacks) == 1
    assert not editor.apply()
    state.check()


@pytest.mark.parametrize('kern', [
    'feature kern {\r pos A B -25;\n} kern;\r\n',
    'feature kern {\r pos A B -25;\r} kern;',
    'feature kern {\r\n pos A B -25;\r\n} kern;',
])
def test_supported_edit_when_sibling_mixed_or_no_eof_then_exact_untouched_slice(real_source, kern):
    state = real_source
    editor = editor_for(state)
    source = '# original\nfeature liga {\n sub A B by A;\n} liga;\n' + kern
    wanted = '# changed\nfeature liga {\n sub A B by A;\n} liga;\n' + kern
    state.models[0].features.text = state.expected[0].features.text = source
    assert editor.refresh()
    assert editor.state.loaded == {'prefix': '# original\n', 'features': [
        ('liga', 'feature liga {\n sub A B by A;\n} liga;\n'), ('kern', kern)]}
    assert editor.text_control.setPlainText('# changed\n')
    state.expected[0].features.text = wanted
    assert editor.apply()
    assert state.fonts[0].features.get_blocks()['features'][1] == ('kern', kern)
    assert state.models[0].features.text == wanted
    assert len(state.logical) == len(state.writes) == len(state.callbacks) == 1
    assert state.callbacks == [(state.fonts[0], wanted)]
    assert not editor.apply()
    state.check()
