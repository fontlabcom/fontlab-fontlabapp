# this_file: tests/test_teaching_host.py
"""Teaching panels retain their real controls and close acknowledgement."""
import importlib
import sys
from types import SimpleNamespace as NS

import pytest
pytest_plugins = ["_studio_qt"]


@pytest.fixture
def host(studio_qt, monkeypatch):
    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.teaching.host', raising=False)
    module = importlib.import_module('fontlabapp.fontui.teaching.host')
    yield module
    for shell in tuple(module.OPEN):
        shell.close()


def test_embedded_panel_and_retained_shell_lifetime(host, studio_qt):
    gui = studio_qt.modules.appshell.QtGui
    shell = host.create('File Search Lab')
    panel = gui.QDialog()
    owner = host.embed(shell, 'Text search', panel)
    assert owner.panel is panel and not panel.isWindow()
    assert shell.tabs.tabText(0) == 'Text search'
    assert host.finish(shell) is shell and shell in host.OPEN
    shell.close()
    assert owner._close_complete and shell not in host.OPEN
    shell.close()


def test_refused_panel_close_retains_owner_for_retry(host, studio_qt):
    gui = studio_qt.modules.appshell.QtGui
    class Panel(gui.QWidget):
        refuse = True
        def closeEvent(self, event):
            event.ignore() if self.refuse else event.accept()
    shell = host.create('Test')
    panel = Panel()
    owner = host.embed(shell, 'Task', panel)
    with pytest.raises(RuntimeError, match='refused'):
        shell.close()
    assert owner in shell.children and shell in host.OPEN
    panel.refuse = False
    shell.close()
    assert shell not in host.OPEN


def test_destroyed_panel_is_not_closed_again(host, studio_qt):
    shell = host.create('Test')
    panel = studio_qt.modules.appshell.QtGui.QWidget()
    owner = host.embed(shell, 'Task', panel)
    panel.destroyed.emit()
    assert owner.panel_dead
    shell.close()


def test_preview_uses_captured_context_and_read_only(host, monkeypatch):
    made = []
    monkeypatch.setattr(host.fontui, 'glyph_view', lambda *a, **k: made.append((a,k)) or object())
    monkeypatch.setattr(host.fontui, 'metrics_preview', lambda *a, **k: made.append((a,k)) or object())
    for kind in ('tglyph', 'tmetrics'):
        shell = NS(preview_kind=kind, widget=object(), hint_check=object(), set_preview=lambda p:p)
        host.bind_preview(shell, 'font', 'A', 'Regular')
        assert made[-1][1]['read_only'] is True
        assert made[-1][1]['layer'] == 'Regular'
    assert made[0][1]['name'] == 'A'
    assert made[1][1]['text'] == '/A'
    assert host.bind_preview(NS(preview_kind=None), 'font') is None
    assert host.bind_preview(NS(preview_kind='tglyph'), None) is None


def test_current_preview_captures_actual_glyph_layer_and_package(host, monkeypatch):
    layer = NS(name='Background', id=41)
    glyph = NS(name='Z', activeLayer=layer)
    package = NS(defaultMaster='Light', id=9)
    monkeypatch.setattr(host, 'current_package', lambda: package)
    monkeypatch.setattr(host, 'current_glyph', lambda p: glyph)
    monkeypatch.setattr(host.fontui, 'current_font', lambda: 'captured font')
    shell = NS()
    calls=[]
    monkeypatch.setattr(host, 'bind_preview', lambda *a: calls.append(a))
    host.bind_current_preview(shell)
    assert calls[-1][1:] == ('captured font','Z','Background')
    assert shell._package() is package
    host.require_current_preview(shell)
    glyph.activeLayer = NS(name='Regular', id=42)
    with pytest.raises(ValueError, match='Refresh'):
        host.require_current_preview(shell)
    monkeypatch.setattr(host, 'current_glyph', lambda p: None)
    assert host.current_target()[1:] == (None, 'Light', (9,None,None))
    monkeypatch.setattr(host, 'current_package', lambda: None)
    assert host.current_target() == (None,None,None,(None,None,None))


def test_refresh_replaces_preview_only_after_ack(host, studio_qt, monkeypatch):
    shell=host.create('Test', 'tglyph')
    old=studio_qt.modules.lifecycle.Owned(shell.widget)
    shell.set_preview(old)
    calls=[]
    monkeypatch.setattr(host, 'bind_current_preview', lambda s:calls.append(s))
    host.refresh_current_preview(shell)
    assert old._close_complete and old not in shell.children and calls == [shell]
    host.refresh_current_preview(shell)
    assert calls == [shell,shell]
    refusing=NS(close=lambda:None, _close_complete=False)
    shell.preview=refusing
    with pytest.raises(RuntimeError, match='incomplete'):
        host.refresh_current_preview(shell)
    shell.preview=None
