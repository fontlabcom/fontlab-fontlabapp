# this_file: tests/test_fontui_feature_proof.py
# SPDX-License-Identifier: Apache-2.0
"""Real source/Sequence composition, fresh publication and two-owner lifetime."""
import importlib

import pytest
import test_fontui_feature_source as _fixtures

real_source = _fixtures.real_source


def window_for(state, font_index=0):
    from PySide6 import QtWidgets
    module = importlib.import_module('fontlabapp.fontui.feature_proof')
    parent = QtWidgets.QWidget()
    owner = module.show(state.fonts[font_index], parent)
    state.owners.append(owner)
    owner._test_parent = parent
    return owner


def test_apply_when_real_linked_proof_then_one_fresh_read_layout_publication(real_source, monkeypatch):
    from PySide6.QtCore import Qt
    state = real_source
    c = window_for(state)
    assert c.editor.font is c.proof.font is state.fonts[0]
    assert c.proof.text_control.text == '' and not c.proof.run.glyphs
    c.proof.text_control.setText('/A /B /A')
    c.proof.select_key(Qt.Key_End)
    before, selected = c.proof.run, c.proof.selected_index
    publications, loads = [], []
    c.proof.on_update = lambda owner: publications.append(owner.run)
    original = c.proof._load_run
    def load():
        loads.append((c.proof.run, c.proof.outlines.copy()))
        original()
    monkeypatch.setattr(c.proof, '_load_run', load)
    assert c.editor.text_control.setPlainText('# accepted\n')
    state.expected[0].features.text = '# accepted\n'+''.join(text for tag,text in c.editor.state.loaded['features'])
    assert c.editor.apply()
    assert len(state.logical) == len(state.writes) == len(loads) == len(publications) == 1
    assert loads == [(None,{})]
    assert c.proof.run is not before and c.proof.run == before
    assert c.proof.selected_index == selected and c.proof.text_control.text == '/A /B /A'
    assert not c.editor.apply() and len(publications) == 1
    with pytest.raises(ValueError, match='captured font'):
        c._source_applied(state.fonts[1], 'foreign')
    state.check()


@pytest.mark.parametrize('mode', ['handled', 'escaped'])
def test_proof_failure_when_source_accepted_then_refresh_retries_without_write(real_source, monkeypatch, mode):
    state = real_source
    c = window_for(state)
    c.proof.text_control.setText('/A')
    target = '_load_run' if mode == 'handled' else 'refresh'
    prior = getattr(c.proof,target)
    def fail(*args):
        raise OSError('owned proof failure')
    monkeypatch.setattr(c.proof,target,fail)
    assert c.editor.text_control.setPlainText('# accepted\n')
    state.expected[0].features.text = '# accepted\n'+''.join(t for _,t in c.editor.state.loaded['features'])
    assert c.editor.apply() and len(state.writes) == 1
    if mode == 'handled':
        assert c.proof.run is None and c.proof.diagnostic.text == 'owned proof failure'
    else:
        assert 'refresh callback failed' in c.editor.diagnostic.text
    monkeypatch.setattr(c.proof,target,prior)
    c.refresh_button.click()
    assert c.proof.run is not None and len(state.writes) == 1
    state.check()


@pytest.mark.parametrize('child', ['editor','proof'])
@pytest.mark.parametrize('failure', ['no_ack', 'exception', 'interrupt'])
def test_release_when_child_refuses_then_immediate_fence_and_retry(real_source, monkeypatch, child, failure):
    state = real_source
    c = window_for(state)
    owner = getattr(c,child); close = owner.close
    error = KeyboardInterrupt('owned cleanup') if failure=='interrupt' else RuntimeError('owned cleanup')
    def fail():
        if failure != 'no_ack':
            raise error
    monkeypatch.setattr(owner,'close',fail)
    assert not c.release()
    assert c.editor.closed and c.proof.closed and c.editor.on_apply is None
    assert not c.editor.text_control.insertPlainText('X') and not c.editor.apply()
    state.app.processEvents()
    assert not c._released and c._stranded[0] is owner
    if failure != 'no_ack':
        assert c._stranded[1] is error
    monkeypatch.setattr(owner,'close',close)
    assert not c.release()
    state.app.processEvents()
    assert c._released and c.release()
    assert not state.writes
    state.check()


