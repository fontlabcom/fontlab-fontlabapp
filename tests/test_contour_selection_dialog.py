# this_file: tests/test_contour_selection_dialog.py
"""Real offscreen widgets exercise accept/error/Escape/parent-destruction paths."""

import importlib
import os
import sys
from types import SimpleNamespace as NS

import pytest
if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtGui, QtWidgets, sip

    def isValid(widget):
        return not sip.isdeleted(widget)
else:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import isValid

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def panel(monkeypatch):
    class LineEdit(QtWidgets.QLineEdit):
        text = property(QtWidgets.QLineEdit.text)

    gui = NS(**{n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")})
    gui.QLineEdit = LineEdit
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=QtCore, QtGui=gui))
    monkeypatch.delitem(
        sys.modules, "fontlabapp.contours.selection.ui", raising=False
    )
    mod = importlib.import_module("fontlabapp.contours.selection.ui")
    calls = []
    monkeypatch.setattr(mod, "capture", lambda **kwargs: "opening source")

    def execute(mode, value, **kwargs):
        from fontlabapp.contours.selection.model import threshold

        threshold(value)
        calls.append((mode, value, kwargs["source"]))
        return 2

    monkeypatch.setattr(mod, "execute", execute)
    widgets = []

    def create(parent=None):
        widget = mod.SmallContoursDialog(parent)
        widgets.append(widget)
        return widget

    yield NS(mod=mod, calls=calls, create=create)
    for widget in widgets:
        if isValid(widget):
            widget.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_accept_repeat_invalid_nonfinite_and_escape(panel):
    widget = panel.create()
    widget.area.setText("51.5")
    widget.apply_button.click()
    assert panel.calls == [("small", "51.5", "opening source")]
    assert widget.status.text() == "2 contours selected."
    for invalid in ("bad", "nan", "inf", "-inf"):
        widget.area.setText(invalid)
        widget.apply_button.click()
        assert "Error:" in widget.status.text()
    assert len(panel.calls) == 1
    widget.reject()
    assert widget._closed and widget.source is None and not widget._connections
    widget.select()
    widget.close_owned()


def test_initial_capture_failure_disables_action_and_close_stays_available(
    panel, monkeypatch
):
    monkeypatch.setattr(
        panel.mod,
        "capture",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("No font")),
    )
    widget = panel.create()
    assert not widget.apply_button.isEnabled()
    assert widget.status.text() == "No font"
    widget.select()
    widget.cancel_button.click()
    assert widget._closed and not panel.calls


@pytest.mark.parametrize("owner", ["direct", "parent"])
def test_destruction_disconnects_and_retained_callbacks_are_inert(panel, owner):
    parent = QtWidgets.QWidget()
    widget = panel.create(parent)
    callback = next(
        slot
        for signal, slot in widget._connections
        if signal == widget.cancel_button.clicked
    )
    (widget if owner == "direct" else parent).deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert widget._closed and not widget._connections
    callback()
    widget.select()
    if isValid(parent):
        parent.deleteLater()


def test_destroy_disconnect_failure_retained_and_registry_removed(panel):
    widget = panel.create()

    class BadSignal:
        def disconnect(self, slot):
            raise RuntimeError("owned disconnect failure")

    widget._connections.append((BadSignal(), lambda: None))
    sys.__dict__.setdefault("_fontlab_samples", {})["select-small-contours"] = widget
    widget._destroyed()
    assert widget.cleanup_errors == ["RuntimeError('owned disconnect failure')"]
    assert "select-small-contours" not in sys._fontlab_samples


def test_public_dialog_factory_and_registry_replacement(panel, monkeypatch):
    import fontlabapp.contours.selection.model as api

    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: None))
    first = api.show_small_contours()
    second = api.show_small_contours()
    assert first._closed and not first._connections
    second.close()


@pytest.mark.parametrize("terminal", ["close", "button", "reject", "escape"])
def test_visible_dialog_closes_accepts_and_destroys_once(panel, terminal):
    widget = panel.create()
    registry = sys.__dict__.setdefault("_fontlab_samples", {})
    registry["select-small-contours"] = widget
    rejected, finished, destroyed = [], [], []
    widget.rejected.connect(lambda: rejected.append(True))
    widget.finished.connect(lambda code: finished.append(code))
    widget.destroyed.connect(lambda: destroyed.append(True))
    widget.show()
    assert widget.isVisible(), "The regression requires a visible QDialog."
    if terminal == "close":
        assert widget.close() is True, "Native Close must accept the event."
    elif terminal == "button":
        widget.cancel_button.click()
    elif terminal == "reject":
        widget.reject()
    else:
        event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Escape, QtCore.Qt.NoModifier)
        QtWidgets.QApplication.sendEvent(widget, event)
    assert not widget.isVisible(), "Cleanup must not leave a visible closed owner."
    assert widget._closed and widget.source is None and not widget._connections
    assert rejected == [True] and finished == [QtWidgets.QDialog.Rejected]
    assert "select-small-contours" not in registry
    assert not panel.calls, "Closing must not select contours."
    QtCore.QCoreApplication.sendPostedEvents(widget, QtCore.QEvent.DeferredDelete)
    assert destroyed == [True] and not isValid(widget)
    widget.reject()
    widget.close_owned()
    assert rejected == [True] and not panel.calls
