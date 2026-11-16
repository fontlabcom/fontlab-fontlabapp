# this_file: tests/test_callback_guard_runtime.py
"""Real standalone Qt signals retain foreign listeners during owned suppression."""

import os
from types import SimpleNamespace

import pytest
from fontlabapp.core.signals.callbacks import quiet_callbacks

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtWidgets
else:
    from PySide6 import QtCore, QtWidgets
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.mark.parametrize("kind", ["line", "text", "slider"])
@pytest.mark.parametrize("initial", [False, True])
@pytest.mark.parametrize("raises", [False, True])
def test_owned_qt_callback_when_nested_signal_then_foreign_receivers_still_run(
    kind, initial, raises
):
    if kind == "line":
        view = QtWidgets.QLineEdit()
        signal, update = view.textChanged, lambda n: view.setText(str(n))
    elif kind == "text":
        view = QtWidgets.QPlainTextEdit()
        signal, update = view.textChanged, lambda n: view.setPlainText(str(n))
    else:
        view = QtWidgets.QSlider()
        signal, update = view.valueChanged, view.setValue
    owner = SimpleNamespace(_quiet=initial, reentered=False)
    foreign, callbacks, states = [], [], []
    error = ValueError("nested failure")

    def observer(*args):
        foreign.append(args)
        if not owner.reentered:
            owner.reentered = True
            try:
                with quiet_callbacks(owner):
                    update(2)
                    if raises:
                        raise error
            except ValueError as caught:
                states.append(caught is error)
            states.append(owner._quiet)

    def report(*args):
        if not owner._quiet:
            callbacks.append(args)

    signal.connect(observer)
    signal.connect(report)
    try:
        with quiet_callbacks(owner):
            update(1)
            assert owner._quiet is True, (
                "inner signal must not release outer suppression"
            )
        assert owner._quiet is initial, (
            "restore prior state after synchronous signal delivery"
        )
        assert len(foreign) == 2, (
            "unrelated Qt listeners must still receive both changes"
        )
        assert callbacks == [], "both programmatic signals must stay quiet"
        assert all(states), "nested failure and suppression state must survive"
        update(3)
        assert len(foreign) == 3, "the foreign connection must remain usable"
        assert len(callbacks) == (0 if initial else 1), (
            "later input uses restored policy"
        )
        assert not view.signalsBlocked(), "never block the native widget's signals"
    finally:
        signal.disconnect(observer)
        signal.disconnect(report)
        view.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
