# this_file: tests/test_crossfont_reports_ui.py
"""Real owned Qt reports, literal MIME, distinct profiles and every terminal."""
import sys
from types import SimpleNamespace as NS
import pytest
import fontlabapp.proof.crossfont.ui as ui
from fontlabapp.proof.crossfont.model import Font, Glyph, Snapshot
from fontlabapp.proof.text_holder.editor import literal_text
from test_spacing_worksheet import GUI, QtCore, drain, valid

@pytest.fixture
def report(monkeypatch):
 snapshot=Snapshot(1,(Font(1,None,'Regular',(Glyph('A&\u00a0\u2028\u2029😀',('one',)),)),Font(2,'/other/font.vfj','Bold',(Glyph('extra'),))))
 monkeypatch.setattr(ui.native,'capture',lambda **kw:snapshot)
 import fontlabapp.core.scripting as scripting
 monkeypatch.setattr(scripting,'_native',lambda n:NS(QtCore=QtCore,QtGui=GUI))
 import fontlabapp
 monkeypatch.setattr(fontlabapp,'_native',lambda n:NS(QtCore=QtCore,QtGui=GUI))
 monkeypatch.setattr(sys,'_fontlab_samples',{},raising=False)
 return snapshot

@pytest.mark.parametrize('composites',[False,True])
@pytest.mark.parametrize('terminal',['close','reject','accept','done','parent'])
def test_all_original_report_text_and_terminal_callbacks(report,composites,terminal):
 parent=GUI.QWidget()
 p=ui.dialog_type(composites,NS(QtCore=QtCore,QtGui=GUI))(parent)
 p.show()
 dead=[]
 p.destroyed.connect(lambda *a:dead.append(True))
 sys._fontlab_samples[p.KEY]=p
 expected=(ui.model.composite_text if composites else ui.model.glyph_sets_text)(report)
 assert literal_text(p.output)==expected and p.output.isReadOnly() and not p.isModal()
 p.output.selectAll()
 mime=p.output.createMimeDataFromSelection()
 assert mime.text()==expected
 event=GUI.QInputMethodEvent()
 event.setCommitString('forbidden')
 p.output.inputMethodEvent(event)
 assert literal_text(p.output)==expected
 if terminal=='parent':parent.deleteLater()
 elif terminal=='done':p.done(42)
 else:getattr(p,terminal)()
 drain()
 assert dead==[True] and not sys._fontlab_samples
 p.refresh()
 p.reject()
 assert p._closed
 if valid(parent):
  parent.deleteLater()
  drain()

def test_refresh_failure_clears_stale_text_and_retry_is_complete(report,monkeypatch):
 p=ui.dialog_type(False,NS(QtCore=QtCore,QtGui=GUI))()
 p.show()
 monkeypatch.setattr(ui.native,'capture',lambda **kw:(_ for _ in ()).throw(ValueError('changed')))
 p.refresh_button.click()
 assert literal_text(p.output)=='' and p.status.text()=='changed'
 monkeypatch.setattr(ui.native,'capture',lambda **kw:report)
 p.refresh_button.click()
 assert literal_text(p.output)==ui.model.glyph_sets_text(report)
 p.close()
 drain()

def test_public_lazy_show_passes_exact_profile(monkeypatch):
 calls=[]
 monkeypatch.setattr(ui,'open_report',lambda **kw:calls.append(kw) or 42)
 assert ui.model.show()==42
 assert ui.model.show(composites=True)==42
 assert calls==[{'composites':False},{'composites':True}]

@pytest.mark.parametrize('parent_dies',[False,True])
def test_failed_close_after_stop_retains_live_retry_or_parent_tombstone(report,monkeypatch,parent_dies):
 from fontlabapp.core.completion import stop
 parent=GUI.QWidget()
 p=ui.dialog_type(False,NS(QtCore=QtCore,QtGui=GUI))(parent)
 p.show()
 dead=[]
 p.destroyed.connect(lambda *a:dead.append(True))
 original=ui.close_script_dialog
 def fail(dialog,event,key):
  stop(dialog)
  raise ValueError('close failed')
 monkeypatch.setattr(ui,'close_script_dialog',fail)
 with pytest.raises(ValueError):p.closeEvent(GUI.QCloseEvent())
 assert not p._closed
 p.refresh()
 assert literal_text(p.output)
 if parent_dies:parent.deleteLater()
 else:
  monkeypatch.setattr(ui,'close_script_dialog',original)
  p.close()
 drain()
 assert dead==[True]
 p.refresh()
 p.reject()
 if valid(parent):
  parent.deleteLater()
  drain()

def test_constructor_failure_stops_owned_completion(report,monkeypatch):
 owners=[]
 original=ui.install
 def install(dialog,key):
  owner=original(dialog,key)
  owners.append(owner)
  return owner
 monkeypatch.setattr(ui,'install',install)
 class Broken(GUI.QPlainTextEdit):
  def __init__(self,parent):raise RuntimeError('allocation')
 monkeypatch.setattr(ui,'editor_type',lambda qt:Broken)
 with pytest.raises(RuntimeError,match='allocation'):ui.dialog_type(False,NS(QtCore=QtCore,QtGui=GUI))()
 assert owners[0].closed and not owners[0].hooks
 drain()

def test_refresh_after_capture_reentrant_retire_does_not_publish(report,monkeypatch):
 p=ui.dialog_type(False,NS(QtCore=QtCore,QtGui=GUI))()
 p.show()
 old=literal_text(p.output)
 def capture(**kw):
  p._closed=True
  return report
 monkeypatch.setattr(ui.native,'capture',capture)
 p.refresh()
 assert literal_text(p.output)==old
 p._closed=False
 p.close()
 drain()
