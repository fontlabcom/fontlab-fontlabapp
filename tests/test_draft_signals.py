# this_file: tests/test_draft_signals.py
"""Exact owned signal pairs, bool failures and a retained Close retry route."""

import pytest

from fontlabapp.core.signals.scope import Scope


class Signal:
    def __init__(self, *, connect_result=None, disconnect_result=None):
        self.connect_result, self.disconnect_result = connect_result, disconnect_result
        self.slots = []

    def connect(self, slot):
        if self.connect_result is False:
            return False
        self.slots.append(slot)
        return self.connect_result

    def disconnect(self, slot):
        if self.disconnect_result is False:
            return False
        if isinstance(self.disconnect_result, Exception):
            raise self.disconnect_result
        self.slots.remove(slot)
        return self.disconnect_result


def test_connect_records_only_success_and_retains_unrelated_slots():
    errors, calls = [], []
    scope = Scope(errors.append)
    signal = Signal()
    other = lambda: calls.append("other")
    signal.connect(other)
    scope.connect(signal, lambda: calls.append("owned"))
    signal.slots[-1]()
    assert calls == ["owned"]
    assert scope.finish() and signal.slots == [other]
    assert scope.finish() and scope.dead and not errors
    with pytest.raises(RuntimeError, match="closed"):
        scope.connect(signal, lambda: None)


def test_false_connect_is_not_recorded():
    scope = Scope(lambda error: None)
    with pytest.raises(RuntimeError, match="connection"):
        scope.connect(Signal(connect_result=False), lambda: None)
    assert not scope.records and scope.finish()


@pytest.mark.parametrize("failure", [False, ValueError("disconnect refused")])
def test_failed_disconnect_retains_pair_owner_and_close_button_until_retry(failure):
    errors, calls = [], []
    scope = Scope(errors.append)
    normal, close = Signal(disconnect_result=failure), Signal()
    scope.connect(normal, lambda: calls.append("normal"))
    scope.connect(close, lambda: calls.append("close"), closing=True, retry=True)
    normal_slot, close_slot = normal.slots[0], close.slots[0]
    assert not scope.finish() and not scope.dead and len(scope.records) == 2
    normal_slot()
    close_slot()
    assert calls == ["close"] and errors
    normal.disconnect_result = None
    assert scope.finish() and not scope.records and not normal.slots and not close.slots
    close_slot()
    assert calls == ["close"], "Successful close fences even queued Close callbacks"


def test_failed_last_button_disconnect_can_retry_and_destroy_drops_dead_wrappers():
    scope = Scope(lambda error: None)
    signal = Signal(disconnect_result=False)
    scope.connect(signal, lambda: None, closing=True, retry=True)
    assert not scope.finish() and len(scope.records) == 1
    assert scope.finish(destroyed=True) and not scope.records and scope.dead
    signal.slots[0]()


def test_callback_errors_report_once_and_late_normal_callbacks_are_fenced():
    errors = []
    scope = Scope(errors.append)
    signal = Signal()

    def fail(*args):
        raise ValueError("callback error")

    scope.connect(signal, fail)
    slot = signal.slots[0]
    slot("argument")
    assert len(errors) == 1 and str(errors[0]) == "callback error"
    assert scope.finish()
    slot("late")
    assert len(errors) == 1


def test_reporting_failure_stays_inside_callback_and_preserves_failed_records():
    def report(error):
        raise ValueError("report failed")

    scope = Scope(report)
    signal = Signal(disconnect_result=False)
    scope.connect(signal, lambda: 1 / 0)
    signal.slots[0]()
    assert "reporting failed" in scope.error
    assert not scope.finish() and len(scope.records) == 1
    assert "reporting failed" in scope.error
