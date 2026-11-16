# this_file: tests/test_ui_b09.py
"""B09 controls: recipe parsing, batch validation before writes, one run at a time."""

import importlib
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

MODULES = (
    "fontlabapp.fontui.batch",
    "fontlabapp.fontui.batch_worker",
    "fontlabapp.fontui.transform",
    "fontlabapp.fontui.transform_view",
    "fontlabapp.fontui.lifecycle",
)


@pytest.fixture
def ui(monkeypatch):
    importlib.import_module(
        "fontlab_fontport.batch"
    )  # [test] installs Fontport; never skip
    importlib.import_module("fontTools.pens.qtPen")
    for name in MODULES:
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setitem(
        sys.modules, "PythonQt", SimpleNamespace(QtGui=Mock(), QtCore=Mock())
    )
    yield SimpleNamespace(
        batch=importlib.import_module("fontlabapp.fontui.batch"),
        transform=importlib.import_module("fontlabapp.fontui.transform"),
    )
    for name in MODULES:
        sys.modules.pop(name, None)


def editor(ui, **fields):
    from fontlab_fontport.recipe import Recipe

    obj = ui.transform.TransformEditor.__new__(ui.transform.TransformEditor)
    values = {
        "xx": "2",
        "xy": "0",
        "yx": "0",
        "yy": "1",
        "dx": "10",
        "dy": "0",
    } | fields
    obj.matrix = {key: SimpleNamespace(text=value) for key, value in values.items()}
    obj.intensity_field = SimpleNamespace(text="50")
    obj.enabled_control = SimpleNamespace(checked=True)
    return obj, Recipe


def test_recipe_fields_parse_into_fontport_recipe(ui):
    obj, Recipe = editor(ui)
    recipe = obj.recipe()
    assert recipe == Recipe(matrix=(2, 0, 0, 1, 10, 0), intensity=50, enabled=True)
    assert tuple(recipe.transform) == (1.5, 0, 0, 1, 5, 0)


@pytest.mark.parametrize(
    "fields,message",
    [({"xx": "two"}, "xx: not a number"), ({"xx": "0", "yy": "0"}, "determinant")],
)
def test_bad_recipe_fields_are_refused(ui, fields, message):
    obj, _ = editor(ui, **fields)
    with pytest.raises(ValueError, match=message):
        obj.recipe()


def panel(ui, sources, folder, python=sys.executable):
    from fontlab_fontport.recipe import Recipe

    obj = ui.batch.BatchPanel.__new__(ui.batch.BatchPanel)
    obj.closed, obj.jobs, obj.results, obj.cancelled = False, None, [], False
    obj.destroying, obj.connections, obj.widget = False, [], Mock()
    obj._closing = False
    obj._close_complete = False
    obj._child_closed = False
    obj._hidden = False
    obj._delete_scheduled = False
    obj._close_error = None
    obj._parent_dead = False
    obj._own_observer = None
    obj._parent_observer = None
    obj._batch_base_ready = True
    obj._batch_close = None
    obj._protocol = None
    obj._batch_owned = []
    obj.python, obj.process = python, None
    obj.runner, obj.sources = ui.batch.BatchRunner(), [str(s) for s in sources]
    obj.recipe = lambda: Recipe(matrix=(1, 0, 0, 1, 7, 0))
    obj.destination_control = SimpleNamespace(text=str(folder))
    for name in ("timer", "start_button", "add_button", "cancel_button"):
        setattr(obj, name, Mock())
    obj.progress, obj.log, obj.status, obj.on_finish = Mock(), Mock(), Mock(), Mock()
    return obj


def ufo(path, x=0):
    from ufoLib2 import Font

    font = Font()
    glyph = font.newGlyph("a")
    glyph.width = 500
    pen = glyph.getPen()
    pen.moveTo((x, 0))
    pen.lineTo((x + 100, 0))
    pen.lineTo((x, 100))
    pen.closePath()
    font.save(path)
    return path


def wait_for(predicate, timeout=20):
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "condition not reached"
        time.sleep(0.01)


def drain(obj, timeout=30):
    wait_for(lambda: (obj.step() or True) and not obj.running, timeout)


def fake_python(tmp_path, body):
    """A stand-in interpreter: shell body, then (optionally) the real one."""
    script = tmp_path / "python.sh"
    script.write_text(f"#!/bin/sh\n{body}\n")
    script.chmod(0o755)
    return str(script)


def message(obj):
    return obj.status.setText.call_args.args[0]


def test_batch_writes_each_destination_in_a_child_process(ui, tmp_path):
    from ufoLib2 import Font

    from fontlab_fontport.batch import BatchResult

    sources = [ufo(tmp_path / "One.ufo"), ufo(tmp_path / "Two.ufo", 5)]
    obj = panel(ui, sources, tmp_path / "out")
    assert obj.start() is True and obj.running and proc(obj).child.pid != os.getpid()
    assert obj.start() is False, "duplicate launch refused while running"
    drain(obj)
    assert [r.ok for r in obj.results] == [True, True]
    assert isinstance(obj.results[0], BatchResult)
    out = Font.open(tmp_path / "out" / "One-transformed.ufo")
    first = out["a"].contours[0].points[0]
    assert (first.x, first.y) == (7, 0)
    assert message(obj) == "Finished: 2 succeeded, 0 failed."
    obj.on_finish.assert_called_once()
    assert released(proc(obj)), "stdout closed, scratch folder removed"


@pytest.mark.parametrize(
    "case", ["no-destination", "missing-source", "no-sources", "no-python"]
)
def test_batch_validation_fails_before_any_write_or_spawn(
    ui, tmp_path, case, monkeypatch
):
    monkeypatch.delenv(ui.batch.PYTHON_ENV, raising=False)
    sources = {"missing-source": [tmp_path / "Gone.ufo"], "no-sources": []}.get(
        case, [ufo(tmp_path / "One.ufo")]
    )
    folder = "" if case == "no-destination" else tmp_path / "out"
    obj = panel(
        ui, sources, folder, python=None if case == "no-python" else sys.executable
    )
    assert obj.start() is False and not obj.running and obj.process is None
    assert not (tmp_path / "out").exists()
    assert message(obj).startswith("Not started")
    obj.on_finish.assert_not_called()


def test_environment_selects_the_child_python(ui, tmp_path, monkeypatch):
    monkeypatch.setenv(ui.batch.PYTHON_ENV, sys.executable)
    obj = panel(ui, [ufo(tmp_path / "One.ufo")], tmp_path / "out", python=None)
    assert obj.start() is True
    drain(obj)
    assert [r.ok for r in obj.results] == [True]


def test_cancel_stops_before_the_next_font(ui, tmp_path):
    sources = [ufo(tmp_path / "One.ufo"), ufo(tmp_path / "Two.ufo")]
    obj = panel(ui, sources, tmp_path / "out")
    assert obj.start() is True
    obj.cancel()
    drain(obj)
    assert len(obj.results) <= 1 and message(obj).startswith("Cancelled")
    assert not (tmp_path / "out" / "Two-transformed.ufo").exists()


def test_existing_destination_and_item_failure(ui, tmp_path):
    sources = [ufo(tmp_path / "One.ufo"), ufo(tmp_path / "Two.ufo")]
    (tmp_path / "out" / "Two-transformed.ufo").mkdir(parents=True)
    obj = panel(ui, sources, tmp_path / "out")
    assert obj.start() is False and obj.process is None
    assert not (tmp_path / "out" / "One-transformed.ufo").exists()
    broken = tmp_path / "Broken.ufo"
    broken.mkdir()
    (broken / "metainfo.plist").write_text("not a plist")
    obj = panel(ui, [sources[0], broken], tmp_path / "out2")
    assert obj.start() is True
    drain(obj)
    assert [r.ok for r in obj.results] == [True, False]
    assert "1 succeeded, 1 failed" in message(obj)


