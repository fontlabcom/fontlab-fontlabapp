# this_file: tests/test_hotkey.py
"""Hotkey lifecycle checks without activating global desktop event capture."""
import importlib
import sys
import types
import pytest


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS event-tap lifecycle")
def test_mac_hotkey_stop_is_safe_before_run_and_repeatable(monkeypatch):
    import fontlabapp
    calls = []
    fakeapp = types.SimpleNamespace(qapp=types.SimpleNamespace(aboutToQuit=types.SimpleNamespace(connect=lambda callback: calls.append('connected'))))
    monkeypatch.setitem(vars(fontlabapp), 'app', fakeapp)
    quartz = types.ModuleType('Quartz')
    constants = ['kCGSessionEventTap', 'kCGHeadInsertEventTap', 'kCGEventTapOptionDefault', 'kCGEventKeyDown', 'kCGEventKeyUp', 'kCGEventFlagsChanged', 'kCFAllocatorDefault', 'kCFRunLoopCommonModes']
    for name in constants: setattr(quartz, name, 0)
    quartz.CGEventMaskBit = lambda value: 1
    tap = object()
    quartz.CGEventTapCreate = lambda *args: tap
    quartz.CFMachPortCreateRunLoopSource = lambda *args: object()
    quartz.CFRunLoopGetCurrent = lambda: 'loop'
    quartz.CFRunLoopAddSource = lambda *args: None
    quartz.CGEventTapEnable = lambda *args: None
    quartz.CFRunLoopRun = lambda: None
    quartz.CFRunLoopStop = lambda loop: calls.append('stop')
    quartz.CFMachPortInvalidate = lambda tap: calls.append('invalidate')
    quartz.CFRunLoopRemoveSource = lambda *args: calls.append('remove-source')
    monkeypatch.setitem(sys.modules, 'Quartz', quartz)
    # Import the platform implementation explicitly without requesting native access.
    module = importlib.import_module('fontlabapp.core.hotkey.mac')
    manager = module.HotkeyManager()
    manager.stop()
    assert calls == ['connected']
    manager.run()
    manager.stop()
    manager.stop()
    assert calls == ['connected', 'stop', 'invalidate', 'remove-source']

    quartz.CGEventTapCreate = lambda *args: None
    with pytest.raises(RuntimeError, match='Accessibility'):
        manager.run()
    manager.stop()
    assert calls == ['connected', 'stop', 'invalidate', 'remove-source']
