# this_file: tests/test_spacing_worksheet.py
"""Real item-view events cover every cell in both original delegate profiles."""

import os
import sys
from types import SimpleNamespace as NS

import pytest

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtGui, QtWidgets, sip
    from PyQt5.QtTest import QTest

    valid = lambda item: not sip.isdeleted(item)
else:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtTest import QTest
    from shiboken6 import isValid as valid

from fontlabapp.metrics.worksheet.data import Baseline, Snapshot, defaults
from fontlabapp.metrics.worksheet.ui import panel_type

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
APP.setFont(QtGui.QFont("Helvetica"))
GUI = NS(**{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
GUI.__dict__.update(
    {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
)


def drain():
    APP.processEvents()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    APP.processEvents()


@pytest.fixture(params=[False, True], ids=["part2", "part3"])
def panel(request):
    state = NS(fail=False, calls=0)

    def capture():
        state.calls += 1
        if state.fail:
            raise ValueError("source changed")
        return Snapshot(
            (9, "Regular"),
            tuple(Baseline(9, 2, i, "A.alt", "Regular", 500.5) for i in range(6)),
        )

    p = panel_type(QtCore, GUI)(None, capture, official=request.param)
    p.show()
    p.activateWindow()
    drain()
    yield p, state
    if valid(p):
        assert p.close()
    drain()


def open_cell(p, row, column, trigger="keyboard"):
    index = p.model.index(row, column)
    p.table.setCurrentIndex(index)
    p.table.setFocus()
    drain()
    if trigger == "mouse":
        point = p.table.visualRect(index).center()
        QTest.mouseClick(p.table.viewport(), QtCore.Qt.LeftButton, pos=point)
        QTest.mouseDClick(p.table.viewport(), QtCore.Qt.LeftButton, pos=point)
    else:
        QTest.keyClick(
            p.table,
            QtCore.Qt.Key_Return if sys.platform == "darwin" else QtCore.Qt.Key_F2,
        )
    drain()
    assert p.delegate.active_editor() is not None, p.last_error
    return index, p.delegate.active_editor()


def test_profile_defaults_headers_and_outer_sizing(panel):
    p, _ = panel
    assert p.values() == defaults(p.official)
    assert p.model.rowCount() == 4 and p.model.columnCount() == 2
    labels = tuple(p.model.headerData(c, QtCore.Qt.Horizontal) for c in range(2))
    assert labels == ((1, 2) if p.official else ("Factor A", "Factor B"))
    assert p.table.showGrid() and p.table.tabKeyNavigation()
    assert (
        "Spin Box Delegate" in p.windowTitle()
        if p.official
        else "Numeric cell delegate" in p.windowTitle()
    )
    if not p.official:
        assert p.size() == QtCore.QSize(640, 460)
    assert p.snapshot is not None and len(p.snapshot.rows) == 6
    assert "532.5" in p.report.toPlainText()


@pytest.mark.parametrize("row,column", [(r, c) for r in range(4) for c in range(2)])
@pytest.mark.parametrize(
    "event",
    [
        "mouse-doubleclick-open",
        "keyboard-edit-trigger-open",
        "mouse-spin-up",
        "mouse-spin-down",
        "manual-text-return",
        "manual-text-tab",
        "manual-text-backtab",
        "manual-text-focus-out",
        "manual-text-cancel",
        "resize-scroll-reopen-geometry",
    ],
)
def test_all_cells_inherited_events_and_four_delegate_virtuals(
    panel, row, column, event
):
    p, _ = panel
    index, editor = open_cell(
        p, row, column, "mouse" if event == "mouse-doubleclick-open" else "keyboard"
    )
    old = int(p.model.data(index, QtCore.Qt.EditRole))
    assert editor.parent() == p.table.viewport()
    assert editor.minimum() == 0 and editor.maximum() == 100 and editor.value() == old
    assert editor.hasFrame() is (not p.official)
    assert editor.singleStep() == 1 and editor.displayIntegerBase() == 10
    assert not editor.wrapping() and editor.prefix() == editor.suffix() == ""
    assert (
        editor.keyboardTracking()
        and editor.correctionMode() == GUI.QAbstractSpinBox.CorrectToPreviousValue
    )
    assert editor.geometry() == p.table.visualRect(index)
    expected = old
    if event.startswith("mouse-spin"):
        option = GUI.QStyleOptionSpinBox()
        editor.initStyleOption(option)
        control = (
            GUI.QStyle.SC_SpinBoxUp
            if event.endswith("up")
            else GUI.QStyle.SC_SpinBoxDown
        )
        rect = editor.style().subControlRect(
            GUI.QStyle.CC_SpinBox, option, control, editor
        )
        QTest.mouseClick(editor, QtCore.Qt.LeftButton, pos=rect.center())
        expected = old + (1 if event.endswith("up") else -1)
        QTest.keyClick(editor, QtCore.Qt.Key_Return)
    elif event.startswith("manual"):
        editor.lineEdit().setText("37")
        key = {
            "manual-text-return": QtCore.Qt.Key_Return,
            "manual-text-tab": QtCore.Qt.Key_Tab,
            "manual-text-backtab": QtCore.Qt.Key_Backtab,
            "manual-text-cancel": QtCore.Qt.Key_Escape,
        }.get(event)
        if key:
            QTest.keyClick(editor, key)
        else:
            p.report.setFocus()
        expected = old if event.endswith("cancel") else 37
    elif event.startswith("resize"):
        p.table.setColumnWidth(column, 220)
        p.resize(720, 500)
        drain()
        assert editor.geometry() == p.table.visualRect(index)
        QTest.keyClick(editor, QtCore.Qt.Key_Escape)
        drain()
        _, editor = open_cell(p, row, column)
        assert editor.geometry() == p.table.visualRect(index)
        QTest.keyClick(editor, QtCore.Qt.Key_Escape)
    else:
        QTest.keyClick(editor, QtCore.Qt.Key_Escape)
    drain()
    assert int(p.model.data(index, QtCore.Qt.EditRole)) == expected
    assert {"createEditor", "setEditorData", "updateEditorGeometry"} <= set(
        p.delegate.observed
    )
    if expected != old:
        assert "setModelData" in p.delegate.observed
    assert not p.last_error


def test_refresh_commit_atomic_failure_reset_exact_types_and_close(panel):
    p, state = panel
    old = p.snapshot
    _, editor = open_cell(p, 3, 1)
    editor.lineEdit().setText("100")
    p.refresh()
    drain()
    assert p.values()[3][1] == 100 and state.calls == 2
    values = p.values()
    report = p.report.toPlainText()
    state.fail = True
    p.refresh()
    assert (
        p.snapshot is not None
        and p.values() == values
        and p.report.toPlainText() == report
    )
    assert "stale" in p.status.text().lower() and "source changed" in p.status.text()
    p.reset()
    drain()
    assert p.values() == defaults(p.official) and state.calls == 3
    assert p.snapshot == old
    _, editor = open_cell(p, 0, 0)
    editor.lineEdit().setText("99")
    assert p.close()
    drain()
    assert p.closed and not p.delegate.records


@pytest.mark.parametrize("requirement", [f"F{n:02}" for n in range(1, 17)])
def test_workflow_requirement_rehearsal(panel, requirement, monkeypatch):
    p, state = panel
    before = p.values()
    snapshot = p.snapshot
    if requirement in {"F01", "F08"}:
        state.fail = True
        p.snapshot = None if requirement == "F01" else snapshot
        p.refresh()
        _, editor = open_cell(p, 1, 1)
        editor.lineEdit().setText("9")
        QTest.keyClick(editor, QtCore.Qt.Key_Return)
        drain()
        assert p.values()[1][1] == 9 and "source changed" in p.last_error
    elif requirement in {"F02", "F03", "F06"}:
        for r, c, n in ((0, 0, 0), (1, 0, 100), (1, 1, 100)):
            _, editor = open_cell(p, r, c)
            editor.lineEdit().setText(str(n))
            QTest.keyClick(editor, QtCore.Qt.Key_Return)
            drain()
        text = p.report.toPlainText()
        assert "Increments: 0, 10000, 18, 32" in text and "10500.5" in text
    elif requirement in {"F04", "F05", "F07", "F15"}:
        assert len(snapshot.rows) == 6 and p.report.toPlainText().count("A.alt") == 6
        assert (
            "Regular" in p.report.toPlainText() and "glyph 2" in p.report.toPlainText()
        )
        assert p.report.isReadOnly() and all(
            row.width == 500.5 for row in snapshot.rows
        )
    elif requirement == "F09":
        index, editor = open_cell(p, 2, 0)
        editor.lineEdit().setText("17")
        p.refresh()
        drain()
        assert (
            p.table.currentIndex() == index
            and p.values()[2][0] == 17
            and state.calls == 2
        )
    elif requirement in {"F10", "F11"}:
        report = p.report.toPlainText()

        def reject():
            raise TimeoutError("selection drift/deadline: no partial report")

        p.capture = reject
        p.refresh()
        assert (
            p.snapshot is snapshot
            and p.values() == before
            and p.report.toPlainText() == report
        )
    elif requirement == "F12":
        report = p.report.toPlainText()
        _, editor = open_cell(p, 0, 0)
        editor.lineEdit().setText("99")
        assert p.report.toPlainText() == report
        QTest.keyClick(editor, QtCore.Qt.Key_Escape)
        drain()
        assert p.values() == before and p.report.toPlainText() == report
    elif requirement == "F13":
        _, editor = open_cell(p, 0, 0)
        editor.lineEdit().setText("")
        p.refresh()
        assert (
            state.calls == 1
            and p.delegate.active_editor() is editor
            and p.values() == before
        )
        editor.lineEdit().setText("41")
        p.refresh()
        drain()
        assert p.values()[0][0] == 41 and state.calls == 2
    elif requirement == "F14":
        _, editor = open_cell(p, 0, 0)
        editor.lineEdit().setText("99")
        QTest.keyClick(editor, QtCore.Qt.Key_Return)
        drain()
        p.reset()
        drain()
        assert p.values() == before and p.snapshot is snapshot and state.calls == 1
        assert all(
            type(a) is type(b) for x, y in zip(p.values(), before) for a, b in zip(x, y)
        )
    else:
        # Rehearsal only: this proves the local injected capture has no writer.
        # Complete native font/getter/cache/save/reopen preservation is pending.
        p.refresh()
        p.reset()
        drain()
        assert p.snapshot == snapshot and p.values() == before and state.calls == 2


@pytest.mark.parametrize("requirement", [f"L{n:02}" for n in range(1, 13)])
def test_lifecycle_requirement_rehearsal(panel, requirement, monkeypatch):
    p, _ = panel
    if requirement in {"L01", "L02", "L03"}:
        if requirement != "L01":
            _, editor = open_cell(p, 0, 0)
            editor.lineEdit().setText("91")
            if requirement == "L03":
                QTest.keyClick(editor, QtCore.Qt.Key_Return)
        assert p.close()
        drain()
        assert p.closed and not p.delegate.active and not p.delegate.records
        assert p.dispose(destroyed=True)
    elif requirement == "L04":
        parent = GUI.QWidget()
        child = type(p)(parent, lambda: p.snapshot, official=p.official)
        child.show()
        drain()
        open_cell(child, 0, 0)
        parent.deleteLater()
        drain()
        assert child.dead and child.closed and not child.delegate.records
    elif requirement == "L05":
        _, first = open_cell(p, 0, 0)
        QTest.keyClick(first, QtCore.Qt.Key_Escape)
        drain()
        assert id(first) not in p.delegate.records
        _, second = open_cell(p, 0, 0)
        assert second is not first
    elif requirement == "L06":
        other = type(p)(None, lambda: p.snapshot, official=not p.official)
        other.show()
        drain()
        assert other.model is not p.model and other.delegate is not p.delegate
        _, editor = open_cell(other, 1, 1)
        editor.lineEdit().setText("75")
        QTest.keyClick(editor, QtCore.Qt.Key_Return)
        drain()
        assert other.values()[1][1] == 75 and int(p.values()[1][1]) == 4
        assert other.close()
        drain()
    elif requirement == "L07":
        import fontlabapp.metrics.worksheet.ui as module

        original = module.build

        def fail(owner, core, gui):
            original(owner, core, gui)
            raise ValueError("injected completed construction failure")

        monkeypatch.setattr(module, "build", fail)
        with pytest.raises(ValueError):
            type(p)(None, lambda: p.snapshot, official=p.official)
        drain()
    elif requirement in {"L08", "L09"}:

        class FaultSignal:
            def __init__(self, signal):
                self.signal, self.fail = signal, True

            def disconnect(self, slot):
                if self.fail:
                    return False
                return self.signal.disconnect(slot)

        signal, slot, retry = p.scope.records[0]
        proxy = FaultSignal(signal)
        p.scope.records[0] = (proxy, slot, retry)
        assert p.close() is False and p.scope.records and not p.scope.dead
        assert any(item[0] is proxy for item in p.scope.records)
        proxy.fail = False
        assert p.close()
        drain()
        assert p.scope.dead
    elif requirement == "L10":
        index, editor = open_cell(p, 0, 0)
        old = p.values()
        foreign = GUI.QStandardItemModel(4, 2)
        assert p.delegate.setModelData(editor, foreign, foreign.index(0, 0)) is None
        assert p.values() == old and "Foreign" in p.last_error
        assert p.delegate.setEditorData(GUI.QSpinBox(), index) is None
        assert p.values() == old
    elif requirement == "L11":
        index, editor = open_cell(p, 0, 0)
        old = p.values()
        p.delegate.writing = True
        assert p.delegate.setModelData(editor, p.model, index) is None
        p.delegate.writing = False
        p.busy = True
        p.refresh()
        p.reset()
        p.changed()
        p.busy = False
        assert p.values() == old
        assert p.dispose()
        assert p.delegate.setModelData(editor, p.model, index) is None
    else:
        # Local application ownership is external to production code. No timers,
        # threads, clipboard, Output, settings or source loader are constructed.
        assert not hasattr(p, "timer") and APP is QtWidgets.QApplication.instance()
        _, editor = open_cell(p, 0, 0)
        QTest.keyClick(editor, QtCore.Qt.Key_Escape)
        drain()
        assert not p.delegate.records


@pytest.mark.parametrize("row,column", [(r, c) for r in range(4) for c in range(2)])
@pytest.mark.parametrize(
    "text", ["0", "100", "-1", "101", "", "alphabetic", "1.5", "9" * 40]
)
def test_every_cell_native_validation_and_correction(panel, row, column, text):
    p, _ = panel
    index, editor = open_cell(p, row, column)
    old = int(p.model.data(index, QtCore.Qt.EditRole))
    control = GUI.QSpinBox()
    control.setRange(0, 100)
    control.setValue(old)
    editor.lineEdit().setText(text)
    control.lineEdit().setText(text)
    control.interpretText()
    expected = control.value()
    QTest.keyClick(editor, QtCore.Qt.Key_Return)
    drain()
    assert p.model.data(index, QtCore.Qt.EditRole) == expected
    assert type(p.model.data(index, QtCore.Qt.EditRole)) is int
    control.deleteLater()
    drain()


@pytest.mark.parametrize("row,column", [(r, c) for r in range(4) for c in range(2)])
def test_every_cell_wheel_modifier_and_arrow_stepping_uses_platform_style(
    panel, row, column
):
    p, _ = panel
    index, editor = open_cell(p, row, column)
    control = GUI.QSpinBox()
    control.setRange(0, 100)
    control.setValue(editor.value())
    QTest.keyClick(editor, QtCore.Qt.Key_Up, QtCore.Qt.ControlModifier)
    QTest.keyClick(control, QtCore.Qt.Key_Up, QtCore.Qt.ControlModifier)
    assert editor.value() == control.value()
    # Real wheel events go through the native spinbox event dispatcher.
    for spin in (editor, control):
        point = QtCore.QPointF(spin.rect().center())
        event = QtGui.QWheelEvent(
            point,
            point,
            QtCore.QPoint(),
            QtCore.QPoint(0, 120),
            QtCore.Qt.NoButton,
            QtCore.Qt.NoModifier,
            QtCore.Qt.NoScrollPhase,
            False,
        )
        APP.sendEvent(spin, event)
    assert editor.value() == control.value()
    QTest.keyClick(editor, QtCore.Qt.Key_Down)
    QTest.keyClick(control, QtCore.Qt.Key_Down)
    expected = control.value()
    QTest.keyClick(editor, QtCore.Qt.Key_Return)
    drain()
    assert p.model.data(index, QtCore.Qt.EditRole) == expected
    control.deleteLater()
    drain()
