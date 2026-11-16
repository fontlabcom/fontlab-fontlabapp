# this_file: tests/test_raise_ascender.py
"""Independent literal-loop controls for both original actions."""

from math import inf, nan

import pytest
from fontlabapp.contours.raise_ascender.model import (
    Layer,
    Point,
    associated_master,
    plan,
)


def layer(key="regular", y=(510.0, 511.0), height=500.0):
    return Layer(key, height, tuple(Point(7.0, value) for value in y))


def test_strict_threshold_and_every_node_including_controls():
    result = plan((layer(),), "10")
    assert result[0].after == (Point(7, 510), Point(7, 521))
    assert result[0].changed == 1


def test_repeated_occurrence_rechecks_after_negative_move():
    source = layer(y=(515.0,))
    result = plan((source, source, source), "-10")
    assert [step.after[0].y for step in result] == [505, 505, 505]
    assert [step.changed for step in result] == [1, 0, 0]


def test_order_independent_layers_and_empty_unknown_association():
    result = plan((layer("aux", (600,), 550), Layer("empty", None, ()), layer()), 0)
    assert [step.key for step in result] == ["aux", "empty", "regular"]
    assert all(step.changed == 0 for step in result)
    assert plan((), 10) == ()


@pytest.mark.parametrize("amount", ["bad", nan, inf, -inf])
def test_invalid_amount_fails_before_any_plan(amount):
    with pytest.raises(ValueError):
        plan((layer(),), amount)


def test_nonfinite_result_and_unknown_association_are_not_partial_success():
    with pytest.raises(ValueError):
        plan((layer(y=(1e308,)),), 1e308)
    with pytest.raises(ValueError, match="associated"):
        plan((Layer("aux", None, (Point(1, 600),)),), 10)


def test_source_association_encoding_and_ambiguity():
    masters = {"Regular": 500.0, "Bold": 510.0}
    assert associated_master("Bold", masters) == "Bold"
    assert associated_master("Regular.sketch", masters) == "Regular"
    assert associated_master("sketch", masters) is None
    assert associated_master("A.B.sketch", {"A": 1.0, "A.B": 2.0}) is None


def test_duplicate_key_conflicting_snapshot_rejected():
    with pytest.raises(ValueError, match="changed"):
        plan((layer(), layer(y=(999.0,))), 10)


def test_literal_original_nested_loop_oracle_108_ordered_actions():
    """Reimplement only source's three nested loops; never execute corpus code."""
    from itertools import product

    cases = 0
    for height, amount, ys, keys in product(
        (0.0, 500.0, 510.0),
        (-20.0, 0.0, 0.5, 10.0),
        ((509.0, 510.0, 511.0), (520.0, 530.0, 540.0), (-1.0, 0.0, 1.0)),
        (("a",), ("a", "a"), ("a", "b", "a")),
    ):
        snapshots = {
            key: Layer(key, height, tuple(Point(i, y) for i, y in enumerate(ys)))
            for key in keys
        }
        source = tuple(snapshots[key] for key in keys)
        actual = plan(source, amount)
        state = {
            key: [[p.x, p.y] for p in layer.points] for key, layer in snapshots.items()
        }
        expected = []
        for key in keys:
            for node in state[key]:
                if node[1] > height + 10:
                    node[1] += amount
            expected.append(tuple(Point(*node) for node in state[key]))
        assert tuple(step.after for step in actual) == tuple(expected)
        cases += 1
    assert cases == 108
