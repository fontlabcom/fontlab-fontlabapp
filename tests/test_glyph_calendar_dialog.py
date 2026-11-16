# this_file: tests/test_glyph_calendar_dialog.py
"""Complete calendar/report refresh and all owned modeless completion routes."""

from module_paths import module_name as _module_name
import importlib
import os
import sys
from types import SimpleNamespace as NS

import pytest
from fontlabapp.qt.tables.filter.model import Table

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtGui, QtWidgets, sip

    valid = lambda item: not sip.isdeleted(item)
else:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import isValid as valid
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
ROWS = (
    ("A<test>", "U+0041 U+0391", "2026-03-20 23:59:59"),
    ("a.alt", "", "2026-03-20 00:00:00"),
    ("B", "U+0042", "2026-03-21 00:00:00"),
    ("undated", "", ""),
)


@pytest.fixture(params=[False, True], ids=["part2", "part3"])
def panel(monkeypatch, request):
    class Dialog(QtWidgets.QDialog):
        palette = property(QtWidgets.QDialog.palette)

    class Label(QtWidgets.QLabel):
        font = property(QtWidgets.QLabel.font)

    gui = NS(**{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
    gui.__dict__.update(
        {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
    )
    gui.QDialog, gui.QLabel = Dialog, Label
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=QtCore, QtGui=gui))
    for name in ["_names_dialog", "_glyph_calendar_dialog"]:
        monkeypatch.delitem(sys.modules, _module_name(name), raising=False)
    module = importlib.import_module("fontlabapp.glyphs.calendar.ui")
    state = NS(rows=ROWS, calls=0, fail=False, deadline=None)

    def capture(*, deadline):
        state.calls += 1
        state.deadline = deadline
        if state.fail:
            raise ValueError("source changed")
        return Table(("Name", "Unicode", "Modified"), state.rows)

    w = module.GlyphCalendarDialog(None, capture, official=request.param)
    w.controls.dates["selected"].setDate(QtCore.QDate(2026, 3, 20))
    yield w, state, module
    if valid(w):
        w.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_complete_calendar_when_day_selected_then_plain_full_glyph_report(panel):
    w, state, _ = panel
    assert not w.isModal() and w.output.isReadOnly() and state.calls == 1
    assert (
        w.output.toPlainText()
        == "A<test> — U+0041 U+0391 — 2026-03-20 23:59:59\na.alt — Not encoded — 2026-03-20 00:00:00"
    )
    assert "2 of 4 glyphs" in w.status.text() and "1 without" in w.status.text()
    w.controls.calendar.setSelectedDate(QtCore.QDate(2026, 3, 21))
    assert w.output.toPlainText() == "B — U+0042 — 2026-03-21 00:00:00"
    assert state.calls == 1, "calendar changes use the complete captured snapshot"


def test_refresh_when_empty_or_failed_then_old_results_never_survive(panel):
    w, state, _ = panel
    w.controls.combos["locale"].setCurrentIndex(1)
    state.rows = ()
    w.refresh_button.click()
    assert "0 of 0 glyphs" in w.status.text() and w.output.toPlainText() == ""
    assert w.controls.combos["locale"].currentIndex() == 1
    state.fail = True
    w.refresh()
    assert w._snapshot is None and w.output.toPlainText() == ""
    assert "source changed" in w.status.text()
    state.fail, state.rows = False, ROWS
    w.refresh()
    assert "2 of 4 glyphs" in w.status.text()


@pytest.mark.parametrize("failure", ["wrong", "expired", "bad-stamp", "closed"])
def test_bad_or_expired_or_closed_observation_never_publishes_partial_results(
    panel, monkeypatch, failure
):
    w, state, module = panel
    if failure == "wrong":
        w._capture = lambda **kw: None
    elif failure == "expired":
        monkeypatch.setattr(module, "monotonic", lambda: -10)
    elif failure == "bad-stamp":
        state.rows = ROWS + (("bad", "", "not a date"),)
    else:

        def capture(**kw):
            w.close()
            return Table(("A", "B", "C"), ROWS)

        w._capture = capture
    w.refresh()
    assert w._snapshot is None and w.output.toPlainText() == ""
    if failure != "closed":
        assert any(
            word in w.status.text()
            for word in ["complete immutable", "expired", "timestamp"]
        )


@pytest.mark.parametrize(
    "route", ["close", "reject", "accept", "done", "escape", "destroy"]
)
def test_each_completion_releases_controls_capture_snapshot_registry_and_callbacks(
    panel, route
):
    w, state, _ = panel
    controls = w.controls
    sys.__dict__.setdefault("_fontlab_samples", {})[w.KEY] = w
    w.show()
    if route == "close":
        w.close_button.click()
    elif route == "destroy":
        w.deleteLater()
    elif route == "done":
        w.done(0)
    elif route == "escape":
        if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
            from PyQt5.QtTest import QTest
        else:
            from PySide6.QtTest import QTest
        QTest.keyClick(w, QtCore.Qt.Key_Escape)
    else:
        getattr(w, route)()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert w._closed and w._capture is None and w._snapshot is None
    assert controls._closed and w.controls is None and not w._connections
    assert w.KEY not in sys._fontlab_samples
    calls = state.calls
    w.refresh()
    w._update()
    w.invalidate()
    w._dispose()
    assert state.calls == calls


def test_parent_destruction_releases_all_owned_callbacks(panel):
    w, _, module = panel
    parent = QtWidgets.QWidget()
    other = module.GlyphCalendarDialog(
        parent, lambda **kw: Table(("A", "B", "C"), ROWS), official=w.official
    )
    controls = other.controls
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert other._closed and controls._closed and not other._connections


@pytest.mark.parametrize("stage", ["scan", "render"])
def test_close_during_day_update_discards_late_result_and_status(
    panel, monkeypatch, stage
):
    w, _, module = panel
    before = w.status.text()
    if stage == "scan":
        original = module.on_day

        def late(*args, **kwargs):
            w.close()
            return original(*args, **kwargs)

        monkeypatch.setattr(module, "on_day", late)
    else:
        original = w.output.setPlainText

        def late(text):
            original(text)
            w.close()

        monkeypatch.setattr(w.output, "setPlainText", late)
    w._update()
    assert w._closed and w._snapshot is None and w.status.text() == before


def test_disconnect_failure_is_recorded_and_all_other_owned_connections_release(panel):
    w, _, _ = panel

    class Broken:
        def disconnect(self, slot):
            raise ValueError("owned disconnect")

    w._connections.append((Broken(), lambda: None))
    w._dispose()
    assert (
        w._closed
        and not w._connections
        and w._disconnect_errors == ["owned disconnect"]
    )


def test_calendar_panel_setup_failure_disconnects_every_registered_control(
    panel, monkeypatch
):
    w, _, module = panel
    import fontlabapp.qt.calendars.classic.controls as controls

    errors = []

    def fail(self, *args):
        errors.append(self)
        raise RuntimeError("owned format setup")

    monkeypatch.setattr(
        module.OfficialControls if w.official else controls.Controls, "_format", fail
    )
    parent = QtWidgets.QWidget()
    with pytest.raises(RuntimeError, match="owned format setup"):
        module.GlyphCalendarDialog(
            parent, lambda **kw: Table(("A", "B", "C"), ROWS), official=w.official
        )
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert errors and errors[0]._closed and parent.children() == []
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
