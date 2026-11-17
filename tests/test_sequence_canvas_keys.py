# this_file: tests/test_sequence_canvas_keys.py
"""Complete sequence-canvas behavior over owned Qt-shaped values, not FontLab."""
import importlib
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from _light_canvas import light_canvas
from fontlabapp.fontui.model import Outline
from test_fontui_browser_keys import Widget


@pytest.fixture
def canvas_module(monkeypatch):
    monkeypatch.delitem(sys.modules,'fontlabapp.fontui.sequence_canvas',raising=False)
    class Base(Widget):
        def keyPressEvent(self,event):
            self.signals.setdefault('base_keys',[]).append(event)
    gui=NS(QWidget=Base)
    for name in ['QPainter','QColor','QPen','QBrush','QPainterPath']:
        setattr(gui,name,Mock())
    core=NS(Qt=NS(StrongFocus=1,WindingFill=2,NoBrush=0),QRectF=lambda x,y,w,h:NS(left=lambda:x))
    monkeypatch.setitem(sys.modules,'PythonQt',NS(QtGui=gui,QtCore=core))
    module=importlib.import_module('fontlabapp.fontui.sequence_canvas')
    light_canvas(monkeypatch,module)
    yield module,gui
    sys.modules.pop('fontlabapp.fontui.sequence_canvas',None)


@pytest.fixture
def owner():
    class Font(dict):
        info=NS(unitsPerEm=1000,ascender=800,descender=-200)
    glyphs=[NS(index=0,name='A',label='A',x=0,advance=500),NS(index=1,name=None,label='?',x=500,advance=100)]
    recording=(('moveTo',((0,0),)),('lineTo',((400,600),)),('closePath',()),('moveTo',((30,20),)),('lineTo',((100,30),)),('endPath',()))
    scroll=Mock()
    scroll.viewport.return_value=NS(width=100)
    return NS(font=Font(A=object()),size_control=NS(value=100),wrap_control=NS(checked=False),scroll=scroll,run=NS(glyphs=glyphs,direction='ltr'),outlines={'A':Outline(recording,(0,0,400,600),500,())},canvas=Mock(rect='owned rect'),closed=False,selected_index=0,fail=Mock(),select_key=Mock(return_value=True),select_at=Mock())


@pytest.mark.parametrize('handled',[True,False])
def test_canvas_when_key_or_mouse_received_then_original_selection_and_shared_routing(canvas_module,owner,handled,monkeypatch):
    module,_=canvas_module
    owner.select_key.return_value=handled
    canvas=module.create_canvas(owner,None)
    assert canvas.keyPressEvent.__func__.__module__ == 'fontlabapp.qt.events.key'
    event=NS(key=lambda:37,accept=Mock())
    canvas.keyPressEvent(event)
    owner.select_key.assert_called_once_with(37)
    if handled:
        event.accept.assert_called_once_with()
        assert 'base_keys' not in canvas.signals
    else:
        assert canvas.signals['base_keys']==[event]
        event.accept.assert_not_called()
    mouse=NS(pos=lambda:NS(x=lambda:12,y=lambda:34),accept=Mock())
    canvas.mousePressEvent(mouse)
    owner.select_at.assert_called_once_with(12,34)
    mouse.accept.assert_called_once_with()
    paint=Mock()
    monkeypatch.setattr(module,'paint',paint)
    canvas.paintEvent(object())
    paint.assert_called_once_with(owner,canvas)


@pytest.mark.parametrize('wrapped,defaults',[(False,False),(True,True)])
def test_prepare_when_font_and_run_valid_then_layout_bounds_and_reveal(canvas_module,owner,wrapped,defaults):
    module,_=canvas_module
    owner.wrap_control.checked=wrapped
    if defaults:
        owner.font.info=NS(unitsPerEm=None,ascender=None,descender=None)
    module.prepare(owner)
    assert owner.scale==0.1
    assert owner.wrap_width==(100 if wrapped else None)
    w,h=owner.canvas.resize.call_args.args
    assert w>=400 and h>=220
    assert module.place(owner,owner.run.glyphs[0])==(20,100)
    module.reveal(owner,owner.run.glyphs[0])
    owner.scroll.ensureVisible.assert_called_once_with(45,100,20,20)
    owner.run.glyphs=[]
    module.prepare(owner)
    owner.canvas.resize.assert_called_with(400,220)


@pytest.mark.parametrize('upm',[0,-1,float('nan'),float('inf')])
def test_prepare_when_upm_invalid_then_no_canvas_resize(canvas_module,owner,upm):
    module,_=canvas_module
    owner.font.info=NS(unitsPerEm=upm)
    with pytest.raises(ValueError,match='positive and finite'):
        module.prepare(owner)
    owner.canvas.resize.assert_not_called()


def test_paint_when_open_closed_and_missing_occurrences_then_balanced_painter(canvas_module,owner):
    module,gui=canvas_module
    module.prepare(owner)
    module.paint(owner,owner.canvas)
    painter=gui.QPainter.return_value
    assert painter.drawPath.call_count==2
    painter.drawRect.assert_called_once()
    painter.drawText.assert_called_once()
    painter.save.assert_called_once()
    painter.restore.assert_called_once()
    painter.end.assert_called_once()
    owner.fail.assert_not_called()


@pytest.mark.parametrize('closed,run',[(True,True),(False,False)])
def test_paint_when_inactive_then_no_glyph_draw_and_painter_ended(canvas_module,owner,closed,run):
    module,gui=canvas_module
    owner.closed=closed
    if not run:owner.run=None
    module.paint(owner,owner.canvas)
    gui.QPainter.return_value.drawPath.assert_not_called()
    gui.QPainter.return_value.end.assert_called_once()


def test_paint_when_source_or_replay_fails_then_failure_route_and_cleanup(canvas_module,owner,monkeypatch):
    module,gui=canvas_module
    module.prepare(owner)
    del owner.font['A']
    module.paint(owner,owner.canvas)
    assert 'Missing glyph: A' in str(owner.fail.call_args.args[0])
    gui.QPainter.return_value.end.assert_called_once()
    owner.font['A']=object()
    owner.fail.reset_mock()
    gui.QPainter.return_value.restore.reset_mock()
    monkeypatch.setattr(module,'replayRecording',Mock(side_effect=RuntimeError('owned replay failure')))
    module.paint(owner,owner.canvas)
    assert 'owned replay failure' in str(owner.fail.call_args.args[0])
    gui.QPainter.return_value.restore.assert_called_once()
    assert gui.QPainter.return_value.end.call_count==2
