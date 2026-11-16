# this_file: tests/test_issue205_root_hotkeys.py
"""Lazy public dispatch and keyboard-event filtering preserve native contracts."""

import importlib
import sys
from types import ModuleType, SimpleNamespace as NS

import pytest


def test_root_when_public_names_requested_then_exact_services_native_values_and_refusals(
    monkeypatch,
):
    import fontlabapp as root

    marker = object()
    application = NS(
        **{
            name: marker
            for name in ("ApplicationPaths", "Versions", "ApplicationUI", "PrefLib")
        }
    )
    application.Application = lambda: marker
    host = NS(
        **{name: marker for name in ("menu", "actions", "panels", "glyph_actions")}
    )
    calls = []

    def load(name):
        calls.append(name)
        return {
            "fontlabapp.core.controls": NS(FontLab=marker),
            "fontlabapp.core.application": application,
            "fontlabapp.core.host": host,
            "fontlabapp.qtsafe": marker,
        }[name]

    monkeypatch.setattr(root, "import_module", load)
    pythonqt = NS(Qt=marker, QtCore=marker, QtGui=marker)
    natives = {
        "PythonQt": pythonqt,
        "fontlab": NS(First=marker),
        "FL": NS(Second=marker),
        "fontgate": marker,
    }
    monkeypatch.setattr(root, "_native", natives.__getitem__)
    names = [
        "FontLab",
        "Application",
        "ApplicationPaths",
        "Versions",
        "ApplicationUI",
        "PrefLib",
        "app",
        "menu",
        "actions",
        "panels",
        "glyph_actions",
        "FL",
        "fontgate",
        "fontlab",
        "PythonQt",
        "Qt",
        "QtCore",
        "QtGui",
        "First",
        "Second",
        "qtsafe",
    ]
    for name in names:
        monkeypatch.setitem(vars(root), name, object())
        expected = (
            application.Application
            if name == "Application"
            else natives.get(name, marker)
        )
        assert root.__getattr__(name) is expected, name
    assert "fontlabapp.qtsafe" in calls and "fontlabapp.core.controls" in calls
    for name in ("_unexported", "NoNativeValue"):
        with pytest.raises(AttributeError, match=name):
            root.__getattr__(name)


def test_native_when_import_fails_then_missing_host_and_missing_dependency_stay_distinct(
    monkeypatch,
):
    import fontlabapp as root

    error = ModuleNotFoundError("missing host", name="fontlab")

    def missing(name):
        raise error

    monkeypatch.setattr(root, "import_module", missing)
    with pytest.raises(RuntimeError, match="inside FontLab") as result:
        root._native("fontlab")
    assert result.value.__cause__ is error
    dependency = ModuleNotFoundError("missing child", name="dependency")
    error = dependency
    with pytest.raises(ModuleNotFoundError) as result:
        root._native("fontlab")
    assert result.value is dependency


def test_lazy_service_packages_when_requested_then_load_only_the_chosen_platform_and_component(
    monkeypatch,
):
    app = importlib.import_module("fontlabapp.core.application")
    calls = []
    marker = object()
    monkeypatch.setattr(
        app,
        "import_module",
        lambda path, package: calls.append((path, package))
        or NS(**{n: marker for n in app.__all__}),
    )
    for name, child in app._COMPONENTS.items():
        monkeypatch.setitem(vars(app), name, object())
        assert app.__getattr__(name) is marker
        assert calls[-1] == ("." + child, app.__name__)
    with pytest.raises(AttributeError):
        app.__getattr__("unknown")
    hotkey = importlib.import_module("fontlabapp.core.hotkey")
    monkeypatch.setattr(
        hotkey,
        "_importlib",
        NS(import_module=lambda name: calls.append(name) or NS(HotkeyManager=marker)),
    )
    for platform, error in (
        ("darwin", None),
        ("win32", NotImplementedError),
        ("linux", AttributeError),
    ):
        monkeypatch.setattr(hotkey, "_sys", NS(platform=platform))
        if error:
            with pytest.raises(error):
                hotkey.__getattr__("HotkeyManager")
        else:
            assert hotkey.__getattr__("HotkeyManager") is marker
            assert calls[-1] == hotkey.__name__ + ".mac"
    with pytest.raises(AttributeError):
        hotkey.__getattr__("unknown")


def test_hotkeys_when_native_events_arrive_then_callbacks_filter_and_timeout_rearms(
    monkeypatch,
):
    import fontlabapp
    from _cov_qt import Signal

    quit_signal = Signal()
    fake_app = NS(qapp=NS(aboutToQuit=quit_signal))
    monkeypatch.setitem(vars(fontlabapp), "app", fake_app)
    quartz = ModuleType("Quartz")
    constants = {
        "kCGEventKeyDown": 10,
        "kCGEventKeyUp": 11,
        "kCGEventFlagsChanged": 12,
        "kCGEventTapDisabledByTimeout": 13,
        "kCGEventFlagMaskAlternate": 1,
        "kCGEventFlagMaskCommand": 2,
        "kCGEventFlagMaskControl": 4,
        "kCGEventFlagMaskShift": 8,
        "kCGKeyboardEventKeycode": 99,
    }
    for name, value in constants.items():
        setattr(quartz, name, value)
    enabled = []
    quartz.CGEventGetIntegerValueField = lambda event, key: event[0]
    quartz.CGEventGetFlags = lambda event: event[1]
    quartz.CGEventTapEnable = lambda tap, flag: enabled.append((tap, flag))
    monkeypatch.setitem(sys.modules, "Quartz", quartz)
    base = importlib.import_module("fontlabapp.core.hotkey.manager")
    monkeypatch.setattr(base, "app", fake_app)
    module = importlib.import_module("fontlabapp.core.hotkey.mac")
    monkeypatch.setattr(module, "Quartz", quartz)
    manager = module.HotkeyManager()
    seen = []
    manager.on(
        "A", lambda: seen.append("down") or False, lambda: seen.append("up") or False
    )
    for flags in (0, 15):
        assert manager._handle_event((0, flags), 10) is True
        assert manager._handle_event((0, flags), 11) is True
    assert seen == ["down", "up", "down", "up"]
    assert manager._handle_event_tap(None, 10, (0, 0), None) is None
    event = (999, 0)
    assert manager._handle_event_tap(None, 10, event, None) is event
    assert manager._handle_event_tap(None, 13, event, None) is event
    assert enabled == [(None, True)]
    assert manager._handle_event((0, 0), 12) is None
    manager._tap = object()
    with pytest.raises(RuntimeError, match="already running"):
        manager.run()
    ordinary = base.HotkeyManager()
    ordinary.on("A", lambda: True)
    before = ordinary._handlers_key_down["A"][:]
    assert ordinary.run() is None and ordinary.stop() is None
    assert ordinary._handlers_key_down["A"] == before
