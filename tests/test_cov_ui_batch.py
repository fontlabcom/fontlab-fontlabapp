# this_file: tests/test_cov_ui_batch.py
"""BatchPanel controls offscreen: validation, polling, cancel, finish and close."""

from types import SimpleNamespace
from typing import Any

import pytest

import _cov_qt as fq

ROW = {
    "index": 1,
    "total": 2,
    "source": "/src/a.ufo",
    "destination": "/dst/a-transformed.ufo",
    "ok": True,
    "error": None,
}


class FakeProcess:
    """Stands in for BatchProcess: scripted rows, no child."""

    made: list = []

    def __init__(self, python: str, jobs: list, recipe: dict) -> None:
        self.python, self.jobs, self.recipe = python, jobs, recipe
        self.rows: list[dict] = []
        self.done = False
        self.read_error: Exception | None = None
        self.tail_error: Exception | None = None
        self.child = SimpleNamespace(returncode=0)
        self.released = False
        self.cancel_calls = 0
        FakeProcess.made.append(self)

    def read(self) -> list[dict]:
        if self.read_error:
            raise self.read_error
        rows, self.rows = self.rows, []
        return rows

    def check_tail(self) -> None:
        if self.tail_error:
            raise self.tail_error

    def failure(self) -> str:
        return "child exploded"

    def release(self) -> None:
        self.released = True

    def cancel(self) -> None:
        self.cancel_calls += 1


@pytest.fixture
def bmod(monkeypatch):
    handle = fq.install(monkeypatch)
    module = handle.load("fontlabapp.fontui.batch")
    FakeProcess.made = []
    supervised: list[tuple] = []
    monkeypatch.setattr(module, "BatchProcess", FakeProcess)
    monkeypatch.setattr(module, "supervise", lambda *a: supervised.append(a))
    module.supervised = supervised
    monkeypatch.delenv(module.PYTHON_ENV, raising=False)
    yield module
    fq.release()


def make(module: Any, tmp_path: Any, **kwargs: Any):
    from fontlab_fontport.recipe import Recipe

    kwargs.setdefault("python", "py3")
    panel = module.BatchPanel(lambda: Recipe(), None, kwargs.pop("on_finish", None), **kwargs)
    panel.runner = SimpleNamespace(
        run=lambda jobs, recipe: SimpleNamespace(close=lambda: None)
    )
    panel.set_sources(["/src/a.ufo", "/src/b.ufo"])
    panel.destination_control.setText(str(tmp_path))
    return panel


def test_init_when_built_then_idle_with_cancel_disabled(bmod, tmp_path):
    panel = make(bmod, tmp_path)
    assert panel.status.text == "Choose source UFOs and a destination folder.", (
        "idle panel prompts for sources and destination"
    )
    assert panel.start_button.enabled, "start is available when idle"
    assert not panel.cancel_button.enabled, "cancel is disabled when idle"
    assert panel.running is False, "a new panel is not running"


def test_set_sources_when_paths_given_then_list_shows_strings(bmod, tmp_path):
    panel = make(bmod, tmp_path)
    panel.set_sources([tmp_path / "x.ufo"])
    assert panel.sources == [str(tmp_path / "x.ufo")], "paths are stored as strings"
    assert [i.text() for i in panel.source_list.items] == panel.sources, (
        "list widget mirrors the stored sources"
    )


def test_add_button_when_directory_chosen_then_appended(bmod, tmp_path, monkeypatch):
    panel = make(bmod, tmp_path)
    monkeypatch.setattr(fq.FakeFileDialog, "path", "/new/c.ufo")
    panel.add_button.clicked.emit()
    assert panel.sources[-1] == "/new/c.ufo", "chosen directory is appended last"
    assert len(panel.sources) == 3, "exactly one source was added"


def test_add_button_when_dialog_cancelled_then_sources_unchanged(bmod, tmp_path, monkeypatch):
    panel = make(bmod, tmp_path)
    monkeypatch.setattr(fq.FakeFileDialog, "path", "")
    panel.add_button.clicked.emit()
    assert len(panel.sources) == 2, "cancelling the dialog adds nothing"


def test_start_when_no_python_then_refused_with_hint(bmod, tmp_path):
    panel = make(bmod, tmp_path, python=None)
    assert panel.start() is False, "start is refused without an interpreter"
    assert panel.status.text.startswith("Not started: Set FONTLABAPP_BATCH_PYTHON"), (
        "status names the environment variable to set"
    )
    assert FakeProcess.made == [], "no child is spawned without an interpreter"


def test_start_when_env_names_python_then_it_is_used(bmod, tmp_path, monkeypatch):
    monkeypatch.setenv(bmod.PYTHON_ENV, "env-py")
    panel = make(bmod, tmp_path, python=None)
    assert panel.start() is True, "the environment interpreter allows the start"
    assert FakeProcess.made[0].python == "env-py", "the child uses the environment interpreter"


def test_start_when_no_destination_then_refused(bmod, tmp_path):
    panel = make(bmod, tmp_path)
    panel.destination_control.setText("  ")
    assert panel.start() is False, "blank destination refuses the start"
    assert panel.status.text == "Not started: Choose a destination folder", (
        "status asks for a destination folder"
    )


def test_start_when_recipe_invalid_then_refused_before_spawn(bmod, tmp_path):
    panel = make(bmod, tmp_path)

    def bad() -> Any:
        raise ValueError("xx: not a number")

    panel.recipe = bad
    assert panel.start() is False, "an invalid recipe refuses the start"
    assert panel.status.text == "Not started: xx: not a number", (
        "status carries the recipe error text"
    )
    assert FakeProcess.made == [], "no child is spawned for an invalid recipe"


def test_start_when_real_runner_rejects_missing_source_then_nothing_spawned(bmod, tmp_path):
    from fontlab_fontport.batch import BatchRunner

    panel = make(bmod, tmp_path)
    panel.runner = BatchRunner()
    panel.set_sources([str(tmp_path / "missing.ufo")])
    assert panel.start() is False, "a missing source refuses the start"
    assert panel.status.text.startswith("Not started: "), panel.status.text
    assert FakeProcess.made == [], "no child is spawned for a missing source"


def test_start_when_valid_then_running_state_and_job_names(bmod, tmp_path):
    panel = make(bmod, tmp_path)
    assert panel.start() is True, "a valid setup starts"
    assert panel.running, "panel is running after start"
    assert [d.name for _, d in panel.jobs] == ["a-transformed.ufo", "b-transformed.ufo"], (
        "destinations are named after each source"
    )
    assert panel.status.text == "Running…", "status shows the running state"
    assert not panel.start_button.enabled, "start is disabled while running"
    assert panel.cancel_button.enabled, "cancel is enabled while running"
    assert ("setRange", (0, 2)) in panel.progress.calls, "progress range spans both fonts"
    assert panel.start() is False, "only one run at a time"
    assert FakeProcess.made[0].recipe["intensity"] == 100.0, "default recipe reaches the child"


def test_start_when_closed_then_refused(bmod, tmp_path):
    panel = make(bmod, tmp_path)
    panel.close()
    assert panel.start() is False, "a closed panel cannot start"
    assert FakeProcess.made == [], "no child is spawned by a closed panel"


def test_step_when_rows_arrive_then_results_logged_and_progress_advances(bmod, tmp_path):
    panel = make(bmod, tmp_path)
    panel.start()
    bad = ROW | {"index": 2, "ok": False, "error": "boom"}
    FakeProcess.made[0].rows = [ROW, bad]
    panel.timer.timeout.emit()
    assert [r.ok for r in panel.results] == [True, False], "both rows become results in order"
    texts = [c[1][0] for c in panel.log.calls if c[0] == "addItem"]
    assert texts == [
        "1/2 a.ufo → a-transformed.ufo: ok",
        "2/2 a.ufo → a-transformed.ufo: FAILED: boom",
    ], texts
    assert panel.progress.value == 2, "progress follows the last finished index"
    assert panel.running, "the child has not finished yet"


