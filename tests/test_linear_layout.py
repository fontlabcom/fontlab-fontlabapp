# this_file: tests/test_linear_layout.py
"""Check the shared solver against independent equation solutions and failures."""

import pytest

from fontlabapp.qt.layouts.linear import InconsistentEquations, solve


@pytest.mark.parametrize(
    "required,hints,count,expected",
    [
        ([], [], 0, []),
        ([], [], 2, [0, 0]),
        ([([1, 1], 10)], [([1, 0], 6), ([0, 1], 3)], 2, [6, 4]),
        ([([1, 1], 3), ([1, -1], 1)], [], 2, [2, 1]),
        ([([0, 2], 8), ([2, 1], 10)], [], 2, [3, 4]),
        ([([0, 0], 0)], [([0, 0], 99)], 2, [0, 0]),
        ([([0, 1, 1], 7)], [], 3, [0, 7, 0]),
        ([([1, 0], 2), ([2, 0], 4)], [([0, 1], 5)], 2, [2, 5]),
    ],
)
def test_required_equations_and_ordered_weak_preferences(
    required, hints, count, expected
):
    before = repr((required, hints))
    assert solve(iter(required), iter(hints), count) == pytest.approx(expected)
    assert repr((required, hints)) == before, (
        "The caller's equations must remain unchanged"
    )


def test_conflicting_required_equations_have_a_distinct_generic_error():
    with pytest.raises(InconsistentEquations, match="Required equations conflict"):
        solve([([1], 1), ([1], 2)], [], 1)
    assert issubclass(InconsistentEquations, ValueError)


def test_existing_epsilon_policy_is_explicit_and_does_not_hide_required_conflict():
    assert solve([([1e-8], 1e-8)], [], 1) == [0]
    assert solve([([1e-8], 1e-8)], [], 1, epsilon=1e-9) == [1]
    with pytest.raises(InconsistentEquations):
        solve([([0], 2e-8)], [], 1)


def test_mismatched_rows_are_not_translated_into_an_equation_conflict():
    with pytest.raises(ValueError) as failure:
        solve([([1, 0], 1), ([0], 0)], [], 2)
    assert not isinstance(failure.value, InconsistentEquations)
