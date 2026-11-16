# this_file: tests/test_wp05_simplify_main.py
"""Simplify Selected Nodes shows its panel, or a warning when the host refuses."""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace as NS

import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'src/fontlabapp/fontui/outline_routes/simplify_selected_nodes.py'


@pytest.fixture
def route(monkeypatch):
    """Load the route over owned stand-ins for the host-bound helpers."""
    import fontlabapp.fontui.outline_simplify  # noqa: F401 - real, host free
    base = type('PanelBase', (), {})
    stubs = {
        'fontlabapp.contours.panel.model': NS(panel_type=lambda: base),
        'fontlabapp.contours.writer': NS(Planner=object, Editor=object),
        'fontlabapp.core.scripting': NS(show_script_dialog=lambda cls, key: ('panel', cls, key)),
    }
    import fontlabapp.contours
    import fontlabapp.core
    for name, stub in stubs.items():
        monkeypatch.setitem(sys.modules, name, stub)
    panel_pkg = NS(model=stubs['fontlabapp.contours.panel.model'])
    monkeypatch.setitem(sys.modules, 'fontlabapp.contours.panel', panel_pkg)
    monkeypatch.setattr(fontlabapp.contours, 'panel', panel_pkg, raising=False)
    monkeypatch.setattr(fontlabapp.contours, 'writer', stubs['fontlabapp.contours.writer'], raising=False)
    monkeypatch.setattr(fontlabapp.core, 'scripting', stubs['fontlabapp.core.scripting'], raising=False)
    spec = importlib.util.spec_from_file_location('simplify_route_under_test', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_returns_what_the_scripting_helper_opens(route):
    assert route.main() == ('panel', route.SimplifyPanel, route.KEY)


def test_panel_planner_and_editor_use_the_shared_simplifier(route, monkeypatch):
    panel = object.__new__(route.SimplifyPanel)
    panel.current_master = 'Regular'
    seen = []
    monkeypatch.setattr(route, 'changes', lambda layer, base: seen.append((layer, base)) or 'plan')
    glyph = NS(findLayer=lambda master: 'base:' + master)
    assert panel.planner()(glyph, 'Bold', 'layer') == 'plan'
    assert seen == [('layer', 'base:Regular')]
    assert isinstance(panel.editor(), route.SimplifyEditor)


@pytest.mark.parametrize('error', [ValueError('no font'), RuntimeError('busy'), TimeoutError('slow')])
def test_main_reports_a_refusal_in_a_standard_warning_box(route, monkeypatch, error):
    def refuse(cls, key):
        raise error

    monkeypatch.setattr(route.scripting, 'show_script_dialog', refuse)
    shown = []
    qt = ModuleType('PythonQt')
    qt.QtGui = NS(QMessageBox=NS(Ok=1024))
    fontlabapp = ModuleType('fontlabapp')
    fontlabapp.fontlab = NS(MainWindow=lambda: 'window')
    dialogs = ModuleType('fontlabapp.qt.dialogs')
    dialogs.run_standard_message_box = lambda *args: shown.append(args)
    monkeypatch.setitem(sys.modules, 'PythonQt', qt)
    monkeypatch.setitem(sys.modules, 'fontlabapp', fontlabapp)
    monkeypatch.setitem(sys.modules, 'fontlabapp.qt.dialogs', dialogs)
    assert route.main() is None
    assert shown == [(qt, 'window', route.TITLE, str(error), 'Warning', 1024)]
