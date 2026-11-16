# this_file: src/fontlabapp/fontui/batch_worker.py
# SPDX-License-Identifier: Apache-2.0
"""Batch child process and its supervisor (no panel references).

Detached UFO work runs in a separate Python (3.11+, with fontlab-fontport),
so it never competes with FontLab's GUI thread for the GIL. The child reads a
{"jobs", "recipe", "cancel"} JSON file named on its command line, prints one
JSON line per font and stops before the next font once the cancel file exists.
Nothing here ever waits on the child, except the bounded kill at the cap.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any

from PythonQt import QtCore

CHILD = r"""
import json, os, sys
from fontlab_fontport.batch import BatchRunner
from fontlab_fontport.recipe import Recipe
with open(sys.argv[1], encoding="utf-8") as spec_file:
    spec = json.load(spec_file)
jobs = BatchRunner().run(spec["jobs"], Recipe(**spec["recipe"]),
                         cancelled=lambda: os.path.exists(spec["cancel"]))
for r in jobs:
    print(json.dumps({"index": r.index, "total": r.total, "source": str(r.source),
                      "destination": str(r.destination), "ok": r.ok, "error": r.error}),
          flush=True)
"""
# The child gets only these variables: FontLab's PYTHON*, DYLD_* and QT_* never reach it.
ENV_KEYS = ("PATH", "HOME", "TMPDIR", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE")
READ_BYTES = 64 * 1024  # per poll
ROWS_PER_POLL = 64
MAX_BUFFER = (
    1024 * 1024
)  # stop reading (the child then blocks) or, without a newline, fail
STDERR_TAIL = 4096
ROW = {
    "index": int,
    "total": int,
    "source": str,
    "destination": str,
    "ok": bool,
    "error": (str, type(None)),
}
MAX_PENDING = 16
KILL_SECONDS = 5.0  # after terminate
KILL_WAIT = 1.0  # bounded wait for a killed child at the cap
_PENDING: list[dict] = []
_TIMER: list = []


class ProtocolError(ValueError):
    """The child printed something that is not a result row."""


def _row(line: bytes) -> dict:
    """Decode one JSON result line; raise ``ProtocolError`` unless it fits ``ROW``."""
    try:
        row = json.loads(line)
    except (ValueError, RecursionError, MemoryError, TypeError):  # any decoder failure
        row = None
    if not isinstance(row, dict) or row.keys() != ROW.keys():
        raise ProtocolError(f"malformed batch output: {line[:120]!r}")
    for key, kind in ROW.items():
        if not isinstance(row[key], kind):
            raise ProtocolError(f"malformed batch output: {key}={row[key]!r}")
    return row


class BatchProcess:
    """One child run and its scratch folder (job spec, cancel file, stderr)."""

    def __init__(self, python: str, jobs: list, recipe: dict) -> None:
        self._supervision: dict | None = None
        self.scratch: str = tempfile.mkdtemp(prefix="fontlabapp-batch-")
        self.cancel_path: str = os.path.join(self.scratch, "cancel")
        self.stderr_path: str = os.path.join(self.scratch, "stderr")
        self.child: subprocess.Popen[bytes] | None = None
        self.output: Any = None
        self.buffer: bytearray = bytearray()
        self.eof: bool = False
        try:
            spec = os.path.join(self.scratch, "spec.json")
            with open(spec, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "jobs": [[str(s), str(d)] for s, d in jobs],
                        "recipe": recipe,
                        "cancel": self.cancel_path,
                    },
                    handle,
                )
            env = {key: os.environ[key] for key in ENV_KEYS if key in os.environ}
            writer = None
            if sys.platform == "darwin":
                self.output, writer = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                with open(self.stderr_path, "wb") as errors:
                    self.child = subprocess.Popen(
                        [python, "-I", "-c", CHILD, spec],
                        stdin=subprocess.DEVNULL,
                        stdout=writer if writer is not None else subprocess.PIPE,
                        stderr=errors,
                        env=env,
                    )
            finally:
                if writer is not None:
                    writer.close()
            if self.output is None:
                self.output = self.child.stdout
            os.set_blocking(self.output.fileno(), False)
        except BaseException:
            try:
                self.kill()
            finally:
                self.release()
            raise

    def cancel(self) -> None:
        if self.child is not None and self.child.poll() is None:
            open(self.cancel_path, "ab").close()

    def kill(self) -> None:
        """SIGKILL and a bounded wait; a child still alive stays with subprocess."""
        if self.child is None or self.child.poll() is not None:
            return
        self.child.kill()
        try:
            self.child.wait(KILL_WAIT)
        except subprocess.TimeoutExpired:  # CPython's Popen.__del__ keeps it in _active
            print(
                f"fontlabapp batch: pid {self.child.pid} survived SIGKILL",
                file=sys.stderr,
            )

    def read(self) -> list[dict]:
        """Up to ROWS_PER_POLL rows available now; never blocks, never unbounded."""
        remaining = READ_BYTES
        while not self.eof and len(self.buffer) < MAX_BUFFER and remaining > 0:
            try:
                chunk = os.read(self.output.fileno(), remaining)
            except BlockingIOError:
                break
            if chunk == b"":
                self.eof = True
                break
            self.buffer += chunk
            remaining -= len(chunk)
        rows = []
        while len(rows) < ROWS_PER_POLL:
            end = self.buffer.find(b"\n")
            if end < 0:
                break
            line = bytes(self.buffer[:end])
            del self.buffer[: end + 1]
            if line.strip():
                rows.append(_row(line))
        if len(self.buffer) >= MAX_BUFFER and b"\n" not in self.buffer:
            raise ProtocolError(f"malformed batch output: line over {MAX_BUFFER} bytes")
        return rows

    @property
    def done(self) -> bool:
        """Exited, all output read and every complete row consumed."""
        return self.eof and b"\n" not in self.buffer and self.child.poll() is not None

    def check_tail(self) -> None:
        if self.child.returncode == 0 and self.buffer.strip():
            raise ProtocolError(f"malformed batch output: {bytes(self.buffer[:120])!r}")

    def failure(self) -> str:
        """Last stderr line of an exited child, read from a bounded tail."""
        with open(self.stderr_path, "rb") as errors:
            errors.seek(max(0, os.fstat(errors.fileno()).st_size - STDERR_TAIL))
            text = errors.read().decode(errors="replace").strip()
        return (
            text.splitlines()[-1]
            if text
            else f"batch process exited with {self.child.returncode}"
        )

    def release(self) -> None:
        """Close output and remove the scratch folder; call once the child exited."""
        if self.output is not None:
            self.output.close()
        shutil.rmtree(self.scratch, ignore_errors=True)


def _ack(answer: Any, stage: str) -> None:
    if answer is False:
        raise RuntimeError(f"Batch {stage} refused")


def _clear_error(entry: dict) -> None:
    entry.update(first_error=None, current_error=None, reporting_error=None,
                 error_group=None, fault_stage=None)


def _error(entry: dict, stage: str, error: BaseException) -> BaseException:
    if entry["fault_stage"] != stage:
        entry["first_error"] = error
    entry.update(fault_stage=stage, current_error=error, reporting_error=None,
                 error_group=None)
    try:
        print(f"fontlabapp batch: {stage}, run {id(entry['process'])}: {type(error).__name__}", file=sys.stderr)
    except BaseException as reporting:
        group = BaseExceptionGroup("Batch operation and reporting failed", [error, reporting])
        group.owner = entry
        entry.update(reporting_error=reporting, error_group=group)
        return group
    return error


def _shared_error(timer: dict, entry: dict, stage: str, error: BaseException) -> BaseException:
    if timer["fault"] is None and entry["current_error"] is not None:
        timer["prior_fault"] = {key: entry[key] for key in
                                ("first_error", "current_error", "reporting_error", "error_group", "fault_stage")}
    timer.update(owner=entry, fault=stage)
    return _error(entry, "timer " + stage, error)


def _shared_resolved(timer: dict, entry: dict) -> None:
    if timer["prior_fault"] is None:
        _clear_error(entry)
    else:
        entry.update(timer["prior_fault"])
    timer.update(owner=None, fault=None, prior_fault=None)


def _watch(entry: dict) -> None:
    if entry["widget"] is None or entry["widget_dead"]:
        entry["witness_retired"] = True
        return
    if entry["witness_connected"]:
        return
    entry["stage"] = "witness connect"
    if entry["witness"] is None:
        def destroyed(*args: Any) -> None:
            entry["widget_dead"] = True
        entry["witness"] = (entry["widget"].destroyed, destroyed)
    signal, callback = entry["witness"]
    if entry["witness_ambiguous"]:
        _ack(signal.disconnect(callback), "witness compensation")
        entry["witness_ambiguous"] = False
    if entry["widget_dead"]:
        entry["witness_retired"] = True
        return
    entry["witness_ambiguous"] = True
    _ack(signal.connect(callback), "witness connect")
    entry["witness_connected"] = True
    entry["witness_ambiguous"] = False


def _setup_timer(entry: dict) -> None:
    if not _TIMER:
        _TIMER.append(dict(timer=None, signal=None, connected=False, ambiguous=False,
                           running=False, stopped=False, busy=False, fault=None,
                           owner=None, prior_fault=None))
    timer = _TIMER[0]
    timer["busy"] = True
    stage = "construct"
    try:
        if timer["timer"] is None:
            timer["timer"] = QtCore.QTimer()
        stage = "connect"
        if timer["signal"] is None:
            timer["signal"] = timer["timer"].timeout
        if timer["ambiguous"]:
            _ack(timer["signal"].disconnect(_tick), "timeout compensation")
            timer["ambiguous"] = False
        if not timer["connected"]:
            timer["ambiguous"] = True
            _ack(timer["signal"].connect(_tick), "timeout connect")
            timer["connected"] = True
            timer["ambiguous"] = False
        stage = "start"
        if not entry["started"] or timer["stopped"]:
            _ack(timer["timer"].start(entry["interval"]), "timer start")
            entry["started"] = True
            timer.update(running=True, stopped=False)
    except BaseException as error:
        raise _shared_error(timer, entry, stage, error)
    finally:
        timer["busy"] = False


def _stop_timer(entry: dict) -> None:
    timer = _TIMER[0]
    if timer["stopped"]:
        return
    timer.update(owner=entry, busy=True)
    try:
        _ack(timer["timer"].stop(), "timer stop")
        timer.update(stopped=True, running=False, owner=None)
    except BaseException as error:
        raise _shared_error(timer, entry, "stop", error)
    finally:
        timer["busy"] = False


def _repair_timer(entry: dict) -> float | None:
    timer = _TIMER[0]
    if timer["owner"] is not entry:
        error = RuntimeError("Batch shared timer fault belongs to another run")
        error.owner = timer["owner"]
        raise error
    stage = timer["fault"]
    now = None
    if stage not in ("stop", "clock"):
        _setup_timer(entry)
    else:
        timer["busy"] = True
        try:
            if stage == "clock":
                now = time.monotonic()
            else:
                _ack(timer["timer"].stop(), "timer stop")
                timer.update(stopped=True, running=False)
        except BaseException as error:
            raise _shared_error(timer, entry, stage, error)
        finally:
            timer["busy"] = False
    _shared_resolved(timer, entry)
    return now


def _advance(entry: dict, now: float) -> None:
    child = entry["process"].child
    if not entry["exited"]:
        entry["stage"] = "poll"
        entry["exited"] = child.poll() is not None
    if entry["exited"]:
        _finish(entry)
        return
    waited = now - entry["since"]
    if waited >= entry["grace"] + KILL_SECONDS:
        if not entry["kill_ack"]:
            entry["stage"] = "kill"
            _ack(child.kill(), "kill")
            entry["kill_ack"] = True
    elif waited >= entry["grace"] and not entry["terminate_ack"]:
        entry["stage"] = "terminate"
        _ack(child.terminate(), "terminate")
        entry["terminate_ack"] = True


def supervise(process: BatchProcess, widget: Any, grace: float, interval: int) -> None:
    """Accept or explicitly resume this run's exact cleanup ownership."""
    entry = process._supervision
    if entry is None:
        entry = dict(process=process, widget=widget, grace=grace, interval=interval,
                     since=None, admitted=False, overflow=False, accepted=False,
                     busy=False, complete=False, started=False, widget_dead=False,
                     witness=None, witness_connected=False, witness_ambiguous=False,
                     witness_retired=False, exited=False, released=False, deleted=False,
                     terminate_ack=False, kill_ack=False, cap_kill_ack=False,
                     first_error=None, current_error=None, reporting_error=None,
                     error_group=None, fault_stage=None, stage="registration")
        process._supervision = entry
    if entry["process"] is not process or entry["widget"] is not widget or entry["grace"] != grace or entry["interval"] != interval:
        raise RuntimeError("Batch supervision arguments changed")
    if entry["busy"]:
        entry["reentry_error"] = RuntimeError("Batch supervision is in progress")
        raise entry["reentry_error"]
    if _TIMER and _TIMER[0]["busy"]:
        raise RuntimeError("Batch timer operation is in progress")
    entry["busy"] = True
    try:
        now = None
        if _TIMER and _TIMER[0]["fault"] is not None:
            now = _repair_timer(entry)
        if entry["complete"]:
            return
        retry = entry["current_error"] is not None
        if entry["accepted"] and not retry:
            return
        if not entry["admitted"] and not entry["overflow"]:
            entry["overflow"] = len(_PENDING) >= MAX_PENDING
            if not entry["overflow"]:
                _PENDING.append(entry)
                entry["admitted"] = True
        if entry["since"] is None:
            entry["stage"] = "initial clock"
            entry["since"] = time.monotonic()
        _watch(entry)
        if entry["overflow"]:
            if not entry["cap_kill_ack"]:
                entry["stage"] = "cap kill"
                print(f"fontlabapp batch: {len(_PENDING)} pending children; killing pid {process.child.pid}", file=sys.stderr)
                _ack(process.kill(), "cap kill")
                entry["cap_kill_ack"] = True
            entry["stage"] = "cap poll"
            entry["exited"] = process.child.poll() is not None
            if not entry["exited"]:
                raise RuntimeError("Batch overflow child remains unreaped")
            _finish(entry)
            _clear_error(entry)
            return
        _setup_timer(entry)
        if retry and entry["accepted"]:
            if now is None:
                timer = _TIMER[0]
                timer.update(owner=entry, busy=True)
                try:
                    now = time.monotonic()
                except BaseException as error:
                    raise _shared_error(timer, entry, "clock", error)
                finally:
                    timer["busy"] = False
                timer["owner"] = None
            _advance(entry, now)
        entry["accepted"] = True
        _clear_error(entry)
        if entry["complete"]:
            _PENDING[:] = [pending for pending in _PENDING if pending is not entry]
            if not any(pending["accepted"] and pending["current_error"] is None for pending in _PENDING):
                _stop_timer(entry)
    except BaseException as error:
        if _TIMER and _TIMER[0]["fault"] is not None:
            raise
        raise _error(entry, entry["stage"], error)
    finally:
        entry["busy"] = False


