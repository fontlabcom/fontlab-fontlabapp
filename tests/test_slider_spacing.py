# this_file: tests/test_slider_spacing.py
"""Immutable geometric spacing candidates and complete native capture fences."""

from dataclasses import FrozenInstanceError
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from fontlabapp.metrics.offset.model import Row, Snapshot, preview


def test_local_offset_keeps_advance_and_empty_margin_unknown():
    row = Row(1, 2, 3, "A", "Regular", 500.5, -10.25, 60.75)
    facts = Snapshot((1, "Regular"), (row, Row(1, 4, 3, "space", "R", 250, None, None)))
    assert preview(facts, 5) == (
        ("A", "Regular", -5.25, 55.75, 500.5),
        ("space", "R", None, None, 250),
    )
    assert row.left == -10.25
    with pytest.raises(FrozenInstanceError):
        row.left = 1


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_facts_refuse(bad):
    with pytest.raises(ValueError):
        preview(Snapshot((), (Row(1, 2, 3, "A", "R", bad, 0, 0),)), 5)


def setup(monkeypatch):
    import fontlabapp.masters.layers.selection as selection
    import fontlabapp.metrics.offset.capture as capture

    package = NS(id=7)
    glyph = NS(id=11, name="A", package=package, isNull=False)
    layer = NS(
        id=12,
        name="Regular",
        isNull=False,
        advanceWidth=500.5,
        shapesCount=1,
        boundingBox=NS(left=lambda: -10.25, right=lambda: 439.75, isNull=lambda: False),
    )
    occurrence = selection.LayerOccurrence(package, glyph, layer, 0, 0)
    selected = selection.LayerSelection(
        (7, "Regular", "font", 5), (occurrence, occurrence)
    )
    monkeypatch.setattr(selection, "capture", Mock(return_value=selected))
    monkeypatch.setattr(
        selection, "document_context", Mock(return_value=selected.context)
    )
    return capture, selection, selected, layer


def test_capture_keeps_repeated_occurrences_and_scalar_margins(monkeypatch):
    c, s, _selected, layer = setup(monkeypatch)
    result = c.capture()
    assert len(result.rows) == 2 and result.rows[0] == result.rows[1]
    assert result.rows[0].left == -10.25 and result.rows[0].right == 60.75
    assert s.capture.call_count == 3
    layer.boundingBox.isNull = lambda: True
    layer.boundingBox.left = Mock(
        side_effect=AssertionError("Null bounds must not be read")
    )
    layer.boundingBox.right = Mock(
        side_effect=AssertionError("Null bounds must not be read")
    )
    assert c.capture().rows[0].left is None
    layer.shapesCount = 0
    assert c.capture().rows[0].left is None


@pytest.mark.parametrize(
    "fault", ["empty", "identity", "context", "values", "selection", "time", "thread"]
)
def test_capture_refuses_complete_result_on_drift(monkeypatch, fault):
    c, s, selected, layer = setup(monkeypatch)
    if fault == "empty":
        s.capture.return_value = NS(occurrences=())
    if fault == "identity":
        layer.id = 99
    if fault == "context":
        s.document_context.return_value = (9,)
    if fault == "values":
        monkeypatch.setattr(c, "read", Mock(side_effect=[(1,), (2,)]))
    if fault == "selection":
        s.capture.side_effect = [
            selected,
            NS(occurrences=selected.occurrences),
            selected,
        ]
    if fault == "time":
        monkeypatch.setattr(c, "monotonic", Mock(side_effect=[0, 3]))
    if fault == "thread":
        monkeypatch.setattr(c, "current_thread", lambda: None)
    with pytest.raises((ValueError, TimeoutError, RuntimeError)):
        c.capture()


def test_capture_own_deadline_refuses(monkeypatch):
    import fontlabapp.metrics.offset.capture as module

    monkeypatch.setattr(module, "monotonic", lambda: 2)
    with pytest.raises(TimeoutError):
        module.check(1)
