# this_file: tests/test_kerning_persistence_dialog.py
"""Real offscreen controls with native-shaped kerning; no FontLab access."""

import importlib
import os
import sys
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid
from test_kerning_persistence import Package

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def panel(monkeypatch):
    class Dialog(QtWidgets.QDialog):
        palette = property(QtWidgets.QDialog.palette)

    class Label(QtWidgets.QLabel):
        font = property(QtWidgets.QLabel.font)

    class LineEdit(QtWidgets.QLineEdit):
        text = property(QtWidgets.QLineEdit.text)

    class Combo(QtWidgets.QComboBox):
        currentIndex = property(QtWidgets.QComboBox.currentIndex)

    class Table(QtWidgets.QTableWidget):
        fail = False

        def setItem(self, *args):
            if self.fail:
                raise RuntimeError("table rendering failed")
            return super().setItem(*args)

    gui = NS(
        **{name: getattr(QtGui, name) for name in dir(QtGui) if name.startswith("Q")}
    )
    gui.__dict__.update(
        {
            name: getattr(QtWidgets, name)
            for name in dir(QtWidgets)
            if name.startswith("Q")
        }
    )
    gui.QDialog, gui.QLabel, gui.QLineEdit, gui.QComboBox, gui.QTableWidget = (
        Dialog,
        Label,
        LineEdit,
        Combo,
        Table,
    )
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=QtCore, QtGui=gui))
    for name in (
        "fontlabapp.glyphs.names.ui",
        "fontlabapp.proof.inspect.ui",
        "fontlabapp.kerning.persistence.ui",
    ):
        monkeypatch.delitem(sys.modules, name, raising=False)
    mod = importlib.import_module("fontlabapp.kerning.persistence.ui")
    state = NS(package=Package())

    def current(expected=None):
        return (
            state.package
            if expected is None
            or (state.package is not None and state.package.id == expected)
            else None
        )

    monkeypatch.setattr(mod.api, "current_package", current)
    monkeypatch.setattr(
        importlib.import_module("fontlabapp.proof.inspect.ui"), "current_package", current
    )
    dialog = mod.KerningPersistenceDialog()
    yield dialog, state, mod, Table
    if isValid(dialog):
        dialog.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    APP.processEvents()


def test_complete_nonmodal_controls_scope_search_exact_zero_and_close(panel):
    dialog, state, _mod, _table = panel
    assert not dialog.isModal()
    assert dialog.scope.count() == 2 and dialog.scope.currentIndex == 0
    assert len(dialog.rows) == 3 and dialog.table.rowCount() == 3
    assert any(row.value == 0 for row in dialog.rows)
    assert "1 at risk" in dialog.status.text() and "9784" in dialog.subtitle.text()
    assert dialog.table.editTriggers() == QtWidgets.QAbstractItemView.NoEditTriggers
    assert dialog.table.selectionMode() == QtWidgets.QAbstractItemView.NoSelection
    assert dialog.table.item(0, 5).toolTip() == dialog.rows[0].reason
    dialog.scope.setCurrentIndex(1)
    assert len(dialog.rows) == 5 and "2 at risk" in dialog.status.text()
    dialog.search.setText("@Right")
    assert len(dialog.shown) == 1 and dialog.table.item(0, 0).text() == "Bold"
    assert dialog.table.item(0, 4).text() == "-2001"
    dialog.search.setText("missing pair")
    assert dialog.table.rowCount() == 0 and "0 shown" in dialog.status.text()
    dialog.search.setText("")
    state.package.values["Bold"][("T", "@Right")] = -2500
    dialog.refresh_button.click()
    assert any(row.value == -2500 for row in dialog.rows)
    dialog.close_button.click()
    assert not dialog._connections and dialog.package is None and not dialog.rows


