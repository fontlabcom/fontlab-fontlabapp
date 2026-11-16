# this_file: tests/test_background_dialog.py
"""Real compact panel class and shared owned signal/close machinery."""

import sys
from types import SimpleNamespace as NS

import fontlabapp.masters.background.ui as ui
import fontlabapp.masters.background.native as native
import fontlabapp.masters.background.model as api
import pytest
from fontlabapp.core import scripting


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot):
        self.slots.remove(slot)

    def emit(self, *args):
        for slot in tuple(self.slots):
            slot(*args)


class Widget:
    def __init__(self, *args):
        self.text = args[0] if args and isinstance(args[0], str) else ""
        self.clicked = Signal()
        self.finished = Signal()
        self.destroyed = Signal()
        self.children = []
        self.closed = False
        self.deleted = False

    def setWindowTitle(self, title):
        self.title = title

    def setFixedSize(self, w, h):
        self.size = (w, h)

    def addWidget(self, child):
        self.children.append(child)

    def setDefault(self, value):
        self.default = value

    def setWordWrap(self, value):
        self.wrap = value

    def setText(self, text):
        self.text = text

    def close(self):
        self.closeEvent(NS())
        return True

    def closeEvent(self, event):
        self.closed = True

    def deleteLater(self):
        self.deleted = True

    def show(self):
        pass

    def raise_(self):
        pass

    def windowFlags(self):
        return 0

    def setWindowFlags(self, flags):
        self.flags = flags


@pytest.fixture
def owned(monkeypatch):
    gui = NS(
        QDialog=Widget,
        QVBoxLayout=Widget,
        QLabel=Widget,
        QLineEdit=Widget,
        QPushButton=Widget,
    )
    lookup = lambda name: (
        NS(QtGui=gui, QtCore=NS(Qt=NS(WindowStaysOnTopHint=1))) if name == "PythonQt" else NS(MainWindow=lambda: None)
    )
    monkeypatch.setattr(ui, "_native", lookup)
    monkeypatch.setattr(scripting, "_native", lookup)
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    return gui


@pytest.mark.parametrize("mode", ["scale", "shift"])
def test_panel_reads_current_numeric_field_and_successfully_closes(
    owned, monkeypatch, mode
):
    calls = []
    monkeypatch.setattr(
        api, "run", lambda mode, value: calls.append((mode, value)) or {"changed": 3}
    )
    dialog = ui.show_dialog(mode)
    assert not dialog.closed and dialog.button.default
    dialog.input.text = "12.5"
    dialog.button.clicked.emit(True)
    assert calls == [(mode, "12.5")] and dialog.last_result == {"changed": 3}
    assert dialog.closed and dialog.deleted and not dialog._connections
    assert (
        not dialog.button.clicked.slots
        and not dialog.finished.slots
        and not dialog.destroyed.slots
    )
    assert "background-" + mode not in sys._fontlab_samples


def test_invalid_input_is_actionable_without_closing_or_clearing_the_field(
    owned, monkeypatch
):
    def run(mode, value):
        api.numeric(value)

    monkeypatch.setattr(api, "run", run)
    dialog = ui.show_dialog("scale")
    dialog.input.text = "invalid"
    dialog.button.clicked.emit(True)
    assert (
        not dialog.closed
        and dialog.input.text == "invalid"
        and "finite number" in dialog.status.text
    )
    dialog.close()
    assert dialog.deleted


def test_manual_close_never_invokes_the_writer_and_reopen_replaces_only_owned_panel(
    owned, monkeypatch
):
    monkeypatch.setattr(api, "run", lambda *args: pytest.fail("Cancel must not write"))
    first = ui.show_dialog("shift")
    second = ui.show_dialog("shift")
    assert first.deleted and not second.closed
    second.close()
    assert second.deleted


def test_public_modes_delegate_and_validate_before_capture(monkeypatch):
    calls = []

    class Backend:
        def __init__(self):
            calls.append("init")

        def capture(self, mode):
            calls.append(("capture", mode))
            return mode

        def apply(self, source, operation):
            calls.append(("apply", source, operation))
            return {"changed": 1}

    monkeypatch.setattr(native, "Backend", Backend)
    with pytest.raises(ValueError):
        api.run("scale", "bad")
    assert not calls
    assert api.run("shift", "-1.5") == {"changed": 1}
    assert calls[-1][2] == api.Transform("shift", -1.5)
    assert api.show("replace") == {"changed": 1} and calls[-1][2] is None
    monkeypatch.setattr(ui, "show_dialog", lambda mode: ("owned", mode))
    assert api.show("scale") == ("owned", "scale") and api.show("shift") == (
        "owned",
        "shift",
    )
    with pytest.raises(ValueError):
        api.show("other")