def _finish(entry: dict) -> None:
    """Commit each observed-exit cleanup ACK before the next fallible stage."""
    if not entry["exited"]:
        raise RuntimeError("Batch finish requires observed child exit")
    if not entry["released"]:
        entry["stage"] = "release"
        _ack(entry["process"].release(), "release")
        entry["released"] = True
    if entry["widget"] is not None and not entry["widget_dead"] and not entry["deleted"]:
        entry["stage"] = "delete"
        _ack(entry["widget"].deleteLater(), "delete")
        entry["deleted"] = True
    if not entry["witness_retired"]:
        entry["stage"] = "witness disconnect"
        if not entry["widget_dead"] and entry["witness_connected"]:
            signal, callback = entry["witness"]
            _ack(signal.disconnect(callback), "witness disconnect")
        entry["witness_retired"] = True
    entry["complete"] = True


def _tick(*args: Any) -> None:
    """Contain faults, advance healthy entries once, and retain shared faults."""
    if not _TIMER:
        return
    timer = _TIMER[0]
    if timer["busy"] or timer["fault"] is not None or not timer["running"]:
        return
    ready = [entry for entry in _PENDING if entry["accepted"] and not entry["busy"]
             and entry["current_error"] is None]
    if not ready:
        owner = next((entry for entry in _PENDING if entry["accepted"]
                      and not entry["busy"] and entry["current_error"] is not None), None)
        if owner is not None:
            try:
                _stop_timer(owner)
            except BaseException:
                pass  # Retained shared housekeeping fault; never an entry retry.
        return
    owner = ready[0]
    timer["owner"] = owner
    try:
        now = time.monotonic()
    except BaseException as error:
        _shared_error(timer, owner, "clock", error)
        return
    timer["owner"] = None
    for entry in ready:
        owner = entry
        entry["busy"] = True
        try:
            _advance(entry, now)
            _clear_error(entry)
            if entry["complete"]:
                _PENDING[:] = [pending for pending in _PENDING if pending is not entry]
        except BaseException as error:
            _error(entry, entry["stage"], error)
        finally:
            entry["busy"] = False
    if not any(entry["accepted"] and entry["current_error"] is None for entry in _PENDING):
        try:
            _stop_timer(owner)
        except BaseException:
            pass  # The exact shared fault and owner remain available to supervise.
