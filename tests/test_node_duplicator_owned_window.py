# this_file: tests/test_node_duplicator_owned_window.py
"""The actual result dialog uses shared parenting/priority/close lifecycle in Qt."""

import sys
from types import SimpleNamespace as NS

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6 import QtCore
from shiboken6 import isValid
import fontlabapp.contours.nodes.duplicator.ui as ui
import fontlabapp.core.scripting as scripting


def test_result_when_queue_disclosed_then_owned_parent_priority_close_and_reopen(
    monkeypatch,
):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    owner = QtWidgets.QMainWindow()
    modules = {
        "fontlab": NS(MainWindow=lambda: owner),
        "PythonQt": NS(QtCore=QtCore, QtGui=QtWidgets),
    }
    monkeypatch.setattr(ui, "_native", modules.__getitem__)
    monkeypatch.setattr(scripting, "_native", modules.__getitem__)
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    outcome = {
        "inserted": 1,
        "skipped": (),
        "no_selection_message": False,
        "pending_updates": (919, 920),
        "pending_note": "FontLab issue 8537: dates may change.",
    }
    first = ui.show_result(outcome)
    assert first.parent() is owner and not first.isModal()
    assert first.windowFlags() & QtCore.Qt.WindowStaysOnTopHint
    text = first.findChild(QtWidgets.QLabel).text()
    assert "919, 920" in text and "8537" in text
    assert first.findChild(QtWidgets.QLabel).wordWrap()
    first.findChild(QtWidgets.QPushButton).click()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(first) and sys._fontlab_samples == {}
    second = ui.show_result(outcome)
    assert second.parent() is owner and second is not first
    second.reject()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(second) and sys._fontlab_samples == {}
    assert isValid(owner), "Closing the owned result must preserve its parent window"
    owner.close()
    assert app is not None
