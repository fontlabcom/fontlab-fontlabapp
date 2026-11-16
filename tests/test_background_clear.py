# this_file: tests/test_background_clear.py
"""Full original whole-font scopes and complete identity-removal planning."""
from dataclasses import FrozenInstanceError
import pytest
from fontlabapp.masters.background.clear.model import Layer, Snapshot, plan


def layer(identity, name, *, glyph='A', glyph_id=1, master=False, service=False, mask=False, auto=False, background=None):
    return Layer(glyph_id, glyph, identity, name, master, service, mask, auto, background)


def facts(*layers):
    return Snapshot((9, 90, 'Regular'), ('Regular', 'Bold'), tuple(layers), ())


def test_whole_font_all_layers_preserves_glyph_layer_order_and_removes_objects_once():
    a=layer(10,'Regular',master=True,background=13)
    b=layer(11,'Regular.copy',background=14)
    c=layer(12,'Bold',master=True)
    d=layer(13,'mask.Regular',service=True,mask=True)
    e=layer(14,'mask.Regular.copy',service=True,mask=True)
    f=layer(20,'Regular',glyph='B',glyph_id=2,master=True,background=21)
    g=layer(21,'mask',glyph='B',glyph_id=2,service=True,mask=True)
    jobs=plan(facts(a,b,c,d,e,f,g),False)
    assert [(r.glyph,r.mask_id,r.foreground_ids) for r in jobs]==[('A',13,(10,)),('A',14,(11,)),('B',21,(20,))]
    masters=plan(facts(a,b,c,d,e,f,g),True)
    assert [(r.glyph,r.mask_id) for r in masters]==[('A',13),('B',21)]


def test_shared_background_is_removed_once_only_when_all_alias_sources_in_scope():
    a=layer(10,'Regular',master=True,background=13)
    b=layer(11,'Regular.copy',background=13)
    m=layer(13,'mask.Regular',service=True,mask=True)
    jobs=plan(facts(a,b,m),False)
    assert len(jobs)==1 and jobs[0].foreground_ids==(10,11)
    with pytest.raises(ValueError,match='shared.*excluded'):
        plan(facts(a,b,m),True)


def test_two_true_masters_can_share_one_native_mask_without_duplicate_removal():
    jobs=plan(facts(layer(10,'Regular',master=True,background=13),layer(11,'Bold',master=True,background=13),layer(13,'mask',service=True,mask=True)),True)
    assert len(jobs)==1 and jobs[0].foreground_ids==(10,11)


@pytest.mark.parametrize('masters',[False,True])
def test_no_backgrounds_is_noop_and_empty_font_is_valid(masters):
    assert plan(facts(),masters)==()
    assert plan(facts(layer(10,'Regular',master=True)),masters)==()


@pytest.mark.parametrize('layers',[
    [layer(10,'Regular',master=True,background=404)],
    [layer(10,'Regular',master=True,background=11),layer(11,'copy')],
    [layer(10,'Regular',master=True,background=11),layer(11,'mask',mask=True)],
    [layer(10,'Regular',master=True,background=11),layer(11,'mask',glyph='B',glyph_id=2,service=True,mask=True)],
    [layer(10,'Regular'),layer(10,'copy')],
])
def test_dangling_cross_owner_and_unrepresentable_background_roles_refuse(layers):
    with pytest.raises(ValueError):plan(facts(*layers),False)


def test_orphan_mask_not_silently_left_or_adopted_as_foreground():
    source=facts(layer(10,'Regular',master=True),layer(11,'mask.orphan',service=True,mask=True))
    with pytest.raises(ValueError,match='unmapped'):
        plan(source,False)
    assert plan(source,True)==()


def test_mask_never_calls_reverse_background_mapping_and_snapshot_is_detached():
    source=facts(layer(10,'Regular',master=True,background=11),layer(11,'mask',service=True,mask=True))
    assert plan(source,False)[0].mask_id==11
    with pytest.raises(FrozenInstanceError):source.layers[0].name='changed'


def test_public_both_facades_own_distinct_keys_and_lazy_shared_registry(monkeypatch):
    from types import SimpleNamespace as S
    import fontlabapp
    import fontlabapp.masters.background.clear.model as api
    import fontlabapp.masters.background.clear.ui as panel
    import fontlabapp.core.scripting as scripting
    calls=[]
    monkeypatch.setattr(fontlabapp,'_native',lambda name:S(QtCore='core',QtGui='gui'))
    monkeypatch.setattr(panel,'panel_type',lambda core,gui,masters:lambda parent,backend:('owned',masters,parent))
    monkeypatch.setattr(scripting,'show_script_dialog',lambda factory,key:calls.append(key) or factory('parent'))
    assert api.show_all()==('owned',False,'parent')
    assert api.show_masters()==('owned',True,'parent')
    assert calls==['background_clear_all','background_clear_masters']
