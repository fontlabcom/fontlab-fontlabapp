# this_file: tests/test_image_viewer_public.py
"""Real public Fly aliases and ownership guards, without font or default-store access."""
import importlib
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
import fontlabapp
from fontlabapp.qt.images.viewer import model as image_viewer
from test_image_viewer_ui import GUI, QtCore
from test_spacing_worksheet import drain, valid


def test_public_profiles_use_existing_runtime_and_fontlab_parent(monkeypatch):
 scripts=importlib.import_module('fontlabapp.core.scripting')
 parent=GUI.QWidget()
 native=NS(MainWindow=lambda:parent)
 monkeypatch.setattr(fontlabapp,'_native',lambda name:NS(QtCore=QtCore,QtGui=GUI) if name=='PythonQt' else native)
 monkeypatch.setattr(scripts,'_native',lambda name:NS(QtCore=QtCore,QtGui=GUI) if name=='PythonQt' else native)
 monkeypatch.setattr(sys,'_fontlab_samples',{},raising=False)
 import fontlabapp.qt.images.viewer.io as io
 monkeypatch.setattr(io,'mkdtemp',lambda **kwargs:(_ for _ in ()).throw(AssertionError('No default-store writes on launch')))
 from fly.ap.image_viewer import show, show_bounded
 a,b=show(),show_bounded()
 assert a.part==2 and b.part==3 and a.parent()==parent and b.parent()==parent
 assert a.windowFlags() & QtCore.Qt.WindowStaysOnTopHint
 assert b.windowFlags() & QtCore.Qt.WindowStaysOnTopHint
 assert a.workspace.path is None and b.workspace.path is None
 a.close()
 b.close()
 drain()
 assert not sys._fontlab_samples
 parent.deleteLater()
 drain()


def test_wrong_thread_and_invalid_profile_refuse_before_native_ui(monkeypatch):
 monkeypatch.setattr(image_viewer,'current_thread',object)
 with pytest.raises(RuntimeError,match='main'):image_viewer.show()
 from fontlabapp.qt.images.viewer.ui import panel_type
 with pytest.raises(ValueError):panel_type(QtCore,GUI,9)


def test_failure_after_terminal_is_inert(tmp_path):
 from fontlabapp.qt.images.viewer.ui import panel_type
 p=panel_type(QtCore,GUI,2)(None,temporary_parent=tmp_path)
 p.close()
 drain()
 before=p.last_error
 p.failure(RuntimeError('late'))
 assert p.last_error==before and p.dispose(destroyed=True)
