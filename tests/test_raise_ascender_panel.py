# this_file: tests/test_raise_ascender_panel.py
"""Actual owned Qt actions/defaults/errors and complete terminal lifetime."""

import os
import sys
from types import SimpleNamespace as NS

import pytest

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore as C, QtGui as G, QtWidgets as W
else:
    from PySide6 import QtCore as C, QtGui as G, QtWidgets as W
import fontlabapp.contours.raise_ascender.ui as ui
import fontlabapp.contours.raise_ascender.model as model
import fontlabapp.core.scripting as scripts


class Gui:
    QCloseEvent = G.QCloseEvent

    def __getattr__(self, name):
        return getattr(W, name)


QT = NS(QtCore=C, QtGui=Gui())


class Backend:
    def __init__(self):
        self.calls = []
        self.fail = False
        self.pending = ()

    def execute(self, amount, all_layers, *, disclosure=None):
        self.calls.append((amount, all_layers))
        from fontlabapp.core.edit_guards import pending_note
        if disclosure is not None:
            disclosure.update(pending_updates=self.pending, pending_note=pending_note(self.pending))
        if self.fail:
            raise ValueError("partial native action: use Undo")
        return {"nodes": 3, "occurrences": 2, "undo_steps": 1}


@pytest.fixture
def panel(monkeypatch):
    app = W.QApplication.instance() or W.QApplication([])
    backend = Backend()
    monkeypatch.setattr(ui, "Backend", lambda: backend)
    monkeypatch.setattr(ui, "_native", lambda name: QT)
    monkeypatch.setattr(
        scripts,
        "_native",
        lambda name: QT if name == "PythonQt" else NS(MainWindow=lambda: None),
    )
    monkeypatch.setattr(sys.modules["fontlabapp"], "_native", lambda name: QT)
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    dialog = model.show()
    yield dialog, backend, app
    if not dialog._closed:
        dialog.close()
    C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)


def test_default_original_actions_keep_amount_and_window_open(panel):
    dialog, backend, _app = panel
    assert dialog.amount.text() == "10" and dialog.go_this.isDefault()
    assert dialog.windowTitle() == "Raise ascender" and not dialog.isModal()
    assert dialog.windowFlags() & C.Qt.WindowType_Mask == C.Qt.Tool
    assert dialog.windowFlags() & C.Qt.WindowStaysOnTopHint
    dialog.go_this.click()
    dialog.amount.setText("-12.5")
    dialog.go_all.click()
    assert backend.calls == [("10", False), ("-12.5", True)]
    assert not dialog._closed and dialog.amount.text() == "-12.5"
    assert "Moved 3 nodes" in dialog.status.text()
    assert not dialog.go_this.geometry().intersects(dialog.amount.geometry())


def test_callback_failure_and_busy_close_keep_undo_diagnosis(panel):
    dialog, backend, _app = panel
    backend.fail = True
    dialog.go_this.click()
    assert "Undo" in dialog.status.text() and not dialog._busy
    dialog._busy = True
    assert dialog.close() is False and not dialog._closed
    dialog.apply(False)
    assert len(backend.calls) == 1
    dialog._busy = False


@pytest.mark.parametrize("terminal", ["close", "reject", "accept", "done"])
def test_all_terminals_disconnect_destroy_and_late_callbacks_inert(panel, terminal):
    dialog, backend, _app = panel
    destroyed = []
    dialog.destroyed.connect(lambda *args: destroyed.append(True))
    if terminal == "done":
        dialog.done(42)
    else:
        getattr(dialog, terminal)()
    C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)
    assert destroyed == [True] and ui.KEY not in sys._fontlab_samples
    assert dialog._completion_lifetime.closed and not dialog._completion_lifetime.hooks
    dialog.apply(True)
    assert not backend.calls


def test_replacement_closes_only_previous_owned_window(panel):
    previous, _backend, _app = panel
    other = model.show()
    assert previous._closed and other is sys._fontlab_samples[ui.KEY]
    other.close()
    C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)


def test_parent_destruction_releases_callbacks_and_late_error_is_inert(panel):
    _old, backend, _app = panel
    parent = W.QWidget()
    dialog = ui.dialog_type(QT)(parent, backend=backend)
    parent.deleteLater()
    C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)
    assert dialog._dead and dialog._closed
    dialog.failure(ValueError('late'))
    dialog.apply(True)
    dialog.reject()
    assert not backend.calls


