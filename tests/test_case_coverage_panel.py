# this_file: tests/test_case_coverage_panel.py
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from test_spacing_worksheet import GUI, QtCore, drain, valid
from test_case_coverage_settings import Memory
from fontlabapp.glyphs.case_coverage.model import Options
from fontlabapp.glyphs.case_coverage.capture import Snapshot, FontReport
from fontlabapp.glyphs.case_coverage.ui import panel_type


def snapshot(clear=True):
    return Snapshot(
        1,
        (
            FontReport(
                1, 2, "Owned", "Regular", dict(all_clear=clear, rows=[], proof=[])
            ),
        ),
    )


def test_controls_persistence_report_optional_details_and_close():
    settings = Memory()
    calls = []
    details = []

    def run(options, cancelled, choices):
        assert not cancelled()
        calls.append(options)
        return snapshot(len(calls) == 1)

    p = panel_type(QtCore, GUI)(
        None, run, lambda: True, details.append, settings=settings
    )
    p.show()
    drain()
    assert p.configuration() == Options()
    p.report_button.click()
    drain()
    assert "No issues" in p.status.text() and details == []
    p.controls["showMacroWindow"].click()
    p.controls["reuseTab"].click()
    p.report_button.click()
    drain()
    assert len(details) == 1 and "findings" in p.status.text()
    assert settings.data["showMacroWindow"] is True
    assert not calls[-1].reuseTab
    assert p.close()
    drain()
    assert p.closed and p.run_report is None and not p.scope.records


def test_no_font_refresh_errors_and_late_callbacks_are_fenced():
    available = Mock(return_value=False)

    def fail(*args):
        raise ValueError("stale font")

    p = panel_type(QtCore, GUI)(None, fail, available, Mock(), settings=Memory())
    assert not p.report_button.isEnabled()
    available.return_value = True
    p.refresh_button.click()
    p.report_button.click()
    drain()
    assert "stale font" in p.status.text()
    p.busy = True
    p.execute()
    p.changed()
    p.busy = False
    available.side_effect = ValueError("font unavailable")
    p.refresh_button.click()
    drain()
    assert not p.report_button.isEnabled() and "unavailable" in p.status.text()
    p.close()
    drain()
    p.execute()
    p.changed()
    p.refresh()


def test_corrupt_settings_and_failed_construction_disconnect_owned_slots():
    settings = Memory()
    settings.data["allFonts"] = "bad"
    p = panel_type(QtCore, GUI)(None, Mock(), lambda: True, Mock(), settings=settings)
    assert "boolean" in p.status.text()
    p.close()
    drain()
    gui = NS(
        **{
            name: getattr(GUI, name)
            for name in ("QDialog", "QVBoxLayout", "QLabel", "QCheckBox", "QPushButton")
        }
    )
    gui.QCheckBox = Mock(side_effect=RuntimeError("construction failure"))
    with pytest.raises(RuntimeError, match="construction"):
        panel_type(QtCore, gui)(None, Mock(), lambda: True, Mock(), settings=Memory())
    drain()


def test_ambiguous_targets_offer_all_views_and_use_explicit_selection():
    from fontlabapp.glyphs.case_coverage.targets import Target, TargetChoiceRequired

    a = Target(2, 10, 100, "Owned other font — view 10")
    b = Target(2, 11, 101, "Owned other font — view 11")
    calls = []
    details = []

    def run(options, cancelled, choices):
        calls.append(choices)
        if not choices:
            raise TargetChoiceRequired({2: (a, b)})
        return snapshot()

    p = panel_type(QtCore, GUI)(
        None, run, lambda: True, details.append, settings=Memory()
    )
    p.execute()
    assert "Choose" in p.status.text() and p.target_choices() == {}
    assert p.target_controls[0][2].count() == 3
    p.offer_targets({2: (a, b)})
    p.target_controls[0][2].setCurrentIndex(2)
    p.execute()
    assert calls[-1] == {2: (11, 101)}
    p.details_button.click()
    drain()
    assert len(details) == 1
    p.close()
    drain()
    p.details()


