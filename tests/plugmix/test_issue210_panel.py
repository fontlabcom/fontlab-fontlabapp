# this_file: tests/plugmix/test_issue210_panel.py
"""Reporters panel state, owned signal and failure behavior with Qt fakes."""

from types import SimpleNamespace as NS

import pytest

from fontlabapp.plugins import boot, menu, registry, reporters_panel
from fontlabapp.plugins.kinds import Services
from test_plugmix_palette import Control, Layout, Signal
from test_plugmix_registry_boot_menu import Menus, Painters


class Checkbox(Control):
    def __init__(self, *args):
        super().__init__(*args)
        self.toggled = Signal()
        self.checked = False
        self.title = args[0]

    def sizeHint(self):
        return NS(width=lambda: len(self.title) * 8 + 24, height=lambda: 24)

    def setChecked(self, checked):
        changed = self.checked != checked
        self.checked = checked
        if changed:
            self.toggled.emit(checked)


def panel(tmp_path, monkeypatch):
    state = registry.Registry(tmp_path)
    owner = Menus()
    owner.main_window = lambda: "main"
    errors, closes, shown = [], [], []
    class GridLayout(Layout):
        def addWidget(self, widget, *args):
            self.rows.append(widget)
        def removeWidget(self, widget):
            if widget in self.rows:
                self.rows.remove(widget)
        def setContentsMargins(self, *args):
            pass
        def setSizeConstraint(self, constraint):
            pass
        def setSpacing(self, spacing):
            pass
    class Widget:
        def __init__(self, *args):
            pass
        def __getattr__(self, name):
            return lambda *args: None
        def viewport(self):
            return NS(width=lambda: 900)
        def resizeEvent(self, event):
            pass
    qt = NS(QtGui=NS(QVBoxLayout=GridLayout, QGridLayout=GridLayout,
                    QCheckBox=Checkbox, QWidget=Widget, QScrollArea=Widget,
                    QFrame=NS(NoFrame=0), QLayout=NS(SetMinimumSize=2)))
    services = Services(qt, None, owner, None, lambda e, s: errors.append(e))
    host = reporters_panel.ReportersPanel(services, state)
    owned = NS(widget=NS(show=lambda: shown.append(True), resize=lambda *args: None,
                         screen=lambda: NS(availableGeometry=lambda: NS(width=lambda: 1024, height=lambda: 768))),
               close=lambda: closes.append(True))

    def create(parent, title, build, area):
        assert (parent, title, area) == ("main", "Reporters", "right")
        build(object())
        return owned

    monkeypatch.setattr(reporters_panel, "import_module", lambda name: NS(create_panel=create))
    return host, state, owner, errors, closes, shown, owned


def test_panel_when_toggled_then_menu_and_external_registry_are_synchronized(tmp_path, monkeypatch):
    host, state, owner, errors, closes, shown, owned = panel(tmp_path, monkeypatch)
    host.install()
    tokens = menu.install(owner, state)
    host.show()
    assert len(host.checks) == 39
    check = host.checks["node_indexes"]
    check.setChecked(True)
    assert state.enabled() == ("node_indexes",)
    assert owner.action(tokens["node_indexes"]).checked
    owner.actions[tokens["node_indexes"]][1]()
    assert not check.checked
    state.enable("node_indexes")
    assert check.checked
    host.show()
    assert shown == [True]
    callbacks = list(check.toggled.slots)
    assert host.close() is True and closes == [True]
    assert not check.toggled.slots and host.sync not in state.listeners
    assert host.close() is True and not errors


def test_panel_when_save_fails_then_reverts_check_and_contains_callback(tmp_path, monkeypatch):
    host, state, owner, errors, _, _, _ = panel(tmp_path, monkeypatch)
    host.show()
    state._save = lambda: (_ for _ in ()).throw(OSError("disk"))
    host.checks["node_indexes"].setChecked(True)
    assert state.enabled() == () and not host.checks["node_indexes"].checked
    assert len(errors) == 1
    assert host.close()


