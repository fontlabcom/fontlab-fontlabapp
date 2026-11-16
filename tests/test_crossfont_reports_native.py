# this_file: tests/test_crossfont_reports_native.py
"""Actual capture adapter contracts; forbidden getters/history/activation tripwires."""
from types import SimpleNamespace as NS
from time import monotonic
import pytest
import fontlabapp.proof.crossfont.native as api

class Font:
 def __init__(self,i,names,path=''):
  self.id=i
  self.glyphs=[NS(name=n) for n in names]
  self.path=path
 @property
 def fgPackage(self):raise AssertionError('Unregistered font promotion forbidden')

class Glyph:
 isNull=False
 def __init__(self,bases):self.bases=bases
 @property
 def fgGlyph(self):raise AssertionError('Note/lib cache getter forbidden')
 @property
 def activeLayer(self):raise AssertionError('Initializing active getter forbidden')
 def findLayer(self,master):
  assert master=='Regular'
  return NS(isNull=False,shapes=[NS(isComponent=False),*[NS(isComponent=True,shapeData=NS(componentGlyph=b)) for b in self.bases]])

class Package:
 isNull=False
 master='Regular'
 masters=('Regular',)
 def __init__(self,i,glyphs):
  self.fgId=i
  self.glyphs=glyphs
 def findName(self,n):return self.glyphs[n]

def setup(monkeypatch):
 fonts=[Font(2,['B','C'],'b.vfj'),Font(1,['A','B'],'a.vfj'),Font(3,['Z'],'z.vfj')]
 packages={1:Package(1,{'A':Glyph(('base',)),'B':Glyph(())}),2:Package(2,{'B':Glyph(('other',)),'C':Glyph(())})}
 native=NS(CurrentFont=lambda:fonts[1],AllFonts=lambda:fonts,flWorkspace=NS(instance=lambda:NS(packages=lambda:packages.values())),flPackage=lambda x:x)
 monkeypatch.setattr(api,'_native',lambda n:native)
 monkeypatch.setattr(api,'require_main_thread',lambda:None)
 return fonts,packages,native

def test_full_original_domains_and_first_other_only(monkeypatch):
 fonts,p,n=setup(monkeypatch)
 s=api.capture(composites=True)
 assert s.current==1
 assert [f.identity for f in s.fonts]==[2,1,3]
 assert s.fonts[2].glyphs==()
 assert s.fonts[1].glyphs[0].components==('base',)

def test_glyph_set_does_not_read_master_or_shapes(monkeypatch):
 fonts,p,n=setup(monkeypatch)
 n.flWorkspace.instance=lambda:(_ for _ in ()).throw(AssertionError('No workspace/master requirement for original names scan'))
 s=api.capture()
 assert [tuple(g.name for g in f.glyphs) for f in s.fonts]==[('B','C'),('A','B'),('Z',)]

@pytest.mark.parametrize('fault',['no-current','one-font','unregistered','unknown-master','missing-glyph','missing-layer','duplicate-id','duplicate-package'])
def test_complete_source_errors_are_explicit_without_writes(monkeypatch,fault):
 fonts,p,n=setup(monkeypatch)
 if fault=='no-current':n.CurrentFont=lambda:None
 elif fault=='one-font':n.AllFonts=lambda:fonts[1:2]
 elif fault=='unregistered':p.pop(2)
 elif fault=='unknown-master':p[2].master='unknown'
 elif fault=='missing-glyph':p[2].findName=lambda name:None
 elif fault=='missing-layer':p[2].glyphs['B'].findLayer=lambda master:None
 elif fault=='duplicate-id':fonts[0].id=1
 elif fault=='duplicate-package':n.flWorkspace.instance=lambda:NS(packages=lambda:[p[1],p[1],p[2]])
 with pytest.raises(ValueError):api.capture(composites=True)

def test_second_pass_drift_and_expired_deadline(monkeypatch):
 fonts,p,n=setup(monkeypatch)
 count=[0]
 def opened():
  count[0]+=1
  if count[0]==2:fonts[0].glyphs.append(NS(name='late'))
  return fonts
 n.AllFonts=opened
 with pytest.raises(ValueError,match='changed'):api.capture()
 with pytest.raises(TimeoutError):api.capture(deadline=monotonic()-1)

@pytest.mark.parametrize('deadline',[float('nan'),float('inf'),True,'bad'])
def test_invalid_absolute_deadline_prevents_native_reads(monkeypatch,deadline):
 setup(monkeypatch)
 monkeypatch.setattr(api,'_read',lambda *args:(_ for _ in ()).throw(AssertionError('Invalid deadline must refuse before source reads')))
 with pytest.raises(ValueError):api.capture(deadline=deadline)

def test_original_one_font_glyph_set_scan_is_successful_without_master_reads(monkeypatch):
 fonts,p,n=setup(monkeypatch)
 n.AllFonts=lambda:fonts[1:2]
 s=api.capture()
 assert len(s.fonts)==1 and [g.name for g in s.fonts[0].glyphs]==['A','B']
