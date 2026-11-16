# this_file: tests/_text_lab.py
"""Real offscreen Qt standing in for PythonQt, with a small Names-dialog base, for teaching_text tests."""

import importlib
import sys

import pytest

from _studio_qt import studio_qt  # noqa: F401


# PythonQt exposes these as properties (no call); real Qt has methods. Wrap to match the host.
PROPERTY_GETTERS = {
    "QLineEdit": ("text",),
    "QComboBox": ("currentText", "currentIndex"),
    "QSpinBox": ("value",),
    "QDoubleSpinBox": ("value",),
    "QTabWidget": ("currentIndex",),
    "QListWidget": ("currentRow",),
    "QStackedWidget": ("currentIndex",),
}


def with_properties(gui):
    """Replace listed QtGui classes with subclasses whose getters read like PythonQt properties."""
    for name, getters in PROPERTY_GETTERS.items():
        base = getattr(gui, name, None)
        if base is None:
            continue
        members = {g: property(lambda self, g=g, base=base: getattr(base, g)(self)) for g in getters}
        setattr(gui, name, type(name, (base,), members))


def dialog_base(gui):
    """The slice of NamesDialog the labs use: subtitle, root layout, _connect, lab hooks."""

    class Base(gui.QDialog):
        def __init__(self, parent, title, key):
            super().__init__(parent)
            self._key, self.last_result = key, None
            self.setWindowTitle(title)
            self.subtitle = gui.QLabel()
            self.root = gui.QVBoxLayout(self)
            self.root.addWidget(self.subtitle)

        def _connect(self, signal, callback):
            signal.connect(callback)

    return Base


@pytest.fixture
def lab(studio_qt, monkeypatch):  # noqa: F811
    """Load a teaching_text module with the stand-in base; return build()'s dialog."""
    import fontlabapp
    import fontlabapp.core.scripting as scripting

    qt = sys.modules["PythonQt"]
    monkeypatch.setattr(fontlabapp, "_native", lambda name: sys.modules[name], raising=False)
    monkeypatch.setattr(scripting, "names_dialog_type", lambda: dialog_base(qt.QtGui))
    with_properties(qt.QtGui)  # the namespace is rebuilt for every test, so no restore is needed
    shown = []
    monkeypatch.setattr(scripting, "show_script_dialog", lambda cls, key: shown.append((cls, key)) or cls(None))

    def load(name):
        module = importlib.import_module("fontlabapp.fontui.teaching_text." + name)
        return module, shown

    yield load
    # A window left shown leaks Qt state into later tests (it broke QAbstractItemModelTester
    # in test_tree_model): close what the test left, then fail the leaking test itself.
    leaked = [w for w in qt.QtGui.QApplication.topLevelWidgets() if w.isVisible()]
    for widget in leaked:
        widget.close()
    assert not leaked, f"test left top-level windows shown: {[type(w).__name__ for w in leaked]}"


def button(dialog, text):
    """The push button of a dialog by its label."""
    found = [b for b in dialog.findChildren(sys.modules["PythonQt"].QtGui.QPushButton) if b.text() == text]
    assert len(found) == 1, text
    return found[0]
