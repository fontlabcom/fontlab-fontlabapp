# this_file: tests/test_background_clear_native.py
"""Whole native object removals, preflight and honest one-final-batch failures."""
from types import SimpleNamespace as S
from time import monotonic
import pytest
import fontlabapp.masters.background.clear.native as api
from test_background_clear_capture import native_layer, native_font


def setup(monkeypatch):
    log=[]
    mask=native_layer(11,'mask.Regular',mask=True,service=True)
    mask.payload={'note':'authored','anchors':[object()],'guides':[object()],'image':object(),'extended':object()}
    body=native_layer(10,'Regular',background=mask)
    aux=native_layer(12,'Regular.copy')
    package,font,glyph=native_font([mask,body,aux])
    package.fgId=90
    package.master='Regular'
    glyph.lastModified='before'
    def resolve(create):
        assert create is False
        return mask if mask in glyph.layers else None
    body.getMaskLayer=resolve
    def remove(target):
        log.append(('remove',target.id))
        glyph.layers.remove(target)
        target.glyph=None
    glyph.removeLayer=remove
    for obj in (mask,body,aux,glyph):
        obj.checkInitHistoryState=lambda zero,obj=obj:log.append(('history',obj.id,zero))
    queue=[]
    native=S(flGlyph=S(updatedFgGlyphs=lambda:tuple(queue)),flItems=lambda:S(notifyChangesApplied=lambda title,objects:log.append(('notify',tuple(x.id for x in objects)))))
    qt=S(QtCore=S(QDateTime=S(currentDateTimeUtc=lambda:'stamp')))
    monkeypatch.setattr(api,'_native',lambda name:native if name=='fontlab' else qt)
    monkeypatch.setattr(api,'current_package',lambda:package)
    monkeypatch.setattr(api,'_context',lambda deadline:((9,90,'Regular'),package,font))
    monkeypatch.setattr(api,'_stamp',lambda g:(g.lastModified,))
    backend=api.Backend()
    return backend,package,glyph,body,mask,aux,log,queue,native


def test_success_removes_entire_original_object_only_and_one_final_batch(monkeypatch):
    backend,package,glyph,body,mask,aux,log,queue,native=setup(monkeypatch)
    original_payload=mask.payload.copy()
    survivors=(body,aux)
    source=backend.capture()
    result=backend.apply(source,False)
    assert result=={'backgrounds':1,'glyphs':1,'layers':1,'pending_updates':(),'pending_note':''}
    assert tuple(glyph.layers)==survivors and mask.payload==original_payload
    assert log==[('history',10,0),('history',1,0),('remove',11),('notify',(10,1))]
    assert glyph.lastModified=='stamp' and package.master=='Regular' and queue==[]


def test_noop_has_no_history_notification_or_dates(monkeypatch):
    backend,package,glyph,body,mask,aux,log,*_=setup(monkeypatch)
    glyph.layers.remove(mask)
    source=backend.capture()
    assert backend.apply(source,False)=={'backgrounds':0,'glyphs':0,'layers':0,'pending_updates':(),'pending_note':''}
    assert not log and glyph.lastModified=='before'


@pytest.mark.parametrize('fault',['stale','auto','dependency','alias','missing'])
def test_all_preflight_faults_precede_history_and_removal(monkeypatch,fault):
    backend,package,glyph,body,mask,aux,log,queue,native=setup(monkeypatch)
    source=backend.capture()
    if fault=='stale':body.name='changed'
    if fault=='auto':
        body.autoLayer=True
        source=backend.capture()
    if fault=='dependency':
        source=type(source)(source.context,source.masters,source.layers,(('child',True,('A',)),),source.glyphs)
        monkeypatch.setattr(backend,'capture',lambda **kw:source)
    if fault=='alias':
        aux.getMaskLayer=lambda create:mask
        source=backend.capture()
    if fault=='missing':glyph.layers.remove(mask)
    with pytest.raises((ValueError,RuntimeError)):
        backend.apply(source,True if fault=='alias' else False)
    assert not log and glyph.lastModified=='before'


def test_native_failure_after_removal_still_finalizes_attempted_history(monkeypatch):
    backend,package,glyph,body,mask,aux,log,queue,native=setup(monkeypatch)
    source=backend.capture()
    original=glyph.removeLayer
    def fail(target):
        original(target)
        raise RuntimeError('after removal')
    glyph.removeLayer=fail
    with pytest.raises(api.PartialWriteError) as caught:backend.apply(source,False)
    assert caught.value.attempted==1 and caught.value.removed==0
    assert mask not in glyph.layers and log[-1]==('notify',(10,1))
    assert 'Undo' in str(caught.value)


def test_readback_mismatch_is_failure_not_success(monkeypatch):
    backend,package,glyph,body,mask,aux,log,queue,native=setup(monkeypatch)
    source=backend.capture()
    glyph.removeLayer=lambda target:log.append(('ineffective',target.id))
    with pytest.raises(api.PartialWriteError):backend.apply(source,False)
    assert log[-1]==('notify',(10,1)) and mask in glyph.layers


def test_history_failure_before_first_write_never_removes_or_notifies(monkeypatch):
    backend,package,glyph,body,mask,aux,log,queue,native=setup(monkeypatch)
    source=backend.capture()
    body.checkInitHistoryState=lambda zero:(_ for _ in ()).throw(RuntimeError('history failed'))
    with pytest.raises(RuntimeError,match='history failed'):backend.apply(source,False)
    assert mask in glyph.layers and not log


def test_notification_failure_is_explicit_partial_outcome(monkeypatch):
    backend,package,glyph,body,mask,aux,log,queue,native=setup(monkeypatch)
    source=backend.capture()
    native.flItems=lambda:S(notifyChangesApplied=lambda *args:(_ for _ in ()).throw(RuntimeError('notify failed')))
    with pytest.raises(api.PartialWriteError,match='notify failed'):backend.apply(source,False)
    assert mask not in glyph.layers and glyph.lastModified=='stamp'


def test_bound_capture_refuses_switched_font_and_expired_deadline(monkeypatch):
    backend,package,*_=setup(monkeypatch)
    backend.capture()
    package.id=99
    with pytest.raises(ValueError,match='original font'):backend.capture()
    with pytest.raises(TimeoutError):backend.capture(deadline=monotonic()-1)


def test_no_current_font_is_recoverable_only_before_binding(monkeypatch):
    backend,*_=setup(monkeypatch)
    monkeypatch.setattr(api,'current_package',lambda:None)
    assert backend.capture() is None
    backend._identity=(9,90)
    with pytest.raises(ValueError,match='original font'):backend.capture()


def test_worker_thread_and_mutating_capture_refuse(monkeypatch):
    backend,package,glyph,*_=setup(monkeypatch)
    monkeypatch.setattr(api,'current_thread',lambda:object())
    with pytest.raises(RuntimeError,match='UI thread'):backend.capture()
    monkeypatch.setattr(api,'current_thread',api.main_thread)
    original=api.read
    def read(*args):
        result=original(*args)
        glyph.lastModified+='x'
        return result
    monkeypatch.setattr(api,'read',read)
    with pytest.raises(ValueError,match='during capture'):backend.capture()