def test_step_when_child_finished_then_totals_and_callback(bmod, tmp_path):
    seen = []
    panel = make(bmod, tmp_path, on_finish=seen.append)
    panel.start()
    process = FakeProcess.made[0]
    process.rows, process.done = [ROW, ROW | {"index": 2, "ok": False, "error": "x"}], True
    panel.step()
    assert panel.status.text == "Finished: 1 succeeded, 1 failed.", "status totals the outcomes"
    assert process.released, "the finished child is released"
    assert not panel.running, "panel stops running when the child is done"
    assert len(seen) == 1, "the finish callback fires once"
    assert len(seen[0]) == 2, seen
    assert panel.start_button.enabled, "start is re-enabled after finishing"
    assert not panel.cancel_button.enabled, "cancel is disabled after finishing"


def test_step_when_callback_raises_then_status_mentions_it(bmod, tmp_path):
    def boom(results: list) -> None:
        raise RuntimeError("consumer bug")

    panel = make(bmod, tmp_path, on_finish=boom)
    panel.start()
    FakeProcess.made[0].done = True
    panel.step()
    assert panel.status.text.endswith("Callback failed: consumer bug"), panel.status.text


def test_step_when_child_exits_nonzero_then_failure_reported(bmod, tmp_path):
    panel = make(bmod, tmp_path)
    panel.start()
    process = FakeProcess.made[0]
    process.done, process.child.returncode = True, 3
    panel.step()
    assert panel.status.text == "Batch stopped: child exploded", (
        "a non-zero exit reports the child failure text"
    )
    assert process.released, "the failed child is released"
    assert not panel.running, "panel stops running after a failed child"


def test_step_when_output_malformed_then_child_supervised_and_run_stops(bmod, tmp_path):
    panel = make(bmod, tmp_path)
    panel.start()
    process = FakeProcess.made[0]
    process.read_error = bmod.ProtocolError("malformed batch output: b'x'")
    panel.step()
    assert panel.status.text == "Batch stopped: malformed batch output: b'x'", (
        "status carries the protocol error"
    )
    assert bmod.supervised[0][0] is process, "the misbehaving child is handed to the supervisor"
    assert bmod.supervised[0][1] is None, "no widget is handed over while the panel lives"
    assert not panel.running, "malformed output stops the run"


def test_step_when_tail_malformed_then_run_stops(bmod, tmp_path):
    panel = make(bmod, tmp_path)
    panel.start()
    process = FakeProcess.made[0]
    process.done = True
    process.tail_error = bmod.ProtocolError("trailing junk")
    panel.step()
    assert panel.status.text == "Batch stopped: trailing junk", (
        "a malformed tail stops the run with its message"
    )


def test_step_when_idle_or_closed_then_nothing_read(bmod, tmp_path):
    panel = make(bmod, tmp_path)
    panel.step()
    panel.start()
    FakeProcess.made[0].rows = [ROW]
    panel.closed = True
    panel.step()
    assert panel.results == [], "closed panels do not poll"


def test_cancel_when_running_then_flag_and_child_told_and_finish_says_cancelled(bmod, tmp_path):
    panel = make(bmod, tmp_path)
    panel.start()
    panel.cancel_button.clicked.emit()
    process = FakeProcess.made[0]
    assert process.cancel_calls == 1, "the child is told to cancel exactly once"
    assert panel.cancelled, "the panel remembers the cancellation"
    assert panel.status.text == "Cancelling after the current font…", (
        "status says the current font will finish first"
    )
    process.done = True
    panel.step()
    assert panel.status.text.startswith("Cancelled: "), "the final status reports cancellation"


def test_cancel_when_idle_then_nothing(bmod, tmp_path):
    panel = make(bmod, tmp_path)
    panel.cancel()
    assert panel.cancelled is False, "idle cancel sets no flag"
    assert panel.status.text.startswith("Choose"), "idle cancel leaves the prompt untouched"


def test_close_when_running_then_child_handed_to_supervisor_and_panel_detached(bmod, tmp_path):
    panel = make(bmod, tmp_path, on_finish=lambda r: None)
    panel.start()
    widget = panel.widget
    panel.close()
    process = FakeProcess.made[0]
    assert process.cancel_calls == 1, "closing cancels the running child"
    assert bmod.supervised == [(process, widget, bmod.BatchPanel.GRACE_SECONDS, 50)], (
        "the child and widget go to the supervisor with the grace period"
    )
    assert ("setParent", (None,)) in widget.calls, "the widget is detached from its parent"
    assert not widget.shown, "the detached widget is hidden"
    assert panel.on_finish is None, "the finish callback is dropped"
    assert not widget.deleted, "the supervisor deletes it"
    assert panel.connections == [], "all signal connections are disconnected"


def test_close_when_idle_then_widget_deleted_and_second_close_is_noop(bmod, tmp_path):
    panel = make(bmod, tmp_path)
    panel.close()
    panel.close()
    assert panel.widget.deleted, "an idle panel deletes its widget on close"
    assert bmod.supervised == [], "nothing is supervised when no child runs"


def test_close_when_widget_already_being_destroyed_then_only_child_supervised(bmod, tmp_path):
    panel = make(bmod, tmp_path)
    panel.start()
    panel.widget.destroyed.emit()
    assert panel.closed, "own-widget destruction closes the panel"
    panel2 = make(bmod, tmp_path)
    panel2.start()
    panel2.destroying = True
    panel2.close()
    assert bmod.supervised[-1][1] is None, "a dying widget is not handed over"



def _new_parented_batch_for_lifetime(bmod, tmp_path, parent):
    from types import SimpleNamespace
    from fontlab_fontport.recipe import Recipe

    panel = bmod.BatchPanel(lambda: Recipe(), parent, None, python="py3")
    panel.runner = SimpleNamespace(run=lambda jobs, recipe: SimpleNamespace(close=lambda: None))
    panel.set_sources(["/src/a.ufo", "/src/b.ufo"])
    panel.destination_control.setText(str(tmp_path))
    return panel


