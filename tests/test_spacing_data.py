# this_file: tests/test_spacing_data.py
"""Immutable worksheet values and complete stable selected-layer capture."""

from types import SimpleNamespace as NS

import pytest

from fontlabapp.metrics.worksheet.data import (
    Baseline,
    Snapshot,
    defaults,
    increments,
    render,
)
from fontlabapp.metrics.worksheet import capture as native


def test_exact_default_types_products_and_full_fractional_report():
    assert defaults(False) == (("1", "2"), ("2", "4"), ("3", "6"), ("4", "8"))
    assert defaults(True) == ((1, 2), (2, 4), (3, 6), (4, 8))
    assert increments(defaults(False)) == (2, 8, 18, 32)
    assert increments(((0, 100), (100, 100), (100, 0), (1, 1))) == (0, 10000, 0, 1)
    rows = tuple(
        Baseline(8, 3, i, "A.alt", "Regular", width)
        for i, width in enumerate((500.5, 0.0, 100.0, 200.0, 300.0))
    )
    report = render(Snapshot((8, "Regular"), rows), defaults(True))
    assert all(str(x) in report for x in (502.5, 508.5, 518.5, 532.5))
    assert report.count("A.alt") == 5 and "Regular" in report
    assert "not applied" in render(None, defaults(False))


@pytest.mark.parametrize(
    "bad",
    [
        (),
        ((1, 2),),
        ((1, 2, 3),) * 4,
        ((True, 2),) * 4,
        ((-1, 2),) * 4,
        ((101, 2),) * 4,
        ((1.5, 2),) * 4,
        (("bad", 2),) * 4,
    ],
)
def test_factors_refuse_noncanonical_shapes_and_values(bad):
    with pytest.raises((TypeError, ValueError)):
        increments(bad)


@pytest.mark.parametrize("width", [float("nan"), float("inf"), -float("inf")])
def test_baseline_rejects_nonfinite_width(width):
    with pytest.raises(ValueError):
        Baseline(1, 2, 3, "A", "Regular", width)


def source(width=500.5):
    layer = NS(id=3, name="Regular", advanceWidth=width, isNull=False)
    glyph = NS(id=2, name="A", isNull=False, package=NS(id=1))
    occurrence = NS(
        glyph=glyph,
        layer=layer,
        glyph_id=2,
        layer_id=3,
        glyph_name="A",
        layer_name="Regular",
        package_id=1,
    )
    return NS(context=(1, "Regular"), occurrences=(occurrence,) * 5)


def test_capture_keeps_every_occurrence_and_one_shared_deadline(monkeypatch):
    selected = source()
    limits = []
    monkeypatch.setattr(
        native.selection,
        "capture",
        lambda deadline: (limits.append(deadline), selected)[1],
    )
    monkeypatch.setattr(
        native.selection,
        "document_context",
        lambda deadline: (limits.append(deadline), selected.context)[1],
    )
    report = native.capture()
    assert len(report.rows) == 5 and all(r.width == 500.5 for r in report.rows)
    assert len(set(limits)) == 1 and len(limits) == 4


@pytest.mark.parametrize(
    "fault", ["empty", "width", "identity", "context", "selection", "deadline"]
)
def test_capture_refuses_whole_snapshot_on_any_drift(monkeypatch, fault):
    selected = source()
    calls = []

    def capture(deadline):
        calls.append(deadline)
        if fault == "empty":
            return NS(context=selected.context, occurrences=())
        if len(calls) == 2:
            if fault == "width":
                selected.occurrences[0].layer.advanceWidth += 1
            if fault == "identity":
                selected.occurrences[0].glyph.id += 1
            if fault == "selection":
                return NS(context=selected.context, occurrences=())
        return selected

    monkeypatch.setattr(native.selection, "capture", capture)
    monkeypatch.setattr(
        native.selection,
        "document_context",
        lambda deadline: (9,) if fault == "context" else selected.context,
    )
    if fault == "deadline":
        monkeypatch.setattr(native, "monotonic", iter((0.0, 4.0)).__next__)
    with pytest.raises((ValueError, TimeoutError)):
        native.capture()


@pytest.mark.parametrize("expiry_call", [2, 3])
def test_capture_budget_covers_final_context_and_plain_fact_construction(
    monkeypatch, expiry_call
):
    from time import monotonic

    now = monotonic()
    calls = []
    selected = source()
    monkeypatch.setattr(native.selection, "capture", lambda deadline: selected)
    monkeypatch.setattr(
        native.selection, "document_context", lambda deadline: selected.context
    )

    def clock():
        calls.append(1)
        return now + 3 if len(calls) == expiry_call else now

    monkeypatch.setattr(native, "monotonic", clock)
    with pytest.raises(TimeoutError):
        native.capture()
