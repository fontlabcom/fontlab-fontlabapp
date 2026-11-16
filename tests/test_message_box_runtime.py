# this_file: tests/test_message_box_runtime.py
"""Standalone owned Qt widgets; never import these bindings into FontLab."""

import os
from types import SimpleNamespace

import fontlabapp.qt.dialogs as api
import pytest

if os.environ.get("FONTLABAPP_TEST_QT5"):
    from PyQt5 import QtCore, QtWidgets, sip

    def alive(value):
        return not sip.isdeleted(value)
else:
    PySide6 = pytest.importorskip("PySide6")
    from PySide6 import QtCore, QtWidgets
    from shiboken6 import isValid as alive


if os.environ.get("FONTLABAPP_TEST_QT5"):
    MessageBox = QtWidgets.QMessageBox
else:

    class MessageBox(QtWidgets.QMessageBox):
        # Test-only bridge: native FontLab exposes Qt5 constants on instances.
        AcceptRole = QtWidgets.QMessageBox.ButtonRole.AcceptRole


@pytest.fixture
def app():
    instance = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield instance
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    instance.processEvents()


@pytest.mark.parametrize("with_accessory", [False, True])
@pytest.mark.parametrize("chosen", [0, 1])
def test_modal_custom_buttons_survive_owned_dialog_deletion(
    app, with_accessory, chosen
):
    parent = QtWidgets.QWidget()
    buttons = [QtWidgets.QPushButton("First", parent), QtWidgets.QPushButton("Second")]
    accessory = (
        QtWidgets.QLineEdit("owned accessory", parent) if with_accessory else None
    )
    box = api.create_message_box(
        SimpleNamespace(QMessageBox=MessageBox), "Choose", "Owned test", "Information"
    )
    observed = []

    def click():
        if accessory is not None:
            observed.append((accessory.width(), box.layout().geometry().width()))
        buttons[chosen].click()

    QtCore.QTimer.singleShot(100, click)
    assert api.run_button_message_box(box, buttons, accessory) == chosen
    assert buttons[0].parentWidget() is parent and buttons[1].parentWidget() is None
    if accessory is not None:
        width, grid_width = observed[0]
        assert width >= grid_width - 2, "accessory must span the full message-box grid"
        assert (
            accessory.parentWidget() is parent and accessory.text() == "owned accessory"
        )
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not alive(box) and all(alive(button) for button in buttons)
    if accessory is not None:
        assert alive(accessory)
    parent.deleteLater()
    buttons[1].deleteLater()


def test_modeless_setup_keeps_ownership_then_releases_only_closed_boxes(app):
    boxes = []
    box = QtWidgets.QMessageBox()
    api.show_message_box(box, boxes, lambda current: current.setText("owned"))
    assert boxes == [box] and box.isVisible() and not box.isModal()
    api.release_closed_message_boxes(boxes)
    assert boxes == [box]
    box.close()
    api.release_closed_message_boxes(boxes)
    assert boxes == []
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not alive(box)
