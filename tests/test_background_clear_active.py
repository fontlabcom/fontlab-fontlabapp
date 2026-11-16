# this_file: tests/test_background_clear_active.py
"""Read-only resolver guard, never the initializing activeLayer/isActive getter."""
import pytest
from test_background_clear_native import setup


def test_active_mask_refuses_before_history_without_initializing_other_glyphs(monkeypatch):
    backend,package,glyph,body,mask,aux,log,*_=setup(monkeypatch)
    glyph.updateActiveLayer=lambda set:mask
    source=backend.capture()
    with pytest.raises(ValueError,match='active background'):backend.apply(source,False)
    assert not log and mask in glyph.layers


def test_locked_mask_refuses_even_if_resolver_hides_actual_locked_pointer(monkeypatch):
    backend,package,glyph,body,mask,aux,log,*_=setup(monkeypatch)
    mask.isLocked=True
    glyph.updateActiveLayer=lambda set:body
    source=backend.capture()
    with pytest.raises(ValueError,match='locked background'):backend.apply(source,False)
    assert not log and mask in glyph.layers


def test_null_pointer_safe_resolver_never_initializes_active_getter(monkeypatch):
    backend,package,glyph,body,mask,aux,log,*_=setup(monkeypatch)
    calls=[]
    def resolve(set):
        assert set is False
        calls.append(set)
        return body
    glyph.updateActiveLayer=resolve
    source=backend.capture()
    assert calls==[False,False]
    assert backend.apply(source,False)['backgrounds']==1
    assert calls==[False]*6


def test_changed_active_resolver_refuses_stale_table_before_history(monkeypatch):
    backend,package,glyph,body,mask,aux,log,*_=setup(monkeypatch)
    glyph.updateActiveLayer=lambda set:body
    source=backend.capture()
    glyph.updateActiveLayer=lambda set:aux
    with pytest.raises(ValueError,match='stale'):backend.apply(source,False)
    assert not log


@pytest.mark.parametrize('fault',['none','null','invalid','foreign'])
def test_unreadable_nonempty_active_resolver_never_authorizes_a_write(monkeypatch,fault):
    from types import SimpleNamespace as S
    backend,package,glyph,body,mask,aux,log,*_=setup(monkeypatch)
    if fault=='none':resolved=None
    else:resolved=S(id=10,isNull=fault=='null',isValid=fault!='invalid',glyph=S(id=999 if fault=='foreign' else 1))
    glyph.updateActiveLayer=lambda set:resolved
    with pytest.raises(ValueError,match='resolver'):backend.capture()
    assert not log
