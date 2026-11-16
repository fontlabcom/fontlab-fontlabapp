# this_file: tests/test_background_clear_capture.py
"""Known native binding facts, whole-font order and no reverse mask access."""
from types import SimpleNamespace as S
from time import monotonic
import pytest
from fontlabapp.masters.background.clear.capture import read


def native_layer(identity,name,*,mask=False,service=False,auto=False,background=None,shapes=()):
    class Layer:
        id=identity
        isNull=False
        isValid=True
        isMaskLayer=mask
        isService=service
        autoLayer=auto
        isLocked=False
        def getMaskLayer(self,create):
            assert create is False
            assert not mask,'getMaskLayer(mask) reverses to foreground!'
            return background
    item=Layer()
    item.name=name
    item.shapes=list(shapes)
    return item


def native_font(layers):
    class Glyph:
        isNull=False
        isValid=True
        id=1
        fgGlyphId=101
        name='A'
        package=S(id=9)
        def updateActiveLayer(self, set):
            assert set is False
            return next((layer for layer in self.layers if not layer.isMaskLayer), None)
        @property
        def activeLayer(self):raise AssertionError('Initializing activeLayer getter is forbidden')
        @property
        def fgGlyph(self):raise AssertionError('Unsafe fgGlyph getter')
    glyph=Glyph()
    glyph.layers=layers
    for layer in layers:layer.glyph=glyph
    record=S(id=101,name='A')
    package=S(id=9,masters=['Regular','Bold'],findFgId=lambda identity:glyph if identity==101 else None)
    return package,S(glyphs=[record]),glyph


def test_complete_physical_order_roles_mask_links_and_no_property_mutation():
    mask=native_layer(11,'mask.Regular',mask=True,service=True)
    aux=native_layer(12,'Regular:50',background=None)
    body=native_layer(10,'Regular',background=mask)
    package,font,glyph=native_font([mask,aux,body])
    layers,dependencies,glyphs=read(package,font,monotonic()+2,lambda g:('stamp',))
    assert [row.identity for row in layers]==[11,12,10]
    assert [row.master for row in layers]==[False,False,True]
    assert [row.background for row in layers]==[None,None,11]
    assert glyphs==((101,1,'A',('stamp',),(11,12,10),12),)
    assert dependencies==( ('A',False,()),('A',False,()),('A',False,()) )
    assert [row.id for row in glyph.layers]==[11,12,10]


def test_missing_mask_is_none_without_creating_native_layer():
    package,font,glyph=native_font([native_layer(10,'Regular')])
    layers,*_=read(package,font,monotonic()+2,lambda g:())
    assert layers[0].background is None


def test_declared_noninterpolating_named_master_included_but_location_aux_excluded():
    package,font,glyph=native_font([native_layer(10,'Regular'),native_layer(12,'Regular:50'),native_layer(13,'#Hidden')])
    package.masters.append('#Hidden')
    layers,*_=read(package,font,monotonic()+2,lambda g:())
    assert [row.master for row in layers]==[True,False,True]


@pytest.mark.parametrize('fault',['owner','duplicate','name','invalid','master','flag'])
def test_unreadable_or_reused_domain_fails_entire_capture(fault):
    package,font,glyph=native_font([native_layer(10,'Regular')])
    if fault=='owner':glyph.package=S(id=999)
    if fault=='duplicate':glyph.layers.append(glyph.layers[0])
    if fault=='name':font.glyphs[0].name='different'
    if fault=='invalid':glyph.isValid=False
    if fault=='master':package.masters=[None]
    if fault=='flag':glyph.layers[0].isMaskLayer=lambda:False
    with pytest.raises((ValueError,TypeError)):
        read(package,font,monotonic()+2,lambda g:())


def test_dependency_records_include_automatic_and_mask_component_bases():
    shape=S(isComponent=True,shapeData=S(componentGlyph='base'))
    package,font,glyph=native_font([native_layer(10,'Regular',auto=True,shapes=(shape,))])
    _,dependencies,_=read(package,font,monotonic()+2,lambda g:())
    assert dependencies==( ('A',True,('base',)), )


def test_expired_capture_never_returns_partial_rows():
    package,font,glyph=native_font([native_layer(10,'Regular')])
    with pytest.raises(TimeoutError):read(package,font,monotonic()-1,lambda g:())
