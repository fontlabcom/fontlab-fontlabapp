# this_file: tests/test_spacing_faults.py
"""Injected faults exercise whole production modules beyond arithmetic success."""

import importlib
import sys
from types import SimpleNamespace as NS

import pytest

from test_spacing_worksheet import APP, GUI, QtCore, drain, open_cell, panel, valid
import fontlabapp.metrics.worksheet.controls as spacing_controls
import fontlabapp.metrics.worksheet.ui as spacing_panel
import fontlabapp.metrics.worksheet.model as spacing_worksheet
from fontlabapp.metrics.worksheet.ui import panel_type


@pytest.mark.parametrize(
    "fault",
    [
        "false",
        "raise",
        "mutate-false",
        "mutate-raise",
        "wrong-type",
        "wrong-equal-type",
        "read-raise",
        "interpret-raise",
        "value-type",
        "signal-block-raise",
        "reentrant",
    ],
)
def test_failed_commit_keeps_exact_model_state_and_is_contained(
    panel, monkeypatch, fault
):
    p, _ = panel
    index, editor = open_cell(p, 0, 0)
    old = p.values()
    original = p.model.setData
    read = p.model.data
    block = p.model.blockSignals
    writes = []

    def write(index, number, role):
        writes.append(1)
        if len(writes) > 1:
            return original(index, number, role)
        if fault == "false":
            return False
        if fault == "raise":
            raise ValueError("write failed")
        if fault.startswith("mutate"):
            original(index, number, role)
            if fault.endswith("raise"):
                raise ValueError("write failed after mutation")
            return False
        if fault.startswith("wrong"):
            original(index, str(number), role)
            return True
        return original(index, number, role)

    if fault == "read-raise":
        monkeypatch.setattr(
            p.model,
            "data",
            lambda *args: (_ for _ in ()).throw(ValueError("read failed")),
        )
    elif fault == "signal-block-raise":
        monkeypatch.setattr(
            p.model,
            "blockSignals",
            lambda *args: (_ for _ in ()).throw(ValueError("block failed")),
        )
    elif fault == "interpret-raise":
        monkeypatch.setattr(
            editor,
            "interpretText",
            lambda: (_ for _ in ()).throw(ValueError("interpret failed")),
        )
    elif fault == "value-type":
        monkeypatch.setattr(editor, "value", lambda: True)
    elif fault == "reentrant":
        p.delegate.writing = True
    else:
        monkeypatch.setattr(p.model, "setData", write)
    editor.lineEdit().setText("1" if fault == "wrong-equal-type" else "39")
    assert p.delegate.setModelData(editor, p.model, index) is None
    monkeypatch.setattr(p.model, "data", read)
    monkeypatch.setattr(p.model, "blockSignals", block)
    if fault != "reentrant":
        assert not p.delegate.writing
    p.delegate.writing = False
    assert p.values() == old and all(
        type(a) is type(b) for x, y in zip(p.values(), old) for a, b in zip(x, y)
    )
    assert p.last_error


@pytest.mark.parametrize(
    "fault",
    [
        "invalid-index",
        "foreign-index",
        "stale-editor",
        "conversion",
        "geometry",
        "report",
        "create-range",
        "create-frame",
    ],
)
def test_all_four_virtual_faults_remain_inside_qt(panel, monkeypatch, fault):
    p, _ = panel
    index, editor = open_cell(p, 0, 0)
    if fault in {"invalid-index", "foreign-index"}:
        foreign = GUI.QStandardItemModel(4, 2)
        target = (
            QtCore.QModelIndex() if fault == "invalid-index" else foreign.index(0, 0)
        )
        assert p.delegate.setEditorData(editor, target) is None
    elif fault == "stale-editor":
        p.delegate.records[id(editor)][3] = False
        assert p.delegate.setModelData(editor, p.model, index) is None
    elif fault == "conversion":
        p.model.setData(index, "not a number", QtCore.Qt.EditRole)
        assert p.delegate.setEditorData(editor, index) is None
    elif fault == "geometry":
        assert p.delegate.updateEditorGeometry(editor, NS(), index) is None
    elif fault == "report":
        p.delegate.failed = lambda error: (_ for _ in ()).throw(
            ValueError("diagnostic failed")
        )
        p.delegate.setEditorData(editor, QtCore.QModelIndex())
        assert "diagnostic failed" in p.delegate.error
        return
    else:
        original = GUI.QSpinBox

        class Broken(original):
            def setRange(self, *args):
                if fault == "create-range":
                    raise ValueError("range failed")
                return super().setRange(*args)

            def setFrame(self, *args):
                raise ValueError("frame failed")

        monkeypatch.setattr(GUI, "QSpinBox", Broken)
        p.delegate.official = True
        assert p.delegate.createEditor(p.table.viewport(), NS(), index) is None
        drain()
    assert p.last_error


