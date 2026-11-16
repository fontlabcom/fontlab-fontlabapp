# this_file: src/fontlabapp/fontui/batch.py
# SPDX-License-Identifier: Apache-2.0
"""Original batch controls; Fontport's BatchRunner runs in a child process."""

import os
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fontlabapp.qt.properties import value as qt_value

from ._fontport import require_fontport

with require_fontport(__name__):
    from fontlab_fontport.batch import BatchResult, BatchRunner
from PythonQt import QtCore, QtGui

from .batch_worker import BatchProcess, ProtocolError, _ack, supervise
from .lifecycle import Owned

PYTHON_ENV = "FONTLABAPP_BATCH_PYTHON"


def _bridge_dead_widget(process: BatchProcess, widget: Any) -> bool:
    entry = process._supervision
    if entry is not None and entry["process"] is process and entry["widget"] is widget:
        entry["widget_dead"] = True
    return entry is not None


class BatchPanel(Owned):
    """Explicit sources and destination folder; one run at a time.

    Start validates every job in FontLab first (Fontport's run() is eager)
    and writes nothing on failure. The work then runs in a separate Python
    3.11+ with fontlab-fontport (python=..., else $FONTLABAPP_BATCH_PYTHON), so
    it never holds FontLab's GIL; each 50 ms poll reads at most 64 KiB and
    records at most 64 rows from a non-blocking socket on Darwin or pipe
    elsewhere. Output that is not a result row stops the run visibly. Cancel stops before the next font. Close
    (including parent or own-widget destruction) normally hands off cleanup
    without waiting; at the pending-child cap, overflow cleanup can wait up to
    KILL_WAIT (1.0 second) for the child after killing it. batch_worker.supervise
    watches for exit (termination after GRACE_SECONDS, killing later; a
    terminated font can leave a partial destination), then attempts scratch
    cleanup and schedules deletion of the surviving hidden, detached panel.
    Outputs are named <stem>-transformed.ufo and never replace a file.
    """

    POLL_MS = 50
    GRACE_SECONDS = 10.0

    def __init__(
        self,
        recipe: Callable[[], Any],
        parent: Any = None,
        on_finish: Callable[[list], None] | None = None,
        python: str | None = None,
    ) -> None:
        self._batch_base_ready = False
        self._batch_close = None
        self._protocol = None
        self._batch_owned = []
        self.timer = None
        self.process = None
        self.jobs = None
        self.on_finish = None
        self.cancelled = False
        super().__init__(parent)
        self._batch_base_ready = True
        self.recipe: Callable[[], Any] = recipe
        self.on_finish: Callable[[list], None] | None = on_finish
        self.python: str | None = python
        self.process: BatchProcess | None = None
        self.runner: BatchRunner = BatchRunner()
        self.jobs: list[tuple[str, Path]] | None = None
        self.results: list[BatchResult] = []
        self.cancelled: bool = False
        self.sources: list[str] = []
        self.source_list = QtGui.QListWidget(self.widget)
        self.source_list.setAccessibleName("Batch source UFOs")
        caption = QtGui.QLabel("Source &UFOs", self.widget)
        caption.setBuddy(self.source_list)
        self.destination_control = QtGui.QLineEdit(self.widget)
        self.destination_control.setAccessibleName("Destination folder")
        target = QtGui.QLabel("&Destination folder", self.widget)
        target.setBuddy(self.destination_control)
        for widget in (caption, self.source_list, target, self.destination_control):
            self.layout.addWidget(widget)
        row = QtGui.QHBoxLayout()
        self.layout.addLayout(row)
        self.add_button = QtGui.QPushButton("&Add sources…", self.widget)
        self.start_button = QtGui.QPushButton("&Start batch", self.widget)
        self.cancel_button = QtGui.QPushButton("&Cancel", self.widget)
        for button in (self.add_button, self.start_button, self.cancel_button):
            row.addWidget(button)
        self.progress = QtGui.QProgressBar(self.widget)
        self.log = QtGui.QListWidget(self.widget)
        self.log.setAccessibleName("Batch log")
        self.status = QtGui.QLabel(self.widget)
        self.status.setWordWrap(True)
        for widget in (self.progress, self.log, self.status):
            self.layout.addWidget(widget)
        self.timer = QtCore.QTimer(self.widget)
        self.timer.setInterval(self.POLL_MS)
        self.connect(self.timer.timeout, lambda *a: self.step())
        self._batch_owned.append((self.connections[-1], self.widget))
        self.connect(self.add_button.clicked, lambda *a: self._choose())
        self._batch_owned.append((self.connections[-1], self.widget))
        self.connect(self.start_button.clicked, lambda *a: self.start())
        self._batch_owned.append((self.connections[-1], self.widget))
        self.connect(self.cancel_button.clicked, lambda *a: self.cancel())
        self._batch_owned.append((self.connections[-1], self.widget))
        self._idle("Choose source UFOs and a destination folder.")

    @property
    def running(self) -> bool:
        return self.jobs is not None

    def _idle(self, message: str) -> None:
        """Stop polling, re-enable Start/Add, disable Cancel, show ``message``."""
        protocol = self._protocol
        if protocol is not None and protocol["process"] is self.process and protocol["timer"] is self.timer and protocol["pending"]:
            if not protocol["stop"]["ack"]:
                _ack(self.timer.stop(), "protocol timer stop")
                protocol["stop"].update(ack=True, first_error=None, current_error=None)
            self.start_button.setEnabled(True)
            self.add_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.status.setText(message)
            self.jobs = None
            return
        self.timer.stop()
        self.jobs = None
        self.start_button.setEnabled(True)
        self.add_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.status.setText(message)

    def set_sources(self, paths: list[str]) -> None:
        self.sources = [str(path) for path in paths]
        self.source_list.clear()
        self.source_list.addItems(self.sources)

    def _choose(self) -> None:
        """Ask for one source UFO folder and append it to the source list."""
        paths = QtGui.QFileDialog.getExistingDirectory(self.widget, "Source UFO")
        if paths:
            self.set_sources([*self.sources, str(paths)])

    def start(self) -> bool:
        if self.closed or self.running:
            return False
        try:
            python = self.python or os.environ.get(PYTHON_ENV)
            if not python:
                raise ValueError(
                    f"Set {PYTHON_ENV} or pass python= (Python 3.11+ with fontlab-fontport)"
                )
            folder = self.destination_control.text.strip()
            if not folder:
                raise ValueError("Choose a destination folder")
            jobs = [
                (src, Path(folder) / f"{Path(src).stem}-transformed.ufo")
                for src in self.sources
            ]
            recipe = self.recipe()
            self.runner.run(jobs, recipe).close()  # eager validation only
            self.results, self.cancelled = [], False
            self.process = BatchProcess(python, jobs, asdict(recipe))
        except Exception as exc:  # noqa: BLE001 - validation fails before any write
            self._idle(f"Not started: {exc}")
            return False
        self.jobs = jobs
        self.progress.setRange(0, len(jobs))
        self.progress.setValue(0)
        self.log.clear()
        self.start_button.setEnabled(False)
        self.add_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status.setText("Running…")
        self.timer.start()
        return True

    def _record(self, row: dict) -> None:
        """Store one child result row; advance the progress bar and the log."""
        result = BatchResult(
            row["index"],
            row["total"],
            Path(row["source"]),
            Path(row["destination"]),
            row["ok"],
            row["error"],
        )
        self.results.append(result)
        self.progress.setValue(result.index)
        text = "ok" if result.ok else f"FAILED: {result.error}"
        self.log.addItem(
            f"{result.index}/{result.total} {result.source.name} → {result.destination.name}: {text}"
        )

    def step(self) -> None:
        """GUI-thread poll: record finished fonts; never waits on the child."""
        if self.closed or not self.running:
            return
        process = self.process
        if self._protocol is not None and self._protocol["process"] is process and self._protocol["pending"]:
            return
        try:
            for row in process.read():
                self._record(row)
            if not process.done:
                return
            process.check_tail()
        except ProtocolError as exc:
            protocol = dict(process=process, timer=self.timer, pending=True,
                            stop={"ack": False, "retired": None, "first_error": None, "current_error": None}, transfer=False,
                            protocol_error=exc, first_error=None, current_error=None, stage="stop")
            self._protocol = protocol
            try:
                _ack(self.timer.stop(), "protocol timer stop")
                protocol["stop"].update(ack=True, first_error=None, current_error=None)
                protocol["stage"] = "transfer"
                _ack(supervise(process, None, 0.0, self.POLL_MS), "protocol transfer")
                protocol["transfer"] = True
                protocol["stage"] = "idle"
                self._idle(f"Batch stopped: {exc}")
                protocol["pending"] = False
            except BaseException as error:
                if protocol["first_error"] is None:
                    protocol["first_error"] = error
                protocol["current_error"] = error
                if not protocol["stop"]["ack"]:
                    protocol["stop"].update(first_error=error, current_error=error)
                self._close_error = error
                try:
                    self.status.setText(f"Batch cleanup failed: {type(error).__name__}")
                except BaseException as reporting:
                    group = BaseExceptionGroup("Batch cleanup and reporting failed", [error, reporting])
                    group.owner = self
                    self._close_error = group
            return
        if process.child.returncode:
            message = f"Batch stopped: {process.failure()}"
            process.release()
            self._idle(message)
        else:
            process.release()
            self._finish()

    def cancel(self) -> None:
        if self.running:
            self.cancelled = True
            self.process.cancel()
            self.status.setText("Cancelling after the current font…")

    def _finish(self) -> None:
        """Show the totals, then call ``on_finish``; its errors go to the status."""
        ok = sum(r.ok for r in self.results)
        failed = len(self.results) - ok
        word = "Cancelled" if self.cancelled else "Finished"
        self._idle(f"{word}: {ok} succeeded, {failed} failed.")
        if self.on_finish is not None:
            try:
                self.on_finish(list(self.results))
            except Exception as exc:  # noqa: BLE001 - consumer callback boundary
                self.status.setText(f"{qt_value(self.status, 'text')} Callback failed: {exc}")

    def close(self) -> None:
        """Resume exact panel cleanup; transfer a live run only after its ACK."""
        if self._closing:
            error = RuntimeError("Batch close is in progress")
            if self._batch_close is not None:
                self._batch_close["reentry_error"] = error
            raise error
        if self._batch_close is not None and self._batch_close["complete"]:
            return
        self.closed, self.cancelled, self.on_finish = True, True, None
        if not self._batch_base_ready:
            raise RuntimeError("Batch base construction is incomplete")
        if self._batch_close is None:
            protocol = self._protocol
            if protocol is not None and (protocol["process"] is not self.process or protocol["timer"] is not self.timer):
                protocol = None
            self._batch_close = dict(process=self.process, widget=self.widget,
                                     timer=self.timer, active=self.running, protocol=protocol,
                                     stop=protocol["stop"] if protocol is not None else {"ack": False, "retired": None, "first_error": None, "current_error": None},
                                     detached=False, cancel_ack=False,
                                     transfer=protocol["transfer"] if protocol is not None else False,
                                     handoff_started=protocol is not None, handoff_widget=None,
                                     complete=False, retired_pairs=[], first_error=None,
                                     current_error=None, fault_stage=None, stage="stop")
        record = self._batch_close
        process, widget = record["process"], record["widget"]
        self.jobs = None
        self._closing = True
        try:
            stop = record["stop"]
            record["stage"] = "stop"
            if not stop["ack"] and stop["retired"] is None:
                if self.destroying or record["timer"] is None:
                    stop["retired"] = "owner-destroyed" if self.destroying else "not-created"
                else:
                    _ack(record["timer"].stop(), "panel timer stop")
                    stop.update(ack=True, first_error=None, current_error=None)
            observers = (self._own_observer, self._parent_observer)
            for pair in reversed(tuple(self.connections)):
                if any(pair is observer for observer in observers):
                    continue
                record["stage"] = ("disconnect", id(pair))
                if self.destroying and any(pair is owned and owner is widget for owned, owner in self._batch_owned):
                    record["retired_pairs"].append((pair, "owner-destroyed"))
                else:
                    _ack(pair[0].disconnect(pair[1]), "ordinary disconnect")
                self.connections[:] = [pending for pending in self.connections if pending is not pair]
                self._batch_owned[:] = [(owned, owner) for owned, owner in self._batch_owned if owned is not pair]
            record["stage"] = "detach"
            if not self.destroying and not record["detached"]:
                _ack(widget.setParent(None), "detach")
                record["detached"] = True
            record["stage"] = "hide"
            if not self.destroying and not self._hidden:
                _ack(widget.hide(), "hide")
                self._hidden = True
            record["stage"] = "cancel"
            if record["active"] and not record["cancel_ack"]:
                _ack(process.cancel(), "cancel")
                record["cancel_ack"] = True
            record["stage"] = "transfer"
            if record["active"] and not record["transfer"]:
                if not record["handoff_started"]:
                    record["handoff_widget"] = None if self.destroying else widget
                    record["handoff_started"] = True
                if self.destroying and record["handoff_widget"] is not None:
                    if not _bridge_dead_widget(process, widget):
                        record["handoff_widget"] = None
                try:
                    grace = 0.0 if record["protocol"] is not None else self.GRACE_SECONDS
                    _ack(supervise(process, record["handoff_widget"], grace, self.POLL_MS), "transfer")
                    record["transfer"] = True
                finally:
                    if self.destroying and record["handoff_widget"] is not None:
                        _bridge_dead_widget(process, widget)
            record["stage"] = "delete"
            if (not record["active"] or record["protocol"] is not None) and not self.destroying and not self._delete_scheduled:
                _ack(widget.deleteLater(), "delete")
                self._delete_scheduled = True
            for pair in reversed(tuple(self.connections)):
                record["stage"] = ("observer disconnect", id(pair))
                dead = (pair is self._own_observer and self.destroying) or (pair is self._parent_observer and self._parent_dead)
                if dead:
                    record["retired_pairs"].append((pair, "sender-destroyed"))
                else:
                    _ack(pair[0].disconnect(pair[1]), "observer disconnect")
                self.connections[:] = [pending for pending in self.connections if pending is not pair]
            record.update(complete=True, first_error=None, current_error=None, fault_stage=None)
            self._close_error = None
        except BaseException as error:
            if record["stage"] == "stop":
                if record["stop"]["first_error"] is None:
                    record["stop"]["first_error"] = error
                record["stop"]["current_error"] = error
                record["first_error"] = record["stop"]["first_error"]
            elif record["fault_stage"] != record["stage"]:
                record["first_error"] = error
            record.update(current_error=error, fault_stage=record["stage"])
            self._close_error = error
            raise
        finally:
            self._closing = False