@pytest.mark.parametrize(
    "change", ["font", "closed", "master", "domain", "upm", "pair", "zero"]
)
def test_search_rejects_stale_source_and_clears_all_displayed_state(panel, change):
    dialog, state, _mod, _table = panel
    font = state.package
    if change == "font":
        state.package = NS(id=9)
    elif change == "closed":
        state.package = None
    elif change == "master":
        font.master = "Bold"
    elif change == "domain":
        font.masters = ("Bold", "Regular")
    elif change == "upm":
        font.upm = 2000
    elif change == "pair":
        font.values["Bold"][("A", "V")] = 10
    else:
        del font.values["Regular"][("A", "V")]
    dialog.search.setText("A")
    assert not dialog.rows and not dialog.shown and dialog.snapshot is None
    assert dialog.table.rowCount() == 0 and "Error:" in dialog.status.text()
    assert dialog.close_button.isEnabled()


def test_failed_read_and_table_publication_leave_close_and_allow_refresh_recovery(
    panel,
):
    dialog, state, _mod, table = panel
    table.fail = True
    dialog.refresh_button.click()
    assert not dialog.rows and "rendering failed" in dialog.status.text()
    table.fail = False
    state.package.upm = 0
    dialog.refresh_button.click()
    assert not dialog.rows and "UPM" in dialog.status.text()
    state.package.upm = 1000
    dialog.refresh_button.click()
    assert len(dialog.rows) == 3 and dialog.close_button.isEnabled()


def test_initial_no_font_or_unreadable_domain_still_builds_all_controls(panel):
    _dialog, state, mod, _table = panel
    state.package = None
    other = mod.KerningPersistenceDialog()
    assert "Open a font" in other.status.text() and other.close_button.isEnabled()
    assert other.table.rowCount() == 0 and not other.snapshot
    other.close()
    state.package = Package()
    state.package.upm = float("nan")
    other = mod.KerningPersistenceDialog()
    assert "UPM" in other.status.text() and other.close_button.isEnabled()
    other.close()


def test_refresh_after_font_switch_never_rebinds_and_parent_destruction_cleans(panel):
    dialog, state, mod, _table = panel
    state.package = NS(id=9)
    dialog.refresh_button.click()
    assert not dialog.rows and "original font" in dialog.status.text()
    state.package = Package()
    parent = QtWidgets.QWidget()
    child = mod.KerningPersistenceDialog(parent)
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(child), (
        "Native parent destruction must delete only its owned dialog"
    )


def test_option_changes_during_native_recheck_cannot_publish_wrong_scope(
    panel, monkeypatch
):
    dialog, _state, mod, _table = panel
    ensure = mod.api.ensure_snapshot
    calls = []

    def changing_options(*args):
        ensure(*args)
        calls.append(True)
        if len(calls) == 2:
            blocked = dialog.search.blockSignals(True)
            dialog.search.setText("changed during read")
            dialog.search.blockSignals(blocked)

    monkeypatch.setattr(mod.api, "ensure_snapshot", changing_options)
    dialog.refresh_button.click()
    assert not dialog.rows and "options changed" in dialog.status.text()


def test_scope_changed_without_refresh_refuses_old_rows_on_filter(panel):
    dialog, _state, _mod, _table = panel
    blocked = dialog.scope.blockSignals(True)
    dialog.scope.setCurrentIndex(1)
    dialog.scope.blockSignals(blocked)
    dialog.search.setText("A")
    assert not dialog.rows and "scope changed" in dialog.status.text()
    dialog.search.setText("No stale snapshot")
    assert not dialog.rows and dialog.close_button.isEnabled()


def test_late_actions_after_close_do_not_access_deleted_widgets(panel, monkeypatch):
    dialog, _state, mod, _table = panel
    dialog.close_button.click()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(dialog), "Deliver actual Qt deletion before the late actions"

    def forbidden(*args):
        raise AssertionError("Closed audit must not read the font")

    monkeypatch.setattr(mod.api, "capture", forbidden)
    dialog.refresh()
    dialog.filter_rows()
    dialog.invalidate()
    assert not dialog.rows and not dialog._connections