def test_close_disconnect_failure_is_retained_and_retried():
    p = panel_type(QtCore, GUI)(None, Mock(), lambda: True, Mock(), settings=Memory())
    real = p.scope.finish
    p.scope.finish = Mock(return_value=False)
    assert p.close() is False
    assert p.closed and "retry" in p.status.text()
    p.scope.finish = real
    assert p.close()
    drain()


def test_closed_during_capture_never_publishes_or_uses_destroyed_children():
    p = None

    def run(*args):
        p.dispose()
        return snapshot()

    p = panel_type(QtCore, GUI)(None, run, lambda: True, Mock(), settings=Memory())
    p.execute()
    assert p.report_result is None and p.closed
    assert callable(p.result), "QDialog.result is a native slot PythonQt refuses to overwrite"
    p.close()
    drain()


def test_complete_report_survives_proof_runtime_refusal():
    from fontlabapp.glyphs.case_coverage.targets import ProofFailure

    result = snapshot(False)
    details = []

    def fail(*args):
        raise ProofFailure(result, ValueError("binding unavailable"))

    p = panel_type(QtCore, GUI)(
        None, fail, lambda: True, details.append, settings=Memory()
    )
    p.execute()
    assert p.report_result is result and p.details_button.isEnabled()
    assert "Analysis is complete" in p.status.text()
    p.details_button.click()
    drain()
    assert details == [result]
    p.close()
    drain()


def test_new_failed_capture_invalidates_previous_details_instead_of_showing_stale_report():
    state = [False]

    def run(*args):
        if state[0]:
            raise ValueError("capture failed before analysis")
        return snapshot()

    p = panel_type(QtCore, GUI)(None, run, lambda: True, Mock(), settings=Memory())
    p.execute()
    assert p.report_result is not None
    state[0] = True
    p.execute()
    assert p.report_result is None and not p.details_button.isEnabled()
    assert "capture failed" in p.status.text()
    p.close()
    drain()


@pytest.mark.parametrize("kind", ["target_choice", "proof_failure"])
def test_automatic_details_when_completed_analysis_cannot_proof_then_opens_retained_report(
    kind,
):
    from fontlabapp.glyphs.case_coverage.targets import (
        ProofFailure,
        TargetChoiceRequired,
    )

    result = snapshot(False)
    details = []
    settings = Memory()
    settings.data["showMacroWindow"] = True

    def fail(options, *args):
        assert options == Options(showMacroWindow=True), (
            "Use the requested automatic-details control"
        )
        if kind == "proof_failure":
            raise ProofFailure(result, ValueError("binding unavailable"))
        error = TargetChoiceRequired({})
        error.snapshot = result
        raise error

    p = panel_type(QtCore, GUI)(
        None, fail, lambda: True, details.append, settings=settings
    )
    try:
        p.execute()
        assert p.report_result is result and p.details_button.isEnabled(), (
            "Retain the complete analysis"
        )
        assert details == [result], (
            "Automatic details must work on both completed-analysis exceptions"
        )
        assert "No issues" not in p.status.text(), "Keep proof-failure/choice feedback"
    finally:
        p.close()
        drain()


def test_automatic_details_when_new_capture_fails_then_never_reopens_stale_report():
    state = [False]
    result = snapshot(False)
    details = []
    settings = Memory()
    settings.data["showMacroWindow"] = True

    def run(*args):
        if state[0]:
            raise ValueError("new capture failed")
        return result

    p = panel_type(QtCore, GUI)(
        None, run, lambda: True, details.append, settings=settings
    )
    try:
        p.execute()
        assert details == [result], "First complete report opens once"
        state[0] = True
        p.execute()
        assert details == [result], "Failed capture cannot reopen the previous report"
        assert p.report_result is None and not p.details_button.isEnabled()
    finally:
        p.close()
        drain()
