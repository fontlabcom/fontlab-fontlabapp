# this_file: tests/plugmix/test_plugmix_registry_boot_menu.py
"""Registry discovery, persistence, menu toggling and boot ownership."""

import json
from types import SimpleNamespace as NS

import pytest

from fontlabapp.plugins import boot, menu, registry
from fontlabapp.plugins.reporter import Reporter


class Painters:
    def __init__(self, *args, **kwargs):
        self.calls = []
        self.closed = False

    def register(self, reporter, qt, sink):
        self.calls.append((reporter, qt, sink))
        return len(self.calls)

    def remove(self, token):
        self.calls.append(("remove", token))

    def close(self):
        self.closed = True


class Action:
    def __init__(self):
        self.checked = False

    def setChecked(self, value):
        self.checked = value


class Submenu:
    def __init__(self, parent, title):
        self.parent, self.title, self.entries = parent, title, []

    def addSeparator(self):
        self.entries.append("-")


class Menus:
    def __init__(self, *args, **kwargs):
        self.actions = {}
        self.titles = {}
        self.menus = {}
        self.closed = False

    def add_menu(self, section, title):
        token = -(len(self.menus) + 1)
        self.menus[token] = Submenu(section, title)
        return token

    def menu(self, token):
        return self.menus[token]

    def add_action(self, section, title, callback, *, checkable=False):
        token = len(self.actions) + 1
        if isinstance(section, Submenu):
            section.entries.append(title)
        assert (
            (
                isinstance(section, Submenu)
                and (section.parent, section.title) == ("View", "Reporters")
                and not title.startswith(("Plugmix", "Show "))
                and checkable == (title != "Hide All")
            )
            or (
                section == "Glyph"
                and title in {"Plugmix: Delete Small Paths…", "Plugmix: Move Outlines…",
                              "Plugmix: Round Outline to Grid…", "Plugmix: Scale Outlines…",
                              "Plugmix: Slant Outlines…"}
                and not checkable
            )
            or (
                isinstance(section, Submenu)
                and (section.parent, section.title) == ("Window", "Panels")
                and title == "Plugmix: Step and Repeat Panel"
                and checkable
            )
            or (isinstance(section, Submenu) and (section.parent, section.title) == ("Window", "Panels") and title == "Reporters" and not checkable)
        )
        self.actions[token] = (Action(), callback)
        self.titles[token] = title
        return token

    def action(self, token):
        return self.actions[token][0]

    def close(self):
        self.closed = True

    def remove(self, token):
        self.actions.pop(token, None)


def test_discovery_includes_builtins_and_entry_points(monkeypatch):
    class External(Reporter):
        name, title = "external", "External"

    groups = []
    points = NS(select=lambda group: groups.append(group) or [NS(load=lambda: External)])
    monkeypatch.setattr(registry.metadata, "entry_points", lambda: points)
    found = registry.discover()
    assert groups == ["fontlabapp.plugmix"]
    assert len(found) == 51
    assert found["external"] is External

    class Bad(Reporter):
        name, title = "node_indexes", "Collision"

    points.select = lambda group: [NS(load=lambda: Bad)]
    errors = []
    assert len(registry.discover(lambda error, source: errors.append(error))) == 50
    points.select = lambda group: [
        NS(load=lambda: object),
        NS(load=lambda: (_ for _ in ()).throw(ImportError("broken"))),
    ]
    assert len(registry.discover(lambda error, source: errors.append(error))) == 50
    assert [type(error) for error in errors] == [ValueError, TypeError, ImportError]