def test_child_crash_is_reported_and_resets_controls(ui, tmp_path):
    noisy = "yes x | head -c 1000000 >&2; echo 'boom: no fontport here' >&2; exit 3"
    python = fake_python(tmp_path, noisy)
    obj = panel(ui, [ufo(tmp_path / "One.ufo")], tmp_path / "out", python=python)
    assert obj.start() is True
    drain(obj)
    assert message(obj) == "Batch stopped: boom: no fontport here"
    obj.start_button.setEnabled.assert_called_with(True)
    assert released(proc(obj))


def worker():
    return sys.modules["fontlabapp.fontui.batch_worker"]


def proc(obj):
    """The panel's current child run (its .child Popen and .scratch folder)."""
    return obj.process


def supervisor_ticks():
    timer = worker().QtCore.QTimer.return_value
    return [call.args[0] for call in timer.timeout.connect.call_args_list]


def supervise_until(predicate, timeout=20):
    """Fire the (mocked) supervisor timer until predicate(); the test never polls."""

    def fired():
        for tick in supervisor_ticks():
            tick()
        return predicate()

    wait_for(fired, timeout)


def pending():
    return len(worker()._PENDING)


def collected(child):
    """True once the supervisor reaped child; reads returncode without polling."""
    return child.returncode is not None


def released(run):
    output = run.output
    closed = output.fileno() == -1 if isinstance(output, socket.socket) else output.closed
    return closed and not os.path.exists(run.scratch)


@pytest.mark.parametrize("trigger", ["close", "parent-destroyed"])
def test_close_returns_promptly_and_releases_everything_after_child_exits(
    ui, tmp_path, trigger
):
    # The child starts late; on start it sees the cancel file and exits.
    python = fake_python(tmp_path, f'sleep 1; exec "{sys.executable}" "$@"')
    sources = [ufo(tmp_path / "One.ufo"), ufo(tmp_path / "Two.ufo")]
    obj = panel(ui, sources, tmp_path / "out", python=python)
    worker().QtCore.QTimer.reset_mock()
    assert obj.start() is True
    run = proc(obj)
    child = run.child
    began = time.monotonic()
    if trigger == "close":
        obj.close()
    else:
        parent = Signal()
        obj.connect(parent, lambda *a: obj.close())  # as Owned wires parent.destroyed
        parent.emit()
    assert time.monotonic() - began < 0.2, "close waited for the child"
    assert obj.closed and child.poll() is None and not obj.connections
    obj.widget.setParent.assert_called_once_with(None)
    obj.widget.hide.assert_called_once()
    obj.widget.deleteLater.assert_not_called()
    supervise_until(lambda: obj.widget.deleteLater.called)
    assert child.returncode == 0 and obj.widget.deleteLater.call_count == 1
    assert released(run), "stdout closed, scratch (cancel, stderr) removed"
    assert pending() == 0
    assert not list((tmp_path / "out").glob("*.ufo")), "cancelled before any font"


def test_close_escalates_terminate_then_kill(ui, tmp_path, monkeypatch):
    # Ignores SIGTERM (and the cancel file): only SIGKILL ends it.
    python = fake_python(tmp_path, "trap '' TERM; while :; do sleep 0.05; done")
    monkeypatch.setattr(ui.batch.BatchPanel, "GRACE_SECONDS", 0.2)
    monkeypatch.setattr(worker(), "KILL_SECONDS", 0.3)
    obj = panel(ui, [ufo(tmp_path / "One.ufo")], tmp_path / "out", python=python)
    worker().QtCore.QTimer.reset_mock()
    assert obj.start() is True
    run = proc(obj)
    obj.close()
    supervise_until(lambda: collected(run.child), timeout=10)
    assert run.child.returncode == -9
    assert released(run) and pending() == 0


@pytest.mark.parametrize("body,code", [("exec sleep 60", -15), ("exit 0", 0)])
def test_own_widget_destroyed_still_collects_and_releases_the_child(
    ui, tmp_path, monkeypatch, body, code
):
    python = fake_python(tmp_path, body)
    monkeypatch.setattr(ui.batch.BatchPanel, "GRACE_SECONDS", 0.2)
    obj = panel(ui, [ufo(tmp_path / "One.ufo")], tmp_path / "out", python=python)
    worker().QtCore.QTimer.reset_mock()
    assert obj.start() is True
    run = proc(obj)
    if code == 0:
        # Exercise an already-exited child deterministically. cancel() has
        # nothing to signal; the supervisor releases scratch on its next tick.
        run.child.wait(timeout=5)
    obj._destroyed()  # Qt is already deleting the panel's own widget
    assert obj.closed
    if code == 0:
        assert not os.path.exists(run.cancel_path), (
            "An exited child needs no cancel request"
        )
    else:
        assert os.path.exists(run.cancel_path), "A live child must receive cancellation"
    obj.widget.deleteLater.assert_not_called()
    obj.widget.setParent.assert_not_called()
    supervise_until(lambda: collected(run.child), timeout=10)
    assert run.child.returncode == code
    assert released(run) and pending() == 0
    obj.widget.deleteLater.assert_not_called()


def test_supervision_is_capped_and_the_extra_child_is_still_collected(
    ui, tmp_path, monkeypatch, capsys
):
    python = fake_python(tmp_path, "exec sleep 60")
    monkeypatch.setattr(ui.batch.BatchPanel, "GRACE_SECONDS", 30.0)
    cap = worker().MAX_PENDING
    source = ufo(tmp_path / "One.ufo")
    panels = []
    try:
        for i in range(cap + 1):
            obj = panel(ui, [source], tmp_path / f"out{i}", python=python)
            assert obj.start() is True
            obj.close()
            panels.append(obj)
            assert pending() <= cap
        extra = proc(panels[-1])
        assert collected(extra.child) and extra.child.returncode == -9
        assert released(extra)
        assert "pending" in capsys.readouterr().err
    finally:
        for obj in panels:
            proc(obj).child.kill()
        supervise_until(lambda: pending() == 0)


def many_sources(tmp_path, count):
    """count existing (empty) .ufo folders with long paths, for a big job spec."""
    root = tmp_path / ("d" * 150)
    root.mkdir()
    sources = [root / f"{i:03d}{'s' * 60}.ufo" for i in range(count)]
    for path in sources:
        path.mkdir()
    return sources, root


def test_start_never_waits_for_the_child_to_take_its_jobs(ui, tmp_path, monkeypatch):
    # 256 jobs exceed the 64 KiB pipe buffer; the child reads nothing for 1 s.
    python = fake_python(tmp_path, "sleep 1; cat >/dev/null; exec sleep 60")
    sources, root = many_sources(tmp_path, 256)
    obj = panel(ui, sources, root / "out", python=python)
    assert 2 * sum(len(str(p)) for p in sources) > 100_000
    worker().QtCore.QTimer.reset_mock()
    began = time.monotonic()
    started = obj.start()
    took = time.monotonic() - began
    run = proc(obj)
    monkeypatch.setattr(ui.batch.BatchPanel, "GRACE_SECONDS", 0.0)
    obj.close()
    supervise_until(lambda: collected(run.child))
    assert started is True and took < 0.5, f"start blocked {took:.2f} s"


