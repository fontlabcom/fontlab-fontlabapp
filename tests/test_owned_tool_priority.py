# this_file: tests/test_owned_tool_priority.py
"""Observe real standalone tool flags, content lifetime and deferred Close."""

import importlib
import sys
from types import SimpleNamespace as NS

import pytest

from test_spacing_worksheet import GUI, QtCore, drain, valid

menus_module = importlib.import_module("fontlabapp.qt.menus")
OwnedMenus = menus_module.OwnedMenus
scripting = importlib.import_module("fontlabapp.core.scripting")


def owner():
    errors = []
    qt = NS(QtGui=GUI, QtCore=QtCore)
    menus = OwnedMenus(qt, NS(), error_sink=lambda error, widget: errors.append(error))
    return menus, errors


def test_tool_when_first_shown_then_priority_precedes_visibility_and_type_stays_tool():
    menus, errors = owner()
    observations, closed = [], []

    class Observed(GUI.QWidget):
        def showEvent(self, event):
            observations.append(self.windowFlags())
            GUI.QWidget.showEvent(self, event)

    menus._window_class = menus_module._tool_window_class(Observed)
    content = GUI.QLineEdit("retained draft")
    try:
        token, window = menus.tool_window(content, "Owned tool", on_close=lambda: closed.append(1))
        assert observations and all(flags & QtCore.Qt.WindowStaysOnTopHint for flags in observations), "Request priority before first native show"
        assert window.windowFlags() & QtCore.Qt.WindowType_Mask == QtCore.Qt.Tool, "Preserve Tool rather than becoming a dialog or embedded widget"
        assert window.windowTitle() == "Owned tool" and content.text() == "retained draft"
        window.hide()
        window.show()
        assert observations[-1] & QtCore.Qt.WindowStaysOnTopHint, "Reuse must retain priority"
        menus.remove(token)
        drain()
        assert not valid(window) and valid(content) and content.parentWidget() is None
        assert closed == [1] and errors == [], "Dispose the shell exactly once and retain caller-owned content"
    finally:
        menus.close()
        content.deleteLater()
        drain()


def test_tool_when_host_parent_dies_and_content_reopens_then_old_reaper_keeps_new_owner():
    menus, errors = owner()
    host = GUI.QMainWindow()
    content = GUI.QLineEdit("still editable", host)
    closed, destroyed = [], []
    try:
        _, first = menus.tool_window(content, "First", on_close=lambda: closed.append("first"))
        first.destroyed.connect(lambda *args: destroyed.append("first"))
        host.deleteLater()
        drain()
        assert valid(content) and valid(first), "Host deletion must not take caller-owned plugin content with it"
        assert first.close(), "Title-bar Close should accept the owned shell"
        token, second = menus.tool_window(content, "Second", on_close=lambda: closed.append("second"))
        drain()
        assert destroyed == ["first"] and not valid(first)
        assert valid(second) and content.parentWidget() is second and content.text() == "still editable"
        assert second.windowFlags() & QtCore.Qt.WindowStaysOnTopHint, "A newly reopened tool also requests priority"
        menus.remove(token)
        drain()
        assert closed == ["first", "second"] and valid(content) and not valid(second)
        assert errors == []
    finally:
        menus.close()
        content.deleteLater()
        if valid(host):
            host.deleteLater()
        drain()


@pytest.mark.parametrize("route", ["panel", "Apply", "Cancel", "titlebar", "unload"])
def test_glyport_plugin_when_opened_and_closed_then_priority_and_exact_owned_lifetime(route):
    host_type = importlib.import_module("fontlab_glyport.plugins.fontlab_host").FontLabPluginHost
    errors, outcomes = [], []
    host = host_type(NS(QtGui=GUI, QtCore=QtCore), NS(), error_sink=lambda error, widget: errors.append(error))

    class View(GUI.QWidget):
        @property
        def geometry(self):
            # PythonQt exposes this Qt getter as a property; use the actual Qt6
            # rectangle unchanged, adapting only the binding's access spelling.
            return GUI.QWidget.geometry(self)

    view = View()
    view.resize(350, 180)
    try:
        if route == "panel":
            token = host.register_panel(view, "Plugin panel", 100, 500)
        else:
            token = host.run_dialog(view, "Plugin filter", "Apply", outcomes.append)
        window = view.parentWidget()
        assert window.windowFlags() & QtCore.Qt.WindowStaysOnTopHint, "Actual Glyport plugin routes must inherit App's priority policy"
        assert window.windowFlags() & QtCore.Qt.WindowType_Mask == QtCore.Qt.Tool
        if route in ("Apply", "Cancel"):
            buttons = {button.text(): button for button in window.findChildren(GUI.QPushButton)}
            buttons[route].click()
            assert valid(window), "Keep native emitters alive until the click dispatch returns"
        elif route == "titlebar":
            window.close()
        else:
            host.remove(token)
        drain()
        assert not valid(window) and valid(view) and view.parentWidget() is None
        assert outcomes == ([] if route == "panel" else [route == "Apply"])
        assert not errors and not host.has_items, "Unregister the exact plugin session without touching caller-owned content"
    finally:
        host.close()
        view.deleteLater()
        drain()


@pytest.mark.parametrize("stage", ["flags", "show", "raise"])
def test_shared_launcher_when_display_fails_then_exact_owner_remains_recoverable(stage, monkeypatch):
    parent = GUI.QWidget()
    qt = NS(QtGui=GUI, QtCore=QtCore)
    monkeypatch.setattr(scripting, "_native", lambda name: NS(MainWindow=lambda: parent) if name == "fontlab" else qt)
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    failure = RuntimeError("display failed at " + stage)
    made, ticks = [], []

    class Dialog(GUI.QDialog):
        def __init__(self, parent):
            GUI.QDialog.__init__(self, parent)
            self._connections = []
            self.timer = QtCore.QTimer(self)
            scripting.connect_guarded(self, self.timer.timeout, lambda: ticks.append(1))
            self.timer.start(50)
            self.inject = stage
            made.append(self)

        def setWindowFlags(self, flags):
            if self.inject == "flags":
                raise failure
            GUI.QDialog.setWindowFlags(self, flags)

        def show(self):
            if self.inject == "show":
                raise failure
            GUI.QDialog.show(self)

        def raise_(self):
            if self.inject == "raise":
                raise failure
            GUI.QDialog.raise_(self)

        def closeEvent(self, event):
            scripting.close_script_dialog(self, event, "failure-test", timers=(self.timer,))

    try:
        with pytest.raises(RuntimeError) as caught:
            scripting.show_script_dialog(Dialog, "failure-test")
        assert caught.value is failure, "Propagate the original display exception"
        (failed,) = made
        assert sys._fontlab_samples["failure-test"] is failed, "Keep a reachable exact owner rather than abandon a wired dialog"
        failed.inject = None

        def healthy(parent):
            dialog = Dialog(parent)
            dialog.inject = None
            return dialog

        replacement = scripting.show_script_dialog(healthy, "failure-test")
        assert sys._fontlab_samples["failure-test"] is replacement
        drain()
        assert not valid(failed), "Retry closes/deletes the original owner before replacing it"
        replacement.close()
        drain()
        assert not valid(replacement) and not sys._fontlab_samples
    finally:
        for dialog in made:
            if valid(dialog):
                dialog.inject = None
                dialog.close()
        parent.deleteLater()
        drain()
