# this_file: tests/test_anchor_duplicates_panel.py
"""Complete public GUI controls, failure containment and exact owned lifetime."""

import os
import sys
from types import SimpleNamespace as NS

import pytest

from fontlabapp.anchors.duplicates.model import KEY, Layer, Pin, Snapshot
from fontlabapp.anchors.duplicates.ui import panel_type

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore as core, QtGui, QtTest, QtWidgets, sip

    valid = lambda w: not sip.isdeleted(w)
else:
    from PySide6 import QtCore as core, QtGui, QtTest, QtWidgets
    from shiboken6 import isValid as valid

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
gui = NS(**{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
gui.__dict__.update(
    {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
)


@pytest.fixture
def panel(monkeypatch):
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    p = (
        Pin(1, "top", 0, 0),
        Pin(2, "top.1", 5, 5),
        Pin(3, "_a", 9, 9),
        Pin(4, "_b", 9, 9),
    )
    layers = (
        Layer("A", "Regular", 10, 20, False, p),
        Layer("B", "Bold", 11, 21, True, p),
    )
    state = NS(
        facts=Snapshot((7,), ("A", "B"), ("B",), ("Regular", "Bold"), layers, ()),
        fail=False,
        stale=False,
        writes=[],
    )

    class Backend:
        def capture(self):
            if state.fail:
                raise ValueError("capture failed")
            return state.facts

        def validate(self, facts):
            if state.stale:
                raise ValueError("source changed")

        def apply(self, facts, coincident, selected):
            self.validate(facts)
            state.writes.append((coincident, selected))
            if state.fail:
                raise RuntimeError("partial write; use Edit > Undo")
            state.facts = Snapshot(
                (7,), ("A", "B"), ("B",), ("Regular", "Bold"), (), ()
            )
            return {"anchors": 2 if coincident else 1, "layers": 1}

    w = panel_type(core, gui)(None, Backend())
    yield w, state
    if valid(w):
        w.close()
    core.QCoreApplication.sendPostedEvents(None, core.QEvent.DeferredDelete)


def test_original_defaults_all_master_rows_sort_counts_and_opt_in(panel):
    w, s = panel
    assert w.scope.currentIndex() == 0 and not w.coincident.isChecked()
    assert [w.table.horizontalHeaderItem(i).text() for i in range(4)] == [
        "Glyph · master",
        "Finding",
        "Anchors",
        "Fix",
    ]
    assert (
        w.table.rowCount() == 4
        and w.table.selectionMode() == QtWidgets.QAbstractItemView.NoSelection
    )
    assert [w.table.item(i, 1).text() for i in range(4)] == [
        "duplicate name",
        "duplicate name",
        "coincident",
        "coincident",
    ]
    assert (
        w.table.item(1, 3).text() == "auto layer, kept" and w.apply_button.isDefault()
    )
    assert w.status.text() == "1 anchor to remove" and w.apply_button.isEnabled()
    w.coincident.setChecked(True)
    assert w.status.text() == "2 anchors to remove"
    w.scope.setCurrentIndex(1)
    assert w.table.rowCount() == 2 and not w.apply_button.isEnabled()
    assert not s.writes


def test_fix_acts_on_all_pending_groups_and_rescans_without_changing_draft(panel):
    w, s = panel
    w.coincident.setChecked(True)
    w.apply_button.click()
    assert s.writes == [(True, False)] and w.last_result == {"anchors": 2, "layers": 1}
    assert w.status.text() == "Removed 2 anchors from 1 layers"
    assert (
        w.table.rowCount() == 0
        and w.coincident.isChecked()
        and not w.apply_button.isEnabled()
    )


@pytest.mark.parametrize("failure", ["stale", "read", "partial"])
def test_failures_discard_actionable_rows_keep_error_and_never_report_success(
    panel, failure
):
    w, s = panel
    if failure == "stale":
        s.stale = True
        w.apply_button.click()
    elif failure == "read":
        s.fail = True
        w.refresh_button.click()
    else:
        s.fail = True
        w.apply_button.click()
    assert w.facts is None and w.last_result is None and w.table.rowCount() == 0
    assert (
        not w.apply_button.isEnabled() and w.last_error and "Error:" in w.status.text()
    )
    if failure == "stale":
        assert not s.writes
    s.stale = s.fail = False
    w.refresh_button.click()
    assert w.facts is not None and w.apply_button.isEnabled()


def test_no_font_empty_and_automatic_dep_preview_refusal(panel):
    w, s = panel
    s.facts = None
    w.refresh()
    assert w.subtitle.text() == "Open a font first." and not w.apply_button.isEnabled()
    s.facts = Snapshot(
        (7,),
        ("A", "B"),
        ("B",),
        ("Regular",),
        (
            Layer(
                "A", "Regular", 10, 20, False, (Pin(1, "a", 1, 2), Pin(2, "a.1", 3, 4))
            ),
        ),
        (("A", False, ()), ("B", True, ("A",))),
    )
    w.refresh()
    assert (
        not w.apply_button.isEnabled() and "automatic dependants: B" in w.warning.text()
    )


@pytest.mark.parametrize("route", ["button", "escape", "reject", "accept", "done"])
def test_terminal_routes_release_only_owned_registry_and_callbacks(panel, route):
    w, s = panel
    other = object()
    sys._fontlab_samples = {KEY: w, "foreign": other}
    w.show()
    late = w.signals.records[0][1]
    if route == "button":
        w.close_button.click()
    elif route == "escape":
        QtTest.QTest.keyClick(w, core.Qt.Key_Escape)
    elif route == "reject":
        w.reject()
    elif route == "accept":
        w.accept()
    else:
        w.done(8)
    assert w.closed and not w.signals.records and w.backend is None
    assert sys._fontlab_samples == {"foreign": other}
    late()
    assert not s.writes


def test_disconnect_failure_refuses_close_but_close_retry_remains_available(panel):
    w, _s = panel

    class Signal:
        fail = True

        def disconnect(self, slot):
            if self.fail:
                raise RuntimeError("owned disconnect failure")

    signal = Signal()
    w.signals.records.insert(0, (signal, lambda: None, False))
    sys._fontlab_samples = {KEY: w}
    assert w.close() is False and sys._fontlab_samples[KEY] is w and w.closed
    assert w.backend is None and "disconnect failure" in w.last_error
    signal.fail = False
    w.close_button.click()
    assert KEY not in sys._fontlab_samples and not w.signals.records


def test_busy_and_closed_callbacks_do_not_read_or_write_and_late_read_cannot_publish(
    panel,
):
    w, s = panel
    w.busy = True
    w.refresh()
    w.changed()
    w.apply()
    assert not s.writes
    w.busy = False
    original = w.backend.capture

    def close_during_capture():
        result = original()
        w.close()
        return result

    w.backend.capture = close_during_capture
    w.refresh()
    assert w.closed and w.facts is None
    w.changed()
    w.apply()
    w.refresh()
    w.completed()
    assert not s.writes


def test_close_during_writer_and_post_commit_rescan_failure_are_diagnosed(panel):
    w, s = panel
    backend = w.backend
    original = backend.apply

    def apply_then_fail_read(*args):
        result = original(*args)
        s.fail = True
        return result

    backend.apply = apply_then_fail_read
    w.apply()
    assert w.last_result is None and "Fix removed 1 anchors" in w.last_error
    assert "changes remain" in w.last_error and "Undo" in w.last_error
    s.fail = False
    w.refresh()

    def close_during_write(*args):
        w.close()
        return {"anchors": 0, "layers": 0}

    backend.apply = close_during_write
    w.apply()
    assert w.closed and w.facts is None


def test_checkbox_after_empty_capture_and_stale_change_clear_preview(panel):
    w, s = panel
    s.facts = None
    w.refresh()
    w.changed()
    assert w.subtitle.text() == "Open a font first."
    s.facts = Snapshot(
        (7,),
        ("A",),
        (),
        ("Regular",),
        (
            Layer(
                "A",
                "Regular",
                10,
                20,
                False,
                (Pin(1, "top", 1, 2), Pin(2, "top.1", 3, 4)),
            ),
        ),
        (),
    )
    w.refresh()
    s.stale = True
    w.coincident.setChecked(True)
    assert w.facts is None and "source changed" in w.last_error


def test_native_close_handler_failure_refuses_deletion_for_retry(panel, monkeypatch):
    w, _s = panel
    original = w.dispose

    def fail(**kwargs):
        raise RuntimeError("dispose failed")

    monkeypatch.setattr(w, "dispose", fail)
    assert w.close() is False and "dispose failed" in w.last_error
    monkeypatch.setattr(w, "dispose", original)
    assert w.close() is True


def test_parent_destruction_drains_terminal_and_controls_without_foreign_registry_loss(
    panel,
):
    w, _s = panel
    parent = QtWidgets.QWidget()
    other = object()
    child = type(w)(parent, w.backend)
    sys._fontlab_samples = {KEY: child, "foreign": other}
    parent.deleteLater()
    core.QCoreApplication.sendPostedEvents(None, core.QEvent.DeferredDelete)
    assert (
        child.closed
        and child.dead
        and not child.signals.records
        and not child.terminal.records
    )
    assert child.backend is None and sys._fontlab_samples == {"foreign": other}


def test_constructor_failure_retains_failed_cleanup_owner_for_retry(panel, monkeypatch):
    import fontlabapp.anchors.duplicates.ui as module

    w, _s = panel

    class Signal:
        fail = True

        def disconnect(self, slot):
            if self.fail:
                raise RuntimeError("constructor disconnect failed")

    signal = Signal()

    def broken(owner, *args):
        owner.signals.records.append((signal, lambda: None, False))
        raise RuntimeError("build failed")

    monkeypatch.setattr(module, "build", broken)
    with pytest.raises(RuntimeError, match="build failed"):
        type(w)(None, w.backend)
    retained = sys._fontlab_samples[KEY]
    assert retained.closed and retained.backend is None
    signal.fail = False
    assert retained.close() is True


def test_other_keys_reach_native_dialog_and_terminal_refusal_reshows(
    panel, monkeypatch
):
    w, _s = panel
    w.show()
    QtTest.QTest.keyClick(w, core.Qt.Key_A)
    original = w.close
    monkeypatch.setattr(w, "close", lambda: False)
    w.completed()
    assert w.isVisible() and not w.completing
    monkeypatch.setattr(w, "close", original)
