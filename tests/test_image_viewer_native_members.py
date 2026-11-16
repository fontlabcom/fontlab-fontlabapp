# this_file: tests/test_image_viewer_native_members.py
"""PythonQt rejects new instance fields that shadow inherited native members."""
from types import SimpleNamespace as NS
import pytest
from fontlabapp.qt.images.viewer.ui import panel_type
from test_image_viewer_ui import GUI, QtCore
from test_spacing_worksheet import drain, valid

@pytest.mark.parametrize('part',[2,3])
def test_complete_panel_does_not_shadow_any_inherited_native_member(part,tmp_path):
 native=GUI.QWidget if part==2 else GUI.QMainWindow
 class NativeMemberGuard(native):
  def __setattr__(self,name,value):
   if not name.startswith('_') and hasattr(native,name):
    raise AttributeError('Native member cannot be overwritten: '+name)
   native.__setattr__(self,name,value)
 gui=NS(**vars(GUI))
 setattr(gui,'QWidget' if part==2 else 'QMainWindow',NativeMemberGuard)
 panel=None
 try:
  panel=panel_type(QtCore,gui,part)(None,temporary_parent=tmp_path)
  panel.show()
  drain()
  assert panel.scroll_area.widget() is panel.image_label
 finally:
  if panel is not None and valid(panel):
   panel.close()
   drain()
