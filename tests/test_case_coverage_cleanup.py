# this_file: tests/test_case_coverage_cleanup.py
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from fontlabapp.glyphs.case_coverage.cleanup import (
    restore,
    CleanupIncomplete,
    PENDING,
    recover,
)


def test_expired_cleanup_stops_before_any_setter_and_retains_exact_pending_states():
    shape = NS(active=True)
    tool = Mock()
    workspace = Mock()
    check = Mock(side_effect=TimeoutError("deadline"))
    try:
        with pytest.raises(CleanupIncomplete) as caught:
            restore({4: (shape, False)}, workspace, None, NS(fg_id=10), tool, check)
        assert tool.call.call_count == 0 and workspace.setActiveCanvas.call_count == 0
        assert shape.active is True and caught.value.pending_states[4][0] is shape
        assert PENDING[-1] is caught.value
    finally:
        PENDING.clear()


def test_success_recovery_is_bounded_and_failed_native_setters_remain_owned():
    shape = NS(active=True)
    tool = Mock()
    workspace = NS(activeFontPanel=None)
    try:
        with pytest.raises(CleanupIncomplete):
            restore(
                {4: (shape, False)},
                workspace,
                None,
                NS(fg_id=10),
                tool,
                Mock(side_effect=TimeoutError()),
            )
        recover(deadline=float("inf"))
        assert not PENDING and not shape.active
        tool.call.side_effect = RuntimeError("context restoration")
        with pytest.raises(CleanupIncomplete) as caught:
            restore(
                {4: (shape, False)}, workspace, None, NS(fg_id=10), tool, lambda: None
            )
        assert caught.value.context_pending and not shape.active
    finally:
        PENDING.clear()
