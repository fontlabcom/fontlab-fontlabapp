# this_file: tests/test_fontui_follow_qt.py
"""follow_changes on a real Qt event loop (PySide6 QtCore stands in for PythonQt).

Real QTimers and real signals: timing, coalescing, feedback and re-entry are
measured, not simulated. FontLab's flItems.qobject is replaced by a QObject
with the measured signal signatures (signal-probe1).
"""

import importlib
import sys
import time
from types import SimpleNamespace

import pytest
from PySide6 import QtCore

APP = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])


class Items(QtCore.QObject):
    historyChanged = QtCore.Signal()
    historyIndexChanged = QtCore.Signal(int)
    glyphUpdated = QtCore.Signal(int, int)
    glyphsUpdated = QtCore.Signal(int, object)
    signalPackageClosed = QtCore.Signal(object)


def spin(ms):
    """Run the real event loop for ms milliseconds."""
    deadline = time.monotonic() + ms / 1000
    while time.monotonic() < deadline:
        APP.processEvents(QtCore.QEventLoop.AllEvents, 5)
        time.sleep(0.001)


class Owner:
    def __init__(self):
        self.widget = QtCore.QObject()
        self.connections = []

    def connect(self, signal, slot):
        signal.connect(slot)
        self.connections.append((signal, slot))

    def close(self):
        for signal, slot in reversed(self.connections):
            signal.disconnect(slot)
        self.connections.clear()


def native(font_id):
    return SimpleNamespace(_backend=SimpleNamespace(font_id=font_id))


@pytest.fixture
def env(monkeypatch):
    items = Items()
    monkeypatch.setitem(
        sys.modules, "PythonQt", SimpleNamespace(QtCore=QtCore, QtGui=SimpleNamespace())
    )
    monkeypatch.setitem(
        sys.modules,
        "fontlab",
        SimpleNamespace(
            flItems=SimpleNamespace(instance=lambda: SimpleNamespace(qobject=items))
        ),
    )
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.lifecycle", raising=False)
    module = importlib.import_module("fontlabapp.fontui.lifecycle")
    owners = []

    def follow(callback, fonts):
        owner = Owner()
        owners.append(owner)
        module.follow_changes(owner, callback, fonts)
        return owner

    yield SimpleNamespace(module=module, items=items, follow=follow)
    for owner in owners:
        owner.close()
    sys.modules.pop("fontlabapp.fontui.lifecycle", None)


def test_burst_gives_one_refresh_after_the_delay(env):
    calls = []
    env.follow(lambda: calls.append(time.monotonic()), lambda: [native(7)])
    began = time.monotonic()
    for _ in range(10):
        env.items.historyChanged.emit()
    spin(env.module.CHANGE_DELAY_MS * 3)
    assert len(calls) == 1, calls
    assert calls[0] - began >= env.module.CHANGE_DELAY_MS / 1000 * 0.9


def test_steady_signals_do_not_starve_refreshes(env):
    """Events every 50 ms for 1 s: refreshes keep coming, each within the bound."""
    calls, emitted = [], []
    env.follow(lambda: calls.append(time.monotonic()), lambda: [native(7)])
    ticker = QtCore.QTimer()
    ticker.setInterval(50)
    ticker.timeout.connect(
        lambda: (emitted.append(time.monotonic()), env.items.historyChanged.emit())
    )
    ticker.start()
    spin(1000)
    ticker.stop()
    spin(env.module.CHANGE_DELAY_MS * 2)
    delay = env.module.CHANGE_DELAY_MS / 1000
    assert len(calls) >= 1 / (delay * 2), (
        f"only {len(calls)} refreshes for {len(emitted)} events"
    )
    for event in emitted:  # every event is followed by a refresh within the bound
        after = [c for c in calls if c >= event]
        assert after and after[0] - event <= delay * 2.5, (event, after[:1])


def test_signals_emitted_by_our_own_refresh_are_ignored(env):
    calls = []

    def refresh():
        calls.append(1)
        env.items.historyChanged.emit()  # feedback from reading/applying
        env.items.glyphUpdated.emit(7, 1)

    env.follow(refresh, lambda: [native(7)])
    env.items.historyChanged.emit()
    spin(env.module.CHANGE_DELAY_MS * 6)
    assert calls == [1], f"{len(calls)} refreshes from one external change"


def test_refresh_is_never_reentered(env):
    depth, worst, calls = [0], [0], []

    def refresh():
        depth[0] += 1
        worst[0] = max(worst[0], depth[0])
        calls.append(1)
        if len(calls) == 1:
            env.items.historyChanged.emit()
            spin(env.module.CHANGE_DELAY_MS * 2)  # nested event loop inside refresh
        depth[0] -= 1

    env.follow(refresh, lambda: [native(7)])
    env.items.historyChanged.emit()
    spin(env.module.CHANGE_DELAY_MS * 5)
    assert worst[0] == 1, f"refresh nested {worst[0]} deep"