@pytest.mark.parametrize(
    "which,state,timing",
    [(which, state, timing) for which in ("own", "parent") for state in ("running", "exited", "idle") for timing in ("pre-ack", "post-ack")],
    ids=[which + "-" + state + "-" + timing for which in ("own", "parent") for state in ("running", "exited", "idle") for timing in ("pre-ack", "post-ack")],
)
def test_close_when_destruction_during_disconnect_then_legacy_order_and_transfer_once(bmod, tmp_path, monkeypatch, which, state, timing):
    parent = fq.FakeWidget()
    panel = _new_parented_batch_for_lifetime(bmod, tmp_path, parent)
    process = None
    if state != "idle":
        assert panel.start() is True
        process = panel.process
        process.done = state == "exited"
        process.child.returncode = 0 if state == "exited" else None
        assert panel.running, "scripted child exit does not clear active panel jobs"
    root = panel.widget
    observer_sender = root.destroyed if which == "own" else parent.destroyed
    observer, = (pair for pair in panel.connections if pair[0] is observer_sender)
    ordinary = fq.Signal()
    panel.connect(ordinary, lambda: None)
    target, = (pair for pair in panel.connections if pair[0] is ordinary)
    records = tuple(panel.connections)
    observers = (panel._own_observer, panel._parent_observer)
    owned_pairs = tuple(pair for pair, owner in panel._batch_owned)
    assert all(owner is root for pair, owner in panel._batch_owned), "ordinary ownership binds the exact Root"
    ordinary_pairs = [pair for pair in records if not any(pair is item for item in observers)]
    expected_death_retirements = ([id(pair) for pair in owned_pairs] + [id(panel._own_observer)]
                                  if which == "own" else [id(panel._parent_observer)])
    expected_order = [id(pair) for pair in reversed(ordinary_pairs)
                      if id(pair) not in expected_death_retirements]
    expected_order += [id(pair) for pair in reversed(observers)
                       if id(pair) not in expected_death_retirements]
    attempts, acknowledgements, observer_errors, frames = [], [], [], []
    observed = [False]
    widget_attempts, widget_acknowledgements = [], []
    widget_methods = [("setParent", root.setParent), ("hide", root.hide), ("deleteLater", root.deleteLater)]

    def widget_delegate(name, normal):
        def call(*args):
            widget_attempts.append((name, args))
            assert all(any(pending is pair for pending in panel.connections) for pair in observers), "lifetime witnesses survive widget stages"
            assert not (which == "own" and observed[0]), "no Root method after actual own observer"
            answer = normal(*args)
            if answer is not False:
                widget_acknowledgements.append((name, args, answer))
            return answer
        return call

    for name, normal in widget_methods:
        monkeypatch.setattr(root, name, widget_delegate(name, normal))

    def observe():
        before = tuple(id(pair) for pair in panel.connections)
        captured = None
        observed[0] = True
        try:
            observer[1]()
        except BaseException as caught:
            captured = caught
        observer_errors.append(captured)
        frames.append((before, tuple(id(pair) for pair in panel.connections)))

    def delegate(signal, normal):
        def disconnect(callback):
            pair, = (pair for pair in records if pair[0] is signal and pair[1] is callback)
            attempts.append(id(pair))
            if pair is target and timing == "pre-ack":
                observe()
            answer = normal(callback)
            if answer is not False:
                acknowledgements.append(id(pair))
            if pair is target and timing == "post-ack":
                observe()
            return answer
        return disconnect

    wrapped = set()
    for signal, _ in records:
        if id(signal) not in wrapped:
            normal = signal.disconnect
            monkeypatch.setattr(signal, "disconnect", delegate(signal, normal))
            wrapped.add(id(signal))
    outer_error = None
    try:
        panel.close()
    except BaseException as caught:
        outer_error = caught
    assert outer_error is None and observer_errors == [None]
    assert len(frames) == 1 and frames[0][0] == frames[0][1]
    assert attempts == expected_order and acknowledgements == expected_order
    assert {id(pair) for pair in records if id(pair) not in attempts} == set(expected_death_retirements), "only witnessed owner/sender death retires without a native ACK"
    assert panel.connections == [] and panel.closed and panel.cancelled
    assert panel._batch_owned == [], "pair retirement also retires exact ownership metadata"
    assert panel.on_finish is None and panel.jobs is None
    assert panel.destroying is (which == "own")
    if state == "idle":
        assert process is None and bmod.supervised == []
    else:
        assert process.cancel_calls == 1
        assert bmod.supervised == [(process, None if which == "own" else root, panel.GRACE_SECONDS, panel.POLL_MS)]
    expected_widget = [] if which == "own" else [("setParent", (None,)), ("hide", ())] + ([("deleteLater", ())] if state == "idle" else [])
    assert widget_attempts == expected_widget
    assert widget_acknowledgements == [(name, args, None) for name, args in expected_widget]
    panel.close()
    assert attempts == expected_order and acknowledgements == expected_order
    assert widget_attempts == expected_widget
    if state != "idle":
        assert process.cancel_calls == 1 and len(bmod.supervised) == 1
    # House records prove only legacy transfer entry, never raw process supervision.


@pytest.mark.parametrize("_case", [None], ids=["idle-normal"])
def test_root_close_event_when_legacy_idle_batch_closes_then_accepts(bmod, tmp_path, _case):
    from types import SimpleNamespace

    panel = _new_parented_batch_for_lifetime(bmod, tmp_path, fq.FakeWidget())
    actions = []
    event = SimpleNamespace(accept=lambda: actions.append("accept"), ignore=lambda: actions.append("ignore"))
    captured = None
    try:
        panel.widget.closeEvent(event)
    except BaseException as caught:
        captured = caught
    assert captured is None and actions == ["accept"]
    assert panel.closed and panel.connections == [] and bmod.supervised == []


# Task12c: actual close/supervisor APIs under the existing fake Qt boundary.
@pytest.fixture
def red12(monkeypatch):
    """Fresh actual modules; only Qt and Popen's external I/O are substituted."""
    from pathlib import Path

    handle = fq.install(monkeypatch)
    batch = handle.load("fontlabapp.fontui.batch")
    worker = handle.load("fontlabapp.fontui.batch_worker")
    assert batch.BatchProcess is worker.BatchProcess
    assert batch.supervise is worker.supervise
    # Relationships only. The controller's expected-source pins bind this run.
    assert Path(batch.BatchPanel.close.__code__.co_filename) == Path(batch.__file__)
    assert Path(worker.supervise.__code__.co_filename) == Path(worker.__file__)
    timers = []
    timer_type = worker.QtCore.QTimer

    def timer(*args):
        result = timer_type(*args)
        timers.append(result)
        return result

    monkeypatch.setattr(worker.QtCore, "QTimer", timer)
    monkeypatch.delenv(batch.PYTHON_ENV, raising=False)
    env = SimpleNamespace(batch=batch, worker=worker, handle=handle, timers=timers)
    yield env
    fq.release()


def red12_attempt(operation):
    try:
        operation()
    except BaseException as error:
        return error
    return None


def red12_fault(monkeypatch, owner, name, failure, *, after=False):
    """One boundary fault; subsequent calls delegate to the original operation."""
    original = getattr(owner, name)
    calls = []

    def invoke(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) == 1:
            if after:
                original(*args, **kwargs)
            if failure is False:
                return False
            raise failure
        return original(*args, **kwargs)

    monkeypatch.setattr(owner, name, invoke)
    return calls


@pytest.fixture
def red12_run(red12, monkeypatch):
    """Real BatchProcess constructors, real scratch/stdout, no OS child."""
    import tempfile
    from pathlib import Path
    from unittest.mock import Mock

    runs = []

    def create(start=None):
        child = Mock()
        child.stdout = tempfile.TemporaryFile("w+b")
        child.returncode = None
        child.pid = 0
        child.poll.side_effect = lambda: child.returncode
        child.kill.side_effect = lambda: setattr(child, "returncode", -9)
        child.terminate.side_effect = lambda: setattr(child, "returncode", -15)
        child.wait.side_effect = lambda *a, **k: child.returncode
        try:
            with monkeypatch.context() as boundary:
                boundary.setattr(red12.worker.sys, "platform", "linux")
                boundary.setattr(red12.worker.subprocess, "Popen", lambda *a, **k: child)
                run = start() if start is not None else red12.worker.BatchProcess("inert-popen-boundary", [], {})
        except BaseException:
            child.stdout.close()
            raise
        runs.append((run, run.release))
        return run

    yield create
    # No OS child exists. Preserve teardown failures separately from test failures.
    errors = []
    for run, release in runs:
        if not run.child.stdout.closed or Path(run.scratch).exists():
            error = red12_attempt(release)
            if error is not None:
                errors.append(error)
    if errors:
        raise BaseExceptionGroup("owned inert run cleanup", errors)


def red12_active(red12, tmp_path, run):
    panel = make(red12.batch, tmp_path)
    panel.process = run
    panel.jobs = [("/src/a.ufo", str(tmp_path / "a.ufo"))]
    return panel


