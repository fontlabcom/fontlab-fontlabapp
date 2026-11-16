# this_file: tests/legacy_panel_qt.py
"""Real Qt adapters for the measured PythonQt property and Qt5 method spellings."""

from module_paths import module_name as _module_name
import importlib
import os
import sys
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class Widget(QtWidgets.QWidget):
    palette = property(QtWidgets.QWidget.palette)
    font = property(QtWidgets.QWidget.font)
    width = property(QtWidgets.QWidget.width)
    height = property(QtWidgets.QWidget.height)
    rect = property(QtWidgets.QWidget.rect)


class Dialog(QtWidgets.QDialog):
    palette = property(QtWidgets.QDialog.palette)

    def __setattr__(self, name, value):
        assert QtWidgets.QDialog.staticMetaObject.indexOfProperty(name) < 0, name
        assert not callable(getattr(QtWidgets.QDialog, name, None)), name
        super().__setattr__(name, value)


class Label(QtWidgets.QLabel):
    font = property(QtWidgets.QLabel.font)


class Spin(QtWidgets.QDoubleSpinBox):
    palette = property(QtWidgets.QDoubleSpinBox.palette)
    value = property(QtWidgets.QDoubleSpinBox.value)


class Metrics(QtGui.QFontMetrics):
    def width(self, text):
        """Qt5 width(text) is Qt6 horizontalAdvance(text), using the real metrics."""
        return self.horizontalAdvance(text)


@pytest.fixture
def legacy_qt(monkeypatch):
    """Load actual production panels against genuine widgets, signals and painters."""
    gui = NS(**{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
    gui.__dict__.update(
        {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
    )
    gui.QWidget, gui.QDialog, gui.QLabel = Widget, Dialog, Label
    gui.QDoubleSpinBox, gui.QFontMetrics = Spin, Metrics
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=QtCore, QtGui=gui))
    names = (
        "_names_dialog",
        "_proof_dialog",
        "_proof_views",
        "_masters_dialog",
        "_masters_views",
        "_master_angles_views",
        "_master_angles_dialog",
    )
    package = importlib.import_module("fontlabapp")
    importlib.import_module("fontlabapp.masters.angles.model")
    for name in names:
        monkeypatch.delitem(sys.modules, _module_name(name), raising=False)
        monkeypatch.delattr(package, name, raising=False)
    modules = {name: importlib.import_module(_module_name(name)) for name in names}
    owned = []
    yield NS(modules=modules, owned=owned, gui=gui)
    for widget in reversed(owned):
        if isValid(widget):
            widget.close()
            widget.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    for name, module in modules.items():
        if sys.modules.get(_module_name(name)) is module:
            sys.modules.pop(_module_name(name))
        if package.__dict__.get(name) is module:
            delattr(package, name)


@pytest.fixture
def font_host(monkeypatch):
    """Only the FontLab process boundary is replaced; no native host is contacted."""
    state = NS(package=None)

    class Workspace:
        @property
        def currentPackage(self):
            return state.package

    workspace = Workspace()
    monkeypatch.setitem(
        sys.modules, "fontlab", NS(flWorkspace=NS(instance=lambda: workspace))
    )
    return state
