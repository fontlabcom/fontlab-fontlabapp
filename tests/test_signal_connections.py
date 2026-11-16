# this_file: tests/test_signal_connections.py
"""Exact connection ownership, reverse teardown and caller error policy."""

import weakref
from types import SimpleNamespace

import pytest
from fontlabapp.core.signals.connections import disconnect_connections, track_connection


class Signal:
    def __init__(self, log, name, error=None):
        self.log, self.name, self.error = log, name, error
        self.listeners = []

    def connect(self, slot):
        if self.error:
            raise self.error
        self.listeners.append(slot)

    def disconnect(self, slot):
        self.log.append((self.name, slot))
        if self.error:
            raise self.error
        self.listeners.remove(slot)


def test_track_when_success_then_keeps_exact_signal_slot_and_duplicate_order():
    pairs, log = [], []
    signal = Signal(log, "owned")
    slot = lambda *args: None
    for _ in range(2):
        track_connection(pairs, signal, slot)
    assert pairs == [(signal, slot), (signal, slot)]
    assert signal.listeners == [slot, slot]
    disconnect_connections(pairs, pytest.fail)
    assert pairs == [] and signal.listeners == []
    assert log == [("owned", slot), ("owned", slot)]


@pytest.mark.parametrize("error", [ValueError("connect"), KeyboardInterrupt()])
def test_track_when_connect_raises_then_retains_no_unconnected_pair(error):
    pairs = []
    with pytest.raises(type(error)) as caught:
        track_connection(pairs, Signal([], "bad", error), lambda: None)
    assert caught.value is error and pairs == []


def test_disconnect_when_empty_or_repeated_then_does_nothing():
    for _ in range(2):
        disconnect_connections([], pytest.fail)


def test_disconnect_when_multiple_then_reverse_order_and_other_listeners_survive():
    pairs, log = [], []
    signal = Signal(log, "one")
    owned, other = lambda: None, lambda: None
    signal.connect(other)
    track_connection(pairs, signal, owned)
    second = Signal(log, "two")
    track_connection(pairs, second, other)
    disconnect_connections(pairs, pytest.fail)
    assert log == [("two", other), ("one", owned)]
    assert signal.listeners == [other] and second.listeners == [] and not pairs


def test_disconnect_when_error_then_reports_exact_error_and_drains_remaining():
    pairs, log, errors = [], [], []
    slot = lambda: None
    first, last = Signal(log, "first"), Signal(log, "last")
    track_connection(pairs, first, slot)
    track_connection(pairs, last, slot)
    last.error = ValueError("already removed")
    disconnect_connections(pairs, errors.append)
    assert errors == [last.error] and not pairs
    assert log == [("last", slot), ("first", slot)]


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(3)])
def test_disconnect_when_base_exception_then_propagates_and_keeps_unattempted(error):
    pairs, log = [], []
    slot = lambda: None
    first, last = Signal(log, "first"), Signal(log, "last")
    track_connection(pairs, first, slot)
    track_connection(pairs, last, slot)
    last.error = error
    with pytest.raises(type(error)) as caught:
        disconnect_connections(pairs, pytest.fail)
    assert caught.value is error and pairs == [(first, slot)]
    assert log == [("last", slot)]


def test_disconnect_when_report_raises_then_preserves_unattempted_connections():
    pairs, log = [], []
    slot = lambda: None
    first, last = Signal(log, "first"), Signal(log, "last")
    track_connection(pairs, first, slot)
    track_connection(pairs, last, slot)
    last.error = ValueError("removed")
    failure = RuntimeError("sink failed")

    def report(error):
        assert error is last.error
        raise failure

    with pytest.raises(RuntimeError) as caught:
        disconnect_connections(pairs, report)
    assert caught.value is failure and pairs == [(first, slot)]


def test_disconnect_when_report_adds_connection_then_drains_new_pair_too():
    pairs, log = [], []
    slot = lambda: None
    old, new = Signal(log, "old"), Signal(log, "new")
    track_connection(pairs, old, slot)
    old.error = ValueError("removed")
    disconnect_connections(pairs, lambda error: track_connection(pairs, new, slot))
    assert not pairs and new.listeners == []
    assert log == [("old", slot), ("new", slot)]


def test_disconnect_when_success_then_releases_slot_target():
    class Target:
        def slot(self):
            pass

    target = Target()
    ref = weakref.ref(target)
    signal = Signal([], "owned")
    pairs = []
    track_connection(pairs, signal, target.slot)
    del target
    assert ref() is not None
    disconnect_connections(pairs, pytest.fail)
    signal.log.clear()
    assert ref() is None


def test_track_when_signal_returns_false_then_preserves_binding_return_semantics():
    """Bindings return None, bool or Connection; the old callers ignored it."""
    pairs = []
    signal = SimpleNamespace(connect=lambda slot: False)
    slot = lambda: None
    track_connection(pairs, signal, slot)
    assert pairs == [(signal, slot)]