def test_other_document_glyph_signal_is_ignored(env):
    calls = []
    env.follow(lambda: calls.append(1), lambda: [native(7)])
    env.items.glyphUpdated.emit(8, 1)
    spin(env.module.CHANGE_DELAY_MS * 3)
    assert not calls


def test_initially_empty_owner_follows_once_fonts_appear(env):
    fonts, calls = [], []
    env.follow(lambda: calls.append(1), lambda: fonts)
    env.items.historyChanged.emit()
    spin(env.module.CHANGE_DELAY_MS * 3)
    assert not calls, "no FontLab font yet: nothing to refresh"
    fonts.append(native(7))
    env.items.historyChanged.emit()
    spin(env.module.CHANGE_DELAY_MS * 3)
    assert calls == [1]


def test_close_disconnects_and_a_pending_refresh_never_runs(env):
    calls = []
    owner = env.follow(lambda: calls.append(1), lambda: [native(7)])
    env.items.historyChanged.emit()
    owner.close()
    spin(env.module.CHANGE_DELAY_MS * 3)
    env.items.historyChanged.emit()
    spin(env.module.CHANGE_DELAY_MS * 3)
    assert not calls


def test_outside_fontlab_nothing_is_connected(env, monkeypatch):
    monkeypatch.setitem(sys.modules, "fontlab", None)
    owner = Owner()
    assert env.module.follow_changes(owner, lambda: None, lambda: [native(7)]) == 0
    assert not owner.connections


def test_fontport_font_reloads_before_callback(env):
    """Fontport 1.x: no change notifications; RFont.refresh() drops stale handles."""
    order, font = [], native(7)
    font.refresh = lambda: order.append("font.refresh")
    env.follow(lambda: order.append("control.refresh"), lambda: [font])
    env.items.historyIndexChanged.emit(3)
    spin(env.module.CHANGE_DELAY_MS * 3)
    assert order == ["font.refresh", "control.refresh"]


def test_detached_font_refresh_is_never_called(env):
    order, detached = [], SimpleNamespace(refresh=lambda: order.append("detached"))
    env.follow(lambda: order.append("control"), lambda: [native(7), detached])
    env.items.historyChanged.emit()
    spin(env.module.CHANGE_DELAY_MS * 3)
    assert order == ["control"]


def test_fontport_invalidate_is_preferred_when_present(env):
    order, font = [], native(7)
    font.invalidate = lambda: order.append("font.invalidate")
    font.refresh = lambda: order.append("font.refresh")
    env.follow(lambda: order.append("control.refresh"), lambda: [font])
    env.items.historyChanged.emit()
    spin(env.module.CHANGE_DELAY_MS * 3)
    assert order == ["font.invalidate", "control.refresh"]


def test_two_followers_do_not_feed_each_other(env):
    """Each refresh emits historyChanged (as a write would); one change, one refresh each."""
    calls = {"a": 0, "b": 0}

    def refresher(name):
        def refresh():
            calls[name] += 1
            env.items.historyChanged.emit()

        return refresh

    env.follow(refresher("a"), lambda: [native(7)])
    env.follow(refresher("b"), lambda: [native(7)])
    env.items.historyChanged.emit()
    spin(env.module.CHANGE_DELAY_MS * 7)
    assert calls == {"a": 1, "b": 1}, calls


def test_failing_font_reload_is_isolated_and_controls_still_refresh(env, capsys):
    order = []
    closed, live = native(7), native(8)

    def fail():
        order.append("closed.invalidate")
        raise RuntimeError("Font document has been closed")

    closed.invalidate = fail
    live.invalidate = lambda: order.append("live.invalidate")
    env.follow(lambda: order.append("control.refresh"), lambda: [closed, live])
    env.items.historyChanged.emit()
    spin(env.module.CHANGE_DELAY_MS * 3)
    assert order == ["closed.invalidate", "live.invalidate", "control.refresh"]
    assert "Font document has been closed" not in capsys.readouterr().err


class Capability(NotImplementedError):
    def __init__(self, capability):
        super().__init__(f"{capability}: fixture")
        self.capability = capability


def test_unfinished_script_edits_are_kept_and_noted(env):
    """Fontport refuses invalidate() while a script has unfinished point edits."""
    order, busy, other = [], native(7), native(8)

    def refuse():
        order.append("busy.invalidate")
        raise Capability("glyph.incompleteContours")

    busy.invalidate = refuse
    busy.refresh = lambda: order.append("busy.refresh")  # must never run instead
    other.invalidate = lambda: order.append("other.invalidate")
    owner = env.follow(lambda: order.append("control.refresh"), lambda: [busy, other])
    owner.diagnostic = SimpleNamespace(text="Ready.")
    owner.diagnostic.setText = lambda value: setattr(owner.diagnostic, "text", value)
    env.items.historyChanged.emit()
    spin(env.module.CHANGE_DELAY_MS * 3)
    assert order == ["busy.invalidate", "other.invalidate", "control.refresh"]
    assert "unfinished script edits" in owner.diagnostic.text
    assert owner.diagnostic.text.startswith("Ready.")