def test_start_failure_after_spawn_kills_child_and_removes_scratch(
    ui, tmp_path, monkeypatch
):
    spawned = []
    real = subprocess.Popen

    def recording(*args, **kwargs):
        spawned.append(real(*args, **kwargs))
        return spawned[-1]

    def refuse(*args):
        raise OSError("fixture: set_blocking refused")

    scratch = tmp_path / "tmp"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    monkeypatch.setattr(subprocess, "Popen", recording)
    monkeypatch.setattr(os, "set_blocking", refuse)
    python = fake_python(tmp_path, "exec sleep 60")
    obj = panel(ui, [ufo(tmp_path / "One.ufo")], tmp_path / "out", python=python)
    assert obj.start() is False and "fixture: set_blocking" in message(obj)
    assert spawned and collected(spawned[0]), "child killed and reaped"
    assert not list(scratch.iterdir()), "scratch folder removed"


def stopped(obj, timeout=10):
    wait_for(lambda: (obj.step() or True) and not obj.running, timeout)
    return message(obj)


ROW = (
    '{"index": %d, "total": %d, "source": "/s.ufo", '
    '"destination": "/d.ufo", "ok": true, "error": null}'
)


@pytest.mark.parametrize(
    "body",
    [
        "echo 'not json'; exec sleep 60",
        """echo '{"index": 1}'; exec sleep 60""",
        """echo '["a list"]'; exec sleep 60""",
        """printf '{"index": 1, "total"'""",  # truncated last line, exit 0
    ],
)
def test_malformed_output_stops_visibly_and_collects_the_child(ui, tmp_path, body):
    python = fake_python(tmp_path, body)
    obj = panel(ui, [ufo(tmp_path / "One.ufo")], tmp_path / "out", python=python)
    worker().QtCore.QTimer.reset_mock()
    assert obj.start() is True
    run = proc(obj)
    assert stopped(obj).startswith("Batch stopped: malformed batch output")
    obj.start_button.setEnabled.assert_called_with(True)
    supervise_until(lambda: collected(run.child))
    assert released(run) and pending() == 0


def test_deeply_nested_output_stops_visibly(ui, tmp_path):
    # 20,002 bytes of nesting: json.loads raises RecursionError, not ValueError.
    deep = f"exec \"{sys.executable}\" -c \"import sys,time; print('[' * 10001 + ']' * 10001, flush=True); time.sleep(60)\""
    python = fake_python(tmp_path, deep)
    obj = panel(ui, [ufo(tmp_path / "One.ufo")], tmp_path / "out", python=python)
    worker().QtCore.QTimer.reset_mock()
    assert obj.start() is True
    run = proc(obj)
    assert stopped(obj).startswith("Batch stopped: malformed batch output")
    obj.start_button.setEnabled.assert_called_with(True)
    supervise_until(lambda: collected(run.child))
    assert released(run) and pending() == 0


def test_oversized_line_stops_visibly(ui, tmp_path, monkeypatch):
    # A small cap keeps the contract (an unterminated line over the cap stops
    # visibly) without also demanding megabytes of pipe throughput in 10 s.
    flood = f'exec "{sys.executable}" -c "import sys,time; sys.stdout.write(\'x\' * (4 << 20)); sys.stdout.flush(); time.sleep(60)"'
    python = fake_python(tmp_path, flood)
    obj = panel(ui, [ufo(tmp_path / "One.ufo")], tmp_path / "out", python=python)
    monkeypatch.setattr(worker(), "MAX_BUFFER", 16 * 1024)
    worker().QtCore.QTimer.reset_mock()
    assert obj.start() is True
    run = proc(obj)
    try:
        assert stopped(obj).startswith("Batch stopped: malformed batch output")
    finally:
        obj.close()
        supervise_until(lambda: collected(run.child))
    assert released(run) and pending() == 0



def test_default_buffer_oversized_line_stops_visibly(ui, tmp_path):
    assert worker().MAX_BUFFER == 1 << 20
    flood = f'exec "{sys.executable}" -c "import sys,time; sys.stdout.write(\'x\' * (4 << 20)); sys.stdout.flush(); time.sleep(60)"'
    python = fake_python(tmp_path, flood)
    obj = panel(ui, [ufo(tmp_path / "One.ufo")], tmp_path / "out", python=python)
    worker().QtCore.QTimer.reset_mock()
    assert obj.start() is True
    run = proc(obj)
    try:
        assert stopped(obj).startswith("Batch stopped: malformed batch output")
    finally:
        obj.close()
        supervise_until(lambda: collected(run.child))
    assert released(run) and pending() == 0


@pytest.fixture
def buffered_process(ui):
    run = worker().BatchProcess.__new__(worker().BatchProcess)
    run.buffer, run.eof = bytearray(), False
    run.child = SimpleNamespace(
        stdout=SimpleNamespace(fileno=lambda: 27182), returncode=0, poll=lambda: 0
    )
    run.output = run.child.stdout
    return run


@pytest.mark.parametrize("chunk_size", [512, 1000])
def test_read_aggregates_short_chunks_within_existing_byte_budget(
    buffered_process, monkeypatch, chunk_size
):
    requested = []

    def short_read(fd, count):
        assert fd == 27182
        requested.append(count)
        return b"x" * min(chunk_size, count)

    monkeypatch.setattr(os, "read", short_read)
    assert buffered_process.read() == []
    assert len(buffered_process.buffer) == worker().READ_BYTES
    consumed = 0
    for count in requested:
        assert count == worker().READ_BYTES - consumed
        consumed += min(chunk_size, count)
    assert consumed == worker().READ_BYTES
    assert requested[-1] == (512 if chunk_size == 512 else 536)


def test_read_short_chunks_reach_unchanged_oversized_line_cap(
    buffered_process, monkeypatch
):
    buffered_process.buffer.extend(b"x" * (worker().MAX_BUFFER - worker().READ_BYTES))
    calls = []

    def short_read(fd, count):
        calls.append(count)
        return b"x" * min(512, count)

    monkeypatch.setattr(os, "read", short_read)
    with pytest.raises(worker().ProtocolError, match="malformed batch output: line over"):
        buffered_process.read()
    assert len(buffered_process.buffer) == worker().MAX_BUFFER
    assert len(calls) == worker().READ_BYTES // 512


@pytest.mark.parametrize("already_eof", [False, True])
def test_read_at_existing_cap_never_admits_more_bytes(
    buffered_process, monkeypatch, already_eof
):
    buffered_process.buffer.extend(b"x" * worker().MAX_BUFFER)
    buffered_process.eof = already_eof
    monkeypatch.setattr(os, "read", lambda *args: pytest.fail("read beyond existing cap"))
    with pytest.raises(worker().ProtocolError, match="malformed batch output: line over"):
        buffered_process.read()


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("stop", [b"", BlockingIOError()])
def test_read_stops_at_initial_or_partial_EOF_or_EAGAIN(
    buffered_process, monkeypatch, partial, stop
):
    chunks = iter(([b"x" * 512] if partial else []) + [stop])
    calls = []

    def finite_read(fd, count):
        calls.append(count)
        chunk = next(chunks)
        if isinstance(chunk, BaseException):
            raise chunk
        return chunk

    monkeypatch.setattr(os, "read", finite_read)
    assert buffered_process.read() == []
    assert buffered_process.buffer == (b"x" * 512 if partial else b"")
    assert buffered_process.eof == (stop == b"")
    assert calls == ([worker().READ_BYTES, worker().READ_BYTES - 512] if partial else [worker().READ_BYTES])
    if buffered_process.eof:
        assert buffered_process.read() == []  # no additional syscall after EOF


@pytest.mark.parametrize("error_type", [OSError, InterruptedError])
@pytest.mark.parametrize("partial", [False, True])
def test_read_propagates_other_errors_and_keeps_received_bytes(
    buffered_process, monkeypatch, error_type, partial
):
    error = error_type("owned read failure")
    chunks = iter(([b"abc"] if partial else []) + [error])

    def failed_read(fd, count):
        chunk = next(chunks)
        if isinstance(chunk, BaseException):
            raise chunk
        return chunk

    monkeypatch.setattr(os, "read", failed_read)
    with pytest.raises(error_type) as caught:
        buffered_process.read()
    assert caught.value is error
    assert buffered_process.buffer == (b"abc" if partial else b"")