def test_panel_when_close_refused_then_retains_signals(tmp_path, monkeypatch):
    host, state, _, _, _, _, owned = panel(tmp_path, monkeypatch)
    host.show()
    owned.close = lambda: False
    assert host.close() is False
    assert host.owned is owned and host.sync in state.listeners
    owned.close = lambda: True
    assert host.close()


def test_panel_when_construction_fails_then_disconnects_partial_controls(tmp_path, monkeypatch):
    host, state, _, _, _, _, _ = panel(tmp_path, monkeypatch)
    checks = []

    def fail(parent, title, build, area):
        build(object())
        checks.extend(host.checks.values())
        raise RuntimeError("construction")

    monkeypatch.setattr(reporters_panel, "import_module", lambda name: NS(create_panel=fail))
    with pytest.raises(RuntimeError, match="construction"):
        host.show()
    assert host.ui is None and not host.checks
    assert all(not check.toggled.slots for check in checks)
    monkeypatch.setattr(reporters_panel, "import_module", lambda name: (_ for _ in ()).throw(ImportError("missing")))
    with pytest.raises(ImportError):
        host.show()


def test_boot_when_host_data_root_then_discovers_extensions_and_is_idempotent(tmp_path, monkeypatch):
    errors = []
    fake = NS(flPreferences=lambda: NS(dataPathDefault=lambda: str(tmp_path)))
    monkeypatch.setattr(boot, "_runtime", lambda: (object(), fake, Menus))
    monkeypatch.setattr(boot, "select_backend", lambda *args: Painters())
    monkeypatch.setattr(boot, "_state", None)
    boot.install()
    state = boot._state
    assert state.extensions_dir == tmp_path / "Extensions"
    assert state.reporters.path == tmp_path / "Data/fontlab-plugmix.json"
    boot.install()
    assert boot._state is state
    with pytest.raises(ValueError):
        boot.install(extensions_dir=tmp_path / "other")
    panel_closes = []
    real_close = state.reporters_panel.close
    state.reporters_panel.close = lambda: panel_closes.append(1) or real_close()
    state.palettes.close = lambda: False
    boot.uninstall()
    assert boot._state is state and not panel_closes, "palette refusal must keep the panel open"
    del state.palettes.close
    state.reporters_panel.close = lambda: False
    boot.uninstall()
    assert boot._state is state
    state.reporters_panel.close = lambda: True
    boot.uninstall()
    assert boot._state is None
    fake.flPreferences = lambda: NS(dataPathDefault="")
    with pytest.raises(RuntimeError, match="user data"):
        boot.install()


def test_show_reporters_when_called_then_boots_and_shows(monkeypatch):
    calls = []
    def install():
        calls.append("boot")
        boot._state = NS(reporters_panel=NS(show=lambda: calls.append("show")))

    monkeypatch.setattr(boot, "install", install)
    monkeypatch.setattr(boot, "_state", None)
    boot.show_reporters()
    assert calls == ["boot", "show"]
    boot.show_reporters()
    assert calls == ["boot", "show", "show"]


def test_rescan_when_reporter_added_then_menu_and_open_panel_gain_toggle(tmp_path, monkeypatch):
    from test_issue210_bundles import bundle

    host, state, owner, errors, _, _, _ = panel(tmp_path, monkeypatch)
    root = tmp_path / "Extensions"
    bundle(root, "One")
    state.extensions_dir = root
    state._classes = None
    tokens = menu.install(owner, state)
    submenu = next(iter(owner.menus.values()))
    submenu.clear = lambda: (_ for _ in ()).throw(AssertionError("unsafe clear during callback"))
    owner.remove = lambda token: (_ for _ in ()).throw(AssertionError("rescan must preserve owned actions"))
    host.show()
    first = host.checks["one"]
    bundle(root, "Two")
    state.rescan()
    assert set(tokens) == set(host.checks) == {"one", "two"}
    assert host.checks["one"] is first
    assert submenu.entries == ["One", "-", "Hide All", "Two"]
    host.checks["two"].setChecked(True)
    assert state.enabled() == ("two",) and owner.action(tokens["two"]).checked
    owner.actions[tokens["two"]][1]()
    assert not host.checks["two"].checked
    controls, actions = dict(host.checks), dict(tokens)
    state.rescan()
    assert host.checks == controls and tokens == actions and not errors
    host.close()


