# this_file: tests/test_background_clear_finalization.py
"""An attempted removal always gets one notification despite individual date errors."""
import pytest
from test_background_clear_native import setup
from fontlabapp.masters.background.clear.native import PartialWriteError


@pytest.mark.parametrize('pre,notify,post',[(True,False,False),(False,False,True),(False,True,False),(True,True,False),(True,False,True),(False,True,True),(True,True,True)])
def test_attempted_batch_aggregates_all_errors_and_notifies_exactly_once(monkeypatch,pre,notify,post):
    backend,package,glyph,body,mask,aux,log,queue,native=setup(monkeypatch)
    source=backend.capture()
    state={'date':'before','sets':0}
    def read(g):return state['date']
    def write(g,value):
        state['sets']+=1
        log.append(('date',state['sets']))
        if (state['sets']==1 and pre) or (state['sets']==2 and post):
            raise RuntimeError('pre-date' if state['sets']==1 else 'post-date')
        state['date']=value
    monkeypatch.setattr(type(glyph),'lastModified',property(read,write),raising=False)
    def notification(*args):
        log.append(('notification',))
        if notify:raise RuntimeError('notification-error')
    from types import SimpleNamespace as S
    native.flItems=lambda:S(notifyChangesApplied=notification)
    with pytest.raises(PartialWriteError) as caught:backend.apply(source,False)
    assert caught.value.attempted==caught.value.removed==1
    assert mask not in glyph.layers and tuple(glyph.layers)==(body,aux)
    assert log.count(('notification',))==1 and state['sets']==2
    assert log[-3:]==[('date',1),('notification',),('date',2)]
    for required,enabled in [('pre-date',pre),('notification-error',notify),('post-date',post)]:
        assert (required in str(caught.value)) is enabled
    assert 'Undo' in str(caught.value)


def test_date_failure_on_first_glyph_does_not_skip_other_glyph_stamps_or_notification():
    from types import SimpleNamespace as S
    from time import monotonic
    from fontlabapp.masters.background.clear.native import Backend
    log=[]
    class Glyph:
        def __init__(self,identity):
            self.id=identity
            self.layers=[S(id=identity*10)]
            self.count=0
        def removeLayer(self,mask):self.layers.remove(mask)
        @property
        def lastModified(self):return 'before'
        @lastModified.setter
        def lastModified(self,value):
            self.count+=1
            log.append((self.id,self.count))
            if self.id==1:raise RuntimeError(f'first-glyph-date-{self.count}')
    one,two=Glyph(1),Glyph(2)
    work=[(one,one.layers[0]),(two,two.layers[0])]
    notifier=S(notifyChangesApplied=lambda *args:log.append(('notify',)))
    with pytest.raises(PartialWriteError) as caught:
        Backend._remove(work,{}, {1:one,2:two},[one,two],notifier,'stamp',monotonic()+2)
    assert log==[(1,1),(2,1),('notify',),(1,2),(2,2)]
    assert caught.value.attempted==caught.value.removed==2
    assert 'first-glyph-date-1' in str(caught.value) and 'first-glyph-date-2' in str(caught.value)


def test_expired_prewrite_checks_budget_before_any_owner_identity_or_layer_reads():
    from time import monotonic
    from types import SimpleNamespace as S
    from fontlabapp.masters.background.clear.native import Backend
    class Owner:
        @property
        def id(self):raise AssertionError('Expired preparation read an owner ID')
        @property
        def layers(self):raise AssertionError('Expired preparation traversed layers')
    owner=Owner()
    with pytest.raises(TimeoutError):
        Backend._remove([(owner,S(id=11))],{}, {1:owner},[],S(),'stamp',monotonic()-1)


def test_expected_survivors_groups_masks_in_one_checked_pass():
    from time import monotonic
    from types import SimpleNamespace as S
    from fontlabapp.masters.background.clear.native import expected_survivors
    reads=[]
    class Owner:
        def __init__(self,identity):
            self.identity=identity
            self.layers=[S(id=identity*2),S(id=identity*2+1)]
        @property
        def id(self):
            reads.append(self.identity)
            return self.identity
    owners={i:Owner(i) for i in range(1000)}
    work=[(g,g.layers[0]) for g in owners.values()]
    assert expected_survivors(work,owners,monotonic()+2)=={i:(i*2+1,) for i in owners}
    assert len(reads)==1000


def test_budget_expiry_before_first_remove_never_notifies_or_suggests_undo(monkeypatch):
    from types import SimpleNamespace as S
    from time import monotonic
    import fontlabapp.masters.background.clear.native as api
    calls=[]
    def check(deadline):
        calls.append('check')
        if len(calls)==2:raise TimeoutError('prewrite budget expired')
    monkeypatch.setattr(api,'check',check)
    glyph=S(removeLayer=lambda mask:calls.append('remove'))
    notifier=S(notifyChangesApplied=lambda *args:calls.append('notify'))
    with pytest.raises(RuntimeError,match='No background removal was attempted') as caught:
        api.Backend._remove([(glyph,S(id=11))],{}, {1:glyph},[],notifier,'stamp',monotonic()+2,{1:()})
    assert calls==['check','check'] and 'Undo' not in str(caught.value)
