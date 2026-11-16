# this_file: tests/test_elastic_physics.py
"""Independent scalar force and source-identity contracts for both originals."""

import math

import pytest
from fontlabapp.components.graph.elastic.physics import (
    Graph,
    fixed,
    geometry,
    step,
    zoom_factor,
)


def oracle(points, edges, part, held=None):
    result = []
    for i, (x, y) in enumerate(points):
        if i == held:
            result.append((x, y))
            continue
        vx = vy = 0.0
        for j, (a, b) in enumerate(points):
            if i == j:
                continue
            dx, dy = x - a, y - b
            d = dx * dx + dy * dy
            if part == 2:
                d = max(1.0, d)
                if d == 1 and dx == dy == 0:
                    dx, dy = math.cos(i * 2.4), math.sin(i * 2.4)
                vx += dx * 170 / d
                vy += dy * 170 / d
            elif d:
                vx += dx * 75 / d
                vy += dy * 75 / d
        neighbours = [b if a == i else a for a, b in edges if a == i or b == i]
        if part == 3:
            neighbours += [i for a, b in edges if a == b == i]
        for other in neighbours:
            rate = 0.015 if part == 2 else 1 / ((len(neighbours) + 1) * 10.0)
            vx += (points[other][0] - x) * rate
            vy += (points[other][1] - y) * rate
        if part == 2:
            vx = max(-5, min(5, vx))
            vy = max(-5, min(5, vy))
            if abs(vx) + abs(vy) < 0.2:
                vx = vy = 0.0
        elif abs(vx) < 0.1 and abs(vy) < 0.1:
            vx = vy = 0.0
        bx, by = (275, 225) if part == 2 else (190, 190)
        result.append((min(bx, max(-bx, x + vx)), min(by, max(-by, y + vy))))
    return tuple(result)


@pytest.mark.parametrize("part", [2, 3])
@pytest.mark.parametrize(
    "points",
    [
        ((0.0, 0.0), (0.0, 0.0), (30.0, 50.0)),
        ((-999.0, 333.0), (25.0, -40.0), (0.0, 0.0)),
        ((0.01, 0.02), (0.1, 0.2), (300.0, 40.0)),
    ],
)
@pytest.mark.parametrize("held", [None, 0, 2])
def test_complete_force_policies_match_independent_scalar_oracle(part, points, held):
    edges = ((0, 1), (1, 2), (1, 2), (2, 0), (2, 2))
    for actual, expected in zip(
        step(points, edges, part, held), oracle(points, edges, part, held), strict=True
    ):
        assert actual == pytest.approx(expected)


def test_fixed_distinct_ordered_nine_node_contracts():
    a, b = fixed(2), fixed(3)
    assert len(a.names) == len(b.names) == 9 and len(a.edges) == len(b.edges) == 12
    assert a.points[0] == (-105.0, -100.0) and b.points[0] == (-50.0, -50.0)
    assert b.edges == (
        (0, 1),
        (1, 2),
        (1, 4),
        (2, 5),
        (3, 0),
        (3, 4),
        (4, 5),
        (4, 7),
        (5, 8),
        (6, 3),
        (7, 6),
        (8, 7),
    )
    assert a.edges != b.edges


def test_font_order_repeats_cycles_missing_and_unencoded_names_remain_distinct():
    graph = Graph.from_rows(
        (("z.alt", ("a", "a", "missing")), ("a", ("z.alt",)), ("無", ()))
    )
    assert graph.names == ("z.alt", "a", "無", "missing")
    assert graph.edges == ((0, 1), (0, 1), (0, 3), (1, 0)) and graph.missing == (
        "missing",
    )
    assert Graph.from_rows(()).names == ()
    with pytest.raises(ValueError):
        Graph.from_rows((("a", ()), ("a", ())))
    with pytest.raises(ValueError):
        Graph.from_rows((("a", ("",)),))


@pytest.mark.parametrize("part,lo,hi", [(2, 0.1, 5), (3, 0.07, 100)])
def test_zoom_boundaries_and_inverse_wheel(part, lo, hi):
    assert zoom_factor(part, 1.0, key=1) == (1.15 if part == 2 else 1.2)
    assert zoom_factor(3, 1.0, wheel=120) == pytest.approx(2 ** (-0.5))
    assert zoom_factor(2, lo, wheel=-120) == 1
    assert zoom_factor(part, lo, key=-1) == 1
    assert zoom_factor(part, hi, key=1) == 1
    assert zoom_factor(2, 1.0, wheel=0) == pytest.approx(1 / 1.15)
    assert zoom_factor(3, 1.0, wheel=0) == 1


def test_edge_endpoints_arrows_and_degenerate_policies():
    assert geometry((0, 0), (0, 0), 2) is None
    assert geometry((0, 0), (20, 0), 3) is None
    a, b, arrows = geometry((0, 0), (100, 0), 2)
    assert a == (17.0, 0.0) and b == (83.0, 0.0) and len(arrows) == 1
    a, b, arrows = geometry((0, 0), (100, 0), 3)
    assert a == (10.0, 0.0) and b == (90.0, 0.0) and len(arrows) == 2


def test_force_and_assembly_deadlines_never_return_partial_results():
    with pytest.raises(TimeoutError):
        step(((0, 0),), (), 2, deadline=0)
    with pytest.raises(TimeoutError):
        Graph.from_rows((("a", ()),), deadline=0)


@pytest.mark.parametrize("part", [2, 3])
def test_100_synchronous_frames_match_independent_original_physics(part):
    graph = fixed(part)
    actual = expected = graph.points
    for frame in range(100):
        held = 4 if 20 <= frame < 30 else None
        actual = step(actual, graph.edges, part, held)
        expected = oracle(expected, graph.edges, part, held)
        for a, b in zip(actual, expected, strict=True):
            assert a == pytest.approx(b)