@pytest.mark.parametrize('signal', ['finished','destroyed','direct'])
def test_close_when_inside_proof_dispatch_then_queued_two_child_ack(real_source, signal):
    state = real_source
    c = window_for(state)
    editor,proof = c.editor,c.proof
    seen=[]
    def update(owner):
        if signal=='direct':
            assert not c.release()
        elif signal=='finished':
            c.owned.content.finished.emit(0)
        else:
            c._destroyed()
        seen.append((editor.closed,proof.closed,editor._close_complete,proof._close_complete))
    proof.on_update=update
    proof.text_control.setText('/A')
    assert seen==[(True,True,False,False)]
    assert not editor.apply() and not state.writes
    state.app.processEvents()
    assert c._released and editor._close_complete and proof._close_complete
    state.check()


def test_show_when_none_and_empty_font_then_distinct_truthful_targets(real_source):
    from PySide6.QtWidgets import QWidget
    from fontlabapp.fontui import feature_proof
    state=real_source
    parent=QWidget()
    c=feature_proof.show(None,parent);state.owners.append(c);c._test_parent=parent
    assert c.font is None and 'No font' in c.target.text
    assert not c.editor.editable and c.proof.run is None
    state.check()


@pytest.mark.parametrize('child', ['features_editor','glyph_sequence'])
@pytest.mark.parametrize('kind', ['ordinary','group','interrupt'])
def test_constructor_when_real_partial_child_cleanup_fails_then_retained_exact_owner(real_source, monkeypatch, child, kind):
    from PySide6.QtWidgets import QWidget
    from fontlabapp import fontui
    from fontlabapp.fontui import feature_proof
    state=real_source
    parent=QWidget()
    factory=getattr(fontui,child)
    partial=[]
    error=KeyboardInterrupt('original constructor') if kind=='interrupt' else ValueError('original constructor')
    def fail(*args,**kwargs):
        owner=factory(*args,**kwargs)
        partial.append((owner,owner.close))
        def refuse():
            raise RuntimeError('owned partial cleanup')
        monkeypatch.setattr(owner,'close',refuse)
        failure=error
        if kind=='group':
            inner=RuntimeError('inner owner');inner.owner=owner
            failure=ExceptionGroup('original grouped factory',[error,inner])
        else:
            failure.owner=owner
        raise failure
    monkeypatch.setattr(fontui,child,fail)
    before=list(feature_proof._HANDLES)
    with pytest.raises(BaseException) as caught:
        feature_proof.show(state.fonts[0],parent)
    added=[c for c in feature_proof._HANDLES if c not in before]
    assert len(added)==1
    c=added[0];state.owners.append(c);c._test_parent=parent
    owner,close=partial[0]
    assert owner in c._failed_owners and owner.closed and not owner._close_complete
    assert caught.value is error if kind!='group' else error in caught.value.exceptions
    assert not state.writes
    monkeypatch.setattr(owner,'close',close)
    assert c._release_now()
    state.check()


def test_controller_when_busy_or_releasing_then_no_reentry_and_retry(real_source):
    c=window_for(real_source)
    before=c.proof.run
    c._busy=1
    c._source_applied(real_source.fonts[0],'x')
    c.refresh_proof()
    assert c.proof.run is before
    assert not c._release_now()
    c._busy=0;c._releasing=True
    assert not c._release_now()
    c._releasing=False
    assert c._release_now()
    real_source.check()


def test_show_when_label_fails_then_source_and_proof_still_borrow_same_font(real_source,monkeypatch):
    from fontlabapp.fontui.model import FontListState
    def fail(font):
        raise OSError('owned label unavailable')
    monkeypatch.setattr(FontListState,'label',fail)
    c=window_for(real_source)
    assert c.target.text=='Target unavailable: owned label unavailable'
    real_source.check()
