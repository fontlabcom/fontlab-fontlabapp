# this_file: tests/test_case_coverage_controller.py
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from fontlabapp.glyphs.case_coverage.model import Options
from fontlabapp.glyphs.case_coverage.capture import Snapshot, FontReport
import fontlabapp.glyphs.case_coverage.controller as controller


def snap(clear):
    return Snapshot(
        7,
        (
            FontReport(
                7,
                70,
                "Owned",
                "Regular",
                dict(all_clear=clear, rows=[], proof=[] if clear else ["A"]),
            ),
        ),
    )


def test_complete_capture_precedes_proof_and_allclear_opens_nothing(monkeypatch):
    events = []
    snapshot = snap(False)
    monkeypatch.setattr(
        controller, "read", lambda *args, **kw: events.append("read") or snapshot
    )
    monkeypatch.setattr(
        controller, "validate", lambda *args, **kw: events.append("validate")
    )
    proof = lambda *args, **kw: events.append("proof")
    assert (
        controller.run(Options(), Mock(), Mock(), proof=proof, clock=lambda: 0)
        == snapshot
    )
    assert events == ["read", "validate", "proof"]
    snapshot = snap(True)
    events.clear()
    controller.run(Options(), Mock(), Mock(), proof=proof, clock=lambda: 0)
    assert events == ["read", "validate"]
    with pytest.raises(InterruptedError):
        controller.run(Options(), None, None, cancelled=lambda: True)


def test_detailed_snapshot_and_lazy_launch(monkeypatch):
    report = Mock()
    monkeypatch.setattr(controller, "show_report", report)
    controller.details(snap(True))
    assert report.call_args.kwargs["title"] == "Case Coverage — detailed report"
    assert report.call_args.kwargs["key"] == "case_coverage_details"
    assert report.call_args.args[0]["fonts"][0]["identity"] == 7
    kind = Mock()
    factory = Mock(return_value=kind)
    monkeypatch.setattr(controller, "panel_type", factory)
    native = NS(QtCore=object(), QtGui=object())
    monkeypatch.setattr(controller, "_native", lambda name: native)
    display = Mock(side_effect=lambda build, key: build("parent"))
    monkeypatch.setattr(controller, "show_script_dialog", display)
    monkeypatch.setattr(controller, "current_package", lambda: object())
    metadata, preferred = Mock(), Mock()
    controller.show(metadata, preferred, settings="isolated")
    assert factory.call_args.args == (native.QtCore, native.QtGui)
    assert kind.call_args.kwargs["settings"] == "isolated"
    assert kind.call_args.args[2]()
    monkeypatch.setattr(controller, "run", lambda *a, **kw: "ran")
    assert kind.call_args.args[1](Options(), lambda: False, {}) == "ran"


def test_proof_failure_keeps_complete_analysis_for_later_detailed_report(monkeypatch):
    from fontlabapp.glyphs.case_coverage.targets import (
        ProofFailure,
        TargetChoiceRequired,
    )

    snapshot = snap(False)
    monkeypatch.setattr(controller, "read", lambda *a, **kw: snapshot)
    monkeypatch.setattr(controller, "validate", lambda *a, **kw: None)

    def fail(*a, **kw):
        raise ValueError("native model binding unavailable")

    with pytest.raises(ProofFailure) as caught:
        controller.run(Options(), Mock(), Mock(), proof=fail, clock=lambda: 0)
    assert caught.value.snapshot is snapshot
    assert "Analysis is complete" in str(caught.value)

    def choose(*a, **kw):
        raise TargetChoiceRequired({})

    with pytest.raises(TargetChoiceRequired) as caught:
        controller.run(Options(), Mock(), Mock(), proof=choose, clock=lambda: 0)
    assert caught.value.snapshot is snapshot
