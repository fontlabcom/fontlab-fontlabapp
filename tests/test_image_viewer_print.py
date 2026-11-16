# this_file: tests/test_image_viewer_print.py
"""Owned real PDF output and exact asynchronous source print policies."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from fontlabapp.qt.images.viewer.ui import panel_type
from test_image_viewer_ui import GUI, QtCore, QPrinter
from test_spacing_worksheet import drain, valid

@pytest.fixture(params=[2,3])
def printing(request,tmp_path):
 printers=[]
 def printer():
  obj=QPrinter()
  obj.setOutputFormat(QPrinter.PdfFormat)
  obj.setOutputFileName(str(tmp_path/f'part2-{len(printers)}.pdf'))
  printers.append(obj)
  return obj
 class PrintDialog(GUI.QDialog):
  def __init__(self,*args):
   parent=args[-1]
   GUI.QDialog.__init__(self,parent)
   self._printer=args[0] if len(args)==2 else printer()
  def printer(self):return self._printer
 gui=NS(**vars(GUI))
 gui.QPrinter=NS(__call__=printer,PdfFormat=QPrinter.PdfFormat)
 class PrinterFactory:
  PdfFormat=QPrinter.PdfFormat
  def __new__(cls):return printer()
 gui.QPrinter=PrinterFactory
 gui.QPrintDialog=PrintDialog
 p=panel_type(QtCore,gui,request.param)(None,temporary_parent=tmp_path)
 p.show()
 drain()
 image=GUI.QImage(128,64,GUI.QImage.Format_RGB32)
 image.fill(GUI.QColor('#ff0000'))
 path=tmp_path/'art.png'
 assert image.save(str(path))
 p.load(str(path))
 yield p,printers,tmp_path
 if valid(p):p.close()
 drain()

def test_accept_prints_owned_real_pdf_and_reject_writes_nothing(printing):
 p,printers,tmp=printing
 dialog=p.print_image()
 target=Path(dialog.printer().outputFileName())
 assert dialog.isVisible() and not target.exists()
 dialog.reject()
 assert not target.exists()
 dialog=p.print_image()
 target=Path(dialog.printer().outputFileName())
 dialog.accept()
 drain()
 assert target.read_bytes().startswith(b'%PDF') and target.stat().st_size>100
 assert len(printers)==2 and not p.last_error

def test_part3_output_format_and_resolved_directory_rechecked_at_accept(printing):
 p,_,tmp=printing
 if p.part!=3:return
 dialog=p.print_image()
 outside=tmp/'foreign.pdf'
 dialog.printer().setOutputFileName(str(outside))
 dialog.accept()
 drain()
 assert not outside.exists() and 'inside' in p.last_error
 dialog=p.print_image()
 dialog.printer().setOutputFormat(QPrinter.NativeFormat)
 dialog.accept()
 drain()
 assert 'PDF' in p.last_error

def test_accepted_dialog_uses_current_loaded_image_and_slot_failure_is_contained(printing,monkeypatch):
 p,_,tmp=printing
 import fontlabapp.qt.images.viewer.dialogs as dialogs
 draw=Mock()
 monkeypatch.setattr(dialogs,'render',draw)
 dialog=p.print_image()
 image=GUI.QImage(21,19,GUI.QImage.Format_RGB32)
 image.fill(GUI.QColor('blue'))
 other=tmp/'other.png'
 image.save(str(other))
 p.load(str(other))
 dialog.accept()
 assert draw.call_args.args[1].width()==21
 draw.side_effect=RuntimeError('owned device failed')
 dialog=p.print_image()
 dialog.accept()
 assert p.last_error=='owned device failed'


def test_print_dialog_and_open_late_callbacks_do_not_write_after_close(printing):
 p,_,tmp=printing
 dialog=p.print_image()
 slots=[record[1] for record in p.scope.records]
 p.close()
 drain()
 for slot in slots:slot()
 assert p.closed and p.print_image() is None and p.open_file() is None and p.message('late','late') is None


def test_borrowed_printer_lease_survives_parent_death_until_dialog_destroyed(printing):
 p,printers,_=printing
 if p.part!=2:return
 dialog=p.print_image()
 device=printers[-1]
 observed=[]
 dialog.destroyed.connect(lambda *args:observed.append(device.outputFormat()))
 assert p._devices==[device] and len(p._leases)==1
 p.deleteLater()
 QtCore.QCoreApplication.sendPostedEvents(p,QtCore.QEvent.DeferredDelete)
 drain()
 assert observed==[QPrinter.PdfFormat] and not p._devices and not p._leases and p.dead
