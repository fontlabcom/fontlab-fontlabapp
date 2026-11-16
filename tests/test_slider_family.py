# this_file: tests/test_slider_family.py
"""Actual Qt5/6 controls: both originals, native input, local results and lifetime."""

import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from fontlabapp.metrics.offset.ui import panel_type
from fontlabapp.metrics.offset.model import Row, Snapshot
from test_spacing_worksheet import GUI, QtCore, QTest, drain, valid


def facts():
    return Snapshot(
        (7, "R"),
        (
            Row(7, 2, 3, "A", "R", 500.5, -10.25, 60.75),
            Row(7, 4, 5, "space", "R", 250, None, None),
        ),
    )


@pytest.fixture(params=[2, 3])
def panel(request):
    state = NS(capture=Mock(return_value=facts()))
    p = panel_type(QtCore, GUI)(None, state.capture, request.param)
    p.show()
    drain()
    yield p, state
    if valid(p):
        p.close()
    drain()


def controls(p):
    return tuple(c for group in p.groups for c in group)


def test_every_original_control_initial_contract(panel):
    p, _ = panel
    assert len(p.groups) == (1 if p.part == 2 else 2)
    for key, initial in (("minimum", 0), ("maximum", 20), ("value", 5)):
        c = p.controls[key]
        assert (c.minimum(), c.maximum(), c.singleStep(), c.value()) == (
            -100,
            100,
            1,
            initial,
        )
    for index, group in enumerate(p.groups):
        assert group[0].orientation() == (
            QtCore.Qt.Horizontal if index == 0 else QtCore.Qt.Vertical
        )
        assert group[1].orientation() == group[0].orientation()
        for c in group:
            assert (c.minimum(), c.maximum(), c.value()) == (0, 20, 5)
        assert group[0].tickInterval() == (10 if p.part == 3 else 0)
        assert group[0].tickPosition() == (
            GUI.QSlider.TicksBothSides if p.part == 3 else GUI.QSlider.NoTicks
        )
        if p.part == 3:
            assert all(c.focusPolicy() == QtCore.Qt.StrongFocus for c in group)
    assert all(
        g[1].invertedControls()
        and not g[0].invertedControls()
        and not g[2].invertedControls()
        for g in p.groups
    )
    assert p.result[0] == ("A", "R", -5.25, 55.75, 500.5)
    assert "margins unavailable" in p.output.toPlainText()


def test_all_controls_cyclic_feedback_and_local_preview(panel):
    p, state = panel
    for n, c in enumerate(controls(p), 7):
        c.setValue(n)
        assert all(other.value() == n for other in controls(p))
        assert p.controls["value"].value() == n
        assert p.result[0][2:4] == (-10.25 + n, 60.75 - n)
    assert state.capture.call_count == 1
    assert p.facts == facts()


def test_distinct_orientation_signal_contract(panel):
    p, _ = panel
    combo = p.controls["orientation"]
    combo.setCurrentIndex(1)
    if p.part == 2:
        assert all(c.orientation() == QtCore.Qt.Vertical for c in p.groups[0][:2])
        combo.setCurrentIndex(0)
        assert p.groups[0][0].orientation() == QtCore.Qt.Horizontal
    else:
        assert p.stack.currentIndex() == 0
        combo.activated.emit(1)
        assert p.stack.currentIndex() == 1
        assert p.groups[0][0].orientation() == QtCore.Qt.Horizontal
        assert p.groups[1][0].orientation() == QtCore.Qt.Vertical


def test_range_editor_contradiction_and_native_clamp(panel):
    p, _ = panel
    p.controls["minimum"].setValue(40)
    assert p.controls["maximum"].value() == (40 if p.part == 2 else 20)
    assert all(
        (c.minimum(), c.maximum(), c.value()) == (40, 40, 40) for c in controls(p)
    )
    p.controls["maximum"].setValue(-20)
    if p.part == 2:
        assert p.controls["maximum"].value() == 40
        assert all(c.value() == 40 for c in controls(p))
    else:
        assert p.controls["minimum"].value() == 40
        assert p.controls["maximum"].value() == -20
        assert all(
            (c.minimum(), c.maximum(), c.value()) == (-20, -20, -20)
            for c in controls(p)
        )
    p.controls["minimum"].setValue(-50)
    p.controls["maximum"].setValue(50)
    p.controls["value"].setValue(100)
    assert all(c.value() == 50 for c in controls(p))
    p.controls["value"].setValue(99)
    assert p.controls["value"].value() == (50 if p.part == 2 else 99)
    assert p.result[0][2] == 39.75  # Actual clamped slider, not stale number editor.


