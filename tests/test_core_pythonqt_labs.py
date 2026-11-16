# this_file: tests/test_core_pythonqt_labs.py
"""Lab assembly preserves profile state and refuses incomplete child cleanup."""
import importlib
import sys
from types import SimpleNamespace

import pytest
from _studio_qt import studio_qt  # noqa: F401


@pytest.fixture
def labs(studio_qt, monkeypatch):  # noqa: F811
    name = 'fontlabapp.fontui.core_pythonqt_labs.app'
    monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module(name)
    monkeypatch.setattr(module, 'QtGui', studio_qt.modules.appshell.QtGui, raising=False)
    original_profiles = module.profiles
    monkeypatch.setattr(module, 'profiles', lambda key: (('First', lambda parent: studio_qt.modules.lifecycle.Owned(parent)),))
    module.original_profiles = original_profiles
    monkeypatch.setattr(module, 'bindings', lambda *args: {})
    monkeypatch.setattr(module, 'current_package', lambda: None)
    monkeypatch.setattr(module.fontui, 'current_font', lambda: None)
    yield module, studio_qt
    sys.modules.pop(name, None)


def test_lab_when_unknown_then_refused_before_widget(labs):
    module, _qt = labs
    with pytest.raises(ValueError, match='Unknown lab'):
        module.show('E99')


@pytest.mark.parametrize('key,kind', [('E01', 'tmetrics'), ('E02', 'tglyph'), ('E09', 'tglyph')])
def test_lab_when_built_then_tabs_preview_and_owned_state(labs, monkeypatch, key, kind):
    module, qt = labs
    seen = []
    def preview(font, parent, **kw):
        seen.append((font, kw))
        owner = qt.modules.lifecycle.Owned(parent)
        owner.refresh = lambda: None
        return owner
    monkeypatch.setattr(module.fontui, 'metrics_preview', preview)
    monkeypatch.setattr(module.fontui, 'glyph_view', preview)
    app = module.show(key, font='captured', package=lambda: None)
    qt.owned.append(app)
    assert app.preview_kind == kind
    assert app.tabs.tabText(0) == 'First'
    assert app.tabs.tabText(1) == 'About'
    assert seen[0][0] == 'captured' and seen[0][1]['read_only']
    assert app.apply_button.isHidden()
    assert app.preview is not None
    first = app.children[1]
    app.tabs.setCurrentIndex(1)
    app.tabs.setCurrentIndex(0)
    assert app.children[1] is first
    app.close()
    assert not app.children


def test_lab_when_no_font_then_controls_still_available(labs):
    module, qt = labs
    app = module.show('E03')
    qt.owned.append(app)
    assert app.preview is None
    assert 'Open a font' in app.status.text()


def test_profile_when_close_refused_then_owner_retained_for_retry(labs):
    module, _qt = labs
    widget = module.QtGui.QWidget()
    calls = []
    child = SimpleNamespace(widget=widget, close=lambda: calls.append(1) or len(calls) > 1)
    owner = module.Profile(None, child)
    with pytest.raises(RuntimeError, match='refused'):
        owner.close()
    assert not owner._close_complete
    owner.close()
    assert owner._close_complete and len(calls) == 2


def test_profile_when_cleanup_incomplete_then_refuses(labs):
    module, _qt = labs
    child = SimpleNamespace(widget=module.QtGui.QWidget(), close=lambda: None, _close_complete=False)
    owner = module.Profile(None, child)
    with pytest.raises(RuntimeError, match='incomplete'):
        owner.close()
    child._close_complete = True
    owner.close()


def test_profile_when_plain_widget_then_embed_and_close(labs):
    module, _qt = labs
    widget = module.QtGui.QWidget()
    owner = module.Profile(None, widget)
    assert widget.parent() == owner.widget
    owner.close()
    owner.close()
    assert owner._close_complete


def test_lab_when_profile_constructor_fails_then_shell_closes(labs, monkeypatch):
    module, qt = labs
    made = []
    def shell(*args, **kw):
        result = qt.modules.appshell.AppShell(*args, **kw)
        made.append(result)
        return result
    monkeypatch.setattr(module.fontui, 'app_shell', shell)
    def fail(parent):
        raise ValueError('profile error')
    monkeypatch.setattr(module, 'profiles', lambda key: (('Broken', fail),))
    with pytest.raises(ValueError, match='profile error'):
        module.show('E01')
    assert made[0]._close_complete


def test_lab_when_profile_named_then_selects_and_rejects_unknown(labs):
    module, qt = labs
    app = module.show('E01', profile='First')
    qt.owned.append(app)
    assert app.tabs.currentIndex() == 0
    with pytest.raises(ValueError, match='Unknown E01 profile'):
        module.show('E01', profile='missing')


def test_public_entry_when_called_then_forwards(labs, monkeypatch):
    module, _qt = labs
    package = importlib.import_module('fontlabapp.fontui.core_pythonqt_labs')
    seen = []
    monkeypatch.setattr(module, 'show', lambda *args, **kwargs: seen.append((args, kwargs)) or 42)
    assert package.show('E02', profile='Tree') == 42
    assert seen[0][1]['profile'] == 'Tree'


def test_profiles_when_requested_then_loads_matching_family(labs, monkeypatch):
    module, _qt = labs
    seen = []
    monkeypatch.setattr(module, 'import_module', lambda name: seen.append(name) or SimpleNamespace(PROFILES={'E07': ('profile',)}))
    assert module.original_profiles('E07') == ('profile',)
    assert seen == ['fontlabapp.fontui.core_pythonqt_labs.profiles.e07_e09']


