# this_file: tests/test_table_items.py
"""Complete native table item construction, flags and ownership ordering."""
from types import SimpleNamespace as NS
import pytest
import fontlabapp.qt.tables.items as table_items


def fixture(fail=None):
    events=[]
    problem=ValueError('native failure')
    def event(*entry):
        events.append(entry)
        if entry[0]==fail:raise problem
    class Item:
        def __init__(self,text):event('construct',text)
        def setFlags(self,value):event('flags',value)
        def setCheckState(self,value):event('checked',value)
    flags=NS(ItemIsSelectable=1,ItemIsEnabled=2,ItemIsEditable=4,ItemIsUserCheckable=8,Checked=2,Unchecked=0)
    qt=NS(QtGui=NS(QTableWidgetItem=Item),QtCore=NS(Qt=flags))
    table=NS(setItem=lambda *args:event('place',*args))
    return events,qt,table,problem


@pytest.mark.parametrize('editable',[False,True])
@pytest.mark.parametrize('value',[None,'',0,False,'literal @ / \u00a0\u2028\u2029\0','𐀀'])
def test_plain_when_any_literal_then_exact_flags_and_native_handoff(editable,value):
    events,qt,table,_=fixture()
    table_items.place_text(qt,lambda:table,-1,999,value,editable)
    assert events[0]==('construct','' if value is None else str(value))
    assert events[1]==('flags',7 if editable else 3)
    assert events[2][:3]==('place',-1,999)


@pytest.mark.parametrize('checkbox',[False,True])
@pytest.mark.parametrize('editable',[False,True])
@pytest.mark.parametrize('value',[None,'',False,True,0,1,'𐀀'])
def test_row_when_plain_or_checkbox_then_complete_order_and_flags(checkbox,editable,value):
    events,qt,table,_=fixture()
    column=NS(cell_title='caption',checkbox=checkbox,editable=editable,key='field')
    def flags(e):
        events.append(('flags-policy',e))
        return table_items.item_flags(qt.QtCore.Qt,e)
    table_items.fill_row(qt.QtGui,4,{'field':value},[column],lambda:flags,lambda:qt.QtCore.Qt,lambda:table)
    assert events[0]==('construct','caption' if checkbox else '' if value is None else str(value))
    assert events[1]==('flags-policy',editable and not checkbox)
    if checkbox:assert events[2]==('checked',2 if value else 0)
    assert events[-2]==('flags',(3|(8 if editable else 0)) if checkbox else (7 if editable else 3))
    assert events[-1][:3]==('place',4,0)


@pytest.mark.parametrize('failure',['construct','flags','place'])
def test_plain_when_native_step_fails_then_same_exception_without_later_steps(failure):
    events,qt,table,problem=fixture(failure)
    with pytest.raises(ValueError) as caught:table_items.place_text(qt,lambda:table,0,0,'x',True)
    assert caught.value is problem
    assert events[-1][0]==failure


@pytest.mark.parametrize('failure',['construct','checked','flags','place'])
def test_checkbox_when_native_step_fails_then_same_exception_without_later_steps(failure):
    events,qt,table,problem=fixture(failure)
    c=NS(cell_title='yes',checkbox=True,editable=True,key='v')
    with pytest.raises(ValueError) as caught:
        table_items.fill_row(qt.QtGui,0,{'v':True},[c],lambda:lambda e:table_items.item_flags(qt.QtCore.Qt,e),lambda:qt.QtCore.Qt,lambda:table)
    assert caught.value is problem
    assert events[-1][0]==failure


def test_empty_columns_when_filled_then_no_native_property_or_table_lookup():
    def forbidden():raise AssertionError('late lookup was eager')
    table_items.fill_row(NS(),-10,{},[],forbidden,forbidden,forbidden)


def test_rows_when_values_trigger_state_change_then_table_lookup_stays_late():
    events,qt,table,_=fixture()
    other=NS(setItem=lambda *args:events.append(('new-table',*args)))
    current=[table]
    class Value:
        def __str__(self):
            current[0]=other
            return 'changed'
    table_items.place_text(qt,lambda:current[0],1,2,Value(),False)
    assert events[-1][0]=='new-table'


def test_mixed_repeated_columns_when_filled_then_original_order_and_every_occurrence():
    events,qt,table,_=fixture()
    a=NS(cell_title='a',checkbox=False,editable=True,key='a')
    b=NS(cell_title='b',checkbox=True,editable=False,key='b')
    table_items.fill_row(qt.QtGui,3,{'a':'first','b':True},[a,b,a],lambda:lambda e:table_items.item_flags(qt.QtCore.Qt,e),lambda:qt.QtCore.Qt,lambda:table)
    assert [e[2] for e in events if e[0]=='place']==[0,1,2]
    assert [e for e in events if e[0]=='construct']==[('construct','first'),('construct','b'),('construct','first')]
