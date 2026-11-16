# this_file: tests/test_core_pythonqt_profiles_lessons_real.py
"""Run the lesson-route controls against the REAL packaged fontlab_python_lessons dialogs.

Opt-in: needs the Examples sibling (``FONTLAB_EXAMPLES_LESSONS_SRC`` or
``../fontlab-python-examples/lessons/src``) and skips with a clear reason without it.
Only the host surface (``fly.qt``, ``fly.ap.core.scripting``) is replaced, by Qt-backed stand-ins; the
dialogs, filter, model and snapshot code under test are the packaged ones. A mutated copy of the
packaged ``panels.py`` must fail the same scenario, so a green run proves the scenario can see defects.
"""
import os
import shutil
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6 import QtCore as _QtCore
from PySide6 import QtUiTools as _Ui
from PySide6 import QtWidgets as _W
from test_spacing_worksheet import GUI, QtCore, drain

from fontlabapp.fontui.core_pythonqt_labs.profiles import e01_e03 as routes
from fontlabapp.fontui.core_pythonqt_labs.profiles.e01_e03_actions import names

ENV = 'FONTLAB_EXAMPLES_LESSONS_SRC'
DEFAULT = Path(__file__).resolve().parents[2] / 'fontlab-python-examples' / 'lessons' / 'src'
SRC = Path(os.environ.get(ENV) or DEFAULT)
pytestmark = pytest.mark.skipif(
    not (SRC / 'fontlab_python_lessons' / 'ui.py').is_file(),
    reason=f'Examples sibling absent: set {ENV} or check out fontlab-python-examples next to the App')

NAMES = ['space', 'A', 'Aacute', 'zero']
SELECTED = ['zero', 'A']
METRICS = {'A': 2, 'zero': 10}


class _LineEdit(_W.QLineEdit):
    """PythonQt exposes ``text`` as a property; the lessons read it that way."""
    text = property(lambda self: _W.QLineEdit.text(self))


def _host(monkeypatch, src, calls):
    """Install the host stand-ins and import the packaged lessons fresh from ``src``."""
    qt_gui = types.SimpleNamespace(**vars(GUI))
    qt_gui.QLineEdit = _LineEdit
    qt_gui.QStringListModel = _QtCore.QStringListModel
    qt_gui.QAbstractTableModel = _QtCore.QAbstractTableModel
    qt = types.ModuleType('fly.qt')
    qt.QtGui, qt.QtCore, qt.QtUiTools = qt_gui, QtCore, _Ui

    class Base(_W.QDialog):
        def __init__(self, parent, title, key):
            super().__init__(parent)
            self.setWindowTitle(title)
            self.root = _W.QVBoxLayout(self)
            self.subtitle = _W.QLabel(self)
            self.root.addWidget(self.subtitle)

        def _connect(self, signal, slot):
            signal.connect(slot)

        def closeEvent(self, event):
            super().closeEvent(event)

    package = SimpleNamespace(id=14, master='Regular')
    api = types.ModuleType('fly.ap.core.scripting')
    api.names_dialog_type = lambda: Base
    api.current_package = lambda *args: package
    api.names_font_glyphs = lambda *args: [(n, ()) for n in NAMES]
    api.names_font_window_selection = lambda *args: list(SELECTED)
    api.select_glyphs = lambda found, **kw: calls.append((list(found), kw)) or list(found)
    api.inspectors_api = lambda: SimpleNamespace(
        layout=lambda pkg, targets, master: [(n, 0, METRICS[n], 0, 0) for n in targets if n in METRICS])
    fly = types.ModuleType('fly')
    fly.qt = qt
    for name, mod in {'fly': fly, 'fly.qt': qt, 'fly.ap': types.ModuleType('fly.ap'),
                      'fly.ap.core': types.ModuleType('fly.ap.core'), 'fly.ap.core.scripting': api}.items():
        monkeypatch.setitem(sys.modules, name, mod)
    for name in [m for m in sys.modules if m.split('.')[0] == 'fontlab_python_lessons']:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.syspath_prepend(str(src))
    import fontlabapp
    monkeypatch.setattr(fontlabapp, '_native', lambda name: SimpleNamespace(QtCore=QtCore, QtGui=qt_gui))


def _scenario(lab, index, calls):
    title, build = routes.PROFILES[lab][index]
    child = build(None)
    try:
        assert child.snapshot.package_id == 14
        child.refresh()
        if title == 'Glyph Name Filter':
            assert names(child, title) == tuple(NAMES)
            child.query.setText('A')
            child.filter_button.click()
            assert names(child, title) == ('A', 'Aacute'), 'typed prefix must filter the list'
            child.query.setText('')
            child.filter_button.click()
            child.view.selectionModel().select(child.model.index(0, 0), QtCore.QItemSelectionModel.Select)
            chosen = child.visible_names[0]
            child.lab_sort.setCurrentIndex(2)
            assert tuple(child.model.stringList()) == tuple(sorted(NAMES, reverse=True))
            assert child.visible_names == tuple(child.model.stringList())
            child.select()
            assert calls[-1][0] == [chosen] and calls[-1][1].get('package_id') == 14
            child.lab_sort.setCurrentIndex(1)
            assert tuple(child.model.stringList()) == tuple(sorted(NAMES))
            child.lab_sort.setCurrentIndex(0)
            assert names(child, title) == tuple(NAMES)
        elif title == 'Glyph Metrics Model':
            assert child.view.isSortingEnabled()
            proxy = child.view.model()
            child.view.sortByColumn(1, QtCore.Qt.DescendingOrder)
            assert names(child, title) == ('zero', 'A')
            child.refresh()
            proxy = child.view.model()
            assert proxy.sourceModel() is child.model
            assert names(child, title) == ('zero', 'A')
        else:
            assert names(child, title) == tuple(row.name for row in child.snapshot.rows)
    finally:
        child.close()
        drain()


CASES = [('E01', 0), ('E03', 0), ('E03', 1)]


@pytest.mark.parametrize('lab,index', CASES)
def test_lesson_routes_drive_real_packaged_dialogs(monkeypatch, lab, index):
    calls = []
    _host(monkeypatch, SRC, calls)
    _scenario(lab, index, calls)


@pytest.mark.parametrize('needle,replacement', [
    ('filtered(scanned.names, str(self.query.text))', 'list(scanned.names)'),
    ('package_id=scanned.package_id', 'package_id=None'),
])
def test_scenario_fails_on_mutated_packaged_panels(monkeypatch, tmp_path, needle, replacement):
    copy = tmp_path / 'src'
    shutil.copytree(SRC, copy, ignore=shutil.ignore_patterns('__pycache__'))
    panels = copy / 'fontlab_python_lessons' / 'panels.py'
    text = panels.read_text()
    assert needle in text, f'packaged panels.py no longer contains {needle!r}; update the mutant'
    panels.write_text(text.replace(needle, replacement))
    calls = []
    _host(monkeypatch, copy, calls)
    with pytest.raises(AssertionError):
        _scenario('E01', 0, calls)