@pytest.mark.parametrize("inverted", [False, True])
def test_keyboard_wheel_and_native_steps(panel, inverted):
    p, _ = panel
    p.controls["keys"].setChecked(not inverted)
    p.controls["keys"].setChecked(inverted)
    p.controls["appearance"].setChecked(True)
    for c in controls(p):
        assert c.invertedControls() == inverted and c.invertedAppearance()
        c.setValue(10)
        QTest.keyClick(c, QtCore.Qt.Key_Right)
        assert c.value() == (9 if inverted else 11)
        c.setValue(10)
        c.triggerAction(GUI.QAbstractSlider.SliderSingleStepAdd)
        assert c.value() == 11
        c.triggerAction(GUI.QAbstractSlider.SliderToMinimum)
        assert c.value() == 0
        c.triggerAction(GUI.QAbstractSlider.SliderToMaximum)
        assert c.value() == 20
        c.setValue(10)
        wheel = GUI.QWheelEvent(
            QtCore.QPointF(10, 10),
            QtCore.QPointF(10, 10),
            QtCore.QPoint(0, 0),
            QtCore.QPoint(0, 120),
            QtCore.Qt.NoButton,
            QtCore.Qt.NoModifier,
            QtCore.Qt.NoScrollPhase,
            False,
        )
        GUI.QApplication.sendEvent(c, wheel)
        assert (c.value() < 10) if inverted else (c.value() > 10)
        c.setValue(10)
        QTest.keyClick(c, QtCore.Qt.Key_Home)
        assert c.value() == 0
        QTest.keyClick(c, QtCore.Qt.Key_End)
        assert c.value() == 20
        c.setValue(10)
        QTest.keyClick(c, QtCore.Qt.Key_PageUp)
        assert (c.value() < 10) if inverted else (c.value() > 10)


def test_refresh_replaces_all_facts_preserves_controls_and_clears_stale(panel):
    p, state = panel
    p.controls["value"].setValue(12)
    state.capture.side_effect = ValueError("selection changed")
    p.refresh()
    assert p.facts is None and p.result is None and "selection changed" in p.last_error
    assert p.controls["value"].value() == 12 and "No captured" in p.output.toPlainText()
    state.capture.side_effect = None
    p.refresh()
    assert p.result[0][2] == 1.75
    p.facts = Snapshot((), (Row(1, 2, 3, "bad", "R", float("nan"), 0, 0),))
    p.changed()
    assert p.result is None and p.output.toPlainText() == ""


@pytest.mark.parametrize("terminal", ["close", "escape", "parent"])
def test_termination_and_late_callbacks_are_inert(panel, terminal):
    p, state = panel
    slots = [slot for _, slot, _ in p.scope.records]
    sys.__dict__.setdefault("_fontlab_samples", {})[p.key] = p
    dead = []
    p.destroyed.connect(lambda *args: dead.append(True))
    if terminal == "parent":
        parent = GUI.QWidget()
        p.setParent(parent)
        parent.deleteLater()
    elif terminal == "escape":
        QTest.keyClick(p, QtCore.Qt.Key_Escape)
    else:
        assert p.close()
    drain()
    assert dead == [True] and p.closed and p.dead
    assert not p.scope.records and not p.terminal.records
    assert p.key not in sys._fontlab_samples
    calls = state.capture.call_count
    for slot in slots:
        slot(1)
    p.refresh()
    p.changed()
    assert state.capture.call_count == calls and p.facts is None


def test_bad_profile_and_lazy_launch(monkeypatch):
    with pytest.raises(ValueError):
        panel_type(QtCore, GUI)(None, facts, 9)
    import fontlabapp
    import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - lazy package native lookup
    import fontlabapp.metrics.offset.model as api

    monkeypatch.setattr(
        fontlabapp, "_native", lambda name: NS(QtCore=QtCore, QtGui=GUI)
    )
    monkeypatch.setattr(
        scripting, "show_script_dialog", lambda build, key: (key, build(None))
    )
    import fontlabapp.metrics.offset.capture as capture

    monkeypatch.setattr(capture, "capture", facts)
    for call, part in ((api.show, 2), (api.show_stacked, 3)):
        key, p = call()
        assert key == f"slider_spacing_{part}"
        p.close()
        drain()
    monkeypatch.setattr(api, "current_thread", lambda: None)
    with pytest.raises(RuntimeError):
        api.show()


def test_validation_edges_and_close_during_capture(panel):
    p, state = panel
    from fontlabapp.metrics.offset.model import preview

    for bad in (-101, 101, True, 1.5):
        with pytest.raises(ValueError):
            preview(facts(), bad)
    with pytest.raises(ValueError):
        preview(Snapshot((), (Row(1, 2, 3, "A", "R", 500, None, 4),)), 5)
    state.capture.side_effect = lambda: (p.close(), facts())[1]
    p.refresh()
    assert p.closed and p.facts is None


def test_disconnect_failure_retains_owner_for_retry(panel, monkeypatch):
    p, _ = panel
    finish = p.scope.finish
    monkeypatch.setattr(p.scope, "finish", Mock(side_effect=[False, True]))
    assert p.close() is False and valid(p) and p.closed
    monkeypatch.setattr(p.scope, "finish", finish)
    assert p.close() is True
    drain()
    assert not valid(p)


def test_close_exception_and_diagnostic_failure_contained(panel, monkeypatch):
    p, _ = panel
    original = p.dispose
    monkeypatch.setattr(p, "dispose", Mock(side_effect=ValueError("disconnect raised")))
    assert p.close() is False and "disconnect raised" in p.last_error
    monkeypatch.setattr(p, "dispose", original)
    status = p.status
    p.status = NS(setText=Mock(side_effect=RuntimeError("deleted label")))
    p.failure(ValueError("failed"))
    assert "status unavailable" in p.last_error
    p.status = status
    QTest.keyClick(p, QtCore.Qt.Key_A)


def test_partial_construction_refuses_without_leaking(monkeypatch):
    import fontlabapp.metrics.offset.ui as module

    before = []

    def broken(owner, *args):
        owner.destroyed.connect(lambda *args: before.append(True))
        raise ValueError("build failed")

    monkeypatch.setattr(module, "build", broken)
    with pytest.raises(ValueError, match="build failed"):
        module.panel_type(QtCore, GUI)(None, facts, 2)
    drain()
    assert before == [True]
