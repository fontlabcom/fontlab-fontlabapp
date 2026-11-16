# this_file: tests/test_crossfont_reports.py
"""Original ordered outputs, distinct target domains and exact suffix policy."""
import pytest
from fontlabapp.proof.crossfont.model import (
 Font,
 Glyph,
 Snapshot,
 composite_text,
 glyph_sets_text,
)

def font(i,path,names,components=()):
 return Font(i,path,'Regular',tuple(Glyph(n,tuple(components[j]) if j<len(components) else ()) for j,n in enumerate(names)))

def test_original_composite_first_other_and_source_order():
 a=font(1,'/a.vfj',['B','A','miss','small.sc','x.pcap','X.SC'],[('base','base'),(),(),(),(),()])
 b=font(2,'/b.vfj',['A','B'],[('new',),('base',)])
 c=font(3,'/c.vfj',['miss'])
 s=Snapshot(1,(a,b,c))
 assert composite_text(s)=='B;base base;base;\nA;;new;\n\nMissing in target:\n\nmiss\nX.SC\n'

def test_original_sets_all_other_target_then_reference_order_and_paths():
 a=font(1,None,['B','A','B'])
 b=font(2,'/raw/path b.vfj',['A','C','C'])
 c=font(3,None,[])
 assert glyph_sets_text(Snapshot(1,(a,b,c)))=='/raw/path b.vfj\n    Extra: C\n    Extra: C\n    Missing: B\n    Missing: B\nNone\n    Missing: B\n    Missing: A\n    Missing: B\n'

def test_current_font_need_not_be_first_and_equal_components_are_quiet():
 a=font(1,'a',['A'],[('x',)])
 b=font(2,'b',['A'],[('x',)])
 assert composite_text(Snapshot(2,(a,b)))=='\nMissing in target:\n\n\n'
 assert glyph_sets_text(Snapshot(2,(a,b)))=='a\n'

@pytest.mark.parametrize('snapshot',[Snapshot(1,()),Snapshot(3,(font(1,'a',[]),font(2,'b',[])))])
def test_unavailable_reference_or_target_is_explicit(snapshot):
 for render in (composite_text,glyph_sets_text):
  with pytest.raises(ValueError):render(snapshot)

def test_literal_names_paths_and_empty_component_names_are_not_normalized():
 a=font(1,'a',['A&\u2028\0B'],[('',)])
 b=font(2,'p\u00a0',['A&\u2028\0B'],[('x',)])
 assert composite_text(Snapshot(1,(a,b))).startswith('A&\u2028\0B;;x;\n')
 assert glyph_sets_text(Snapshot(1,(a,b)))=='p\u00a0\n'

@pytest.mark.parametrize('render',[composite_text,glyph_sets_text])
def test_expired_whole_report_deadline_never_returns_partial_text(render):
 with pytest.raises(TimeoutError):render(Snapshot(1,()),deadline=0)

def test_one_reference_font_retains_original_successful_empty_set_report():
 s=Snapshot(1,(font(1,None,['A']),))
 assert glyph_sets_text(s)==''
 with pytest.raises(ValueError):composite_text(s)