def test_read_short_chunks_preserve_newlines_and_64_row_backlog(
    buffered_process, monkeypatch
):
    data = b"\n" + b"".join((ROW % (i, 100)).encode() + b"\n" for i in range(1, 101))
    chunks = iter([data[:17], data[17:], b""])
    monkeypatch.setattr(os, "read", lambda fd, count: next(chunks))
    first = buffered_process.read()
    assert len(first) == worker().ROWS_PER_POLL == 64
    assert buffered_process.eof and buffered_process.buffer
    second = buffered_process.read()
    assert [row["index"] for row in first + second] == list(range(1, 101))
    assert not buffered_process.buffer and buffered_process.done
    assert buffered_process.read() == []


def test_read_preexisting_cap_admission_keeps_bounded_overshoot(
    buffered_process, monkeypatch
):
    buffered_process.buffer.extend(b"x" * (worker().MAX_BUFFER - 1))
    requests = []

    def full_read(fd, count):
        requests.append(count)
        return b"x" * count

    monkeypatch.setattr(os, "read", full_read)
    with pytest.raises(worker().ProtocolError, match="malformed batch output: line over"):
        buffered_process.read()
    assert requests == [worker().READ_BYTES]
    assert len(buffered_process.buffer) == worker().MAX_BUFFER - 1 + worker().READ_BYTES


def test_oversized_failure_finally_collects_actual_owned_child(
    ui, tmp_path, monkeypatch
):
    captured = []
    original_proc = proc

    def capture(obj):
        run = original_proc(obj)
        captured.append((obj, run))
        return run

    def sentinel(*args):
        raise AssertionError("owned cleanup sentinel")

    monkeypatch.setattr(sys.modules[__name__], "proc", capture)
    monkeypatch.setattr(sys.modules[__name__], "stopped", sentinel)
    try:
        with pytest.raises(AssertionError, match="owned cleanup sentinel"):
            test_default_buffer_oversized_line_stops_visibly(ui, tmp_path)
        assert len(captured) == 1
        assert collected(captured[0][1].child) and released(captured[0][1])
        assert pending() == 0
    finally:
        # OLD RED must not orphan its real flood child when its assertion fails.
        for obj, run in captured:
            obj.close()
            supervise_until(lambda: collected(run.child))
            assert collected(run.child) and released(run)


def test_output_burst_is_processed_in_bounded_slices(ui, tmp_path):
    rows = 10_000
    script = tmp_path / "burst.py"
    script.write_text(
        f"import sys\nfor i in range(1, {rows} + 1):\n"
        f"    print({ROW!r} % (i, {rows}))\n"
    )
    python = fake_python(tmp_path, f'exec "{sys.executable}" "{script}"')
    obj = panel(ui, [ufo(tmp_path / "One.ufo")], tmp_path / "out", python=python)
    assert obj.start() is True
    time.sleep(0.5)  # the whole burst is waiting in the pipe
    limit = worker().ROWS_PER_POLL
    sizes = []
    while obj.running:
        before = len(obj.results)
        obj.step()
        sizes.append(len(obj.results) - before)
        time.sleep(0.001)
    assert max(sizes) <= limit, f"one poll recorded {max(sizes)} rows"
    assert len(obj.results) == rows, "no row dropped after exit"
    assert message(obj) == f"Finished: {rows} succeeded, 0 failed."


def test_child_environment_is_an_explicit_allowlist(ui, tmp_path, monkeypatch):
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "DYLD_LIBRARY_PATH"):
        monkeypatch.setenv(name, f"/fontlab-marker-{name}")
    monkeypatch.setenv("QT_PLUGIN_PATH", "/fontlab-marker-qt")
    # The child records variable names and a marker count, never values.
    names, markers = tmp_path / "names.txt", tmp_path / "markers.txt"
    python = fake_python(
        tmp_path,
        f'env | cut -d= -f1 > "{names}"; env | grep -c fontlab-marker > "{markers}"; '
        f'exec "{sys.executable}" "$@"',
    )
    obj = panel(ui, [ufo(tmp_path / "One.ufo")], tmp_path / "out", python=python)
    assert obj.start() is True
    drain(obj)
    assert [r.ok for r in obj.results] == [True]
    seen = set(names.read_text().split())
    assert markers.read_text().strip() == "0", "a FontLab-side variable leaked"
    assert "PATH" in seen and not {n for n in seen if n.startswith(("PYTHON", "DYLD"))}


def test_child_environment_carries_no_secret_like_names(ui, tmp_path, monkeypatch):
    planted = ("FONTLAB_FIXTURE_API_KEY", "FIXTURE_TOKEN", "FIXTURE_SECRET")
    for name in planted:
        monkeypatch.setenv(name, "fixture-not-a-secret")
    # The child writes only how many of its variable names look secret-like.
    count = tmp_path / "count.txt"
    python = fake_python(
        tmp_path,
        f'env | cut -d= -f1 | grep -ciE "KEY|TOKEN|SECRET" > "{count}"; '
        f'exec "{sys.executable}" "$@"',
    )
    assert all(n in os.environ for n in planted), "fixture variables not set"
    obj = panel(ui, [ufo(tmp_path / "One.ufo")], tmp_path / "out", python=python)
    assert obj.start() is True
    drain(obj)
    assert [r.ok for r in obj.results] == [True]
    found = int(count.read_text().strip() or 0)
    assert found == 0, f"{found} secret-like variable names reached the child"


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot):
        self.slots.remove(slot)

    def emit(self, *args):
        for slot in list(self.slots):
            slot(*args)


class Field:
    def __init__(self, text=""):
        self.text = text

    def setText(self, text):
        self.text = text

    def blockSignals(self, flag):
        return False


class Number(Field):
    def __init__(self):
        super().__init__()
        self.value = 0

    def setValue(self, value):
        self.value = value


class Check(Field):
    checked = True

    def setChecked(self, flag):
        self.checked = flag


@pytest.mark.parametrize(
    "matrix,intensity",
    [
        ((1.23456789, 0.1, -0.30000000000000004, 1, 1e-12, 12345.678901234), 60.25),
        ((2, 0, 0, 1, 10, 0), 33.333333333333336),
    ],
)
def test_settings_round_trip_keeps_full_precision(ui, tmp_path, matrix, intensity):
    from fontlab_fontport.recipe import Recipe

    cls = ui.transform.TransformEditor
    obj = cls.__new__(cls)
    obj.matrix = {key: Field() for key in ("xx", "xy", "yx", "yy", "dx", "dy")}
    obj.intensity_field, obj.intensity_slider = Field(), Number()
    obj.enabled_control = Check()
    wanted = Recipe(matrix=matrix, intensity=intensity)
    obj._show(wanted)
    assert obj.recipe() == wanted
    assert obj.intensity_slider.value == round(intensity)
    obj.diagnostic = Mock()
    obj.save_settings(str(tmp_path / "r.json"))
    assert Recipe.load(tmp_path / "r.json") == wanted


