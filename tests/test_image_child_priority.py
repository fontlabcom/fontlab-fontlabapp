# this_file: tests/test_image_child_priority.py
"""Image child priority preserves each profile and printer lifetime."""

import pytest
from test_child_dialog_priority import assert_priority
from test_find_files_dialog import C, W
from test_image_viewer_ui import viewer as viewer
from test_image_viewer_print import printing as printing
from test_spacing_worksheet import drain, valid

if "PyQt5" in C.__name__:
    from PyQt5.QtPrintSupport import QPrintDialog
else:
    from PySide6.QtPrintSupport import QPrintDialog


def test_image_children_keep_opposite_profile_modalities_and_cancel(viewer):
    p = viewer
    baseline = W.QFileDialog(p)
    baseline.setOption(W.QFileDialog.DontUseNativeDialog, True)
    baseline.setFileMode(W.QFileDialog.ExistingFile)
    dialog = p.open_file()
    modality = C.Qt.WindowModal if p.part == 2 else C.Qt.NonModal
    assert_priority(dialog, p, baseline.windowFlags(), modality)
    assert dialog.isVisible()
    dialog.reject()
    assert p.image is None
    baseline.deleteLater()
    baseline = W.QMessageBox(p)
    baseline.setWindowTitle("About")
    baseline.setText("Owned help")
    modality = C.Qt.WindowModal if p.part == 3 else C.Qt.NonModal
    baseline.setWindowModality(modality)
    baseline.open() if p.part == 3 else baseline.show()
    box = p.message("About", "Owned help")
    assert_priority(box, p, baseline.windowFlags(), modality)
    assert box.isVisible()
    box.reject()
    baseline.deleteLater()


def test_real_print_dialog_keeps_parent_modal_flags_and_lease(printing, monkeypatch):
    p, _, _ = printing

    class PrintDialog(QPrintDialog):
        def setVisible(self, visible):
            # Offscreen checks must not open the macOS system print panel.
            W.QDialog.setVisible(self, visible)

        def open(self):
            # PySide hides the inherited zero-argument QDialog overload.
            W.QDialog.open(self)

    monkeypatch.setattr(p._gui, "QPrintDialog", PrintDialog)
    baseline = QPrintDialog(p)
    dialog = p.print_image()
    assert_priority(dialog, p, baseline.windowFlags(), C.Qt.WindowModal)
    assert dialog.isVisible()
    if p.part == 2:
        assert dialog.printer() in p._devices and len(p._leases) == 1
    dialog.reject()
    baseline.deleteLater()
    p.close()
    drain()
    assert not p._devices and not p._leases


def test_image_priority_failure_retains_unshown_child_for_cleanup(viewer, monkeypatch):
    p = viewer

    class FailedFile(W.QFileDialog):
        def setWindowFlags(self, flags):
            raise RuntimeError("priority refused")

    monkeypatch.setattr(p._gui, "QFileDialog", FailedFile)
    with pytest.raises(RuntimeError, match="priority refused"):
        p.open_file()
    assert len(p._dialogs) == 1 and not p._dialogs[0].isVisible()
    child = p._dialogs[0]
    p.close()
    drain()
    assert not valid(child)


def test_print_priority_failure_keeps_borrowed_device_until_child_cleanup(
    printing, monkeypatch
):
    p, _, _ = printing

    class FailedPrint(p._gui.QPrintDialog):
        def setWindowFlags(self, flags):
            raise RuntimeError("priority refused")

    monkeypatch.setattr(p._gui, "QPrintDialog", FailedPrint)
    with pytest.raises(RuntimeError, match="priority refused"):
        p.print_image()
    child = p._dialogs[-1]
    assert not child.isVisible()
    if p.part == 2:
        assert child.printer() in p._devices and len(p._leases) == 1
    p.close()
    drain()
    assert not valid(child) and not p._devices and not p._leases
