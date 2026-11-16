# this_file: tests/test_background_clear_ordering.py
"""Original full-font paired-scope oracle and complete writer ordering failures."""
from itertools import product
from types import SimpleNamespace as S
import pytest
from fontlabapp.masters.background.clear.model import Layer, Snapshot, plan
from test_background_clear_native import setup


def test_independent_complete_original_scope_oracle_over_background_presence():
    # Derive the original nested glyph/layer loop, without importing corpus code.
    for presence in product((False,True),repeat=6):
        physical=[]
        expected={False:[],True:[]}
        for i,present in enumerate(presence):
            glyph=i//3+1
            name=f'g{glyph}'
            master=i%3!=2
            identity=100+i
            physical.append(Layer(glyph,name,identity,f'l{i}',master,False,False,False,1000+i if present else None))
            if present:
                physical.append(Layer(glyph,name,1000+i,f'mask.l{i}',False,True,True,False,None))
                expected[False].append((glyph,1000+i,(identity,)))
                if master:expected[True].append((glyph,1000+i,(identity,)))
        source=Snapshot((1,),('Regular','Bold'),tuple(physical),())
        for masters in (False,True):
            assert [(r.glyph_id,r.mask_id,r.foreground_ids) for r in plan(source,masters)]==expected[masters]


def test_all_removals_follow_source_scope_order_and_single_foreground_history(monkeypatch):
    backend,package,glyph,body,mask,aux,log,*_=setup(monkeypatch)
    from test_background_clear_capture import native_layer
    second=native_layer(13,'mask.Regular.copy',mask=True,service=True)
    second.glyph=glyph
    aux.getMaskLayer=lambda create:second if second in glyph.layers else None
    glyph.layers.insert(0,second)
    facts=backend.capture()
    result=backend.apply(facts,False)
    assert result=={'backgrounds':2,'glyphs':1,'layers':2,'pending_updates':(),'pending_note':''}
    assert log==[('history',10,0),('history',12,0),('history',1,0),('remove',11),('remove',13),('notify',(10,12,1))]
    assert tuple(glyph.layers)==(body,aux)


def test_survivor_reordering_is_never_success(monkeypatch):
    backend,package,glyph,body,mask,aux,log,*_=setup(monkeypatch)
    facts=backend.capture()
    remove=glyph.removeLayer
    def reordered(target):
        remove(target)
        glyph.layers.reverse()
    glyph.removeLayer=reordered
    from fontlabapp.masters.background.clear.native import PartialWriteError
    with pytest.raises(PartialWriteError,match='order changed'):backend.apply(facts,False)
    assert log[-1]==('notify',(10,1))


def test_native_fallback_after_removal_is_never_success(monkeypatch):
    backend,package,glyph,body,mask,aux,log,*_=setup(monkeypatch)
    facts=backend.capture()
    body.getMaskLayer=lambda create:mask
    from fontlabapp.masters.background.clear.native import PartialWriteError
    with pytest.raises(PartialWriteError,match='fallback remains'):backend.apply(facts,False)
    assert log[-1]==('notify',(10,1))


def test_expired_analysis_cannot_publish_partial_plan():
    from time import monotonic
    with pytest.raises(TimeoutError):
        plan(Snapshot((),(),(),()),False,monotonic()-1)


def test_automatic_dependency_walk_keeps_manual_chains_cycles_and_deadline():
    from time import monotonic
    from fontlabapp.masters.background.clear.model import automatic_dependants
    source=Snapshot((),(),(),(('B',False,('A',)),('C',True,('B',)),('A',False,('C',)),('unrelated',True,('other',))))
    assert automatic_dependants(source,{'A'},monotonic()+2)==['C']
    assert automatic_dependants(source,{'none'},monotonic()+2)==[]
    with pytest.raises(TimeoutError):automatic_dependants(source,{'A'},monotonic()-1)
