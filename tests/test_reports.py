# this_file: tests/test_reports.py
# SPDX-License-Identifier: Apache-2.0
"""Detached JSON reports import without a host and preserve input snapshots."""

import json
import sys
from types import SimpleNamespace

import pytest


def test_format_report_unicode_plain_text_strict_and_detached():
    from fontlabapp.proof.reports.model import format_report

    data = {"text": "<b>مرحبا</b>", "values": [1]}
    text = format_report(data)
    assert "مرحبا" in text and "\n  " in text
    assert json.loads(text) == data
    with pytest.raises(ValueError):
        format_report({"bad": float("nan")})
    with pytest.raises(TypeError):
        format_report({"bad": object()})


def test_show_report_forwards_immutable_snapshot_and_owned_key(monkeypatch):
    from fontlabapp.proof.reports.model import show_report

    calls = []
    monkeypatch.setitem(
        sys.modules,
        "fontlabapp.proof.reports.ui",
        SimpleNamespace(
            show=lambda text, title, key: calls.append((text, title, key)) or "handle"
        ),
    )
    value = {"rows": [1]}
    assert show_report(value, title="Report", key="test-report") == "handle"
    value["rows"].append(2)
    assert json.loads(calls[0][0]) == {"rows": [1]}
    assert calls[0][1:] == ("Report", "test-report")


@pytest.fixture
def report_ui(monkeypatch):
    import importlib
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtGui, QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    class Dialog(QtWidgets.QDialog):
        palette = property(QtWidgets.QDialog.palette)

    class Label(QtWidgets.QLabel):
        font = property(QtWidgets.QLabel.font)

    gui = SimpleNamespace(
        **{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")}
    )
    gui.__dict__.update(
        {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
    )
    gui.QDialog, gui.QLabel = Dialog, Label
    parent = Dialog()
    monkeypatch.setitem(
        sys.modules, "PythonQt", SimpleNamespace(QtCore=QtCore, QtGui=gui)
    )
    package = importlib.import_module("fontlabapp")
    monkeypatch.setattr(
        package,
        "_native",
        lambda name: (
            SimpleNamespace(QtCore=QtCore, QtGui=gui)
            if name == "PythonQt"
            else SimpleNamespace(MainWindow=lambda: parent)
        ),
    )
    for name in ("fontlabapp.glyphs.names.ui", "fontlabapp.proof.reports.ui"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    mod = importlib.import_module("fontlabapp.proof.reports.ui")
    scripting = importlib.import_module("fontlabapp.core.scripting")
    monkeypatch.setattr(scripting, "_native", package._native)
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    yield mod, parent, QtCore
    for dialog in list(sys._fontlab_samples.values()):
        dialog.close()
    from shiboken6 import isValid

    if isValid(parent):
        parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()


def test_report_window_readonly_plain_nonmodal_and_replacement_close(report_ui):
    from fontlabapp.proof.reports.model import show_report

    _mod, _parent, _core = report_ui
    data = {"text": "<b>مرحبا</b>", "rows": [1]}
    first = show_report(data, key="owned-test")
    assert first.editor.isReadOnly() and not first.isModal()
    assert "<b>مرحبا</b>" in first.editor.toPlainText()
    data["rows"].append(2)
    assert first.report["rows"] == [1]
    assert len(first._connections) == 2
    assert len(first._completion_lifetime.hooks) == 2
    assert first._release in first._completion_lifetime.on_destroyed
    second = show_report({"next": True}, key="owned-test")
    assert first._released and first._connections == []
    assert sys._fontlab_samples["owned-test"] is second
    second.close_button.click()
    assert second._released and second._connections == []
    assert "owned-test" not in sys._fontlab_samples
    second._release()


def test_report_parent_destruction_releases_callback_registry(report_ui):
    from fontlabapp.proof.reports.model import show_report

    _mod, parent, core = report_ui
    dialog = show_report({"rows": []}, key="parent-test")
    parent.deleteLater()
    core.QCoreApplication.sendPostedEvents(None, core.QEvent.DeferredDelete)
    assert dialog._released and not dialog._connections
    assert "parent-test" not in sys._fontlab_samples


def test_report_initial_render_failure_disconnects_owned_callbacks(
    report_ui, monkeypatch
):
    mod, _parent, _core = report_ui

    def fail(*args):
        raise RuntimeError("render failed")

    monkeypatch.setattr(mod.QtGui, "QPlainTextEdit", fail)
    with pytest.raises(RuntimeError, match="render failed"):
        mod.show("{}", "Failed", "failed-test")
    assert "failed-test" not in sys._fontlab_samples


def test_reports_import_in_clean_process_without_native_modules():
    import subprocess

    code = """
import importlib.abc, sys
class NoHost(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'fontlab','fontgate','fontpr','PythonQt','PySide6','FL'}:
            raise AssertionError('Eager host import: '+fullname)
sys.meta_path.insert(0, NoHost())
from fontlabapp.proof.reports.model import format_report
assert format_report({'test': 1})
assert 'fontlabapp.proof.reports.ui' not in sys.modules
"""
    import os
    from pathlib import Path

    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    subprocess.run([sys.executable, "-c", code], check=True, env=env, timeout=15)


def test_report_show_failure_releases_new_window_without_touching_other_owner(
    report_ui, monkeypatch
):
    mod, parent, _core = report_ui
    created = []

    def failed_show(factory, key):
        dialog = factory(parent)
        created.append(dialog)
        sys._fontlab_samples[key] = dialog
        raise RuntimeError("show failed")

    other = object()
    sys._fontlab_samples["other-owner"] = other
    monkeypatch.setattr(mod, "show_script_dialog", failed_show)
    with pytest.raises(RuntimeError, match="show failed"):
        mod.show("{}", "Failure", "failed-show")
    assert created[0]._released and not created[0]._connections
    assert sys._fontlab_samples == {"other-owner": other}
    sys._fontlab_samples.pop("other-owner")


def test_report_direct_destruction_releases_and_saved_callbacks_are_inert(report_ui):
    from fontlabapp.proof.reports.model import show_report

    _mod, _parent, core = report_ui
    dialog = show_report({"rows": []}, key="direct-delete")
    callbacks = [slot for signal, slot in dialog._connections]
    dialog.deleteLater()
    core.QCoreApplication.sendPostedEvents(None, core.QEvent.DeferredDelete)
    assert dialog._released and not dialog._connections
    assert "direct-delete" not in sys._fontlab_samples
    # The first callback was the Close button. No callback may enter a deleted wrapper.
    for callback in callbacks:
        callback()