@pytest.fixture
def transport(ui, tmp_path, monkeypatch):
    """Actual socket endpoints and constructor, with no live child to orphan."""
    pairs, calls, scratch = [], [], []
    real_pair, real_mkdtemp = socket.socketpair, tempfile.mkdtemp
    child = SimpleNamespace(stdout=None, returncode=None)
    child.poll = Mock(side_effect=lambda: child.returncode)
    child.kill = Mock(side_effect=lambda: setattr(child, "returncode", -9))
    child.wait = Mock(side_effect=lambda *args: child.returncode)

    def pair(*args):
        assert args == (socket.AF_UNIX, socket.SOCK_STREAM)
        endpoints = real_pair(*args)
        pairs.append(endpoints)
        return endpoints

    def spawn(*args, **kwargs):
        calls.append(kwargs)
        if kwargs["stdout"] != subprocess.PIPE:
            assert os.get_blocking(kwargs["stdout"].fileno()), "child writer stays blocking"
        return child

    def directory(*args, **kwargs):
        path = real_mkdtemp(*args, dir=tmp_path, **kwargs)
        scratch.append(path)
        return path

    monkeypatch.setattr(socket, "socketpair", pair)
    monkeypatch.setattr(subprocess, "Popen", spawn)
    monkeypatch.setattr(tempfile, "mkdtemp", directory)
    monkeypatch.setattr(worker().sys, "platform", "darwin")
    try:
        yield SimpleNamespace(pairs=pairs, calls=calls, scratch=scratch, child=child)
    finally:
        # OLD RED/new assertion failures still close every owned fixture endpoint.
        for endpoints in pairs:
            for endpoint in endpoints:
                endpoint.close()
        if child.stdout is not None:
            child.stdout.close()
        for path in scratch:
            shutil.rmtree(path, ignore_errors=True)


def test_darwin_constructor_owns_receiver_and_closes_parent_writer(transport):
    run = None
    try:
        run = worker().BatchProcess(sys.executable, [], {})
        receiver, writer = transport.pairs[0]
        assert run.output is receiver and run.child.stdout is None
        assert transport.calls[0]["stdout"] is writer
        assert writer.fileno() == -1 and not os.get_blocking(receiver.fileno())
        assert run.read() == [] and run.eof, "closed parent writer permits actual EOF"
        run.child.returncode = 0
        assert run.done
        run.release()
        run.release()
        assert released(run), "receiver closed and scratch removed, twice safely"
    finally:
        if run is not None:
            run.kill()
            run.release()


@pytest.mark.parametrize("failure", ["pair", "spawn", "stderr", "nonblocking"])
def test_darwin_constructor_failure_closes_endpoints_and_collects_child(
    transport, monkeypatch, failure
):
    error = OSError("owned " + failure + " failure")

    def refuse(*args, **kwargs):
        raise error

    if failure == "pair":
        monkeypatch.setattr(socket, "socketpair", refuse)
    elif failure == "spawn":
        monkeypatch.setattr(subprocess, "Popen", refuse)
    elif failure == "stderr":
        real_open = open

        def refuse_stderr(path, *args, **kwargs):
            if os.fspath(path).endswith("/stderr"):
                raise error
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr(worker(), "open", refuse_stderr, raising=False)
    else:
        monkeypatch.setattr(os, "set_blocking", refuse)
    with pytest.raises(OSError) as caught:
        worker().BatchProcess(sys.executable, [], {})
    assert caught.value is error, "successful cleanup preserves the launch error"
    assert len(transport.pairs) == (0 if failure == "pair" else 1)
    assert all(endpoint.fileno() == -1 for pair in transport.pairs for endpoint in pair)
    assert all(not os.path.exists(path) for path in transport.scratch)
    assert transport.child.kill.call_count == (1 if failure == "nonblocking" else 0)
    assert transport.child.wait.call_count == (1 if failure == "nonblocking" else 0)
    if failure == "nonblocking":
        assert transport.child.returncode == -9


def test_release_closes_receiver_without_a_child_and_is_repeatable(ui, tmp_path):
    receiver, writer = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    run = worker().BatchProcess.__new__(worker().BatchProcess)
    run.child, run.output = None, receiver
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    run.scratch = str(scratch)
    try:
        run.release()
        run.release()
        assert receiver.fileno() == -1 and not scratch.exists()
    finally:
        receiver.close()
        writer.close()
        shutil.rmtree(scratch, ignore_errors=True)


def test_non_darwin_constructor_retains_pipe_and_owns_actual_stdout(
    transport, monkeypatch, tmp_path
):
    monkeypatch.setattr(worker().sys, "platform", "linux")
    transport.child.stdout = tempfile.TemporaryFile(dir=tmp_path)
    run = None
    try:
        run = worker().BatchProcess(sys.executable, [], {})
        assert transport.calls[0]["stdout"] == subprocess.PIPE and not transport.pairs
        assert run.output is run.child.stdout
        assert not os.get_blocking(run.output.fileno())
        run.release()
        assert released(run)
    finally:
        if run is not None:
            run.kill()
            run.release()



def test_constructor_cleanup_failure_chains_primary_and_still_closes_output(
    transport, monkeypatch
):
    primary, cleanup_error = OSError("owned nonblock failure"), OSError("owned kill failure")

    def refuse_blocking(*args):
        raise primary

    def refuse_kill():
        raise cleanup_error

    transport.child.kill.side_effect = refuse_kill
    monkeypatch.setattr(os, "set_blocking", refuse_blocking)
    with pytest.raises(OSError) as caught:
        worker().BatchProcess(sys.executable, [], {})
    assert caught.value is cleanup_error and caught.value.__context__ is primary
    assert transport.child.returncode is None, "failed cleanup is not collection success"
    assert all(endpoint.fileno() == -1 for pair in transport.pairs for endpoint in pair)
    assert all(not os.path.exists(path) for path in transport.scratch)


def test_oversized_fixture_timer_failure_chains_original_and_outer_finally_collects(
    ui, tmp_path, monkeypatch
):
    captured = []
    original_proc = proc
    primary, cleanup_error = AssertionError("owned original assertion"), OSError("owned timer failure")

    def capture(obj):
        run = original_proc(obj)
        captured.append((obj, run))
        worker().QtCore.QTimer.return_value.start.side_effect = cleanup_error
        return run

    def refuse(*args):
        raise primary

    monkeypatch.setattr(sys.modules[__name__], "proc", capture)
    monkeypatch.setattr(sys.modules[__name__], "stopped", refuse)
    try:
        with pytest.raises(OSError) as caught:
            test_default_buffer_oversized_line_stops_visibly(ui, tmp_path)
        assert caught.value is cleanup_error and caught.value.__context__ is primary
    finally:
        # An injected supervisor-timer failure remains an error; this test owns
        # the extra final collector so it cannot leave its flood child running.
        worker().QtCore.QTimer.return_value.start.side_effect = None
        for obj, run in captured:
            run.kill()
            worker().supervise(run, obj.widget, obj.GRACE_SECONDS, obj.POLL_MS)
            supervise_until(lambda: collected(run.child) and pending() == 0)
            assert collected(run.child) and released(run)


def test_read_when_two_short_fragments_ready_then_both_collected_in_one_poll(
    ui, monkeypatch
):
    module = worker()
    run = module.BatchProcess.__new__(module.BatchProcess)
    run.buffer, run.eof = bytearray(), False
    run.child = SimpleNamespace(stdout=SimpleNamespace(fileno=lambda: -234))
    run.output = run.child.stdout
    fragments = [b"x" * 512, b"y" * 512]
    requests = []
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        requests.append(count)
        if not fragments:
            raise BlockingIOError
        chunk = fragments.pop(0)
        assert len(chunk) <= count, "the owned seam must honor os.read's request"
        return chunk

    monkeypatch.setattr(os, "read", read_fd)
    assert run.read() == []
    assert run.buffer == bytearray(b"x" * 512 + b"y" * 512), (
        "one poll must collect both immediately ready short fragments"
    )
    assert run.eof is False
    assert requests == [module.READ_BYTES, module.READ_BYTES - 512, module.READ_BYTES - 1024]