def test_registry_enable_disable_persists_and_restores(tmp_path):
    state = registry.Registry(tmp_path)
    assert len(state.available()) == 50
    assert state.enabled() == ()
    assert not state.path.exists(), "initialization must not write preferences"
    painters = Painters()
    state.attach(painters, object(), lambda e, p: None)
    assert state.enable("duplicate_anchors") is True
    assert state.enable("duplicate_anchors") is True
    assert len(painters.calls) == 1
    assert json.loads(state.path.read_text())["enabled"] == ["duplicate_anchors"]
    state.detach()
    assert state.enabled() == ("duplicate_anchors",)
    restored = registry.Registry(tmp_path)
    again = Painters()
    restored.attach(again, object(), lambda e, p: None)
    assert len(again.calls) == 1
    assert restored.toggle("duplicate_anchors") is False
    assert json.loads(state.path.read_text())["enabled"] == []
    assert restored.disable("duplicate_anchors") is False
    with pytest.raises(KeyError):
        restored.enable("missing")
    with pytest.raises(KeyError):
        restored.disable("missing")


def test_registry_skips_bad_json_and_proxy_functions(tmp_path, monkeypatch):
    path = tmp_path / "fontlab-plugmix.json"
    errors = []
    for raw in ('{"enabled": "bad"}', '{"enabled": [2]}', "{bad json"):
        path.write_text(raw)
        state = registry.Registry(tmp_path, lambda error, source: errors.append(error))
        assert state.enabled() == ()
        assert path.read_text() == raw, "install must preserve the bad document"
    assert len(errors) == 3
    path.unlink()
    monkeypatch.setattr(registry, "_current", None)
    current = registry.configure(tmp_path)
    assert registry.current() is current
    assert "node_indexes" in registry.available()
    assert registry.enable("node_indexes") is True
    assert registry.enabled() == ("node_indexes",)
    assert registry.toggle("node_indexes") is False
    assert registry.disable("node_indexes") is False


def test_registry_restores_saved_reporter_and_rolls_back_failed_save(tmp_path):
    path = tmp_path / "fontlab-plugmix.json"
    errors = []
    path.write_text('{"enabled": ["offcurve_outside_bounds"]}')
    assert registry.Registry(tmp_path, lambda e, s: errors.append(e)).enabled() == ()
    assert "Invalid plugmix params" in str(errors[0]), "params is required"
    saved = '{"enabled": ["offcurve_outside_bounds"], "params": {}}'
    path.write_text(saved)
    state = registry.Registry(tmp_path)
    assert state.enabled() == ("offcurve_outside_bounds",)
    painters = Painters()
    state.attach(painters, object(), lambda error, source: None)
    assert len(painters.calls) == 1, "the saved reporter should restore"
    state._save = lambda: (_ for _ in ()).throw(OSError("read-only"))
    with pytest.raises(OSError, match="read-only"):
        state.enable("duplicate_anchors")
    assert state.enabled() == ("offcurve_outside_bounds",)
    assert "duplicate_anchors" not in state._tokens
    assert painters.calls[-1] == ("remove", 2)
    assert path.read_text() == saved


def test_registry_disable_save_failure_keeps_reporter_active(tmp_path):
    state = registry.Registry(tmp_path)
    painters = Painters()
    state.attach(painters, object(), lambda e, p: None)
    state.enable("node_indexes")
    state._save = lambda: (_ for _ in ()).throw(OSError("read-only"))
    with pytest.raises(OSError, match="read-only"):
        state.disable("node_indexes")
    assert state.enabled() == ("node_indexes",)
    assert "node_indexes" in state._tokens
    assert not any(call[0] == "remove" for call in painters.calls)


def test_registry_detach_continues_and_save_error_survives_rollback_error(tmp_path):
    errors = []
    state = registry.Registry(tmp_path, lambda error, source: errors.append(str(error)))

    class BrokenPainters(Painters):
        def remove(self, token):
            super().remove(token)
            if token == 1 or getattr(self, "fail_all", False):
                raise TypeError("remove failed")

    painters = BrokenPainters()
    state.attach(painters, object(), lambda error, source: None)
    state.enable("center_lines")
    state.enable("duplicate_anchors")
    state.detach()
    assert ("remove", 2) in painters.calls
    assert state._tokens == {} and state._painters is None
    assert errors == ["remove failed"]

    state.attach(painters, object(), lambda error, source: None)
    painters.fail_all = True
    state._save = lambda: (_ for _ in ()).throw(OSError("save failed"))
    with pytest.raises(OSError, match="save failed"):
        state.enable("node_indexes")
    assert state.enabled() == ("center_lines", "duplicate_anchors")
    assert errors[-1] == "remove failed"


