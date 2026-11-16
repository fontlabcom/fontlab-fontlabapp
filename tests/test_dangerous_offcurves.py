# this_file: tests/test_dangerous_offcurves.py
"""Independent analytic roots and complete original Dangerous Offcurves policy."""

import math

import fontlabapp.contours.dangerous_offcurves.model as api
import pytest


def test_three_analytic_roots_keep_ascending_curve_time():
    curve = ((0, -0.08), (1 / 3, 0.14), (2 / 3, -0.14), (1, 0.08))
    hits = api.axis_hits(curve, (0.2, 0), 0)
    assert [h[0] for h in hits] == pytest.approx([0.2, 0.5, 0.8], abs=1e-8)
    assert [h[1][0] for h in hits] == pytest.approx([0.2, 0.5, 0.8], abs=1e-8)
    assert abs(hits[0][1][0] - 0.2) < 0.05 and abs(hits[-1][1][0] - 0.2) > 0.05


def test_tangent_endpoint_and_coincident_projection_backend_semantics():
    tangent = ((0, 0.25), (1 / 3, -1 / 12), (2 / 3, -1 / 12), (1, 0.25))
    hits = api.axis_hits(tangent, (0.5, 0), 0)
    assert hits and all(t == pytest.approx(0.5, abs=1e-7) for t, p in hits)
    line = ((0, 0), (1 / 3, 1 / 3), (2 / 3, 2 / 3), (1, 1))
    assert api.axis_hits(line, (0, 0), 0)[0][0] == 0
    assert api.axis_hits(line, (1, 1), 0)[0][0] == 1
    assert api.axis_hits(((0, 0), (0, 0), (0, 0), (0, 0)), (0, 0), 0) == ()


def test_finite_line_probe_filters_infinite_line_intersections():
    curve = ((20001, 0), (20002, 1 / 3), (20003, 2 / 3), (20004, 1))
    assert api.axis_hits(curve, (0, 0.5), 0) == ()
    assert api.axis_hits(curve, (20002.5, 0), 1)


@pytest.mark.parametrize(
    "distance,expected",
    [(0.05, False), (math.nextafter(0.05, 0), True), (0.051, False)],
)
def test_original_strict_any_distance_requires_all_four_hits(
    monkeypatch, distance, expected
):
    curve = ((0, 0), (0, 0), (3, 4), (5, 6))
    values = iter(
        [((0, (distance, 0)),), ((0, (0, 1)),), ((0, (4, 4)),), ((0, (3, 5)),)]
    )
    monkeypatch.setattr(api, "axis_hits", lambda *a, **k: next(values))
    assert api.dangerous(curve) == expected


def test_missing_one_intersection_rejects_even_other_exact_hits(monkeypatch):
    values = iter([((0, (1, 2)),), (), ((0, (3, 4)),), ((0, (3, 4)),)])
    monkeypatch.setattr(api, "axis_hits", lambda *a, **k: next(values))
    assert not api.dangerous(((0, 0), (1, 2), (3, 4), (5, 6)))


def test_raw_node_neighbour_windows_wrap_open_and_quadratic_source_pattern():
    path = (api.Node(0, 0, False), api.Node(0.5, 1, True), api.Node(1, 0, False))
    assert api.curves(path) == (((0, 0), (0.5, 1), (1, 0), (0, 0)),)
    assert api.curves(()) == () and api.curves((api.Node(0, 0, True),)) == ()


def test_layer_identity_dedup_keeps_order_and_repeated_hit_logs(monkeypatch):
    path = (
        api.Node(0, 0, False),
        api.Node(1, 1, True),
        api.Node(2, 2, True),
        api.Node(3, 3, False),
    )
    rows = (
        api.Layer((1, 2), "A", "Bold", (path, path)),
        api.Layer((3, 4), "B", "Aux", (path,)),
    )
    monkeypatch.setattr(api, "dangerous", lambda *a, **k: True)
    result = api.analyse(rows)
    assert result.layers == ((1, 2), (3, 4)) and len(result.hits) == 3
    assert api.render(result) == "A -- Bold\nA -- Bold\nB -- Aux\n"
    assert "0.05 units" in api.render(api.analyse(()))


