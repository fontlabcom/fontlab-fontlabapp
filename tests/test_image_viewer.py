# this_file: tests/test_image_viewer.py
"""Independent original image geometry, owned PDF boundary and painter controls."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from fontlabapp.qt.images.viewer.model import scaled_size, scroll_value
from fontlabapp.qt.images.viewer.io import Workspace, render
from test_spacing_worksheet import GUI, QtCore

@pytest.mark.parametrize('size,scale,result', [((161,121),1.25,(201,151)),((161,121),.8,(128,96)),((1,1),.01,(0,0)),((400,300),1,(400,300))])
def test_raw_image_dimensions_truncate_without_new_zoom_clamp(size,scale,result):
 assert scaled_size(*size,scale)==result

@pytest.mark.parametrize('factor,old,page,expected', [(1.25,100,200,150),(.8,150,200,100),(1.25,0,101,12),(.8,0,101,-10)])
def test_zoom_preserves_source_center_scroll_integer_formula(factor,old,page,expected):
 assert scroll_value(factor,old,page)==expected

def test_owned_pdf_destination_and_identity_cleanup(tmp_path):
 w=Workspace(tmp_path)
 assert w.path is None
 root=w.directory()
 assert root.parent==tmp_path and w.directory()==root
 output=w.destination(str(root/'output.pdf'))
 output.write_bytes(b'owned')
 for bad in [tmp_path/'outside.pdf',root]:
  with pytest.raises(ValueError):w.destination(str(bad))
 (root/'escape').symlink_to(tmp_path,target_is_directory=True)
 with pytest.raises(ValueError):w.destination(str(root/'escape/foreign.pdf'))
 w.close()
 assert not root.exists() and w.path is None
 w.close()

def test_changed_temporary_directory_is_preserved_for_retry(tmp_path):
 w=Workspace(tmp_path)
 root=w.directory()
 moved=root.with_name(root.name+'-original')
 root.rename(moved)
 root.mkdir()
 (root/'foreign').write_text('retain')
 with pytest.raises(RuntimeError):w.close()
 assert (root/'foreign').read_text()=='retain'
 (root/'foreign').unlink()
 root.rmdir()
 moved.rename(root)
 w.close()
 assert not root.exists()

def test_missing_owned_temporary_directory_cleanup_is_noop(tmp_path):
 w=Workspace(tmp_path)
 root=w.directory()
 root.rmdir()
 w.close()
 assert w.path is None

@pytest.mark.parametrize('part',[2,3])
def test_original_print_geometry_and_unconditional_painter_end(part):
 image=GUI.QImage(400,400,GUI.QImage.Format_RGB32)
 pixmap=GUI.QPixmap.fromImage(image)
 painter=NS(isActive=lambda:True,viewport=QtCore.QRect(10,20,900,400),setViewport=Mock(),setWindow=Mock(),drawPixmap=Mock(),drawImage=Mock(),end=Mock())
 render(part,image,pixmap,object(),QtCore,NS(QPainter=lambda p:painter))
 if part==2:
  painter.drawImage.assert_called_once_with(QtCore.QPoint(0,0),image)
  painter.setViewport.assert_not_called()
 else:
  painter.setViewport.assert_called_once_with(10,20,400,400)
  painter.setWindow.assert_called_once_with(pixmap.rect())
  painter.drawPixmap.assert_called_once_with(0,0,pixmap)
 painter.end.assert_called_once_with()

def test_painter_error_ends_device_and_propagates_to_owned_slot_boundary():
 painter=NS(isActive=lambda:True,drawImage=Mock(side_effect=RuntimeError('owned print error')),end=Mock())
 with pytest.raises(RuntimeError,match='owned print error'):render(2,object(),object(),object(),QtCore,NS(QPainter=lambda p:painter))
 painter.end.assert_called_once()

def test_inactive_painter_diagnoses_failed_printer():
 painter=NS(isActive=lambda:False,end=Mock())
 with pytest.raises(RuntimeError,match='printer'):render(2,object(),object(),object(),QtCore,NS(QPainter=lambda p:painter))
 painter.end.assert_not_called()


def test_closed_workspace_cannot_create_late_files(tmp_path):
 w=Workspace(tmp_path)
 w.close()
 with pytest.raises(RuntimeError,match='closed'):w.directory()

def test_replaced_temporary_symlink_is_not_removed(tmp_path):
 w=Workspace(tmp_path)
 root=w.directory()
 moved=root.with_name(root.name+'-old')
 root.rename(moved)
 foreign=tmp_path/'foreign'
 foreign.mkdir()
 root.symlink_to(foreign,target_is_directory=True)
 with pytest.raises(RuntimeError):w.close()
 assert foreign.is_dir()
 root.unlink()
 moved.rename(root)
 w.close()

def test_generated_reference_image_retains_original_geometric_artwork():
 from fontlabapp.qt.images.viewer.io import generated_image
 image=generated_image(GUI)
 assert (image.width(),image.height())==(160,120)
 assert image.pixelColor(0,0).name()=='#f0e5c8'
 assert image.pixelColor(50,50).name()=='#407eaa'
 assert image.pixelColor(100,80).name()=='#ad6851'