def test_registry_restores_other_reporters_when_one_constructor_fails(
    tmp_path, monkeypatch
):
    class Broken(Reporter):
        name, title = "broken", "Broken"

        def __init__(self):
            raise RuntimeError("plugin failed")

    path = tmp_path / "fontlab-plugmix.json"
    path.write_text('{"enabled": ["broken", "node_indexes"], "params": {}}')
    classes = registry.discover()
    classes["broken"] = Broken
    monkeypatch.setattr(registry, "discover", lambda sink: classes)
    errors = []
    state = registry.Registry(tmp_path, lambda error, source: errors.append(error))
    painters = Painters()
    state.attach(painters, object(), lambda error, source: None)
    assert len(painters.calls) == 1
    assert painters.calls[0][0].name == "node_indexes"
    assert isinstance(errors[0], RuntimeError)


def test_menu_check_state_tracks_registry_even_after_failure(tmp_path):
    state = registry.Registry(tmp_path)
    owner = Menus()
    tokens = menu.install(owner, state)
    action, callback = owner.actions[tokens["node_indexes"]]
    assert action.checked is False
    callback()
    assert action.checked is True
    state.toggle = lambda name: (_ for _ in ()).throw(OSError("disk"))
    action.setChecked(False)
    with pytest.raises(OSError):
        callback()
    assert action.checked is True


def test_menu_when_installed_then_view_reporters_submenu_lists_bare_titles(tmp_path):
    owner = Menus()
    tokens = menu.install(owner, registry.Registry(tmp_path))
    labels = {name: owner.titles[token] for name, token in tokens.items()}
    assert labels["show_background"] == "Background"
    assert labels["label_color"] == "Label Color"
    assert labels["show_stems"] == "Stems"
    assert labels["blindfold"] == "Blindfold"
    assert labels["node_count"] == "Node Count"
    [submenu] = owner.menus.values()
    assert (submenu.parent, submenu.title) == ("View", "Reporters")
    assert submenu.entries == [*sorted(labels.values()), "-", "Hide All"], submenu.entries


def test_menu_hide_all_when_reporters_on_then_all_disabled_and_unchecked(tmp_path):
    state = registry.Registry(tmp_path)
    owner = Menus()
    tokens = menu.install(owner, state)
    for name in ("node_indexes", "blindfold"):
        owner.actions[tokens[name]][1]()
    assert set(state.enabled()) == {"node_indexes", "blindfold"}
    [hide_all] = [cb for t, (_, cb) in owner.actions.items() if owner.titles[t] == "Hide All"]
    hide_all()
    assert state.enabled() == ()
    assert not any(owner.actions[token][0].checked for token in tokens.values())


