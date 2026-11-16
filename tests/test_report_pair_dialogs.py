# this_file: tests/test_report_pair_dialogs.py
"""Actual external Qt widgets exercise both new shared panels, never FontLab."""

from module_paths import module_name as _module_name
import importlib
import os
import sys
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from fontlabapp.masters.layers.compatibility.model import GlyphLayers, Layer
from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture(params=["master", "svg"])
def panel(request, monkeypatch):
    class Dialog(QtWidgets.QDialog):
        palette = property(QtWidgets.QDialog.palette)

    class Label(QtWidgets.QLabel):
        font = property(QtWidgets.QLabel.font)

    gui = NS(**{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
    gui.__dict__.update(
        {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
    )
    gui.QDialog, gui.QLabel = Dialog, Label
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtGui=gui, QtCore=QtCore))
    for name in ("_names_dialog", "_snapshot_text_dialog", "_report_pair_dialogs"):
        monkeypatch.delitem(sys.modules, _module_name(name), raising=False)
    module = importlib.import_module("fontlabapp.proof.reports.specialized_ui")
    state = NS(calls=0, fail=False)

    def capture():
        state.calls += 1
        if state.fail:
            raise ValueError("owned stale source")
        return (
            (GlyphLayers("a", (Layer("Regular", ()),)),)
            if request.param == "master"
            else ()
        )

    api = (
        module.master_node_report_native
        if request.param == "master"
        else module.svg_path_commands_native
    )
    monkeypatch.setattr(api, "capture", capture)
    cls = (
        module.MasterNodeReportDialog
        if request.param == "master"
        else module.SvgPathCommandsDialog
    )
    widget = cls()
    yield widget, state, request.param
    if isValid(widget):
        widget.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_owned_panel_when_refresh_failure_close_then_full_lifecycle(panel):
    widget, state, kind = panel
    assert not widget.isModal() and widget.output.isReadOnly()
    if kind == "master":
        assert "Paths: 0" in widget.output.toPlainText()
    widget.refresh_button.click()
    assert state.calls == 2
    state.fail = True
    widget.refresh_button.click()
    assert (
        widget.output.toPlainText() == ""
        and widget.report is None
        and "owned stale" in widget.status.text()
    )
    state.fail = False
    widget.refresh_button.click()
    assert widget.report is not None
    widget.close_button.click()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert widget._closed and not widget._connections
    before = state.calls
    widget.refresh()
    assert state.calls == before


@pytest.mark.parametrize("kind", ["master_node_report", "svg_path_commands"])
def test_show_when_fly_public_dispatch_then_shared_registry(kind, monkeypatch):
    api = importlib.import_module(_module_name(kind))
    assert importlib.import_module("fly.ap." + kind).show is api.show
    from fontlabapp.core import scripting

    monkeypatch.setattr(
        scripting, "show_script_dialog", lambda cls, key: (cls.__name__, key)
    )
    result = api.show()
    assert result[1] == kind