def test_show_reporters_when_installed_with_explicit_path_then_uses_owner(tmp_path, monkeypatch):
    from test_plugmix_tool_general import environment

    services, _, _, _ = environment(tmp_path)
    services.menus.close = lambda: services.menus.actions.clear()
    services.painters.close = lambda: None
    monkeypatch.setattr(boot, "_runtime", lambda: (services.qt, services.fontlab, lambda *args, **kw: services.menus))
    monkeypatch.setattr(boot, "select_backend", lambda *args: services.painters)
    monkeypatch.setattr(boot, "_state", None)
    boot.install(tmp_path)
    state = boot._state
    calls = []
    state.reporters_panel.show = lambda: calls.append(True)
    boot.show_reporters()
    assert boot._state is state and calls == [True]
    listeners = tuple(state.reporters.listeners)
    assert listeners
    close = state.reporters_panel.close
    panel_closes = []
    real_close = state.reporters_panel.close
    state.reporters_panel.close = lambda: panel_closes.append(1) or real_close()
    state.palettes.close = lambda: False
    boot.uninstall()
    assert boot._state is state and not panel_closes, "palette refusal must keep the panel open"
    del state.palettes.close
    state.reporters_panel.close = lambda: False
    boot.uninstall()
    assert tuple(state.reporters.listeners) == listeners
    state.reporters_panel.close = close
    boot.uninstall()
    assert not state.reporters.listeners
    state.menus.action = lambda token: (_ for _ in ()).throw(AssertionError("dead owner"))
    state.reporters.enable("node_indexes")
    assert state.reporters.enabled() == ("node_indexes",)


def test_boot_when_menu_setup_fails_then_drops_owned_listeners(tmp_path, monkeypatch):
    from test_plugmix_tool_general import environment

    services, _, _, _ = environment(tmp_path)
    services.menus.close = lambda: services.menus.actions.clear()
    services.painters.close = lambda: None
    monkeypatch.setattr(boot, "_runtime", lambda: (services.qt, services.fontlab, lambda *args, **kw: services.menus))
    monkeypatch.setattr(boot, "select_backend", lambda *args: services.painters)
    monkeypatch.setattr(boot, "_state", None)
    saved = menu.install

    def fail(owner, state):
        saved(owner, state)
        assert state.listeners
        raise RuntimeError("setup")

    monkeypatch.setattr(menu, "install", fail)
    with pytest.raises(RuntimeError, match="setup"):
        boot.install(tmp_path)
    assert not registry.current().listeners and boot._state is None


@pytest.mark.parametrize("failure", ["screen", "resize"])
def test_panel_when_initial_screen_query_fails_then_keeps_usable_owner_and_cleanup(tmp_path, monkeypatch, failure):
    host, state, _, errors, _, _, owned = panel(tmp_path, monkeypatch)
    setattr(owned.widget, failure, lambda *args: (_ for _ in ()).throw(RuntimeError("fitting unavailable")))
    host.show()
    assert host.owned is owned and len(host.checks) == 39
    assert host.sync in state.listeners and len(errors) == 1
    host.show()
    host.checks["node_count"].setChecked(True)
    assert "node_count" in state.enabled()
    host.sync()
    assert host.close() and not state.listeners


def test_panel_when_qt_properties_are_values_then_build_sync_and_close_work(tmp_path, monkeypatch):
    monkeypatch.setattr(Checkbox, "sizeHint", property(
        lambda self: NS(width=len(self.title) * 8 + 24, height=24)
    ))
    host, state, _, errors, _, _, owned = panel(tmp_path, monkeypatch)
    owned.widget.screen = NS(availableGeometry=NS(width=800, height=600))
    host.show()
    assert len(host.checks) == 39 and not errors
    host.checks["node_count"].setChecked(True)
    assert "node_count" in state.enabled()
    host.sync()
    assert host.close() and not state.listeners