@pytest.mark.parametrize(
    "stage",
    [
        "QLabel",
        "QTableView",
        "QPlainTextEdit",
        "QPushButton",
        "QStandardItemModel",
        "QStandardItem",
    ],
)
def test_each_constructor_stage_unwinds_owned_widget(panel, monkeypatch, stage):
    p, _ = panel

    # The owner and native superclass exist before a factory can fail.
    def reject(*args, **kwargs):
        raise ValueError("constructor " + stage)

    monkeypatch.setattr(GUI, stage, reject)
    if stage == "QStandardItem" and p.official:
        other = type(p)(None, lambda: p.snapshot, official=True)
        assert other.close()
        drain()
        return
    with pytest.raises(ValueError, match="constructor"):
        type(p)(None, lambda: p.snapshot, official=p.official)
    drain()


def test_constructor_signal_failure_and_cleanup_retry_are_visible(panel, monkeypatch):
    from fontlabapp.core.signals.scope import Scope

    p, _ = panel
    old = Scope.connect

    def reject(self, signal, call, **kwargs):
        if len(self.records) == 1:
            raise ValueError("connect failed")
        return old(self, signal, call, **kwargs)

    monkeypatch.setattr(Scope, "connect", reject)
    with pytest.raises(ValueError, match="connect failed"):
        type(p)(None, lambda: p.snapshot, official=p.official)
    drain()


def test_reset_failure_keeps_previous_exact_factors_and_report(panel, monkeypatch):
    p, _ = panel
    old = p.values()
    report = p.report.toPlainText()
    write = p.model.setData
    calls = []

    def fail_once(*args):
        calls.append(1)
        if len(calls) == 3:
            return False
        return write(*args)

    monkeypatch.setattr(p.model, "setData", fail_once)
    p.reset()
    assert (
        p.values() == old
        and p.report.toPlainText() == report
        and "refused" in p.last_error
    )


def test_refresh_reentrancy_wrong_result_and_native_close_failure(panel, monkeypatch):
    p, _ = panel
    old = p.snapshot

    def capture():
        p.refresh()
        p.reset()
        return None

    p.capture = capture
    p.refresh()
    assert p.snapshot is old and "complete" in p.last_error
    monkeypatch.setattr(
        p.delegate, "cancel", lambda: (_ for _ in ()).throw(ValueError("cancel failed"))
    )
    assert not p.close() and "cancel failed" in p.last_error


def test_closed_midcapture_and_report_failure_do_not_replace_snapshot(
    panel, monkeypatch
):
    p, _ = panel
    old = p.snapshot

    def capture():
        p.dispose()
        return old

    p.capture = capture
    p.refresh()
    assert p.snapshot is old
    p.refresh()
    p.reset()
    p.changed()


def test_public_both_lazy_entry_points_and_main_thread_guard(panel, monkeypatch):
    import fontlabapp
    import fontlabapp.core.scripting as scripting

    p, _ = panel
    seen = []
    monkeypatch.setattr(
        fontlabapp, "_native", lambda name: NS(QtCore=QtCore, QtGui=GUI)
    )

    def show(kind, key):
        child = kind(None)
        seen.append((key, child.official))
        child.close()
        return child

    monkeypatch.setattr(scripting, "show_script_dialog", show)
    monkeypatch.setattr(
        importlib.import_module("fontlabapp.metrics.worksheet.capture"),
        "capture",
        lambda: p.snapshot,
    )
    spacing_worksheet.show()
    spacing_worksheet.show_official()
    drain()
    assert seen == [("spacing_worksheet", False), ("spacing_worksheet_official", True)]
    monkeypatch.setattr(spacing_worksheet, "current_thread", lambda: object())
    with pytest.raises(RuntimeError, match="main UI thread"):
        spacing_worksheet.show()


def test_pending_commit_updates_candidates_when_capture_fails(panel):
    p, state = panel
    state.fail = True
    _, editor = open_cell(p, 0, 0)
    editor.lineEdit().setText("50")
    p.refresh()
    assert p.values()[0][0] == 50
    assert "Increments: 100, 8, 18, 32" in p.report.toPlainText()
    assert "source changed" in p.last_error


def test_unrelated_signal_listener_survives_owned_disposal(panel):
    p, _ = panel
    calls = []

    def other(*args):
        calls.append(1)

    p.reset_button.clicked.connect(other)
    assert p.dispose()
    from fontlabapp.qt.spinbox.delegate import emit

    emit(p.reset_button.clicked)
    assert calls == [1]
    p.reset_button.clicked.disconnect(other)


def test_editor_destroyed_connection_failure_retains_tombstone_until_native_death(
    panel, monkeypatch
):
    from fontlabapp.core.signals.scope import Scope

    p, _ = panel
    original = Scope.connect

    def fail(self, *args, **kwargs):
        if (
            self is not p.scope
            and self is not p.terminal
            and self is not p.delegate.scope
        ):
            raise ValueError("editor destroyed connection failed")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Scope, "connect", fail)
    index = p.model.index(0, 0)
    assert p.delegate.createEditor(p.table.viewport(), NS(), index) is None
    drain()
    assert p.delegate.records, (
        "Failed editor owner must survive until owned native panel death"
    )
    assert p.close()
    drain()
    assert not p.delegate.records and p.terminal.dead
