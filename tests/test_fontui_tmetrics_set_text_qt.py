# this_file: tests/test_fontui_tmetrics_set_text_qt.py
# SPDX-License-Identifier: Apache-2.0
"""Real Qt text signals drive TMetrics; unrelated widgets use existing doubles."""

import os

import pytest

from _tmetrics_fakes import EditableFont
from test_cov_ui_tmetrics import tm_mod  # noqa: F401

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtWidgets
else:
    from PySide6 import QtCore, QtWidgets

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TextField(QtWidgets.QLineEdit):
    text = property(QtWidgets.QLineEdit.text)


@pytest.fixture
def window(tm_mod):  # noqa: F811
    owner = tm_mod.TMetrics(EditableFont(), text="AV")
    field = TextField("AV")
    owner.text_control = field
    owner.connect(field.textChanged, lambda *args: owner.refresh())
    refresh = owner.refresh
    owner.refresh_count = 0

    def counted():
        owner.refresh_count += 1
        refresh()

    owner.refresh = counted
    yield owner
    owner.close()
    assert owner.connections == [], "the real signal must use owned cleanup"
    field.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_set_text_when_changed_then_one_refresh_precedes_observers(window):
    seen = []
    window.connect(window.text_control.textChanged, lambda text: seen.append(
        (text, window.model.settings.text, tuple(c.name for c in window.model.cells))))
    window.set_text("VA")
    assert window.refresh_count == 1
    assert seen == [("VA", "VA", ("V", "A"))]
    assert not window.text_control.signalsBlocked()


@pytest.mark.parametrize("blocked,text", [(False, "AV"), (True, "VA")])
def test_set_text_when_no_signal_then_refreshes_font_and_keeps_block(window, blocked, text):
    seen = []
    window.connect(window.text_control.textChanged, lambda text: seen.append(text))
    window.text_control.blockSignals(blocked)
    window.font.ufo["A"].width = 720
    window.set_text(text)
    assert window.refresh_count == 1 and seen == []
    assert window.text_control.signalsBlocked() is blocked
    assert window.model.settings.text == text
    assert next(c.width for c in window.model.cells if c.name == "A") == 720


def test_set_text_when_truncated_to_same_text_then_refreshes_once(window):
    window.text_control.setMaxLength(2)
    window.set_text("AVextra")
    assert window.refresh_count == 1
    assert window.text_control.text == window.model.settings.text == "AV"


def test_set_text_when_reentrant_then_each_changed_value_refreshes_once(window):
    seen = []

    def change(text):
        seen.append((text, window.model.settings.text))
        if text == "VA":
            window.set_text("AA")

    window.connect(window.text_control.textChanged, change)
    window.set_text("VA")
    assert window.refresh_count == 2
    assert seen == [("VA", "VA"), ("AA", "AA")]
    assert window.text_control.text == window.model.settings.text == "AA"


def test_set_text_when_first_reshape_fails_then_explicit_refresh_retries(window, monkeypatch):
    reshape = window.model.reshape
    attempts = []

    def fail_once():
        attempts.append(None)
        if len(attempts) == 1:
            raise ValueError("first reshape refused")
        reshape()

    monkeypatch.setattr(window.model, "reshape", fail_once)
    window.set_text("VA")
    assert len(attempts) == window.refresh_count == 2
    assert window.drawn is not None
    assert tuple(c.name for c in window.model.cells) == ("V", "A")


def test_set_text_when_observer_edits_font_and_refreshes_then_final_model_is_current(window):
    def edit(text):
        window.font.ufo["V"].width = 720
        window.refresh()

    window.connect(window.text_control.textChanged, edit)
    window.set_text("VA")
    assert window.refresh_count == 2, "one signal refresh plus the observer's necessary refresh"
    assert window.model.cells[0].width == 720


def test_set_text_when_first_layout_fails_then_explicit_refresh_retries(window, monkeypatch):
    relayout = window._relayout
    attempts = []

    def fail_once():
        attempts.append(None)
        if len(attempts) == 1:
            raise ValueError("first layout refused")
        relayout()

    monkeypatch.setattr(window, "_relayout", fail_once)
    window.set_text("VA")
    assert len(attempts) == window.refresh_count == 2
    assert window.drawn is not None
    assert window.diagnostic.text == "shaped (HarfBuzz)"


def test_set_text_when_observer_closes_owner_then_cleanup_stays_complete(window):
    window.connect(window.text_control.textChanged, lambda text: window.close())
    window.set_text("VA")
    assert window.closed and window._close_complete
    assert window.connections == [] and window.refresh_count == 1


def test_refresh_when_layout_fails_then_generation_stays_and_drawn_is_not_cleared(window, monkeypatch):
    generation = window._refresh_generation

    def refuse():
        raise ValueError("layout refused")

    monkeypatch.setattr(window, "_relayout", refuse)
    window.refresh()
    assert window._refresh_generation == generation
    assert window.drawn is not None, "retain the existing partial-refresh state"
    assert window.diagnostic.text == "Error: layout refused"


def test_set_text_when_closed_then_no_signal_or_refresh(window):
    seen = []
    window.connect(window.text_control.textChanged, lambda text: seen.append(text))
    window.close()
    window.set_text("VA")
    assert window.refresh_count == 0 and seen == []
    assert window.text_control.text == "AV"
