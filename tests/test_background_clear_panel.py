# this_file: tests/test_background_clear_panel.py
"""Whole-font background controls, actual Qt actions and owned terminal paths."""
import sys
from types import SimpleNamespace as S
import pytest
from test_anchor_duplicates_panel import core, gui, APP, valid
from fontlabapp.masters.background.clear.model import Layer, Snapshot
from fontlabapp.masters.background.clear.ui import panel_type


def make(monkeypatch, masters=False):
    monkeypatch.setattr(sys,'_fontlab_samples',{},raising=False)
    rows=(Layer(1,'A&emoji😀',10,'Regular',True,False,False,False,11),
          Layer(1,'A&emoji😀',11,'mask.Regular',False,True,True,False,None))
    state=S(facts=Snapshot((1,),('Regular',),rows,()),writes=[],fail=False,partial=False)
    class Backend:
        def capture(self):
            if state.fail:raise ValueError('capture failed')
            return state.facts
        def apply(self,facts,scope,*,disclosure=None):
            state.writes.append((facts,scope))
            if state.partial:raise RuntimeError('partial removal; use Undo')
            state.facts=Snapshot((1,),('Regular',),(),())
            return {'backgrounds':1,'glyphs':1,'layers':1}
    panel=panel_type(core,gui,masters)(None,Backend())
    panel.show()
    APP.processEvents()
    return panel,state


@pytest.mark.parametrize('masters',[False,True])
def test_complete_scan_real_clear_refresh_and_literal_names(monkeypatch,masters):
    panel,state=make(monkeypatch,masters)
    try:
        assert panel.table.rowCount()==1
        assert panel.table.item(0,0).text()=='A&emoji😀'
        panel.apply_button.click()
        assert state.writes[0][1] is masters
        assert panel.table.rowCount()==0 and not panel.apply_button.isEnabled()
        assert panel.last_result['backgrounds']==1 and 'Removed 1' in panel.status.text()
        panel.refresh_button.click()
        assert panel.last_result is None
    finally:
        panel.close()
        APP.processEvents()


@pytest.mark.parametrize('fault',['capture','partial','rescan'])
def test_failures_clear_stale_action_targets(monkeypatch,fault):
    panel,state=make(monkeypatch)
    try:
        if fault=='capture':
            state.fail=True
            panel.refresh_button.click()
        elif fault=='partial':
            state.partial=True
            panel.apply_button.click()
        else:
            original=panel.backend.apply
            def apply(*args,**kwargs):
                result=original(*args)
                state.fail=True
                return result
            panel.backend.apply=apply
            panel.apply_button.click()
        assert panel.facts is None and not panel.apply_button.isEnabled()
        assert panel.last_result is None and panel.last_error
        if fault=='rescan':assert 'changes remain' in panel.last_error
    finally:
        panel.close()
        APP.processEvents()


@pytest.mark.parametrize('terminal',['close','accept','reject','done','escape','destroy'])
def test_all_terminal_paths_fence_late_actions(monkeypatch,terminal):
    panel,state=make(monkeypatch)
    if terminal=='escape':
        event=gui.QKeyEvent(core.QEvent.KeyPress,core.Qt.Key_Escape,core.Qt.NoModifier)
        panel.keyPressEvent(event)
    elif terminal=='done':panel.done(42)
    elif terminal=='destroy':
        panel.deleteLater()
        core.QCoreApplication.sendPostedEvents(None,core.QEvent.DeferredDelete)
    else:getattr(panel,terminal)()
    APP.processEvents()
    assert panel.closed and panel.backend is None
    panel.refresh()
    panel.apply()
    assert not state.writes
    assert panel.signals.records==[]


def test_no_font_and_busy_controls_never_write(monkeypatch):
    panel,state=make(monkeypatch)
    try:
        state.facts=None
        panel.refresh()
        assert not panel.apply_button.isEnabled() and panel.table.rowCount()==0
        panel.apply()
        panel.busy=True
        panel.refresh()
        assert not state.writes
    finally:
        panel.busy=False
        panel.close()
        APP.processEvents()


def test_disconnect_failure_retains_only_owned_retry_and_registry(monkeypatch):
    panel,state=make(monkeypatch)
    class Signal:
        fail=True
        def disconnect(self,slot):
            if self.fail:raise RuntimeError('owned disconnect failure')
    signal=Signal()
    panel.signals.records.insert(0,(signal,lambda:None,False))
    other=object()
    sys._fontlab_samples={'background_clear_all':panel,'foreign':other}
    assert panel.close() is False
    assert panel.closed and panel.backend is None and 'disconnect' in panel.last_error
    assert sys._fontlab_samples['background_clear_all'] is panel
    signal.fail=False
    panel.close_button.click()
    assert sys._fontlab_samples=={'foreign':other} and not panel.signals.records


@pytest.mark.parametrize('during',['capture','apply'])
def test_reentrant_close_fences_post_callback_publication(monkeypatch,during):
    panel,state=make(monkeypatch)
    original=getattr(panel.backend,during)
    def close(*args,**kwargs):
        result=original(*args,**kwargs)
        panel.close()
        return result
    setattr(panel.backend,during,close)
    getattr(panel,'refresh' if during=='capture' else 'apply')()
    assert panel.closed and panel.facts is None and panel.last_result is None
    panel.completed()
    panel.failure(RuntimeError('late'))


def test_non_escape_keys_delegate_to_native_and_foreign_registry_survives(monkeypatch):
    panel,state=make(monkeypatch)
    try:
        other=object()
        sys._fontlab_samples={'background_clear_all':other}
        event=gui.QKeyEvent(core.QEvent.KeyPress,core.Qt.Key_A,core.Qt.NoModifier)
        panel.keyPressEvent(event)
        assert not panel.closed
    finally:panel.close()
    assert sys._fontlab_samples['background_clear_all'] is other


def test_setup_failure_disconnects_controls_before_owned_delete(monkeypatch):
    import fontlabapp.masters.background.clear.ui as module
    original=module.build
    seen=[]
    def broken(owner,*args):
        original(owner,*args)
        seen.append(owner)
        raise RuntimeError('setup failed')
    monkeypatch.setattr(module,'build',broken)
    with pytest.raises(RuntimeError,match='setup failed'):
        module.panel_type(core,gui,False)(None,S(capture=lambda:None))
    assert seen[0].closed and not seen[0].signals.records
