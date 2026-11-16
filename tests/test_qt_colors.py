# this_file: tests/test_qt_colors.py
"""Complete injected color mechanics without loading any Qt binding."""
from types import SimpleNamespace as NS
import pytest
from fontlabapp.qt.colors import (
    ColorDialog,
    rgba255,
    rgba_css,
    group_box_style,
    color_palette,
)

@pytest.mark.parametrize('values',[(0,0,0,0),(1,1,1,1),(0.5,0.1,0.9,0.25),(-1,2,0,0.5)])
def test_rgba_when_all_channels_then_exact_original_rounding(values):
    expected=tuple(round(x*255) for x in values)
    assert rgba255(values)==expected
    assert rgba_css(values)=='rgba('+', '.join(map(str,expected))+')'

@pytest.mark.parametrize('fill',[None,'rgba(1, 2, 3, 4)'])
@pytest.mark.parametrize('border',[None,'rgba(5, 6, 7, 8)'])
@pytest.mark.parametrize('width',[None,0,0.5,2.5,-1])
@pytest.mark.parametrize('radius',[None,0,2.5])
def test_box_when_optional_rules_then_order_and_noop(fill,border,width,radius):
    rules=[]
    if fill is not None:rules.append('background-color: '+fill+';')
    if border is not None:rules.append(f'border: {round(width or 1)}px solid {border};')
    if radius is not None:rules.append(f'border-radius: {round(radius)}px;')
    assert group_box_style(None if fill is None else lambda:fill,None if border is None else lambda:border,width,radius)==('QGroupBox { '+' '.join(rules)+' }' if rules else None)

def test_palette_when_none_then_new_default_without_widget_or_role_read():
    palette=object()
    assert color_palette(NS(QPalette=lambda:palette),lambda:pytest.fail('read'),None,lambda p:pytest.fail('role')) is palette

def test_palette_when_method_or_property_then_same_mutation_and_conversion_order():
    log=[]
    p=NS(setColor=lambda role,color:log.append((role,color)))
    for attr in [p,lambda:p]:
        widget=NS(palette=attr)
        assert color_palette(NS(QPalette=object),lambda:widget,lambda:'native',lambda cls:'role') is p
    assert log==[('role','native')]*2

def test_dialog_when_open_twice_dispose_then_creation_order_and_fresh_reopen():
    log=[]
    picker=ColorDialog()
    class Dialog:
        def __init__(self,color,parent):
            self.colorSelected='signal'
            log.append(('new',color,parent))
        def open(self):log.append(('open',picker.dialog is self))
        def deleteLater(self):log.append(('delete',picker.dialog is self))
    gui=NS(QColor=lambda *v:v,QColorDialog=Dialog)
    args=(gui,lambda:(1,2,3,4),lambda:'parent',lambda:lambda signal,slot:log.append(('track',signal,slot)),lambda:'slot')
    picker.open(*args)
    first=picker.dialog
    picker.open(*args)
    assert log==[('new',(1,2,3,4),'parent'),('track','signal','slot'),('open',True)]
    picker.dispose()
    assert picker.dialog is None
    picker.dispose()
    picker.open(*args)
    assert picker.dialog is not first
    assert log[3]==('delete',True)

@pytest.mark.parametrize('point',['construct','track','open','delete'])
def test_dialog_when_failure_then_original_ownership_is_retained(point):
    picker=ColorDialog()
    def fail():raise RuntimeError(point)
    class Dialog:
        colorSelected='signal'
        def __init__(self,*args):
            if point=='construct':fail()
        def open(self):
            if point=='open':fail()
        def deleteLater(self):
            if point=='delete':fail()
    def track(*args):
        if point=='track':fail()
    args=(NS(QColor=lambda *v:v,QColorDialog=Dialog),lambda:(1,2,3,4),lambda:None,lambda:track,lambda:'slot')
    with pytest.raises(RuntimeError,match=point):
        picker.open(*args)
        picker.dispose()
    assert (picker.dialog is None)==(point=='construct')


@pytest.mark.parametrize('length',range(7))
def test_css_when_arity_overflows_then_never_consumes_past_original_fifth(length):
    seen=[]
    def channels():
        for i in range(length):
            seen.append(i)
            yield i/10
    if length==4:assert rgba_css(channels())=='rgba(0, 26, 51, 76)'
    else:
        with pytest.raises(ValueError):rgba_css(channels())
    assert seen==list(range(min(length,5)))

@pytest.mark.parametrize('failure_index',[4,5,10])
def test_css_when_extra_channel_raises_then_original_exception_wins(failure_index):
    seen=[]
    def channels():
        for i in range(20):
            seen.append(i)
            if i==failure_index:raise RuntimeError('channel')
            yield 0.5
    with pytest.raises(RuntimeError if failure_index==4 else ValueError):rgba_css(channels())
    assert seen==list(range(5))

def test_css_when_tail_is_unbounded_then_fifth_produced_value_is_last_read():
    seen=[]
    def channels():
        while True:
            seen.append(len(seen))
            if len(seen)>5:raise AssertionError('read beyond original unpack boundary')
            yield 0.5
    with pytest.raises(ValueError):rgba_css(channels())
    assert seen==[0,1,2,3,4]

@pytest.mark.parametrize('role_fails',[False,True])
@pytest.mark.parametrize('setter_fails',[False,True])
@pytest.mark.parametrize('convert_fails',[False,True])
def test_palette_when_multiple_descriptors_fail_then_original_role_setter_convert_order(role_fails,setter_fails,convert_fails):
    log=[]
    class Palette:
        @property
        def setColor(self):
            log.append('setter')
            if setter_fails:raise RuntimeError('setter')
            return lambda role,color:log.append('set')
    palette=Palette()
    def role(cls):
        log.append('role')
        if role_fails:raise ValueError('role')
        return 'role'
    def convert():
        log.append('convert')
        if convert_fails:raise LookupError('convert')
        return 'color'
    if role_fails:
        with pytest.raises(ValueError,match='role'):color_palette(NS(QPalette=Palette),lambda:NS(palette=palette),convert,role)
        assert log==['role']
    elif setter_fails:
        with pytest.raises(RuntimeError,match='setter'):color_palette(NS(QPalette=Palette),lambda:NS(palette=palette),convert,role)
        assert log==['role','setter']
    elif convert_fails:
        with pytest.raises(LookupError,match='convert'):color_palette(NS(QPalette=Palette),lambda:NS(palette=palette),convert,role)
        assert log==['role','setter','convert']
    else:
        assert color_palette(NS(QPalette=Palette),lambda:NS(palette=palette),convert,role) is palette
        assert log==['role','setter','convert','set']
