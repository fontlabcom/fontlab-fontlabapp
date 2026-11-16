# this_file: tests/test_node_duplicator_finish.py
"""Exact partial-failure outcomes for owned recovery and history publication."""

from time import monotonic

import pytest

from test_node_duplicator_native import setup
from fontlabapp.contours.nodes.duplicator._write import stage, publish, WriteError


def prepared():
    owned, result, native, qt, notifications, contour = setup()
    staged = stage(owned, result, native, qt, monotonic() + 2)
    return owned, result, staged, native, qt, notifications, contour


@pytest.mark.parametrize("owner", ["layer", "glyph"])
def test_publish_when_history_initialization_raises_then_finalizes_without_inserting(
    owner,
):
    owned, result, staged, native, qt, notifications, contour = prepared()
    glyph, layer = owned.bound[30]

    def broken(value):
        raise RuntimeError("owned history init failure")

    (layer if owner == "layer" else glyph).checkInitHistoryState = broken
    with pytest.raises(WriteError, match="history init failure") as failed:
        publish(owned, result, staged, native, qt, monotonic() + 2)
    assert len(contour.nodes()) == 1 and len(notifications) == 1
    assert failed.value.history_finalized and failed.value.pending_nodes == ()
    assert not hasattr(glyph, "lastModified"), (
        "No insertion means no manual timestamp write"
    )


@pytest.mark.parametrize("owner", ["layer", "glyph"])
def test_publish_when_cache_rebuild_refuses_then_rolls_back_owned_nodes_and_retains_error(
    owner,
):
    owned, result, staged, native, qt, notifications, contour = prepared()
    glyph, layer = owned.bound[30]
    (layer if owner == "layer" else glyph).update = lambda: False
    with pytest.raises(WriteError, match="cache update failed") as failed:
        publish(owned, result, staged, native, qt, monotonic() + 2)
    assert len(contour.nodes()) == 1 and len(notifications) == 1
    assert failed.value.pending_nodes and failed.value.history_finalized


def test_publish_when_removal_raises_then_retains_both_errors_and_exact_owned_handles():
    owned, result, staged, native, qt, notifications, contour = prepared()
    contour.fail = True

    def broken(node):
        raise RuntimeError("owned remove failure")

    contour.removeOne = broken
    with pytest.raises(WriteError) as failed:
        publish(owned, result, staged, native, qt, monotonic() + 2)
    assert len(contour.nodes()) == 2 and len(notifications) == 1
    assert any("after attachment" in str(e) for e in failed.value.errors)
    assert any("remove failure" in str(e) for e in failed.value.errors)
    assert failed.value.pending_nodes[0][0] is contour
    assert failed.value.pending_nodes[0][1] is contour.nodes()[1]


def test_publish_when_notification_raises_then_never_claims_confirmed_history():
    owned, result, staged, native, qt, notifications, contour = prepared()

    def broken(*args):
        raise RuntimeError("owned notification failure")

    from types import SimpleNamespace

    native.flItems = lambda: SimpleNamespace(notifyChangesApplied=broken)
    with pytest.raises(WriteError, match="notification failure") as failed:
        publish(owned, result, staged, native, qt, monotonic() + 2)
    assert not failed.value.history_finalized and failed.value.pending_nodes
    assert len(contour.nodes()) == 2, (
        "A failed notification is not evidence of rollback"
    )


def test_publish_when_timestamp_setter_raises_then_reports_error_and_preserves_notification(
    monkeypatch,
):
    owned, result, staged, native, qt, notifications, contour = prepared()
    glyph = owned.bound[30][0]

    def broken(self, value):
        raise RuntimeError("owned stamp failure")

    monkeypatch.setattr(
        type(glyph), "lastModified", property(fset=broken), raising=False
    )
    with pytest.raises(WriteError, match="stamp failure") as failed:
        publish(owned, result, staged, native, qt, monotonic() + 2)
    assert len(notifications) == 1 and failed.value.history_finalized


def test_publish_when_scope_changes_after_insertion_then_refuses_unsafe_notification():
    owned, result, staged, native, qt, notifications, contour = prepared()
    from types import SimpleNamespace as NS

    workspace = NS(getActiveCanvas=lambda: None)
    native.flWorkspace = NS(instance=lambda: workspace)
    original = contour.insert

    def changed(index, node):
        original(index, node)
        workspace.getActiveCanvas = lambda: NS(isNull=False, textBlocks=lambda: [])

    contour.insert = changed
    with pytest.raises(WriteError, match="Font window") as failed:
        publish(owned, result, staged, native, qt, monotonic() + 2)
    assert not notifications and not failed.value.history_finalized
    assert failed.value.pending_nodes
