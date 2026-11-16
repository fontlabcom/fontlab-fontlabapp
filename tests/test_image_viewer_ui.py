# this_file: tests/test_image_viewer_ui.py
"""Actual Qt image files, source-profile actions, asynchronous dialogs and teardown."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
import sys
import pytest
from fontlabapp.qt.images.viewer.ui import panel_type
from test_spacing_worksheet import GUI as BASE, QtCore, drain, valid
if 'PyQt5' in QtCore.__name__:
 from PyQt5.QtPrintSupport import QPrinter
else:
 from PySide6.QtPrintSupport import QPrinter
GUI=NS(**vars(BASE))
GUI.QPrinter=QPrinter

@pytest.fixture(params=[2,3])
def viewer(request,tmp_path):
 p=panel_type(QtCore,GUI,request.param)(None,temporary_parent=tmp_path)
 p.show()
 drain()
 yield p
 if valid(p):p.close()
 drain()

@pytest.fixture
def picture(tmp_path):
 image=GUI.QImage(1600,1200,GUI.QImage.Format_ARGB32)
 image.fill(GUI.QColor('#456789'))
 path=tmp_path/'reference 😀.png'
 assert image.save(str(path))
 return path

def test_complete_original_defaults_and_empty_actions(viewer):
 p=viewer
 assert p.image is None and p.workspace.path is None and p.scale==(1 if p.part==2 else 0)
 assert (p.width(),p.height())==((640,460) if p.part==2 else (500,400))
 assert [k for k in p.commands if p.commands[k].isEnabled()]==['open','exit','about']+(['about_qt'] if p.part==3 else [])
 assert p.commands['fit'].isCheckable()==(p.part==3)
 assert p.image_label.hasScaledContents()==(p.part==3)
 p.zoom(1.25)
 p.normal()
 assert p.image is None
 if p.part==3:assert p.commands['normal'].shortcut().toString()=='Ctrl+S'

def test_open_zoom_center_fit_normal_and_invalid_load_preservation(viewer,picture,tmp_path):
 p=viewer
 assert p.load(str(picture))
 drain()
 assert p.scale==1 and p.image.width()==1600
 original=picture.read_bytes()
 p.scroll_area.horizontalScrollBar().setValue(200)
 p.scroll_area.verticalScrollBar().setValue(150)
 p.commands['zoom_in'].trigger()
 drain()
 assert p.scale==1.25 and (p.image_label.width(),p.image_label.height())==(2000,1500)
 assert p.scroll_area.horizontalScrollBar().value()==int(1.25*200+.25*p.scroll_area.horizontalScrollBar().pageStep()/2)
 p.commands['fit'].trigger()
 drain()
 assert p.fit and p.scroll_area.widgetResizable() and not p.commands['zoom_in'].isEnabled()
 saved=p.scale
 p.commands['fit'].trigger()
 drain()
 assert not p.fit and not p.scroll_area.widgetResizable() and p.scale==(saved if p.part==2 else 1)
 p.commands['normal'].trigger()
 assert p.scale==1
 state=(p.image,p.scale,p.fit,p.image_label.pixmap().cacheKey(),[a.isEnabled() for a in p.commands.values()])
 assert not p.load(str(tmp_path/'missing.png')) and 'image' in p.last_error.lower()
 assert state==(p.image,p.scale,p.fit,p.image_label.pixmap().cacheKey(),[a.isEnabled() for a in p.commands.values()])
 assert picture.read_bytes()==original

@pytest.mark.parametrize('direction,steps,expected', [('zoom_in',5,1.25**5),('zoom_out',6,.8**6)])
def test_profile_bounds_and_normal_action_quirk(viewer,picture,direction,steps,expected):
 p=viewer
 p.load(str(picture))
 for _ in range(steps):
  if p.commands[direction].isEnabled():p.commands[direction].trigger()
 if p.part==3:
  expected=1.25**5 if direction=='zoom_in' else .8**5
  assert p.scale==pytest.approx(expected) and not p.commands[direction].isEnabled()
  p.commands['normal'].trigger()
  assert p.scale==1 and not p.commands[direction].isEnabled()
  p.commands['fit'].trigger()
  p.commands['fit'].trigger()
  assert p.commands[direction].isEnabled()
 else:assert p.scale==pytest.approx(expected) and p.commands[direction].isEnabled()

def test_async_open_cancel_and_selected_unicode_file(viewer,picture):
 p=viewer
 dialog=p.open_file()
 assert dialog.isVisible() and p.workspace.path is not None
 dialog.reject()
 assert p.image is None
 dialog=p.open_file()
 dialog.selectFile(str(picture))
 dialog.accept()
 drain()
 assert p.image is not None and p.scale==1

@pytest.mark.parametrize('terminal',['close','escape','parent-destroy'])
def test_full_owned_children_temp_lifetime_and_late_callbacks(tmp_path,terminal):
 parent=GUI.QWidget()
 p=panel_type(QtCore,GUI,3)(parent,temporary_parent=tmp_path)
 p.show()
 drain()
 p.open_file()
 p.message('About','Reference image preview')
 root=p.workspace.directory()
 dead=[]
 p.destroyed.connect(lambda *a:dead.append(True))
 slots=[r[1] for scope in [p.scope,p.closers,p.terminal] for r in scope.records]
 if terminal=='parent-destroy':
  parent.deleteLater()
  QtCore.QCoreApplication.sendPostedEvents(parent,QtCore.QEvent.DeferredDelete)
 elif terminal=='escape':
  from test_spacing_worksheet import QTest
  QTest.keyClick(p,QtCore.Qt.Key_Escape)
 else:p.close()
 drain()
 assert dead==[True] and not root.exists() and not p.scope.records and not p.closers.records
 for slot in slots:slot()
 p.failure(RuntimeError('late'))
 p.zoom(1.25)
 p.normal()
 assert p.closed
 if valid(parent):
  parent.deleteLater()
  drain()


def test_failed_disconnect_retains_panel_and_owned_close_retry(viewer, monkeypatch):
 p=viewer
 original=p.scope.finish
 monkeypatch.setattr(p.scope,'finish',lambda **kwargs:False)
 assert not p.close() and p.isVisible() and p.closing and not p.closed
 assert p.open_file() is None and p.message('late','late') is None
 monkeypatch.setattr(p.scope,'finish',original)
 p.commands['exit'].trigger()
 drain()
 assert p.closed and not valid(p)


def test_changed_workspace_refuses_close_then_retries_without_removing_foreign_data(viewer):
 p=viewer
 root=p.workspace.directory()
 renamed=root.with_name(root.name+'-owned')
 root.rename(renamed)
 root.mkdir()
 foreign=root/'untouched'
 foreign.write_text('owner')
 assert not p.close() and p.isVisible() and not p.closed and foreign.read_text()=='owner'
 foreign.unlink()
 root.rmdir()
 renamed.rename(root)
 p.commands['exit'].trigger()
 drain()
 assert p.closed and not root.exists()


def test_partial_build_failure_disposes_owned_children_and_temp(tmp_path,monkeypatch):
 import fontlabapp.qt.images.viewer.ui as module
 parents=[]
 roots=[]
 def broken(panel,*args):
  parents.append(panel)
  GUI.QLabel('partial',panel)
  roots.append(panel.workspace.directory())
  raise RuntimeError('layout failed')
 monkeypatch.setattr(module,'build',broken)
 with pytest.raises(RuntimeError,match='layout failed'):module.panel_type(QtCore,GUI,2)(None,temporary_parent=tmp_path)
 drain()
 assert not roots[0].exists() and not valid(parents[0])


def test_error_label_failure_is_contained_and_ordinary_key_forwards(viewer):
 p=viewer
 p.status=NS(setText=Mock(side_effect=RuntimeError('dead label')))
 p.failure(RuntimeError('original failure'))
 assert p.last_error=='original failure'
 from test_spacing_worksheet import QTest
 QTest.keyClick(p,QtCore.Qt.Key_A)
 assert not p.closed


def test_distinct_original_fit_callback_not_confused_with_disabled_user_action(viewer,picture):
 p=viewer
 p.load(str(picture))
 p.commands['fit'].trigger()
 assert p.fit
 p.zoom(1.25)
 assert p.scale==(1 if p.part==2 else 1.25)
 if p.part==3:
  assert p.fit and p.commands['zoom_in'].isEnabled() and not p.commands['normal'].isEnabled()


def test_distinct_original_help_and_open_modalities(viewer):
 p=viewer
 p.commands['about'].trigger()
 assert p._dialogs[-1].windowModality()==(QtCore.Qt.WindowModal if p.part==3 else QtCore.Qt.NonModal)
 if p.part==3:
  p._dialogs[-1].reject()
  p.commands['about_qt'].trigger()
  assert p._dialogs[-1].windowModality()==QtCore.Qt.WindowModal
  p._dialogs[-1].reject()
 chooser=p.open_file()
 assert chooser.windowModality()==(QtCore.Qt.WindowModal if p.part==2 else QtCore.Qt.NonModal)


def test_shortcuts_when_binding_rejects_str_then_key_sequences_are_passed(tmp_path):
 """FontLab's PythonQt QAction.setShortcut accepts only QKeySequence (native probe)."""
 class Strict(GUI.QAction):
  def setShortcut(self, shortcut):
   if isinstance(shortcut, str):raise ValueError('wrong arguments: str')
   return super().setShortcut(shortcut)
 p=panel_type(QtCore,NS(**{**vars(GUI),'QAction':Strict}),3)(None,temporary_parent=tmp_path)
 try:assert p.commands['normal'].shortcut().toString()=='Ctrl+S'
 finally:
  if valid(p):p.close()
  drain()
