# this_file: tests/test_child_dialog_priority.py
"""Actual child windows retain parent/type/modality and owned failure cleanup."""

from types import SimpleNamespace as NS

import pytest

import fontlabapp.kerning.group_proof.native as proof
from test_find_files_dialog import C, W, panel as panel
from test_spacing_worksheet import drain, valid


def assert_priority(dialog, parent, flags, modality):
    assert dialog.parent() is parent
    assert dialog.windowFlags() == flags | C.Qt.WindowStaysOnTopHint
    assert dialog.windowModality() == modality


@pytest.mark.parametrize("profile", ["text", "bytes"])
def test_find_children_keep_native_type_nonmodal_and_cancel(panel, profile):
    _, create, _, root = panel
    w = create(profile)
    baseline = W.QProgressDialog(w)
    assert_priority(w.progress, w, baseline.windowFlags(), C.Qt.NonModal)
    baseline.deleteLater()
    baseline = W.QFileDialog(w)
    baseline.setOption(W.QFileDialog.DontUseNativeDialog, True)
    baseline.setFileMode(W.QFileDialog.Directory)
    w.browse_button.click()
    assert_priority(w._browser, w, baseline.windowFlags(), C.Qt.NonModal)
    assert w._browser.isVisible()
    before = w.directory.currentText()
    w._browser.reject()
    assert w.directory.currentText() == before
    baseline.deleteLater()
    (root / "owned.txt").write_text("owned")
    w.find_button.click()
    assert w.progress.isVisible()
    w.cancel_button.click()
    assert not w.progress.isVisible() and not w._timer.isActive()


@pytest.mark.parametrize("failure", [False, True])
def test_real_diagnostic_exec_or_flag_failure_always_deletes(monkeypatch, failure):
    parent = W.QWidget()
    made, observed = [], []

    class Box(W.QMessageBox):
        def __init__(self, owner):
            super().__init__(owner)
            self.original_flags = self.windowFlags()
            made.append(self)

        def setWindowFlags(self, flags):
            if failure:
                raise RuntimeError("priority refused")
            super().setWindowFlags(flags)

        def exec(self):
            def reject():
                observed.append(
                    (
                        self.isVisible(),
                        self.isModal(),
                        self.windowFlags(),
                        self.windowModality(),
                    )
                )
                self.reject()

            C.QTimer.singleShot(0, reject)
            return super().exec()

    qt = NS(QtGui=NS(QMessageBox=Box), QtCore=C)
    monkeypatch.setattr(
        proof,
        "_native",
        lambda name: qt if name == "PythonQt" else NS(MainWindow=lambda: parent),
    )
    try:
        if failure:
            with pytest.raises(RuntimeError, match="priority refused"):
                proof.diagnose("No peers", "Owned diagnostic")
        else:
            proof.diagnose("No peers", "Owned diagnostic")
            assert observed == [
                (
                    True,
                    True,
                    made[0].original_flags | C.Qt.WindowStaysOnTopHint,
                    C.Qt.ApplicationModal,
                )
            ]
        drain()
        assert made and not valid(made[0])
    finally:
        parent.deleteLater()
        drain()


def test_find_browser_priority_failure_remains_hidden_and_retry_configures(
    panel, monkeypatch
):
    _, create, _, root = panel
    w = create("text")

    class RetryFile(W.QFileDialog):
        attempts = 0

        def setWindowFlags(self, flags):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("priority refused")
            super().setWindowFlags(flags)

    monkeypatch.setattr(w._gui, "QFileDialog", RetryFile, raising=False)
    w.browse_button.click()
    browser = w._browser
    assert browser is not None and not browser.isVisible()
    assert w.status.text() == "priority refused"
    w.browse_button.click()
    assert browser.isVisible() and browser.attempts == 2
    assert browser.windowFlags() & C.Qt.WindowStaysOnTopHint
    assert browser.windowModality() == C.Qt.NonModal
    assert browser.testOption(W.QFileDialog.DontUseNativeDialog)
    browser.selectFile(str(root))
    browser.accept()
    assert w.directory.currentText() == str(root)


def test_progress_priority_failure_deletes_partial_owner(panel):
    from fontlabapp.qt.find_files.ui import dialog_type
    from test_find_files_dialog import Gui

    owners, children = [], []

    class FailedProgress(W.QProgressDialog):
        def __init__(self, parent):
            super().__init__(parent)
            owners.append(parent)
            children.append(self)

        def setWindowFlags(self, flags):
            raise RuntimeError("priority refused")

    gui = Gui()
    gui.QProgressDialog = FailedProgress
    with pytest.raises(RuntimeError, match="priority refused"):
        dialog_type("text", NS(QtCore=C, QtGui=gui))()
    drain()
    assert not valid(owners[0]) and not valid(children[0])
