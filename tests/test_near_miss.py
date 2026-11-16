# this_file: tests/test_near_miss.py
"""Independent equations for Simon's complete strict-boundary contract."""

import math
from dataclasses import replace
from itertools import pairwise

import fontlabapp.contours.near_miss.model as n
import pytest


def row(paths=(), horizontal=(), vertical=(), metrics=(800, 700, 500, -200)):
    return n.Glyph("a", "Regular", "Regular", metrics, horizontal, vertical, paths)


def path(*points):
    return tuple(n.Node((x, y), off) for x, y, off in points)


def oracle(angle, length, horizontal, vertical):
    """Frozen mathematical contract, no source import or execution."""
    result = []
    for target in (0, 180, 90, -90):
        if angle != target and target - 2 < angle < target + 2:
            result.append(("angle", angle, target))
    for label, stems, axes in [
        ("horizontal stem", horizontal, (0, 180)),
        ("vertical stem", vertical, (90, -90)),
    ]:
        if length in stems:
            continue
        if any(axis - 2 < angle < axis + 2 for axis in axes):
            result.extend(
                (label, length, s)
                for s in stems
                if length != s and s * 0.95 < length < s * 1.05
            )
    return tuple(result)


@pytest.mark.parametrize(
    "angle",
    [
        -180,
        -179,
        -92,
        -91,
        -90,
        -89,
        -88,
        -2,
        -1,
        0,
        1,
        2,
        88,
        89,
        90,
        91,
        92,
        178,
        179,
        180,
    ],
)
@pytest.mark.parametrize("length", [0, 95, 95.001, 99, 100, 101, 104.999, 105])
def test_segment_matches_independent_original_oracle(angle, length):
    assert n.segment_findings(
        angle, length, (100, 102, 100), (100, 102, 100)
    ) == oracle(angle, length, (100, 102, 100), (100, 102, 100))


def test_exact_stem_suppresses_all_nearby_matches():
    assert n.segment_findings(0, 100, (99, 100, 101), ()) == ()
    assert n.segment_findings(90, 100, (), (99, 100, 101)) == ()


def test_all_six_node_checks_include_handles_duplicates_and_boundaries():
    item = row((path((1, 1, True), (2, 2, True), (0, 0, False)),), metrics=(0, 0, 0, 0))
    hits = [h for h in n.findings((item,)) if h.kind.startswith("node")]
    assert [(h.index, h.kind, h.target) for h in hits] == [
        (0, "node x zero", 0),
        (0, "node y zero", 0),
        (0, "node ascender", 0),
        (0, "node cap height", 0),
        (0, "node x height", 0),
        (0, "node descender", 0),
    ]


def test_original_open_closure_and_curve_sampling_retained():
    points = path((0, 0, False), (100, 1, False))
    assert n.segments(points) == (((100, 1), (0, 0)), ((0, 0), (100, 1)))
    control = ((0, 0), (20, 80), (80, -80), (100, 1))
    angle, length = n.measure(control)
    assert angle == math.degrees(math.atan2(1, 100))
    t = 0.0
    samples = []
    while t < 1:
        samples.append(
            tuple(
                sum(
                    p[d] * math.comb(3, i) * (1 - t) ** (3 - i) * t**i
                    for i, p in enumerate(control)
                )
                for d in (0, 1)
            )
        )
        t += 0.02
    expected = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in pairwise(samples))
    assert length == pytest.approx(expected) and length != pytest.approx(
        math.hypot(100, 1)
    )