def test_failed_signal_disconnection_refuses_close_then_retry_finishes(panel, monkeypatch):
    dialog, _backend, _app = panel
    finish = dialog.signals.finish
    monkeypatch.setattr(dialog.signals, 'finish', lambda **kwargs: False)
    event = G.QCloseEvent()
    dialog.closeEvent(event)
    assert not event.isAccepted()
    monkeypatch.setattr(dialog.signals, 'finish', finish)
    dialog.close()


def test_constructor_failure_has_owned_cleanup_before_rethrow(panel, monkeypatch):
    _old, backend, _app = panel
    class BrokenGui(Gui):
        def QFormLayout(self):
            raise ValueError('layout allocation failed')
    broken = NS(QtCore=C, QtGui=BrokenGui())
    with pytest.raises(ValueError, match='layout allocation'):
        ui.dialog_type(broken)(backend=backend)
    C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)


@pytest.mark.parametrize('terminal', ['close', 'reject', 'accept', 'done', 'close-button'])
def test_normal_terminal_late_failure_is_inert_after_real_destruction(panel, terminal):
    dialog, backend, _app = panel
    dead = []
    retained_callbacks = [slot for _, slot, _ in dialog.signals.records]
    dialog.destroyed.connect(lambda *args: dead.append(True))
    if terminal == 'done':
        dialog.done(42)
    elif terminal == 'close-button':
        dialog.close_button.click()
    else:
        getattr(dialog, terminal)()
    C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)
    assert dead == [True] and dialog._closed
    for callback in retained_callbacks:
        callback()
    dialog.failure(ValueError('late retained callback'))
    dialog.apply(False)
    dialog.reject()
    assert not backend.calls


def test_live_failed_close_still_displays_diagnostic_and_retry_succeeds(panel, monkeypatch):
    dialog, backend, _app = panel
    original = dialog.signals.finish
    monkeypatch.setattr(dialog.signals, 'finish', lambda **kwargs: False)
    event = G.QCloseEvent()
    dialog.closeEvent(event)
    assert not event.isAccepted()
    dialog.failure(ValueError('live failed-close retry diagnosis'))
    assert 'live failed-close retry diagnosis' in dialog.status.text()
    monkeypatch.setattr(dialog.signals, 'finish', original)
    dialog.close()
    C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)
    dialog.failure(ValueError('late after successful retry'))
    assert not backend.calls


@pytest.mark.parametrize('after_stop', [False, True])
@pytest.mark.parametrize('parent_dies', [False, True])
def test_close_helper_failure_rearms_live_lifetime(panel, monkeypatch, after_stop, parent_dies):
    _old, backend, _app = panel
    from fontlabapp.core.completion import stop
    parent = W.QWidget()
    dialog = ui.dialog_type(QT)(parent, backend=backend)
    dead = []
    dialog.destroyed.connect(lambda *args: dead.append(True))
    original = ui.close_script_dialog
    def broken(dialog, event, key):
        if after_stop:
            stop(dialog)
        event.ignore()
        raise RuntimeError('close helper failed')
    monkeypatch.setattr(ui, 'close_script_dialog', broken)
    with pytest.raises(RuntimeError, match='close helper failed'):
        dialog.closeEvent(G.QCloseEvent())
    dialog.failure(ValueError('live diagnosis'))
    assert 'live diagnosis' in dialog.status.text()
    assert not dialog._completion_lifetime.closed
    monkeypatch.setattr(ui, 'close_script_dialog', original)
    if parent_dies:
        parent.deleteLater()
        C.QCoreApplication.sendPostedEvents(parent, C.QEvent.DeferredDelete)
        assert dialog._dead
    else:
        dialog.close()
        C.QCoreApplication.sendPostedEvents(dialog, C.QEvent.DeferredDelete)
        parent.deleteLater()
        C.QCoreApplication.sendPostedEvents(parent, C.QEvent.DeferredDelete)
    assert dead == [True]
    dialog.failure(ValueError('late diagnosis'))
    dialog.apply(True)
    dialog.reject()
    assert not backend.calls


@pytest.mark.parametrize("fail", [False, True])
def test_queue_warning_visible_on_success_and_failure_then_cleared(panel, fail, capsys):
    dialog, backend, _ = panel
    backend.pending, backend.fail = (99,), fail
    dialog.go_this.click()
    assert dialog.status.text().count("8537") == 1
    assert ("Undo" if fail else "Moved") in dialog.status.text()
    backend.pending = ()
    dialog.go_all.click()
    assert "8537" not in dialog.status.text(), "Do not reuse an earlier action's warning"
    assert "8537" not in capsys.readouterr().out, "GUI warnings belong in owned status"
