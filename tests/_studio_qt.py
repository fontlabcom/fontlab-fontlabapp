# this_file: tests/_studio_qt.py
"""Real offscreen Qt (PySide6) as ``PythonQt`` for the studio shell, table and widgets.

PythonQt (Qt 5) puts widget and item-model classes in ``QtGui``; the fixture
merges PySide6 ``QtWidgets`` and the ``QtCore`` model classes into that
namespace and reloads the named App modules against it.
"""

import importlib
import os
import sys
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6 import QtCore, QtGui, QtWidgets

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

MODULES = ("fontlabapp.fontui.lifecycle", "fontlabapp.fontui.table", "fontlabapp.fontui.appshell")


def gui_namespace() -> NS:
    names = {n: getattr(QtCore, n) for n in dir(QtCore) if n.startswith("Q")}
    names.update({n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
    names.update({n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")})
    return NS(**names)


@pytest.fixture
def studio_qt(monkeypatch):
    """Install real Qt as PythonQt; yield freshly loaded shell/table modules."""
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=QtCore, QtGui=gui_namespace()))
    for name in MODULES:
        monkeypatch.delitem(sys.modules, name, raising=False)
    modules = NS(**{name.rsplit(".", 1)[1]: importlib.import_module(name) for name in MODULES})
    owned: list = []
    yield NS(modules=modules, owned=owned, app=APP, QtCore=QtCore)
    for item in reversed(owned):
        item.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    for name in MODULES:
        sys.modules.pop(name, None)


@pytest.fixture
def isolated_studio_modules():
    """Import ``fontlabapp.studios.*`` fresh for this test, then restore the previous modules.

    Removes the cached studio modules (so they bind this test's Qt namespace) and, afterwards,
    drops what the test imported and puts back the earlier modules and parent-package attributes.
    """
    prefix = "fontlabapp.studios."
    saved = {n: m for n, m in sys.modules.items() if n.startswith(prefix)}
    for name in saved:
        del sys.modules[name]
    yield
    for name in [n for n in sys.modules if n.startswith(prefix)]:
        module = sys.modules.pop(name)
        parent, _, leaf = name.rpartition(".")
        if parent in sys.modules and getattr(sys.modules[parent], leaf, None) is module:
            delattr(sys.modules[parent], leaf)
    for name, module in saved.items():
        sys.modules[name] = module
        parent, _, leaf = name.rpartition(".")
        if parent in sys.modules:
            setattr(sys.modules[parent], leaf, module)
