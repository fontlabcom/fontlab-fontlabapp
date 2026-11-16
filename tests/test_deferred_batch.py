# this_file: tests/test_deferred_batch.py
"""Ordered zero-timer batches retain source scheduling and failure boundaries."""
from types import SimpleNamespace
import subprocess
import sys

import pytest
from fontlabapp.core.signals.deferred import DeferredBatch


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)


class Timer:
    def __init__(self):
        self.timeout = Signal()
        self.starts = 0

    def setSingleShot(self, value):
        self.single = value

    def setInterval(self, value):
        self.interval = value

    def start(self):
        self.starts += 1

    def fire(self):
        for slot in self.timeout.slots:
            slot()


def batch(process):
    return DeferredBatch(SimpleNamespace(QtCore=SimpleNamespace(QTimer=Timer)), process)


def test_schedule_when_duplicate_equal_targets_then_restarts_but_processes_once():
    calls = []
    work = batch(calls.append)
    first, equal = [1], [1]
    work.schedule(first)
    work.schedule(equal)
    work.schedule([2])
    assert work.pending == [first, [2]]
    assert work.pending[0] is first
    assert work.timer.starts == 3
    assert work.timer.single is True and work.timer.interval == 0
    assert len(work.timer.timeout.slots) == 1 and calls == []
    work.timer.fire()
    assert calls == [first, [2]] and work.pending == []
    work.timer.fire()
    assert calls == [first, [2]], 'Empty or repeated timeout does no work'


def test_drain_when_callback_schedules_more_then_detaches_current_batch():
    observed = []
    def process(value):
        observed.append((value, list(work.pending)))
        if value == 'first':
            work.schedule('next')
    work = batch(process)
    work.schedule('first')
    work.schedule('last')
    retained = work.pending
    work.timer.fire()
    assert observed == [('first', []), ('last', ['next'])]
    assert retained == ['first', 'last'] and work.pending == ['next']
    work.timer.fire()
    assert observed[-1] == ('next', []) and work.pending == []


def test_drain_when_nested_event_loop_then_new_batch_runs_once():
    calls = []
    def process(value):
        calls.append(value)
        if value == 'first':
            work.schedule('nested')
            work.timer.fire()
    work = batch(process)
    work.schedule('first')
    work.schedule('last')
    work.timer.fire()
    assert calls == ['first', 'nested', 'last']
    work.timer.fire()
    assert calls == ['first', 'nested', 'last']


@pytest.mark.parametrize('exception', [RuntimeError('callback'), KeyboardInterrupt('callback')])
def test_drain_when_process_fails_then_same_exception_and_no_retry_of_detached_tail(exception):
    calls = []
    def process(value):
        calls.append(value)
        work.schedule('new')
        raise exception
    work = batch(process)
    work.schedule('first')
    work.schedule('unattempted')
    with pytest.raises(type(exception)) as raised:
        work.timer.fire()
    assert raised.value is exception
    assert calls == ['first'] and work.pending == ['new']


def test_schedule_when_start_fails_then_queued_target_is_retained():
    work = batch(lambda value: None)
    error = RuntimeError('timer start')
    def start():
        raise error
    work.timer.start = start
    with pytest.raises(RuntimeError) as raised:
        work.schedule('queued')
    assert raised.value is error and work.pending == ['queued']


def test_schedule_when_comparison_fails_then_no_append_or_restart():
    class Target:
        def __eq__(self, other):
            raise ValueError('comparison')
    work = batch(lambda value: None)
    original = Target()
    work.schedule(original)
    with pytest.raises(ValueError, match='comparison'):
        work.schedule(object())
    assert len(work.pending) == 1 and work.pending[0] is original and work.timer.starts == 1


@pytest.mark.parametrize('step', ['construct', 'single', 'interval', 'connect'])
def test_setup_when_binding_operation_fails_then_exact_error_escapes(step):
    error = RuntimeError(step)
    calls = []
    def operation(name):
        calls.append(name)
        if name == step:
            raise error
    class BrokenTimer(Timer):
        def __init__(self):
            operation('construct')
            super().__init__()
            self.timeout.connect = lambda slot: operation('connect')
        def setSingleShot(self, value):
            assert value is True
            operation('single')
        def setInterval(self, value):
            assert value == 0
            operation('interval')
    with pytest.raises(RuntimeError) as raised:
        DeferredBatch(SimpleNamespace(QtCore=SimpleNamespace(QTimer=BrokenTimer)), lambda value: None)
    assert raised.value is error
    assert calls == ['construct', 'single', 'interval', 'connect'][:['construct', 'single', 'interval', 'connect'].index(step)+1]


def test_import_when_no_binding_loaded_then_has_no_host_or_consumer_dependency():
    code = 'import sys; from fontlabapp.core.signals.deferred import DeferredBatch; assert not any(n.split(".")[0] in {"PythonQt","PySide6","PyQt5","fontlab","fontlab_glyport","fontlab_fontport"} for n in sys.modules)'
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
