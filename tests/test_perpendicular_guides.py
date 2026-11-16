# this_file: tests/test_perpendicular_guides.py
"""Independent arithmetic/identity oracle, without executing third-party source."""

import math

import pytest
from fontlabapp.guides.perpendicular.model import plan


@pytest.mark.parametrize(
    "points",
    [
        (),
        ((1, 2),),
        ((0, 0), (10, 0)),
        ((0, 0), (0, 10)),
        ((4, 3), (4, 3)),
        ((0, 0), (8, 0), (4, 6)),
        ((0, 0), (0, 0), (2, 2)),
        ((-5, 7), (4, -3), (3, 4), (9, 1)),
    ],
)
def test_original_stored_order_and_mean(points):
    nodes = tuple((i, *p) for i, p in enumerate(points))
    rows, messages = plan(nodes, ())
    if len(points) < 2:
        assert rows == ()
        assert bool(messages)
        return
    centre = tuple(sum(p[j] for p in points) / len(points) for j in (0, 1))
    if len(points) == 2:
        a, b = points
    else:
        order = sorted(
            range(len(points)),
            key=lambda i: sum((points[i][j] - centre[j]) ** 2 for j in (0, 1)),
        )
        a, b = (points[i] for i in order[:2])
    assert rows == (
        (centre[0], centre[1], math.atan2(b[1] - a[1], b[0] - a[0]) + math.pi / 2),
    )
    assert not messages


@pytest.mark.parametrize("nodes", [(), ((1, 2, 3),), ((1, 0, 0), (2, 2, 0))])
def test_component_branch_runs_alongside_nodes(nodes):
    rows, messages = plan(nodes, ((11, -8, 4, 20, 6), (12, 5, -9, 0, 0)))
    assert rows[-4:] == (
        (2, 7, 0),
        (2, 7, math.pi / 2),
        (5, -9, 0),
        (5, -9, math.pi / 2),
    )
    assert len(rows) == 4 + (len(nodes) > 1)
    assert bool(messages) == (len(nodes) == 1)


@pytest.mark.parametrize("value", [float("inf"), float("nan"), -float("inf")])
def test_nonfinite_refused_before_writes(value):
    with pytest.raises(ValueError):
        plan(((1, value, 0), (2, 0, 0)), ())
    with pytest.raises(ValueError):
        plan((), ((1, 0, 0, value, 2),))


def test_duplicate_identity_refused_but_coincident_distinct_nodes_retained():
    with pytest.raises(ValueError):
        plan(((1, 0, 0), (1, 0, 0)), ())
    assert len(plan(((1, 0, 0), (2, 0, 0)), ())[0]) == 1


def test_public_lazy_entry_invokes_native_complete_action(monkeypatch):
    import fontlabapp.guides.perpendicular.native as native
    from fontlabapp.guides.perpendicular.model import run

    monkeypatch.setattr(native, "execute", lambda: {"guides": 5})
    assert run() == {"guides": 5}