def test_read_when_short_fragments_reach_max_buffer_then_existing_protocol_error(
    ui, monkeypatch
):
    module = worker()
    run = module.BatchProcess.__new__(module.BatchProcess)
    run.buffer, run.eof = bytearray(b"z" * (module.MAX_BUFFER - 1024)), False
    run.child = SimpleNamespace(stdout=SimpleNamespace(fileno=lambda: -234))
    run.output = run.child.stdout
    fragments = [b"x" * 512, b"y" * 512]
    requests = []
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        requests.append(count)
        if not fragments:
            raise BlockingIOError
        chunk = fragments.pop(0)
        assert len(chunk) <= count, "the owned seam must honor os.read's request"
        return chunk

    monkeypatch.setattr(os, "read", read_fd)
    with pytest.raises(
        module.ProtocolError,
        match=f"^malformed batch output: line over {module.MAX_BUFFER} bytes$",
    ):
        run.read()
    assert len(run.buffer) == module.MAX_BUFFER
    assert run.eof is False
    assert requests == [module.READ_BYTES, module.READ_BYTES - 512]


@pytest.fixture
def reader_run(ui):
    module = worker()
    run = module.BatchProcess.__new__(module.BatchProcess)
    run.buffer, run.eof = bytearray(), False
    run.child = SimpleNamespace(
        stdout=SimpleNamespace(fileno=lambda: -234), returncode=0, poll=lambda: 0
    )
    run.output = run.child.stdout
    return run


@pytest.mark.parametrize("fragment", [b"", b"tail"])
def test_read_when_eagain_then_prebuffered_row_parsed_and_fragment_retained(
    reader_run, monkeypatch, fragment
):
    module, run = worker(), reader_run
    run.buffer.extend((ROW % (1, 2) + "\n").encode())
    ready = [fragment] if fragment else []
    requests = []
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        assert count > 0
        requests.append(count)
        if ready:
            chunk = ready.pop()
            assert len(chunk) <= count
            return chunk
        raise BlockingIOError

    monkeypatch.setattr(os, "read", read_fd)
    assert run.read() == [{
        "index": 1, "total": 2, "source": "/s.ufo", "destination": "/d.ufo",
        "ok": True, "error": None,
    }]
    assert run.buffer == bytearray(fragment) and run.eof is False
    assert requests == [module.READ_BYTES] + (
        [module.READ_BYTES - len(fragment)] if fragment else []
    )


@pytest.mark.parametrize("fragment", [b"", b" "])
def test_read_when_eof_then_backlog_returns64_then1_without_more_reads(
    reader_run, monkeypatch, fragment
):
    module, run = worker(), reader_run
    run.buffer.extend("".join(ROW % (i, 65) + "\n" for i in range(1, 66)).encode())
    ready = [fragment] if fragment else []
    requests = []
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        assert count > 0
        requests.append(count)
        if ready:
            chunk = ready.pop()
            assert len(chunk) <= count
            return chunk
        return b""

    monkeypatch.setattr(os, "read", read_fd)
    first = run.read()
    assert len(first) == 64 and run.eof and not run.done
    recorded = list(requests)
    second = run.read()
    assert len(second) == 1 and run.done
    assert first + second == [{
        "index": i, "total": 65, "source": "/s.ufo", "destination": "/d.ufo",
        "ok": True, "error": None,
    } for i in range(1, 66)]
    assert run.read() == [] and requests == recorded
    assert requests == [module.READ_BYTES] + (
        [module.READ_BYTES - 1] if fragment else []
    )
    run.check_tail()


def test_read_when_always_ready_tiny_fragments_then16_calls_per_poll(
    reader_run, monkeypatch
):
    module, run = worker(), reader_run
    requests = []
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        assert count > 0
        requests.append(count)
        return b"x"

    monkeypatch.setattr(os, "read", read_fd)
    expected = [module.READ_BYTES - i for i in range(module.READ_BYTES)]
    assert run.read() == []
    assert requests == expected and run.buffer == bytearray(b"x" * module.READ_BYTES)
    assert run.read() == []
    assert requests == expected * 2 and run.buffer == bytearray(b"x" * (2 * module.READ_BYTES))
    assert run.eof is False


