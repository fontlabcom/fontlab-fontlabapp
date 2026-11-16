# this_file: tests/test_node_duplicator_deadlines.py
"""Partial native-shaped failure retains owned recovery facts and respects budgets."""

from time import monotonic

import pytest

from test_node_duplicator_native import setup
from fontlabapp.contours.nodes.duplicator._write import stage, publish, WriteError


def test_publish_when_deadline_expires_after_attachment_then_stops_mutating_and_retains_handles():
    owned, result, native, qt, notifications, contour = setup()
    staged = stage(owned, result, native, qt, monotonic() + 2)
    clock = [0.0]
    original = contour.insert

    def expired(index, node):
        original(index, node)
        clock[0] = 10.0
        raise TimeoutError("owned attachment deadline")

    import fontlabapp.contours.nodes.duplicator._capture as capture
    from unittest.mock import patch

    contour.insert = expired
    with patch.object(capture, "monotonic", side_effect=lambda: clock[0]):
        with pytest.raises(WriteError) as failed:
            publish(owned, result, staged, native, qt, 1.0)
    assert not notifications, (
        "An expired budget must stop cleanup and finalization calls"
    )
    assert len(contour.nodes()) == 2, "Do not claim rollback after its budget expired"
    assert failed.value.pending_nodes, (
        "Retain exact owned handles for inspected recovery"
    )
    assert failed.value.history_finalized is False
    assert any(isinstance(error, TimeoutError) for error in failed.value.errors)


def test_publish_when_attachment_fails_with_budget_then_removes_only_owned_nodes_and_finalizes():
    owned, result, native, qt, notifications, contour = setup()
    staged = stage(owned, result, native, qt, monotonic() + 2)
    contour.fail = True
    with pytest.raises(WriteError) as failed:
        publish(owned, result, staged, native, qt, monotonic() + 2)
    assert len(contour.nodes()) == 1 and len(notifications) == 1
    assert failed.value.history_finalized is True
    assert failed.value.pending_nodes, (
        "Keep failure recovery identities, even after attempted rollback"
    )