def test_multiroot_example_does_not_bypass_original_four_probe_gate():
    curve = ((0, -0.08), (1 / 3, 0.14), (2 / 3, -0.14), (1, 0.08))
    assert len(api.axis_hits(curve, (0.2, 0), 0)) == 3
    assert not api.axis_hits(curve, curve[1], 0)
    assert not api.dangerous(curve)


@pytest.mark.parametrize("a", [0, 0.1, 0.5, 0.9, 1])
@pytest.mark.parametrize("b", [0, 0.1, 0.5, 0.9, 1])
def test_endpoint_range_controls_have_monotone_projection(a, b):
    # All four probe existence forces each control coordinate into the endpoint
    # range. Bernstein derivative is nonnegative for every a,b in that box.
    for i in range(101):
        t = i / 100
        derivative = 3 * (
            a * (1 - t) ** 2 + 2 * (b - a) * (1 - t) * t + (1 - b) * t * t
        )
        assert derivative >= -1e-14
    curve = ((0, 0), (a, a), (b, b), (1, 1))
    for control in curve[1:3]:
        for axis in (0, 1):
            hits = api.axis_hits(curve, control, axis)
            assert hits and max(h[0] for h in hits) - min(h[0] for h in hits) < 1e-5


def test_numeric_solver_failure_and_absolute_deadline(monkeypatch):
    curve = ((0, 0), (1, 1), (2, 2), (3, 3))
    monkeypatch.setattr(
        api, "_intersections", lambda *args: (_ for _ in ()).throw(ValueError("solver"))
    )
    assert api.axis_hits(curve, (1, 1), 0) == ()
    with pytest.raises(TimeoutError):
        api.analyse((), deadline=0)
    with pytest.raises(ValueError):
        api.analyse((), float("nan"))
    with pytest.raises(ValueError):
        api.axis_hits(((float("inf"), 0), (1, 1), (2, 2), (3, 3)), (1, 1), 0)
    with pytest.raises(ValueError):
        api.axis_hits(curve, (1, 1), 2)


def test_exact_probe_boundary_endpoints_are_not_extended():
    curve = ((-10000, 0), (-9999, 1 / 3), (9999, 2 / 3), (10000, 1))
    assert api.axis_hits(curve, curve[0], 0)[0] == (0, curve[0])
    assert api.axis_hits(curve, curve[-1], 0)[-1] == (1, curve[-1])
    outside = ((-10001, 0), (-9999, 1 / 3), (9999, 2 / 3), (10001, 1))
    assert api.axis_hits(outside, outside[0], 0) == ()
    assert api.axis_hits(outside, outside[-1], 0) == ()


@pytest.mark.parametrize("axis", [0, 1])
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("reverse", [False, True])
def test_strictly_outside_control_hull_has_no_finite_probe_hit(axis, sign, reverse):
    step = math.ulp(api.PROBE)
    curve = tuple((sign * x, y) for x, y in (
        (api.PROBE + 2 * step, 0), (api.PROBE + step, .3),
        (api.PROBE + step, .7), (api.PROBE + step, 1),
    ))
    if reverse:
        curve = tuple(reversed(curve))
    if axis:
        curve = tuple((y, x) for x, y in curve)
    assert all(sign * point[axis] > api.PROBE for point in curve)
    assert api.axis_hits(curve, curve[1], axis) == ()
    assert not api.dangerous(curve), "A curve outside a finite probe cannot win"