@pytest.mark.parametrize("fragment_size", [65536, 10000])
def test_read_when_byte_budget_spent_then_no_extra_or_zero_read(
    reader_run, monkeypatch, fragment_size
):
    module, run = worker(), reader_run
    requests, sizes = [], []
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        assert count > 0
        requests.append(count)
        size = min(count, fragment_size)
        sizes.append(size)
        return b"x" * size

    monkeypatch.setattr(os, "read", read_fd)
    assert run.read() == []
    assert run.buffer == bytearray(b"x" * module.READ_BYTES)
    assert sum(sizes) == module.READ_BYTES and run.eof is False
    assert requests == [module.READ_BYTES - i * fragment_size
                        for i in range((module.READ_BYTES + fragment_size - 1) // fragment_size)]
    assert len(requests) < 16


@pytest.mark.parametrize("extra", [0, 1])
@pytest.mark.parametrize("complete", [False, True])
def test_read_when_buffer_at_threshold_then_no_read_and_existing_parse_or_error(
    reader_run, monkeypatch, extra, complete
):
    module, run = worker(), reader_run
    run.buffer.extend(b" " * (module.MAX_BUFFER + extra))
    if complete:
        run.buffer.extend((ROW % (1, 2) + "\n").encode())
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        raise AssertionError("no read may start at or above MAX_BUFFER")

    monkeypatch.setattr(os, "read", read_fd)
    if complete:
        assert run.read() == [{
            "index": 1, "total": 2, "source": "/s.ufo", "destination": "/d.ufo",
            "ok": True, "error": None,
        }]
        assert run.buffer == bytearray()
    else:
        with pytest.raises(module.ProtocolError, match="malformed batch output: line over"):
            run.read()
        assert len(run.buffer) == module.MAX_BUFFER + extra
    assert run.eof is False


def test_read_when_threshold_crossed_then_old_maximum_overshoot_preserved(
    reader_run, monkeypatch
):
    module, run = worker(), reader_run
    run.buffer.extend(b" " * (module.MAX_BUFFER - 1))
    requests = []
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        assert count > 0
        requests.append(count)
        return b" " * count

    monkeypatch.setattr(os, "read", read_fd)
    with pytest.raises(module.ProtocolError, match="malformed batch output: line over"):
        run.read()
    assert requests == [module.READ_BYTES]
    assert len(run.buffer) == module.MAX_BUFFER - 1 + module.READ_BYTES
    assert run.eof is False


def test_read_when_ready_complete_row_crosses_threshold_then_old_row_accepted(
    reader_run, monkeypatch
):
    module, run = worker(), reader_run
    run.buffer.extend(b" " * (module.MAX_BUFFER - 1))
    ready = bytearray((ROW % (1, 2) + "\n").encode())
    requests = []
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        assert count > 0
        requests.append(count)
        chunk = bytes(ready[:count])
        del ready[:count]
        return chunk

    monkeypatch.setattr(os, "read", read_fd)
    assert run.read() == [{
        "index": 1, "total": 2, "source": "/s.ufo", "destination": "/d.ufo",
        "ok": True, "error": None,
    }]
    assert run.buffer == bytearray() and not ready and run.eof is False
    assert requests == [module.READ_BYTES]


@pytest.mark.parametrize("between_polls", [False, True])
def test_read_when_valid_json_fragmented_then_exact_row_within_or_across_polls(
    reader_run, monkeypatch, between_polls
):
    run = reader_run
    encoded = (ROW % (1, 2) + "\n").encode()
    first, second = encoded[:20], encoded[20:]
    ready = [first] if between_polls else [first, second]
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        assert count > 0
        if not ready:
            raise BlockingIOError
        chunk = ready.pop(0)
        assert len(chunk) <= count
        return chunk

    monkeypatch.setattr(os, "read", read_fd)
    if between_polls:
        assert run.read() == [] and run.buffer == bytearray(first)
        assert run.eof is False
        ready.append(second)
    assert run.read() == [{
        "index": 1, "total": 2, "source": "/s.ufo", "destination": "/d.ufo",
        "ok": True, "error": None,
    }]
    assert run.buffer == bytearray() and run.eof is False


@pytest.mark.parametrize("line", [b"not JSON\n", b"[" * 10001 + b"]" * 10001 + b"\n"])
def test_read_when_malformed_or_deeply_nested_then_actual_protocol_error(
    reader_run, monkeypatch, line
):
    module, run = worker(), reader_run
    run.buffer.extend(line)
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        assert count > 0
        raise BlockingIOError

    monkeypatch.setattr(os, "read", read_fd)
    with pytest.raises(module.ProtocolError, match="malformed batch output"):
        run.read()


@pytest.mark.parametrize("tail", [b"unfinished", b" \t\r"])
def test_read_when_eof_tail_then_success_rejects_nonblank_and_accepts_whitespace(
    reader_run, tail
):
    module, run = worker(), reader_run
    run.eof = True
    run.buffer.extend(tail)
    assert run.read() == [] and run.done
    if tail.strip():
        with pytest.raises(module.ProtocolError, match="malformed batch output"):
            run.check_tail()
    else:
        run.check_tail()


def test_read_when_other_os_error_then_same_error_propagates(reader_run, monkeypatch):
    run = reader_run
    error = OSError(5, "owned fixture read failure")
    requests = []
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        assert count > 0
        requests.append(count)
        raise error

    monkeypatch.setattr(os, "read", read_fd)
    with pytest.raises(OSError) as caught:
        run.read()
    assert caught.value is error and requests == [worker().READ_BYTES]
    assert run.buffer == bytearray() and run.eof is False



@pytest.fixture
def expected_reader_origin(reader_run):
    """Bind the real reader to independent source or controller expectations."""
    import hashlib
    import json
    from pathlib import Path

    # Pinned combined-source candidate; final independent review validates this digest.
    approved_hash = "55eee9192350e076d80c45f86633e733672674802cd0df3c902925c0536d654e"
    record_path = os.environ.get("FONTLABAPP_READER_ORIGIN_RECORD")
    if record_path is None:
        prefix = Path(os.path.abspath(__file__)).parent.parent
        root = prefix / "src" / "fontlabapp"
        expected = root / "fontui" / "batch_worker.py"
    else:
        assert record_path, "reader-origin: explicit record path is empty"
        record_file = Path(record_path)
        assert record_file.is_absolute(), "reader-origin: record path must be absolute"
        assert record_file == record_file.resolve(strict=True), "reader-origin: record symlink"
        record = json.loads(record_file.read_text(encoding="utf-8"))
        assert type(record) is dict and set(record) == {
            "prefix", "package_root", "worker_file", "worker_sha256"
        }, "reader-origin: record fields differ"
        assert all(type(value) is str and value for value in record.values()), "reader-origin: record values"
        assert record["worker_sha256"] == approved_hash, "reader-origin: unapproved worker hash"
        prefix = Path(record["prefix"])
        root = Path(record["package_root"])
        expected = Path(record["worker_file"])
        assert root.name == "fontlabapp" and root.is_relative_to(prefix), "reader-origin: package outside prefix"
    for path in (prefix, root, expected):
        assert path.is_absolute() and path == path.resolve(strict=True), "reader-origin: missing or symlinked path"
    assert expected == root / "fontui" / "batch_worker.py", "reader-origin: wrong worker path"
    assert hashlib.sha256(expected.read_bytes()).hexdigest() == approved_hash, "reader-origin: worker bytes differ"
    module = worker()
    assert module.__name__ == "fontlabapp.fontui.batch_worker", "reader-origin: module name"
    assert module.__package__ == "fontlabapp.fontui", "reader-origin: module package"
    assert module.__spec__ is not None, "reader-origin: module has no spec"
    assert module.__spec__.name == module.__name__ and module.__spec__.parent == module.__package__, "reader-origin: spec name/package"
    assert module.__spec__.origin == module.__file__ == str(expected), "reader-origin: spec/file differ"
    assert list(sys.modules["fontlabapp"].__path__) == [str(root)], "reader-origin: package root differs"
    assert list(sys.modules["fontlabapp.fontui"].__path__) == [str(root / "fontui")], "reader-origin: fontui root differs"
    assert type(reader_run) is module.BatchProcess, "reader-origin: reader class differs"
    assert reader_run.read.__func__ is module.BatchProcess.read, "reader-origin: bound method differs"
    assert reader_run.read.__func__.__code__.co_filename == str(expected), "reader-origin: code filename differs"
    return str(expected)


def test_read_when_transient_eagain_between_ready_fragments_then_collected_in_one_poll(
    reader_run, monkeypatch, expected_reader_origin
):
    module, run = worker(), reader_run
    origin = f"module={module.__file__}; read={run.read.__func__.__code__.co_filename}"
    expected_origin = expected_reader_origin
    assert module.__file__ == run.read.__func__.__code__.co_filename == expected_origin
    assert run.read.__func__ is module.BatchProcess.read
    ready, requests = [b"x" * 512, None, b"y" * 512], []
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        assert count > 0
        requests.append(count)
        chunk = ready.pop(0) if ready else None
        if chunk is None:
            raise BlockingIOError
        assert len(chunk) <= count
        return chunk

    monkeypatch.setattr(os, "read", read_fd)
    assert run.read() == []
    assert run.buffer == bytearray(b"x" * 512), origin
    assert requests == [module.READ_BYTES, module.READ_BYTES - 512]
    assert ready == [b"y" * 512] and run.eof is False
    assert run.read() == []
    assert run.buffer == bytearray(b"x" * 512 + b"y" * 512), origin
    assert run.eof is False
    assert requests == [module.READ_BYTES, module.READ_BYTES - 512] * 2


def test_read_when_transient_eagain_then_ready_fragments_reach_limit_then_protocol_error(
    reader_run, monkeypatch, expected_reader_origin
):
    module, run = worker(), reader_run
    origin = f"module={module.__file__}; read={run.read.__func__.__code__.co_filename}"
    expected_origin = expected_reader_origin
    assert module.__file__ == run.read.__func__.__code__.co_filename == expected_origin
    assert run.read.__func__ is module.BatchProcess.read
    run.buffer.extend(b"z" * (module.MAX_BUFFER - 1024))
    ready, requests = [b"x" * 512, None, b"y" * 512], []
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        assert count > 0
        requests.append(count)
        chunk = ready.pop(0) if ready else None
        if chunk is None:
            raise BlockingIOError
        assert len(chunk) <= count
        return chunk

    monkeypatch.setattr(os, "read", read_fd)
    assert run.read() == []
    assert run.buffer == bytearray(b"z" * (module.MAX_BUFFER - 1024) + b"x" * 512), origin
    assert len(run.buffer) == module.MAX_BUFFER - 512
    assert ready == [b"y" * 512] and run.eof is False
    assert requests == [module.READ_BYTES, module.READ_BYTES - 512]
    caught = None
    try:
        run.read()
    except module.ProtocolError as error:
        caught = error
    assert caught is not None, origin
    assert type(caught) is module.ProtocolError
    assert str(caught) == f"malformed batch output: line over {module.MAX_BUFFER} bytes"
    assert len(run.buffer) == module.MAX_BUFFER
    assert run.eof is False
    assert requests == [module.READ_BYTES, module.READ_BYTES - 512, module.READ_BYTES]
    assert run.buffer == bytearray(b"z" * (module.MAX_BUFFER - 1024) + b"x" * 512 + b"y" * 512)


def test_read_when_all_eagain_then_exactly16_attempts_without_bytes_or_eof(
    reader_run, monkeypatch, expected_reader_origin
):
    module, run = worker(), reader_run
    origin = f"module={module.__file__}; read={run.read.__func__.__code__.co_filename}"
    expected_origin = expected_reader_origin
    assert module.__file__ == run.read.__func__.__code__.co_filename == expected_origin
    assert run.read.__func__ is module.BatchProcess.read
    requests = []
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        assert count > 0
        requests.append(count)
        raise BlockingIOError

    monkeypatch.setattr(os, "read", read_fd)
    assert run.read() == []
    assert requests == [module.READ_BYTES], origin
    assert run.buffer == bytearray()
    assert run.eof is False


def test_read_when_initial_eagain_then_data_and_eof_then_stops_at_eof(
    reader_run, monkeypatch, expected_reader_origin
):
    module, run = worker(), reader_run
    origin = f"module={module.__file__}; read={run.read.__func__.__code__.co_filename}"
    expected_origin = expected_reader_origin
    assert module.__file__ == run.read.__func__.__code__.co_filename == expected_origin
    assert run.read.__func__ is module.BatchProcess.read
    ready, requests = [None, b"x" * 512, b""], []
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        assert count > 0
        requests.append(count)
        assert ready, "EOF must stop collection immediately"
        chunk = ready.pop(0)
        if chunk is None:
            raise BlockingIOError
        assert len(chunk) <= count
        return chunk

    monkeypatch.setattr(os, "read", read_fd)
    assert run.read() == []
    assert run.buffer == bytearray() and run.eof is False
    assert requests == [module.READ_BYTES]
    assert ready == [b"x" * 512, b""]
    assert run.read() == []
    assert run.buffer == bytearray(b"x" * 512), origin
    assert run.eof is True
    assert requests == [module.READ_BYTES, module.READ_BYTES, module.READ_BYTES - 512]
    assert ready == []


@pytest.mark.parametrize("budget", ["byte-cap", "attempt-cap"], ids=["byte-cap", "attempt-cap"])
def test_read_when_mixed_eagain_and_data_then_existing_attempt_and_byte_budgets_hold(
    reader_run, monkeypatch, expected_reader_origin, budget
):
    module, run = worker(), reader_run
    origin = f"module={module.__file__}; read={run.read.__func__.__code__.co_filename}"
    expected_origin = expected_reader_origin
    assert module.__file__ == run.read.__func__.__code__.co_filename == expected_origin
    assert run.read.__func__ is module.BatchProcess.read
    if budget == "byte-cap":
        ready = [b"x" * 16384, None, b"x" * 16384, None, b"x" * 16384, None, b"x" * 16384, None]
        expected = b"x" * module.READ_BYTES
        expected_requests = [module.READ_BYTES, module.READ_BYTES - 16384] * 4
    else:
        ready = [None, b"x"] * 8 + [None]
        expected = b"x" * 8
        expected_requests = [module.READ_BYTES] + [module.READ_BYTES, module.READ_BYTES - 1] * 8
    requests = []
    real_read = os.read

    def read_fd(fd, count):
        if fd != -234:
            return real_read(fd, count)
        assert count > 0
        requests.append(count)
        assert ready, "each poll must stop at its first EAGAIN"
        chunk = ready.pop(0)
        if chunk is None:
            raise BlockingIOError
        assert len(chunk) <= count
        return chunk

    monkeypatch.setattr(os, "read", read_fd)
    polls = 0
    while ready:
        previous = len(requests)
        assert run.read() == []
        polls += 1
        assert len(requests) - previous <= module.READ_BYTES + 1
    assert polls == (4 if budget == "byte-cap" else 9)
    assert run.buffer == bytearray(expected), origin
    assert requests == expected_requests
    assert len(run.buffer) <= module.READ_BYTES and len(requests) == len(expected_requests)
    assert run.eof is False and ready == []


@pytest.mark.parametrize("release_fault", [False, True], ids=["control", "retry"])
def test_red12_real_child_release_uses_registered_callback_and_explicit_retry(ui, tmp_path, monkeypatch, release_fault):
    """Actual constructor/child, bounded collection, and exact owned cleanup."""
    module = worker()
    run = module.BatchProcess(fake_python(tmp_path, "exit 0"), [], {})
    original_release = run.release
    primary = None
    try:
        run.child.wait(timeout=5.0)
        assert run.child.returncode == 0
        calls = []
        injected = RuntimeError("owned real child release")

        def release():
            calls.append(True)
            if release_fault and len(calls) == 1:
                raise injected
            return original_release()

        monkeypatch.setattr(run, "release", release)
        module.supervise(run, None, 10.0, 50)
        ticks = supervisor_ticks()
        assert len(ticks) == 1, "actual supervision registered exactly one callback"
        escaped = None
        try:
            ticks[0]()
        except BaseException as error:
            escaped = error
        assert escaped is None, "the actual registered timeout contains release failure"
        if release_fault:
            assert calls == [True] and not (run.output.fileno() == -1 if isinstance(run.output, socket.socket) else run.output.closed) and pending() == 1
            ticks[0]()
            assert calls == [True], "timeout delivery cannot implicitly retry release"
            module.supervise(run, None, 10.0, 50)
            ticks[0]()
            assert calls == [True, True]
        else:
            assert calls == [True]
        assert released(run) and collected(run.child) and pending() == 0
    except BaseException as error:
        primary = error
        raise
    finally:
        cleanup = []
        try:
            if run.child.poll() is None:
                run.child.kill()
            run.child.wait(timeout=5.0)
        except BaseException as error:
            cleanup.append(error)
        try:
            # Bypass the injected boundary only for exact owned test cleanup.
            if not (run.output.fileno() == -1 if isinstance(run.output, socket.socket) else run.output.closed) or os.path.exists(run.scratch):
                original_release()
        except BaseException as error:
            cleanup.append(error)
        if cleanup:
            errors = ([primary] if primary is not None else []) + cleanup
            raise BaseExceptionGroup("owned real-child primary and cleanup failures", errors) from None


@pytest.mark.parametrize("transport_kind", ["pipe", "socket"])
def test_read_when_real_nonblocking_endpoint_pauses_then_next_poll_preserves_bytes(
    reader_run, expected_reader_origin, transport_kind
):
    """Reader adapter owns a real endpoint; read and os.read stay unreplaced."""
    if transport_kind == "pipe":
        read_fd, write_fd = os.pipe()
        endpoint = os.fdopen(read_fd, "rb", buffering=0)
        writer = os.fdopen(write_fd, "wb", buffering=0)
    else:
        endpoint, writer = socket.socketpair()
        read_fd, write_fd = endpoint.fileno(), writer.fileno()
    reader_run.output = endpoint
    first, second = b"a" * 512, b"b" * 512
    try:
        os.set_blocking(read_fd, False)
        assert not os.get_blocking(read_fd)
        assert os.read.__module__ == "posix"
        assert os.write(write_fd, first) == len(first)
        assert reader_run.read() == []
        assert reader_run.buffer == first and not reader_run.eof
        with pytest.raises(BlockingIOError):
            os.read(read_fd, 1)
        assert os.write(write_fd, second) == len(second)
        assert reader_run.read() == []
        assert reader_run.buffer == first + second and not reader_run.eof
        with pytest.raises(BlockingIOError):
            os.read(read_fd, 1)
        writer.close()
        assert reader_run.read() == []
        assert reader_run.eof and reader_run.buffer == first + second
        assert reader_run.read() == []
        assert reader_run.buffer == first + second
    finally:
        writer.close()
        endpoint.close()
        for descriptor in (read_fd, write_fd):
            with pytest.raises(OSError):
                os.fstat(descriptor)