def test_complete_report_retains_occurrences_and_quiet_sources():
    first = row((path((0, 0, False), (101, 1, False)),), (100,), (100,))
    second = replace(first, name="b", master="Bold")
    hits = n.findings((first, second, first, row()))
    assert [h.glyph for h in hits] == ["a"] * (len(hits) // 3) + ["b"] * (
        len(hits) // 3
    ) + ["a"] * (len(hits) // 3)
    text = n.render((first, second, first, row()))
    assert "4 selected glyph occurrences" in text and "Bold" in text
    assert all(x in text for x in ["horizontal stem", "angle", "node y zero"])
    assert "No near misses" in n.render((row(),)) and n.segments(()) == ()


@pytest.mark.parametrize("points", [((0, 0), (1, 1), (2, 2)), ((0, 0),), ()])
def test_unrepresentable_segment_refuses(points):
    with pytest.raises(ValueError, match="line or cubic"):
        n.measure(points)


@pytest.mark.parametrize("value", [float("inf"), float("nan"), True, "bad"])
def test_bad_numbers_refuse_whole_report(value):
    with pytest.raises((ValueError, TypeError)):
        n.findings((row(), row((path((0, 0, False), (value, 1, False)),))))


def test_malformed_controls_and_no_selection_refuse():
    with pytest.raises(ValueError):
        n.segments(path((0, 0, False), (1, 1, True), (2, 2, False)))
    with pytest.raises(ValueError, match="Select"):
        n.render(())


def test_invalid_record_shapes_and_expired_analysis_refuse():
    from time import monotonic

    with pytest.raises(ValueError, match="four"):
        n.findings((row(metrics=(1, 2, 3)),))
    with pytest.raises(ValueError, match="coordinates"):
        n.findings((row(((n.Node((1,), False),),)),))
    with pytest.raises(TimeoutError):
        n.findings((row((path((0, 0, False)),)),), monotonic() - 1)


def test_cubic_arithmetic_bits_preserve_exact_stem_suppression_N107():
    angle, length = n.measure(((0, 0), (0, 100), (100, 100), (100, 0)))
    assert length == 194.0873913301843
    assert (
        n.segment_findings(angle, length, (194.0873913301843, 196.02826524348615), ())
        == ()
    )


@pytest.mark.parametrize("phase", ["segments", "nodes"])
def test_analysis_checkpoints_bound_segment_and_node_phases(monkeypatch, phase):
    state = {"time": 0, "measured": 0}
    monkeypatch.setattr(n, "monotonic", lambda: state["time"])
    original_segments, original_measure = n.segments, n.measure

    def slow_segments(points):
        result = original_segments(points)
        if phase == "segments":
            state["time"] = 3
        return result

    def slow_measure(points):
        result = original_measure(points)
        state["measured"] += 1
        if phase == "nodes" and state["measured"] == 2:
            state["time"] = 3
        return result

    monkeypatch.setattr(n, "segments", slow_segments)
    monkeypatch.setattr(n, "measure", slow_measure)
    with pytest.raises(TimeoutError):
        n.findings((row((path((0, 0, False), (101, 1, False)),)),), 1)


def test_render_checks_own_deadline_before_returning_prefix(monkeypatch):
    monkeypatch.setattr(
        n,
        "findings",
        lambda *args: (n.Finding("a", "Regular", "Regular", 0, 0, "angle", 1, 0),),
    )
    clock = iter((0, 10))
    monkeypatch.setattr(n, "monotonic", lambda: next(clock))
    with pytest.raises(TimeoutError):
        n.render((row(),))


def test_expired_quiet_row_is_not_an_empty_success():
    with pytest.raises(TimeoutError):
        n.findings((row(),), -1)


def test_quiet_render_refuses_when_final_work_expires(monkeypatch):
    clock = iter((0, 3))
    monkeypatch.setattr(n, "monotonic", lambda: next(clock))
    monkeypatch.setattr(n, "findings", lambda *args: ())
    with pytest.raises(TimeoutError):
        n.render((row(),))


def test_quiet_metric_cost_is_checked_after_analysis(monkeypatch):
    state = {"time": 0}
    original = n.number

    def slow_number(value):
        result = original(value)
        state["time"] = 3
        return result

    monkeypatch.setattr(n, "monotonic", lambda: state["time"])
    monkeypatch.setattr(n, "number", slow_number)
    with pytest.raises(TimeoutError):
        n.findings((row(),), 2)