def red12_clock(red12, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(red12.worker, "time", SimpleNamespace(monotonic=lambda: now[0]))
    return now


def red12_register(red12, run, widget=None):
    red12.worker.supervise(run, widget, 10.0, 50)
    timer = red12.timers[-1]
    assert timer.timeout.slots, "supervise installs an actual timeout callback"
    return timer


@pytest.mark.parametrize("refusal", ["raise", "false"])
def test_red12_disconnect_retry_keeps_acknowledged_pairs_retired(red12, tmp_path, monkeypatch, refusal):
    panel = make(red12.batch, tmp_path)
    pairs = list(panel.connections)
    acknowledged, pending_pair = pairs[-1], pairs[-2]
    acknowledged_calls = []
    disconnect = acknowledged[0].disconnect
    monkeypatch.setattr(acknowledged[0], "disconnect", lambda cb: (acknowledged_calls.append(cb), disconnect(cb))[1])
    error = RuntimeError("middle disconnect")
    attempts = red12_fault(monkeypatch, pending_pair[0], "disconnect", error if refusal == "raise" else False)
    observed = red12_attempt(panel.close)
    assert observed is error if refusal == "raise" else isinstance(observed, RuntimeError)
    assert not any(pair is acknowledged for pair in panel.connections), "an ACKed pair is not pending"
    assert red12_attempt(panel.close) is None
    assert len(attempts) == 2 and len(acknowledged_calls) == 1
    assert panel.connections == [] and panel.widget.deleted


@pytest.mark.parametrize("stage", ["stop", "detach", "hide", "cancel", "transfer", "delete"])
@pytest.mark.parametrize("refusal", ["raise", "false"])
def test_red12_close_stage_retries_only_the_unacknowledged_call(red12, red12_run, tmp_path, monkeypatch, stage, refusal):
    run = red12_run()
    panel = red12_active(red12, tmp_path, run) if stage in {"cancel", "transfer"} else make(red12.batch, tmp_path)
    target, name = {
        "stop": (panel.timer, "stop"), "detach": (panel.widget, "setParent"),
        "hide": (panel.widget, "hide"), "cancel": (run, "cancel"),
        "transfer": (red12.batch, "supervise"), "delete": (panel.widget, "deleteLater"),
    }[stage]
    error = RuntimeError(stage)
    calls = red12_fault(monkeypatch, target, name, error if refusal == "raise" else False)
    observed = red12_attempt(panel.close)
    assert observed is error if refusal == "raise" else isinstance(observed, RuntimeError)
    assert panel.closed and panel.cancelled and panel.on_finish is None
    assert red12_attempt(panel.close) is None
    assert len(calls) == 2, "explicit close retries the failed boundary"
    assert red12_attempt(panel.close) is None and len(calls) == 2


@pytest.mark.parametrize("stage", ["disconnect", "cancel", "transfer"])
def test_red12_close_preserves_baseexception_identity_and_retry(red12, red12_run, tmp_path, monkeypatch, stage):
    run = red12_run()
    panel = red12_active(red12, tmp_path, run)
    target, name = {"disconnect": (panel.connections[-1][0], "disconnect"), "cancel": (run, "cancel"), "transfer": (red12.batch, "supervise")}[stage]
    error = KeyboardInterrupt(stage)
    calls = red12_fault(monkeypatch, target, name, error)
    assert red12_attempt(panel.close) is error
    assert red12_attempt(panel.close) is None
    assert len(calls) == 2, "BaseException does not poison the close retry guard"


def test_red12_reentrant_close_is_rejected_without_poisoning_retry(red12, tmp_path, monkeypatch):
    panel = make(red12.batch, tmp_path)
    original = panel.widget.hide
    nested = []

    def hide():
        nested.append(red12_attempt(panel.close))
        return original()

    monkeypatch.setattr(panel.widget, "hide", hide)
    panel.close()
    assert len(nested) == 1 and isinstance(nested[0], RuntimeError)
    assert red12_attempt(panel.close) is None and len(nested) == 1


def test_red12_lifetime_observers_survive_until_actual_handoff(red12, red12_run, tmp_path, monkeypatch):
    panel = red12_active(red12, tmp_path, red12_run())
    observer = panel._own_observer
    witnessed = []
    original = panel.widget.hide

    def hide():
        witnessed.append(any(pair is observer for pair in panel.connections))
        return original()

    monkeypatch.setattr(panel.widget, "hide", hide)
    panel.close()
    assert witnessed == [True], "the owner witness survives widget work before worker acceptance"
    assert panel.widget.destroyed.slots, "actual supervisor retains its own lifetime witness"


@pytest.mark.parametrize("stage", ["detach", "hide", "cancel"])
@pytest.mark.parametrize("death", ["own", "parent"])
@pytest.mark.parametrize("when", ["pre", "post"])
def test_red12_death_during_close_is_observed_without_mutating_callback_frame(red12, red12_run, tmp_path, monkeypatch, stage, death, when):
    from fontlab_fontport.recipe import Recipe

    parent = fq.FakeWidget()
    panel = red12.batch.BatchPanel(lambda: Recipe(), parent, python="inert")
    panel.process, panel.jobs = red12_run(), [("a", "b")]
    signal = panel.widget.destroyed if death == "own" else parent.destroyed
    target, name = {"detach": (panel.widget, "setParent"), "hide": (panel.widget, "hide"), "cancel": (panel.process, "cancel")}[stage]
    original = getattr(target, name)
    frames, dead_calls = [], []
    dead = [False]
    owned_signals = [pair[0] for pair in panel.connections[-4:]]
    boundaries = [(panel.widget, "setParent"), (panel.widget, "hide"), (panel.widget, "deleteLater"), (panel.timer, "stop"), (panel.widget.destroyed, "connect"), (panel.widget.destroyed, "disconnect")]
    boundaries += [(signal, "disconnect") for signal in owned_signals]
    for boundary_owner, boundary_name in boundaries:
        boundary_original = getattr(boundary_owner, boundary_name)

        def guarded(*args, _original=boundary_original, _name=boundary_name):
            if dead[0]:
                dead_calls.append(_name)
                return None
            return _original(*args)

        monkeypatch.setattr(boundary_owner, boundary_name, guarded)

    def emit():
        before = tuple(id(pair) for pair in panel.connections)
        if death == "own":
            dead[0] = True
        signal.emit()
        frames.append((before, tuple(id(pair) for pair in panel.connections)))

    def operation(*args):
        if dead[0] and stage != "cancel":
            dead_calls.append(name)
            return None
        if when == "pre":
            emit()
        result = original(*args)
        if when == "post":
            emit()
        return result

    monkeypatch.setattr(target, name, operation)
    panel.close()
    assert panel.destroying if death == "own" else panel._parent_dead
    assert all(before == after for before, after in frames), "observer callbacks only record facts"
    assert dead_calls == [], "Root death forbids later Root and owned-child native calls"
    if death == "parent":
        assert not panel.destroying, "parent death is not evidence of Root death"


def test_red12_dead_owned_senders_retire_but_live_external_signal_disconnects(red12, tmp_path, monkeypatch):
    panel = make(red12.batch, tmp_path)
    owned = list(panel.connections[-4:])
    external = fq.Signal()
    panel.connect(external, lambda: None)
    external_pair = panel.connections.pop()
    panel.connections.insert(1, external_pair)
    external_disconnect, external_calls = external.disconnect, []
    monkeypatch.setattr(external, "disconnect", lambda cb: (external_calls.append(cb), external_disconnect(cb))[1])
    fail = RuntimeError("owned disconnect")
    red12_fault(monkeypatch, owned[-2][0], "disconnect", fail)
    assert red12_attempt(panel.close) is fail
    before = tuple(id(pair) for pair in panel.connections)
    panel.widget.destroyed.emit()
    assert tuple(id(pair) for pair in panel.connections) == before
    dead_calls = []
    for signal, _ in owned:
        monkeypatch.setattr(signal, "disconnect", lambda cb: dead_calls.append(cb))
    panel.close()
    assert dead_calls == [], "known-dead Root children receive no further native disconnect"
    assert panel.connections == [] and external.slots == []
    assert external_calls == [external_pair[1]], "the still-live external pair really disconnects on retry"


@pytest.mark.parametrize("stage,refusal", [("construct", "raise"), ("connect", "raise"), ("connect", "false"), ("start", "raise"), ("start", "false")])
def test_red12_supervisor_registration_retry_has_one_owner(red12, red12_run, monkeypatch, stage, refusal):
    run = red12_run()
    error = RuntimeError(stage)
    failure = error if refusal == "raise" else False
    original_factory = red12.worker.QtCore.QTimer
    boundary_calls = []
    created = []

    def factory(*args):
        if stage == "construct" and not boundary_calls:
            boundary_calls.append(args)
            raise error
        timer = original_factory(*args)
        created.append(timer)
        if len(created) == 1 and stage != "construct":
            red12_fault(monkeypatch, timer.timeout if stage == "connect" else timer, "connect" if stage == "connect" else "start", failure)
        return timer

    monkeypatch.setattr(red12.worker.QtCore, "QTimer", factory)
    first = red12_attempt(lambda: red12.worker.supervise(run, None, 10.0, 50))
    assert first is error if refusal == "raise" else isinstance(first, RuntimeError)
    second = red12_attempt(lambda: red12.worker.supervise(run, None, 10.0, 50))
    assert len(red12.worker._PENDING) == 1, "retry never appends a duplicate run"
    if stage == "connect":
        assert isinstance(second, BaseException), "unconnected ambiguous callback cannot be retired by an invented ACK"
        assert len(created) == 1
    else:
        assert second is None


def test_red12_connect_after_effect_requires_exact_compensation(red12, red12_run, monkeypatch):
    run = red12_run()
    original_factory = red12.worker.QtCore.QTimer
    created, connects, disconnects = [], [], []
    error = RuntimeError("connect after effect")

    def factory(*args):
        timer = original_factory(*args)
        created.append(timer)
        connect, disconnect = timer.timeout.connect, timer.timeout.disconnect

        def attach(callback):
            connects.append(callback)
            connect(callback)
            if len(connects) == 1:
                raise error

        def detach(callback):
            disconnects.append(callback)
            return disconnect(callback)

        monkeypatch.setattr(timer.timeout, "connect", attach)
        monkeypatch.setattr(timer.timeout, "disconnect", detach)
        return timer

    monkeypatch.setattr(red12.worker.QtCore, "QTimer", factory)
    assert red12_attempt(lambda: red12.worker.supervise(run, None, 10.0, 50)) is error
    assert red12_attempt(lambda: red12.worker.supervise(run, None, 10.0, 50)) is None
    assert len(created) == 1 and len(red12.worker._PENDING) == 1
    assert len(connects) == 2 and disconnects == [connects[0]] and connects[0] is connects[1]


def test_red12_registration_callback_cannot_poll_before_start_ack(red12, red12_run, monkeypatch):
    run = red12_run()
    original_factory = red12.worker.QtCore.QTimer
    polls_during_start = []

    def factory(*args):
        timer = original_factory(*args)
        start = timer.start

        def starting(interval):
            timer.timeout.emit()
            polls_during_start.append(run.child.poll.call_count)
            return start(interval)

        monkeypatch.setattr(timer, "start", starting)
        return timer

    monkeypatch.setattr(red12.worker.QtCore, "QTimer", factory)
    red12.worker.supervise(run, None, 10.0, 50)
    assert polls_during_start == [0], "a provisional registration is not runnable"


@pytest.mark.parametrize("moment", ["before_exit", "during_release", "during_delete"])
def test_red12_supervisor_observes_late_widget_death(red12, red12_run, monkeypatch, moment):
    run, widget = red12_run(), fq.FakeWidget()
    timer = red12_register(red12, run, widget)
    dead, deletes = [], []
    release, delete = run.release, widget.deleteLater

    def die():
        dead.append(True)
        widget.destroyed.emit()

    def releasing():
        if moment == "during_release":
            die()
        return release()

    def deleting():
        assert not dead, "worker must not call a known-dead widget"
        deletes.append(True)
        if moment == "during_delete":
            die()
        return delete()

    monkeypatch.setattr(run, "release", releasing)
    monkeypatch.setattr(widget, "deleteLater", deleting)
    if moment == "before_exit":
        die()
    run.child.returncode = 0
    assert red12_attempt(timer.timeout.emit) is None, "registered callback contains cleanup errors"
    assert len(deletes) == (1 if moment == "during_delete" else 0)
    assert red12.worker._PENDING == []


@pytest.mark.parametrize("stage", ["poll", "terminate", "kill", "release", "delete", "witness"])
def test_red12_tick_fault_is_contained_and_does_not_implicitly_retry(red12, red12_run, monkeypatch, stage):
    now = red12_clock(red12, monkeypatch)
    run, widget = red12_run(), fq.FakeWidget()
    timer = red12_register(red12, run, widget)
    target, name = {
        "poll": (run.child, "poll"), "terminate": (run.child, "terminate"),
        "kill": (run.child, "kill"), "release": (run, "release"),
        "delete": (widget, "deleteLater"), "witness": (widget.destroyed, "disconnect"),
    }[stage]
    if stage in {"release", "delete", "witness"}:
        run.child.returncode = 0
    now[0] = 16.0 if stage == "kill" else 11.0
    error = KeyboardInterrupt(stage)
    calls = red12_fault(monkeypatch, target, name, error)
    assert red12_attempt(timer.timeout.emit) is None, "no BaseException escapes the Qt timeout"
    assert len(calls) == 1, "the actual failing boundary was reached"
    assert red12_attempt(timer.timeout.emit) is None and len(calls) == 1
    assert red12_attempt(lambda: red12.worker.supervise(run, widget, 10.0, 50)) is None
    timer.timeout.emit()
    if stage == "poll":
        assert len(calls) >= 2, "explicit retry resumes poll; later exit observations remain allowed"
    else:
        assert len(calls) == 2, "only explicit same-run retry resumes the faulted boundary"


@pytest.mark.parametrize("stage", ["terminate", "kill", "release", "delete", "witness"])
def test_red12_tick_false_ack_is_a_retained_fault(red12, red12_run, monkeypatch, stage):
    now = red12_clock(red12, monkeypatch)
    run, widget = red12_run(), fq.FakeWidget()
    timer = red12_register(red12, run, widget)
    target, name = {"terminate": (run.child, "terminate"), "kill": (run.child, "kill"), "release": (run, "release"), "delete": (widget, "deleteLater"), "witness": (widget.destroyed, "disconnect")}[stage]
    if stage in {"release", "delete", "witness"}:
        run.child.returncode = 0
    now[0] = 16.0 if stage == "kill" else 11.0
    calls = red12_fault(monkeypatch, target, name, False)
    assert red12_attempt(timer.timeout.emit) is None
    assert len(calls) == 1, "the actual refusing boundary was reached"
    timer.timeout.emit()
    assert len(calls) == 1 and len(red12.worker._PENDING) == 1, "False neither acknowledges completion nor permits timer retries"


def test_red12_faulted_entry_does_not_block_a_healthy_peer(red12, red12_run, monkeypatch):
    broken, healthy = red12_run(), red12_run()
    timer = red12_register(red12, broken)
    red12.worker.supervise(healthy, None, 10.0, 50)
    healthy.child.returncode = 0
    red12_fault(monkeypatch, broken.child, "poll", RuntimeError("poll"))
    assert red12_attempt(timer.timeout.emit) is None
    assert healthy.child.stdout.closed and not broken.child.stdout.closed
    assert len(red12.worker._PENDING) == 1


@pytest.mark.parametrize("stage", ["delete", "witness"])
def test_red12_finish_retry_does_not_replay_prior_ack(red12, red12_run, monkeypatch, stage):
    run, widget = red12_run(), fq.FakeWidget()
    timer = red12_register(red12, run, widget)
    release, delete = run.release, widget.deleteLater
    releases, deletes = [], []
    monkeypatch.setattr(run, "release", lambda: (releases.append(True), release())[1])
    monkeypatch.setattr(widget, "deleteLater", lambda: (deletes.append(True), delete())[1])
    target, name = (widget, "deleteLater") if stage == "delete" else (widget.destroyed, "disconnect")
    original = getattr(target, name)
    first, second = RuntimeError("first " + stage), KeyboardInterrupt("second " + stage)
    failures, attempts = [first, second], []

    def operation(*args):
        if failures:
            error = failures.pop(0)
            attempts.append(error)
            raise error
        attempts.append(None)
        return original(*args)

    monkeypatch.setattr(target, name, operation)
    run.child.returncode = 0
    assert red12_attempt(timer.timeout.emit) is None
    assert attempts == [first], "the actual failing finish boundary was reached"
    entry = run._supervision
    assert any(pending is entry for pending in red12.worker._PENDING)
    assert entry["first_error"] is first and entry["current_error"] is first
    assert entry["reporting_error"] is None and entry["error_group"] is None
    observed = red12_attempt(lambda: red12.worker.supervise(run, widget, 10.0, 50))
    assert observed is second, "direct retry raises the exact current primary error"
    assert run._supervision is entry and attempts == [first, second]
    assert entry["first_error"] is first and entry["current_error"] is second
    assert entry["reporting_error"] is None and entry["error_group"] is None
    timer.timeout.emit()
    assert attempts == [first, second], "timer delivery cannot retry the second failure"
    red12.worker.supervise(run, widget, 10.0, 50)
    timer.timeout.emit()
    assert attempts == [first, second, None]
    assert all(entry[key] is None for key in ("first_error", "current_error", "reporting_error", "error_group"))
    assert releases == [True] and deletes == [True], "successful finish stages execute once across retries"
    assert red12.worker._PENDING == []


def test_red12_cap_timeout_retains_uncollected_run_without_replaying_kill(red12, red12_run, monkeypatch):
    runs = [red12_run() for _ in range(red12.worker.MAX_PENDING + 1)]
    for run in runs[:-1]:
        red12.worker.supervise(run, None, 10.0, 50)
    overflow = runs[-1]
    overflow.child.kill.side_effect = lambda: None
    overflow.child.wait.side_effect = red12.worker.subprocess.TimeoutExpired("owned inert child", red12.worker.KILL_WAIT)
    first = red12_attempt(lambda: red12.worker.supervise(overflow, None, 10.0, 50))
    assert isinstance(first, RuntimeError), "a bounded wait timeout is not actual collection"
    assert not overflow.child.stdout.closed and len(red12.worker._PENDING) == 16
    assert overflow.child.wait.call_args.args == (1.0,)
    overflow.child.returncode = -9
    red12.worker.supervise(overflow, None, 10.0, 50)
    assert overflow.child.stdout.closed and overflow.child.kill.call_count == 1
    assert len(red12.worker._PENDING) == 16


@pytest.mark.parametrize("boundary", ["stop", "registration"])
def test_red12_protocol_fault_keeps_run_owned_and_fences_poll_reentry(red12, red12_run, tmp_path, monkeypatch, boundary):
    run = red12_run()
    panel = red12_active(red12, tmp_path, run)
    error = red12.worker.ProtocolError("bad row")
    monkeypatch.setattr(run, "read", lambda: (_ for _ in ()).throw(error))
    target, name = (panel.timer, "stop") if boundary == "stop" else (red12.worker.QtCore, "QTimer")
    calls = red12_fault(monkeypatch, target, name, RuntimeError(boundary))
    assert red12_attempt(panel.step) is None, "the polling callback retains cleanup failure"
    assert panel.running and panel.process is run and panel.start() is False
    panel.step()
    panel.timer.timeout.emit()
    assert len(calls) == 1, "timer delivery does not implicitly retry a fault"
    panel.close()
    assert len(calls) == 2


def test_red12_protocol_stop_ack_is_shared_with_idle_and_later_close(red12, red12_run, tmp_path, monkeypatch):
    run = red12_run()
    panel = red12_active(red12, tmp_path, run)
    stop, stops = panel.timer.stop, []
    monkeypatch.setattr(panel.timer, "stop", lambda: (stops.append(True), stop())[1])
    monkeypatch.setattr(run, "read", lambda: (_ for _ in ()).throw(red12.worker.ProtocolError("bad row")))
    panel.step()
    assert not panel.running and stops == [True]
    panel.close()
    assert stops == [True], "step, protocol idle and close share one acknowledged stop"
    assert len(red12.worker._PENDING) == 1


@pytest.mark.parametrize("control", ["start", "add", "cancel", "status"])
def test_red12_protocol_idle_ui_failure_keeps_start_fenced(red12, red12_run, tmp_path, monkeypatch, control):
    run = red12_run()
    panel = red12_active(red12, tmp_path, run)
    monkeypatch.setattr(run, "read", lambda: (_ for _ in ()).throw(red12.worker.ProtocolError("bad row")))
    target, name = {"start": (panel.start_button, "setEnabled"), "add": (panel.add_button, "setEnabled"), "cancel": (panel.cancel_button, "setEnabled"), "status": (panel.status, "setText")}[control]
    calls = red12_fault(monkeypatch, target, name, RuntimeError(control))
    assert red12_attempt(panel.step) is None, "fallible idle UI remains inside protocol cleanup ownership"
    assert panel.running and panel.process is run and panel.start() is False
    attempts_after_report = len(calls)
    panel.step()
    panel.timer.timeout.emit()
    assert len(calls) == attempts_after_report and len(red12.worker._PENDING) == 1
    panel.close()
    assert len(red12.worker._PENDING) == 1, "close adopts the accepted child-only handoff"


@pytest.mark.parametrize("boundary", ["root", "base_layout", "post_base", "timer"])
def test_red12_public_factory_partial_constructor_preserves_error_and_owner(red12, monkeypatch, boundary):
    from fontlab_fontport.recipe import Recipe

    public = red12.handle.load("fontlabapp.fontui")
    original = RuntimeError("constructor " + boundary)
    if boundary == "root":
        target, name = fq.FakeWidget, "__init__"
    elif boundary == "base_layout":
        target, name = red12.batch.QtGui, "QVBoxLayout"
    elif boundary == "post_base":
        target, name = red12.batch.QtGui, "QListWidget"
    else:
        target, name = red12.batch.QtCore, "QTimer"
    red12_fault(monkeypatch, target, name, original)
    observed = red12_attempt(lambda: public.batch_panel(lambda: Recipe(), python="inert"))
    if boundary == "base_layout":
        assert isinstance(observed, BaseExceptionGroup) and observed.exceptions[0] is original
        assert isinstance(observed.exceptions[1], RuntimeError), "incomplete Owned construction is an explicit refusal"
        assert observed.owner.widget is not None
    else:
        assert observed is original, "successful partial cleanup preserves the exact constructor exception"


def test_red12_factory_cleanup_group_retains_exact_order_and_retry_owner(red12, monkeypatch):
    from fontlab_fontport.recipe import Recipe

    original, cleanup = RuntimeError("constructor"), KeyboardInterrupt("cleanup")
    public = red12.handle.load("fontlabapp.fontui")
    red12_fault(monkeypatch, red12.batch.QtGui, "QListWidget", original)
    red12_fault(monkeypatch, fq.FakeWidget, "hide", cleanup)
    observed = red12_attempt(lambda: public.batch_panel(lambda: Recipe(), python="inert"))
    assert isinstance(observed, BaseExceptionGroup)
    assert observed.exceptions == (original, cleanup), "factory groups original and cleanup identities in order"
    assert red12_attempt(observed.owner.close) is None
    assert observed.owner.widget.deleted


def test_red12_root_close_event_retries_failed_close(red12, tmp_path, monkeypatch):
    from unittest.mock import Mock

    panel = make(red12.batch, tmp_path)
    error = RuntimeError("hide")
    calls = red12_fault(monkeypatch, panel.widget, "hide", error)
    first, second = Mock(), Mock()
    panel.widget.closeEvent(first)
    assert panel._close_error is error and first.ignore.call_count == 1
    panel.widget.closeEvent(second)
    assert len(calls) == 2 and panel.widget.deleted, "a later closeEvent reaches unfinished work"
    assert second.accept.call_count == 1


def test_red12_final_timer_stop_fault_has_same_run_retry(red12, red12_run, monkeypatch):
    run, widget = red12_run(), fq.FakeWidget()
    timer = red12_register(red12, run, widget)
    release, delete, start = run.release, widget.deleteLater, timer.start
    releases, deletes, starts = [], [], []
    monkeypatch.setattr(run, "release", lambda: (releases.append(True), release())[1])
    monkeypatch.setattr(widget, "deleteLater", lambda: (deletes.append(True), delete())[1])
    monkeypatch.setattr(timer, "start", lambda interval: (starts.append(interval), start(interval))[1])
    error = RuntimeError("last stop")
    stops = red12_fault(monkeypatch, timer, "stop", error)
    run.child.returncode = 0
    assert red12_attempt(timer.timeout.emit) is None, "the final shared stop error is contained"
    assert red12.worker._PENDING == [] and releases == [True] and deletes == [True]
    entry = run._supervision
    assert entry["first_error"] is error and entry["current_error"] is error
    assert entry["reporting_error"] is None and entry["error_group"] is None
    polls = run.child.poll.call_count
    timer.timeout.emit()
    assert len(stops) == 1, "a faulted timer callback does not retry itself"
    red12.worker.supervise(run, widget, 10.0, 50)
    assert len(stops) == 2 and starts == [] and run.child.poll.call_count == polls
    assert releases == [True] and deletes == [True] and red12.worker._PENDING == []
    assert run._supervision is entry
    assert all(entry[key] is None for key in ("first_error", "current_error", "reporting_error", "error_group"))


def test_red12_shared_clock_fault_is_contained_and_explicitly_resumed(red12, red12_run, monkeypatch):
    now = red12_clock(red12, monkeypatch)
    run, peer = red12_run(), red12_run()
    timer = red12_register(red12, run)
    red12.worker.supervise(peer, None, 10.0, 50)
    calls = red12_fault(monkeypatch, red12.worker.time, "monotonic", RuntimeError("clock"))
    assert red12_attempt(timer.timeout.emit) is None
    timer.timeout.emit()
    assert len(calls) == 1 and run.child.poll.call_count == 0 and peer.child.poll.call_count == 0
    now[0] = 11.0
    red12.worker.supervise(run, None, 10.0, 50)
    timer.timeout.emit()
    assert run.child.terminate.call_count == 1 and peer.child.terminate.call_count == 1, "retry retains both original grace deadlines"


def test_red12_reporting_failure_does_not_escape_or_repeat_callback(red12, red12_run, monkeypatch):
    run = red12_run()
    timer = red12_register(red12, run)
    first, second = RuntimeError("first poll"), KeyboardInterrupt("second poll")
    reporting = RuntimeError("report")
    original_poll = run.child.poll
    failures, polls, writes = [first, second], [], []

    def poll():
        if failures:
            error = failures.pop(0)
            polls.append(error)
            raise error
        polls.append(None)
        return original_poll()

    def write(text):
        writes.append(text)
        raise reporting

    monkeypatch.setattr(run.child, "poll", poll)
    monkeypatch.setattr(red12.worker, "sys", SimpleNamespace(stderr=SimpleNamespace(write=write, flush=lambda: None)))
    assert red12_attempt(timer.timeout.emit) is None
    assert polls == [first] and writes, "both the primary and reporting faults were actually reached"
    entry = run._supervision
    assert any(pending is entry for pending in red12.worker._PENDING)
    assert entry["first_error"] is first and entry["current_error"] is first
    assert entry["reporting_error"] is reporting
    first_group = entry["error_group"]
    assert isinstance(first_group, BaseExceptionGroup)
    assert first_group.exceptions == (first, reporting) and first_group.owner is entry
    count = len(writes)
    timer.timeout.emit()
    assert polls == [first] and len(writes) == count
    observed = red12_attempt(lambda: red12.worker.supervise(run, None, 10.0, 50))
    assert run._supervision is entry and polls == [first, second]
    assert entry["first_error"] is first and entry["current_error"] is second
    assert entry["reporting_error"] is reporting
    second_group = entry["error_group"]
    assert observed is second_group and isinstance(second_group, BaseExceptionGroup)
    assert second_group.exceptions == (second, reporting) and second_group.owner is entry
    assert first_group.exceptions == (first, reporting) and first_group.owner is entry
    count = len(writes)
    timer.timeout.emit()
    assert polls == [first, second] and len(writes) == count
    run.child.returncode = 0
    red12.worker.supervise(run, None, 10.0, 50)
    timer.timeout.emit()
    assert all(entry[key] is None for key in ("first_error", "current_error", "reporting_error", "error_group"))
    assert first_group.exceptions == (first, reporting) and second_group.exceptions == (second, reporting)
    assert run.child.stdout.closed and red12.worker._PENDING == []


@pytest.mark.parametrize("ack", [None, 0])
def test_red12_non_false_void_ack_is_accepted(red12, tmp_path, monkeypatch, ack):
    panel = make(red12.batch, tmp_path)
    original = panel.timer.stop
    calls = []

    def stop():
        calls.append(True)
        original()
        return ack

    monkeypatch.setattr(panel.timer, "stop", stop)
    panel.close()
    panel.close()
    assert calls == [True] and panel.widget.deleted


def test_red12_side_effect_then_raise_is_not_forged_disconnect_ack(red12, tmp_path, monkeypatch):
    panel = make(red12.batch, tmp_path)
    signal, callback = panel.connections[-1]
    error = RuntimeError("disconnect after effect")
    red12_fault(monkeypatch, signal, "disconnect", error, after=True)
    assert red12_attempt(panel.close) is error
    assert callback not in signal.slots and not panel.destroying
    observed = red12_attempt(panel.close)
    assert isinstance(observed, ValueError), "unknown disconnect completion remains an exact retry refusal"
    assert any(pair[0] is signal and pair[1] is callback for pair in panel.connections)


@pytest.mark.parametrize("stage", ["kill", "release", "delete"])
def test_red12_cap_fault_retry_preserves_successful_stages(red12, red12_run, monkeypatch, stage):
    for _ in range(red12.worker.MAX_PENDING):
        red12.worker.supervise(red12_run(), None, 10.0, 50)
    run, widget = red12_run(), fq.FakeWidget()
    counts = {"kill": [], "release": [], "delete": []}
    for label, owner, name in [("kill", run, "kill"), ("release", run, "release"), ("delete", widget, "deleteLater")]:
        original = getattr(owner, name)

        def counted(*args, _label=label, _original=original):
            counts[_label].append(True)
            return _original(*args)

        monkeypatch.setattr(owner, name, counted)
    target, name = {"kill": (run, "kill"), "release": (run, "release"), "delete": (widget, "deleteLater")}[stage]
    error = RuntimeError("overflow " + stage)
    calls = red12_fault(monkeypatch, target, name, error)
    assert red12_attempt(lambda: red12.worker.supervise(run, widget, 10.0, 50)) is error
    assert len(red12.worker._PENDING) == 16
    red12.worker.supervise(run, widget, 10.0, 50)
    red12.worker.supervise(run, widget, 10.0, 50)
    assert len(calls) == 2 and all(value == [True] for value in counts.values()), "cap retry and completed replay never repeat successful stages"
    assert run.child.stdout.closed and widget.deleted and len(red12.worker._PENDING) == 16


def test_red12_later_new_run_does_not_inherit_protocol_stop_ack(red12, red12_run, tmp_path, monkeypatch):
    old = red12_run()
    panel = red12_active(red12, tmp_path, old)
    stop, stops = panel.timer.stop, []
    monkeypatch.setattr(panel.timer, "stop", lambda: (stops.append(True), stop())[1])
    monkeypatch.setattr(old, "read", lambda: (_ for _ in ()).throw(red12.worker.ProtocolError("old bad row")))
    panel.step()
    assert not panel.running and stops == [True]
    def start_run():
        assert panel.start() is True
        return panel.process

    new = red12_run(start_run)
    assert new is not old and panel.process is new
    monkeypatch.setattr(new, "read", lambda: (_ for _ in ()).throw(red12.worker.ProtocolError("new bad row")))
    panel.step()
    assert stops == [True, True], "new process identity owns its own stop acknowledgement"
    panel.close()
    assert stops == [True, True], "later close consumes only the new run's ACK"


def test_red12_public_factory_failure_after_timer_creation_cleans_up(red12, monkeypatch):
    from fontlab_fontport.recipe import Recipe

    original = RuntimeError("initial idle status")
    public = red12.handle.load("fontlabapp.fontui")
    real_label = red12.batch.QtGui.QLabel

    def label(*args):
        result = real_label(*args)
        red12_fault(monkeypatch, result, "setText", original)
        return result

    monkeypatch.setattr(red12.batch.QtGui, "QLabel", label)
    observed = red12_attempt(lambda: public.batch_panel(lambda: Recipe(), python="inert"))
    assert red12.timers, "the real constructor reached timer creation before the fault"
    assert observed is original, "post-timer cleanup must preserve the original exception"


@pytest.mark.parametrize("after_effect", [False, True])
def test_red12_failed_worker_witness_then_own_death_bridges_actual_handoff(red12, red12_run, tmp_path, monkeypatch, after_effect):
    panel = red12_active(red12, tmp_path, red12_run())
    error = RuntimeError("worker witness connect")
    calls = red12_fault(monkeypatch, panel.widget.destroyed, "connect", error, after=after_effect)
    assert red12_attempt(panel.close) is error, "actual supervisor attempts the worker lifetime witness"
    before = tuple(id(pair) for pair in panel.connections)
    panel.widget.destroyed.emit()
    assert panel.destroying and tuple(id(pair) for pair in panel.connections) == before
    dead_calls = []
    for owner, name in [(panel.widget, "setParent"), (panel.widget, "hide"), (panel.widget, "deleteLater"), (panel.widget.destroyed, "connect"), (panel.widget.destroyed, "disconnect"), (panel.timer, "stop")]:
        monkeypatch.setattr(owner, name, lambda *args: dead_calls.append(args))
    panel.close()
    assert dead_calls == [] and len(calls) == 1, "own death bridges failed acceptance without touching the dead wrapper"
    assert len(red12.worker._PENDING) == 1 and panel.connections == []
    panel.process.child.returncode = 0
    red12.timers[-1].timeout.emit()
    assert panel.process.child.stdout.closed and red12.worker._PENDING == []


def test_red12_supervisor_reentry_and_wrong_arguments_preserve_original_owner(red12, red12_run, monkeypatch):
    run, widget = red12_run(), fq.FakeWidget()
    factory = red12.worker.QtCore.QTimer
    nested, entered = [], [False]

    def timer(*args):
        result = factory(*args)
        start = result.start

        def starting(interval):
            if not entered[0]:
                entered[0] = True
                nested.append(red12_attempt(lambda: red12.worker.supervise(run, widget, 10.0, 50)))
            return start(interval)

        monkeypatch.setattr(result, "start", starting)
        return result

    monkeypatch.setattr(red12.worker.QtCore, "QTimer", timer)
    red12.worker.supervise(run, widget, 10.0, 50)
    assert len(nested) == 1 and isinstance(nested[0], RuntimeError)
    assert isinstance(red12_attempt(lambda: red12.worker.supervise(run, fq.FakeWidget(), 10.0, 50)), RuntimeError)
    assert len(red12.worker._PENDING) == 1


@pytest.mark.parametrize("stage", ["release", "delete", "witness"])
def test_red12_retry_clock_failure_preserves_unacknowledged_cleanup_error(red12, red12_run, monkeypatch, stage):
    """A failed retry clock cannot replace a still-unacknowledged cleanup error."""
    red12_clock(red12, monkeypatch)
    run, widget = red12_run(), fq.FakeWidget()
    timer = red12_register(red12, run, widget)
    first = RuntimeError("original " + stage)
    second = RuntimeError("retry " + stage)
    clock_error = RuntimeError("retry clock")
    failures = [first, second]
    attempts = {"release": 0, "delete": 0, "witness": 0}
    for label, target, name in (("release", run, "release"), ("delete", widget, "deleteLater"), ("witness", widget.destroyed, "disconnect")):
        original = getattr(target, name)

        def operation(*args, _label=label, _original=original):
            attempts[_label] += 1
            if _label == stage and failures:
                raise failures.pop(0)
            return _original(*args)

        monkeypatch.setattr(target, name, operation)
    run.child.returncode = 0
    assert red12_attempt(timer.timeout.emit) is None
    assert attempts[stage] == 1, "the original cleanup failure was reached"
    entry = run._supervision
    assert any(pending is entry for pending in red12.worker._PENDING)
    assert entry["first_error"] is first and entry["current_error"] is first
    assert entry["reporting_error"] is None and entry["error_group"] is None
    before_clock = dict(attempts)
    clock_reads, clock_fails = [], [True]

    def clock():
        clock_reads.append(True)
        if clock_fails[0]:
            raise clock_error
        return 0.0

    monkeypatch.setattr(red12.worker.time, "monotonic", clock)
    observed = red12_attempt(lambda: red12.worker.supervise(run, widget, 10.0, 50))
    assert observed is clock_error, "explicit retry exposes the exact clock failure"
    assert run._supervision is entry and attempts == before_clock
    assert len(clock_reads) == 1
    assert red12_attempt(timer.timeout.emit) is None
    assert len(clock_reads) == 1 and attempts == before_clock, "a faulted callback does not retry the clock or cleanup"
    # The shared fault may expose C temporarily while its finite snapshot owns E1.
    # Only the restored original cleanup stage's first/current identities bind here.
    clock_fails[0] = False
    observed = red12_attempt(lambda: red12.worker.supervise(run, widget, 10.0, 50))
    assert observed is second and attempts[stage] == 2
    assert run._supervision is entry
    assert entry["first_error"] is first, "the unacknowledged original cleanup error survives a retry-clock failure"
    assert entry["current_error"] is second
    assert entry["reporting_error"] is None and entry["error_group"] is None
    before_resolution, reads_before_resolution = dict(attempts), len(clock_reads)
    assert red12_attempt(timer.timeout.emit) is None
    assert attempts == before_resolution and len(clock_reads) == reads_before_resolution
    assert red12_attempt(lambda: red12.worker.supervise(run, widget, 10.0, 50)) is None
    assert attempts == {name: 3 if name == stage else 1 for name in attempts}, "prior cleanup ACKs do not replay"
    assert run._supervision is entry and red12.worker._PENDING == []
    assert all(entry[key] is None for key in ("first_error", "current_error", "reporting_error", "error_group"))
    assert run.child.stdout.closed and widget.deleted


@pytest.mark.parametrize("method", [True, False], ids=["method", "property"])
def test_step_when_status_text_is_method_or_property_then_callback_error_appends_to_text(
    bmod, tmp_path, method
):
    def boom(results: list) -> None:
        raise RuntimeError("consumer bug")

    class Label:
        shown = "x"

        def setText(self, value: str) -> None:
            self.shown = value

    # PySide exposes text() as a method; FontLab PythonQt exposes a property.
    Label.text = (lambda self: self.shown) if method else property(lambda self: self.shown)
    panel = make(bmod, tmp_path, on_finish=boom)
    panel.start()
    FakeProcess.made[0].done = True
    label = Label()
    panel.status = label
    panel.step()
    assert label.shown.startswith("Finished: "), label.shown
    assert label.shown.endswith(" Callback failed: consumer bug"), label.shown
    assert "bound method" not in label.shown and "function" not in label.shown, label.shown
