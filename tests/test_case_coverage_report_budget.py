# this_file: tests/test_case_coverage_report_budget.py
import json
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from fontlabapp.proof.reports.model import format_report, show_report


def test_bounded_shared_serialization_keeps_every_unicode_row_and_default_bytes():
    data = {"rows": [{"glyph": "Ż.alt", "values": list(range(100))} for _ in range(40)]}
    assert format_report(data, deadline=10, clock=lambda: 0) == json.dumps(
        data, ensure_ascii=False, indent=2, allow_nan=False
    )
    calls = 0

    def clock():
        nonlocal calls
        calls += 1
        return 0 if calls < 100 else 10

    with pytest.raises(TimeoutError):
        format_report(data, deadline=5, clock=clock)
    assert calls == 100
    with pytest.raises(InterruptedError):
        format_report(data, cancelled=lambda: True)
    with pytest.raises(ValueError):
        format_report({"not_json": float("nan")})


def test_report_deadline_before_and_after_native_show_never_counts_overrun_as_success(
    monkeypatch,
):
    show = Mock(return_value="owned")
    monkeypatch.setitem(sys.modules, "fontlabapp.proof.reports.ui", NS(show=show))
    assert show_report({"complete": True}, deadline=2, clock=lambda: 0) == "owned"
    # Native view call may overrun, but an immediate post-call check must fail.
    now = [0]

    def native(*args):
        now[0] = 3
        return "owned complete view"

    show.side_effect = native
    with pytest.raises(TimeoutError):
        show_report({}, deadline=2, clock=lambda: now[0])
    assert show.call_count == 2