def test_guard_when_target_changes_before_or_during_capture_then_refused(labs):
    module, _qt = labs
    package = SimpleNamespace(id=1, master='Regular')
    state = [package]
    called = []
    run = module.guarded(lambda: called.append(1), lambda: state[0], (1, 'Regular'))
    run()
    state[0] = None
    with pytest.raises(ValueError, match='active font'):
        run()
    assert called == [1]
    state[0] = package
    def change():
        package.master = 'Bold'
    with pytest.raises(ValueError, match='during capture'):
        module.guarded(change, lambda: package, (1, 'Regular'))()


def test_publish_when_output_changes_then_preview_uses_exact_text_and_layer(labs):
    module, _qt = labs
    calls = []
    shell = SimpleNamespace(preview_kind='tmetrics', preview=SimpleNamespace(set_text=calls.append, set_layer=lambda layer: None))
    module.publish(shell, ('A', 'a.alt'), 'Regular')
    module.publish(shell, 'A Ω', 'Regular')
    assert calls == ['/A /a.alt', 'A Ω']
    shell.preview_kind = 'tglyph'
    shell.preview.load = lambda name, layer: calls.append((name, layer))
    module.publish(shell, (), 'Regular')
    module.publish(shell, ('A',), 'Regular')
    assert calls[-1] == ('A', 'Regular')
    shell.preview = None
    shell.set_status = calls.append
    module.publish(shell, ('A',), None)
    assert 'Open a font' in calls[-1]


def test_lab_when_local_close_clicked_then_whole_shell_closes(labs, monkeypatch):
    module, qt = labs
    built = []
    def build(parent):
        dialog = module.QtGui.QDialog(parent)
        layout = module.QtGui.QVBoxLayout(dialog)
        button = module.QtGui.QPushButton('Close', dialog)
        layout.addWidget(button)
        button.clicked.connect(dialog.close)
        built.append((dialog, button))
        return dialog
    monkeypatch.setattr(module, 'profiles', lambda key: (('Local', build),))
    app = module.show('E01')
    qt.owned.append(app)
    built[0][1].click()
    assert not app.closed
    qt.app.processEvents()
    assert app._close_complete


def test_close_filter_when_escape_or_ordinary_event_then_correct_route(labs):
    module, qt = labs
    events = []
    fake = SimpleNamespace(widget=module.QtGui.QWidget(), _closing=False, closed=False,
                           _run_action=events.append)
    child = module.QtGui.QWidget()
    guard = module.CloseFilter(fake, child)
    event = SimpleNamespace(type=lambda: qt.QtCore.QEvent.KeyPress,
                            key=lambda: qt.QtCore.Qt.Key_Escape, ignore=lambda: None)
    assert guard.eventFilter(child, event)
    assert guard.eventFilter(child, event)
    qt.app.processEvents()
    assert events == ['close']
    ordinary = SimpleNamespace(type=lambda: qt.QtCore.QEvent.Show)
    assert not guard.eventFilter(child, ordinary)
    fake.closed = True
    assert not guard.eventFilter(child, event)
    child.deleteLater()
    fake.widget.deleteLater()


def test_lab_when_capture_endpoint_used_then_bound_target_guard_remains(labs, monkeypatch):
    module, qt = labs
    current = SimpleNamespace(id=7, master='Regular')
    child = qt.modules.lifecycle.Owned(None)
    child.capture = lambda: 'snapshot'
    monkeypatch.setattr(module, 'profiles', lambda key: (('Bound', lambda parent: child),))
    monkeypatch.setattr(module, 'bindings', lambda *args: {'refresh': child.capture})
    app = module.show('E01', package=lambda: current)
    qt.owned.append(app)
    assert child.capture() == 'snapshot'
    current.master = 'Bold'
    with pytest.raises(ValueError, match='active font'):
        child.capture()
    app._run_action('refresh')
    assert 'active font' in app.status.text()


def test_supplied_font_when_different_from_active_then_refused_before_build(labs, monkeypatch):
    module, _qt = labs
    monkeypatch.setattr(module.fontui, 'current_font', lambda: object())
    with pytest.raises(ValueError, match='supplied font'):
        module.show('E01', font=object())


def test_studio_public_entry_when_called_then_uses_public_fontui_factory(labs, monkeypatch):
    module, _qt = labs
    studio = importlib.import_module('fontlabapp.studios.core_pythonqt_labs')
    calls = []
    monkeypatch.setattr(module.fontui, 'core_pythonqt_lab', lambda *a, **k: calls.append((a, k)) or 43)
    assert studio.show('E06', profile='Draggable Glyph Names') == 43
    assert calls[0][1]['profile'] == 'Draggable Glyph Names'


def test_public_fontui_factory_when_called_then_loads_lab(labs, monkeypatch):
    module, _qt = labs
    calls = []
    monkeypatch.setattr(module.fontui, '_load', lambda name: SimpleNamespace(show=lambda *a, **k: calls.append((name, a, k)) or 44))
    assert module.fontui.core_pythonqt_lab('E04') == 44
    assert calls[0][0] == 'core_pythonqt_labs'


def test_controller_close_when_called_directly_then_routes_whole_shell(labs):
    module, qt = labs
    events = []
    shell = SimpleNamespace(widget=module.QtGui.QWidget(), _closing=False, closed=False,
                            _run_action=events.append)
    child = module.QtGui.QWidget()
    closer = module.CloseFilter(shell, child)
    routed = closer.route(lambda: events.append('controller') or True)
    assert routed() is False
    assert routed() is False
    qt.app.processEvents()
    assert events == ['close']
    shell._closing = True
    assert routed() is True
    assert events == ['close', 'controller']
    child.deleteLater()
    shell.widget.deleteLater()