def test_boot_install_is_idempotent_and_uninstall_preserves_preferences(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(boot, "_runtime", lambda: (object(), object(), Menus))
    monkeypatch.setattr(boot, "select_backend", lambda *args: Painters())

    class NoopHost:
        def __init__(self, *args):
            pass

        def install(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(boot, "ToolHost", NoopHost)
    monkeypatch.setattr(boot, "GeneralHost", NoopHost)
    monkeypatch.setattr(boot, "_state", None)
    boot.install(tmp_path)
    state = boot._state
    assert state is not None and len(state.menus.actions) == 47  # 39 reporters, Hide All, five filters, two panels
    boot.install(tmp_path)
    assert boot._state is state
    with pytest.raises(ValueError):
        boot.install(tmp_path / "other")
    state.reporters.enable("center_lines")
    boot.uninstall()
    assert state.painters.closed and state.menus.closed
    assert json.loads(state.reporters.path.read_text())["enabled"] == ["center_lines"]
    boot.uninstall()
    boot.install(tmp_path)
    assert "center_lines" in registry.enabled()
    boot.uninstall()


def test_boot_runtime_imports_are_lazy(monkeypatch):
    modules = {
        "PythonQt": object(),
        "fontlab": object(),
        "fontlabapp.qt.menus": NS(OwnedMenus=Menus),
    }
    monkeypatch.setattr(boot, "import_module", modules.__getitem__)
    assert boot._runtime() == (modules["PythonQt"], modules["fontlab"], Menus)


def test_boot_uninstall_keeps_owner_when_palette_refuses_close(monkeypatch):
    calls = []
    accepted = [False]

    def palette_close():
        calls.append("palette")
        return accepted[0]

    def owner(label):
        return NS(close=lambda: calls.append(label))

    state = NS(
        palettes=NS(close=palette_close),
        generals=owner("general"),
        tools=owner("tool"),
        filters=owner("filter"),
        menus=owner("menu"),
        reporters=NS(detach=lambda: calls.append("reporter"), listeners=[]),
        painters=owner("painter"),
    )
    monkeypatch.setattr(boot, "_state", state)
    boot.uninstall()
    assert boot._state is state and calls == ["palette"]
    accepted[0] = True
    boot.uninstall()
    assert boot._state is None
    assert calls == [
        "palette", "palette", "general", "tool", "filter", "menu", "reporter", "painter"
    ]


def test_boot_cleans_up_failed_install_and_error_sink_never_raises(
    tmp_path, monkeypatch
):
    class FailingMenus(Menus):
        def add_action(self, section, title, callback, *, checkable):
            raise RuntimeError("menu missing")

    monkeypatch.setattr(boot, "_runtime", lambda: (object(), object(), FailingMenus))
    monkeypatch.setattr(boot, "select_backend", lambda *args: Painters())
    monkeypatch.setattr(boot, "_state", None)
    with pytest.raises(RuntimeError, match="menu missing"):
        boot.install(tmp_path)
    assert boot._state is None
    boot._error(ValueError("bad"), object())


def test_boot_closes_backend_if_menu_constructor_fails(tmp_path, monkeypatch):
    class FailingMenus:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("menu owner unavailable")

    painters = Painters()
    monkeypatch.setattr(boot, "_runtime", lambda: (object(), object(), FailingMenus))
    monkeypatch.setattr(boot, "select_backend", lambda *args: painters)
    monkeypatch.setattr(boot, "_state", None)
    with pytest.raises(RuntimeError, match="menu owner unavailable"):
        boot.install(tmp_path)
    assert painters.closed and boot._state is None


def test_hide_all_when_save_fails_then_checkmarks_keep_persisted_state(tmp_path, monkeypatch):
    state = registry.Registry(tmp_path)
    owner = Menus()
    tokens = menu.install(owner, state)
    for name in ("blindfold", "node_indexes"):
        state.enable(name)
    before = state.path.read_bytes()
    monkeypatch.setattr(state, "_save", lambda: (_ for _ in ()).throw(OSError("disk")))
    [hide_all] = [cb for t, (_, cb) in owner.actions.items() if owner.titles[t] == "Hide All"]
    with pytest.raises(OSError, match="disk"):
        hide_all()
    assert state.path.read_bytes() == before
    assert set(state.enabled()) == {"blindfold", "node_indexes"}
    assert {name for name, token in tokens.items() if owner.action(token).checked} == set(state.enabled())


def test_hide_all_when_action_removed_then_remaining_checks_still_sync():
    disabled = []
    action = Action()
    state = NS(enabled=lambda: ("missing_plugin", "reporter"), disable=disabled.append)
    owner = NS(action=lambda token: action if token == 2 else None)
    menu._hide_all(owner, state, {"removed_action": 1, "reporter": 2})
    assert disabled == ["reporter"] and action.checked