@pytest.mark.parametrize("axis", [0, 1])
@pytest.mark.parametrize("sign", [-1, 1])
def test_outside_hull_exclusion_does_not_call_numerical_solver(monkeypatch, axis, sign):
    outside = math.nextafter(sign * api.PROBE, sign * math.inf)
    curve = tuple((outside, y) for y in (0, 1, 2, 3))
    if axis:
        curve = tuple((y, x) for x, y in curve)
    def unexpected(*args):
        pytest.fail("Strict outside-hull exclusion must precede numerical roots")
    monkeypatch.setattr(api, "_intersections", unexpected)
    assert api.axis_hits(curve, curve[1], axis) == ()


@pytest.mark.parametrize("axis", [0, 1])
@pytest.mark.parametrize("sign", [-1, 1])
def test_probe_boundary_and_one_ulp_inside_retain_hits(axis, sign):
    for position in (sign * api.PROBE, math.nextafter(sign * api.PROBE, 0)):
        curve = tuple((position, y) for y in (0, .3, .7, 1))
        if axis:
            curve = tuple((y, x) for x, y in curve)
        hits = api.axis_hits(curve, curve[0], axis)
        assert (0, curve[0]) in hits, "Exact finite endpoint must remain admitted"
        assert api.axis_hits(curve, curve[1], axis), "Hull touching probe must be solved"


@pytest.mark.parametrize("axis", [0, 1])
@pytest.mark.parametrize("sign", [-1, 1])
def test_overlapping_hull_keeps_only_finite_multiple_roots(axis, sign):
    curve = ((9999, -.75), (9999 + 2 / 3, 13 / 12),
             (10000 + 1 / 3, -13 / 12), (10001, .75))
    curve = tuple((sign * x, y) for x, y in curve)
    if axis:
        curve = tuple((y, x) for x, y in curve)
    hits = api.axis_hits(curve, (0, 0), axis)
    assert [hit[0] for hit in hits] == pytest.approx([.25, .5], abs=1e-8)
    assert [hit[1][axis] for hit in hits] == pytest.approx(
        [sign * 9999.5, sign * 10000], abs=1e-8)


@pytest.mark.parametrize("axis", [0, 1])
@pytest.mark.parametrize("sign", [-1, 1])
def test_constant_degenerate_outside_curve_stays_empty(axis, sign):
    outside = math.nextafter(sign * api.PROBE, sign * math.inf)
    point = (outside, 0) if axis == 0 else (0, outside)
    assert api.axis_hits((point,) * 4, point, axis) == ()
    assert not api.dangerous((point,) * 4)


@pytest.mark.parametrize("axis", [0, 1])
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("reverse", [False, True])
def test_overlapping_hull_cannot_admit_rounded_outside_endpoint(axis, sign, reverse):
    # y(t)=2.1t²-1.1t³ is positive for0<t<=1. Its only horizontal
    # zero is the exact start, whose x is strictly outside the finite probe.
    curve = ((math.nextafter(api.PROBE, math.inf), 0), (9999.99, 0),
             (9998, .7), (9997, 1))
    curve = tuple((sign * x, y) for x, y in curve)
    if reverse:
        curve = tuple(reversed(curve))
    if axis:
        curve = tuple((y, x) for x, y in curve)
    assert api.axis_hits(curve, (0, 0), axis) == ()
    assert not api.dangerous(curve), "Outside endpoints do not become finite hits"


@pytest.mark.parametrize("axis", [0, 1])
@pytest.mark.parametrize("sign", [-1, 1])
def test_invalid_endpoint_removal_preserves_valid_interior_roots(axis, sign):
    # y(t)=8t(t-1/2)(t-3/4). Exclude t0 only; retain both interior hits.
    outside = math.nextafter(api.PROBE, math.inf)
    curve = ((outside, 0), (outside - 2 / 3, 1),
             (outside - 4 / 3, -4 / 3), (outside - 2, 1))
    curve = tuple((sign * x, y) for x, y in curve)
    if axis:
        curve = tuple((y, x) for x, y in curve)
    hits = api.axis_hits(curve, (0, 0), axis)
    assert [hit[0] for hit in hits] == pytest.approx([.5, .75], abs=1e-8)