@pytest.mark.parametrize("owner", ["parent", "dialog"])
@pytest.mark.parametrize("queued", [False, True])
def test_actual_destruction_disables_retained_actions_and_slots(
    panel, monkeypatch, owner, queued
):
    _original, _state, mod, _table = panel
    parent = QtWidgets.QWidget()
    dialog = mod.KerningPersistenceDialog(parent)
    callbacks = [slot for _signal, slot in dialog._connections]
    monkeypatch.setattr(sys, "_fontlab_samples", {dialog.KEY: dialog}, raising=False)

    def forbidden(*args):
        pytest.fail("Destroyed audit must never read its font")

    monkeypatch.setattr(mod.api, "capture", forbidden)
    failures, delivered = [], []

    def late():
        try:
            dialog.refresh()
            dialog.filter_rows()
            dialog.invalidate()
            for callback in callbacks:
                callback()
        except Exception as error:  # noqa: BLE001 - report queued failures to pytest
            failures.append(repr(error))
        delivered.append(True)

    if queued:
        QtCore.QTimer.singleShot(0, late)
    (parent if owner == "parent" else dialog).deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(dialog), "Delete native Qt before delivering queued callbacks"
    if queued:
        APP.processEvents()
    else:
        late()
    assert delivered and not failures, failures
    assert dialog._closed and not dialog._connections
    assert dialog.package is None and dialog.snapshot is None and not dialog.rows
    assert dialog.KEY not in sys._fontlab_samples
    if isValid(parent):
        parent.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_parent_destruction_preserves_replacement_registry_and_failed_panel(
    panel, monkeypatch
):
    _original, state, mod, _table = panel
    state.package.upm = 0
    parent = QtWidgets.QWidget()
    dialog = mod.KerningPersistenceDialog(parent)
    assert "UPM" in dialog.status.text()
    replacement, unrelated = object(), object()
    registry = {dialog.KEY: replacement, "unrelated": unrelated}
    monkeypatch.setattr(sys, "_fontlab_samples", registry, raising=False)
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(dialog) and dialog._closed
    dialog.refresh()
    assert not dialog._connections and dialog.package is None
    assert registry == {dialog.KEY: replacement, "unrelated": unrelated}


@pytest.mark.parametrize("owner", ["parent", "dialog"])
def test_destruction_explicitly_disconnects_callbacks_before_live_children_die(
    panel, owner
):
    _original, _state, mod, _table = panel
    parent = QtWidgets.QWidget()
    dialog = mod.KerningPersistenceDialog(parent)
    connected = tuple(dialog._connections)
    children = (dialog.scope, dialog.search, dialog.table, dialog.close_button)
    disconnected = []

    class CheckedSignal:
        def __init__(self, signal):
            self.signal = signal

        def disconnect(self, slot):
            assert all(isValid(widget) for widget in children)
            if owner == "parent":
                assert isValid(dialog), "Parent cleanup must precede dialog destruction"
            disconnected.append(slot)
            self.signal.disconnect(slot)

    dialog._connections[:] = [
        (CheckedSignal(signal), slot) for signal, slot in connected
    ]
    (parent if owner == "parent" else dialog).deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert len(disconnected) == len(connected), "Explicitly disconnect every owned slot"
    assert not dialog._connections and not dialog._disconnect_errors
    if isValid(parent):
        parent.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_destructor_disconnect_failure_is_retained_without_escaping_qt(panel):
    _original, _state, mod, _table = panel
    parent = QtWidgets.QWidget()
    dialog = mod.KerningPersistenceDialog(parent)
    attempts = []

    class FailedSignal:
        def disconnect(self, slot):
            attempts.append(slot)
            raise RuntimeError("injected disconnect failure")

    dialog._connections.append((FailedSignal(), lambda: None))
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert len(attempts) == 1 and not isValid(dialog)
    assert dialog._disconnect_errors == ["RuntimeError('injected disconnect failure')"]
    assert not dialog._connections and dialog._closed
