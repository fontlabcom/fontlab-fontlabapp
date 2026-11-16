# this_file: tests/test_regexp_panel.py
"""Real widget events/lifetime; Qt6 uses scripted native-call doubles, not a parser."""

import json
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from test_spacing_worksheet import GUI, QtCore, QTest, drain, valid

from fontlabapp.qt.regexp.ui import panel_type


def core_for_panel():
    if hasattr(QtCore, "QRegExp"):
        return QtCore
    expression = Mock()
    expression.isValid.return_value = True
    expression.errorString.return_value = ""
    expression.indexIn.return_value = 0
    expression.matchedLength.return_value = 1
    expression.captureCount.return_value = 0
    expression.cap.return_value = "fixture"
    factory = Mock(return_value=expression)
    for i, name in enumerate(("RegExp", "RegExp2", "Wildcard", "FixedString")):
        setattr(factory, name, i)
    return NS(Qt=QtCore.Qt, QRegExp=factory)


@pytest.fixture
def panel():
    state = NS(words=("A", "a.alt", "s", "s.alt", "uni1F600"), error=None, calls=0)

    def capture(**kwargs):
        state.calls += 1
        if state.error:
            raise state.error
        return state.words

    widget = panel_type(core_for_panel(), GUI)(None, capture)
    widget.show()
    drain()
    yield widget, state
    if valid(widget):
        assert widget.close()
    drain()


def test_full_original_controls_and_live_edits(panel):
    p, state = panel
    assert p.pattern.isEditable() and p.input.isEditable()
    assert (
        p.pattern.currentText() == r"(s\w+)" and p.input.currentText() == "small stones"
    )
    assert [p.syntax.itemText(i) for i in range(p.syntax.count())] == [
        "Regular expression",
        "Regular expression 2",
        "Wildcard",
        "Fixed string",
    ]
    assert not p.case.isChecked() and not p.minimal.isChecked()
    assert p.output.isReadOnly() and (p.width(), p.height()) == (760, 540)
    p.pattern.lineEdit().selectAll()
    QTest.keyClicks(p.pattern.lineEdit(), "A(.*)")
    p.input.lineEdit().selectAll()
    QTest.keyClicks(p.input.lineEdit(), "A.alt")
    p.case.click()
    p.minimal.click()
    p.syntax.setCurrentIndex(1)
    drain()
    assert (
        p.result["pattern"] == "A(.*)"
        and json.loads(p.output.toPlainText()) == p.result
    )
    assert (
        p.configuration()[0].case
        and p.configuration()[0].minimal
        and p.configuration()[0].syntax == 1
    )
    assert state.calls == 1


def test_native_history_and_captured_choice_keep_authored_pattern(panel):
    p, _ = panel
    p.pattern.setEditText("custom.*")
    p.input.setEditText("draft")
    QTest.keyClick(p.input.lineEdit(), QtCore.Qt.Key_Return)
    drain()
    assert p.input.findText("draft") >= 0
    p.glyphs.setFocus()
    p.glyphs.setCurrentIndex(0)
    QTest.keyClick(p.glyphs, QtCore.Qt.Key_Down)
    drain()
    assert p.input.currentText() == "a.alt" and p.pattern.currentText() == "custom.*"


def test_refresh_failure_then_complete_replacement_preserves_both_drafts(panel):
    p, state = panel
    p.pattern.setEditText("A.*")
    p.input.setEditText("local draft")
    state.error = ValueError("font context changed")
    p.refresh_button.click()
    drain()
    assert p.words == () and not p.glyphs.isEnabled() and p.result["tested_glyphs"] == 0
    assert "context changed" in p.status.text()
    assert p.pattern.currentText() == "A.*" and p.input.currentText() == "local draft"
    state.error = None
    state.words = ("B", "C")
    p.refresh_button.click()
    drain()
    assert (
        p.words == ("B", "C")
        and p.glyphs.count() == 2
        and p.result["tested_glyphs"] == 2
    )
    assert p.pattern.currentText() == "A.*" and p.input.currentText() == "local draft"


def test_bad_capture_and_close_during_capture_publish_no_partial_data(panel):
    p, state = panel
    state.words = ("A", "A")
    p.refresh()
    assert not p.words
    p.capture = lambda **kw: p.dispose() or ("late",)
    p.refresh()
    assert p.closed and p.result is None and not p.words


def test_close_refuses_failed_disconnect_then_retries_and_fences_old_slots(panel):
    p, _ = panel
    late = p.scope.records[0][1]
    signal = NS(disconnect=lambda slot: False)
    p.scope.records.insert(0, (signal, lambda: None, False))
    assert p.close() is False and p.closed and p.scope.records
    before = p.output.toPlainText()
    late("queued")
    assert p.output.toPlainText() == before
    signal.disconnect = lambda slot: True
    assert p.close()
    drain()
    assert p.scope.dead and p.terminal.dead


def test_parent_destruction_releases_callbacks_and_registry():
    parent = GUI.QWidget()
    p = panel_type(core_for_panel(), GUI)(parent, lambda **kw: ("A",))
    sys.__dict__.setdefault("_fontlab_samples", {})[p.KEY] = p
    parent.deleteLater()
    drain()
    assert p.dead and not p.scope.records and not p.terminal.records
    assert p.KEY not in sys._fontlab_samples


def test_reporting_failure_and_property_binding_configuration(panel):
    p, _ = panel
    old = p.case, p.minimal
    p.case, p.minimal = NS(checked=True), NS(checked=False)
    assert p.configuration()[0].case and not p.configuration()[0].minimal
    p.case, p.minimal = old
    with pytest.raises(ValueError):
        p.choose(-1)
    p.status = NS(
        setText=lambda value: (_ for _ in ()).throw(ValueError("report failure"))
    )
    p.failure(ValueError("owned fault"))
    assert "owned fault" in p.last_error and "report failure" in p.last_error
    p.status = None


def test_reentrant_closed_and_late_publish_routes_are_fenced(panel):
    p, _state = panel

    def capture(**kw):
        p.changed()
        p.refresh()
        return ("A",)

    p.capture = capture
    p.refresh()
    assert p.words == ("A",)
    p.closed = True
    p.changed()
    p.refresh()
    p.choose(-1)
    p.publish((), 10**20)
    p.failure(ValueError("closed"))
    p.closed = False
    p.busy = True
    p.changed()
    p.refresh()
    p.busy = False


def test_qt_configuration_failure_is_contained_and_close_retry_survives(panel):
    p, _ = panel
    old = p.pattern
    p.pattern = NS(currentText=None)
    p.changed()
    assert "pattern" in p.last_error.lower()
    p.pattern = old
    finish = p.scope.finish
    p.scope.finish = lambda **kw: (_ for _ in ()).throw(ValueError("close fault"))
    assert p.close() is False and "close fault" in p.last_error
    p.scope.finish = finish


def test_capture_closing_then_raising_cannot_republish(panel):
    p, _ = panel

    def capture(**kw):
        p.dispose()
        raise ValueError("late source failure")

    p.capture = capture
    p.refresh()
    assert p.result is None and not p.words


def test_constructor_failure_closes_its_owned_connections(monkeypatch):
    import fontlabapp.qt.regexp.ui as module

    observed = []

    def broken(owner, *args):
        observed.append(owner)
        raise ValueError("setup fault")

    monkeypatch.setattr(module, "build", broken)
    with pytest.raises(ValueError, match="setup fault"):
        module.panel_type(core_for_panel(), GUI)(None, lambda **kw: ())
    drain()
    assert observed[0].closed and not observed[0].scope.records
