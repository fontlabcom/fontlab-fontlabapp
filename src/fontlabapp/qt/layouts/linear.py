# this_file: src/fontlabapp/qt/layouts/linear.py
# SPDX-License-Identifier: MIT
"""Binding-free linear UI equations, extracted from Glyport's layout backend.

Foreign constraint syntax, error metadata, intrinsic hints and geometry writes
remain with callers. No Qt, host, Fontport or Glyport imports. See NOTICE.
"""

from collections.abc import Iterable

Equation = tuple[Iterable[float], float]
DEFAULT_EPSILON = 1e-8


class InconsistentEquations(ValueError):
    """The required equalities cannot all hold under the given tolerance."""


def solve(
    required: Iterable[Equation],
    hints: Iterable[Equation],
    count: int,
    *,
    epsilon: float = DEFAULT_EPSILON,
) -> list[float]:
    """Solve required rows first, then compatible weak preferences in order.

    Each equation is (coefficients, right-hand side), with `count` coefficients.
    Callers supply finite numbers, a nonnegative variable count and positive
    epsilon. Free variables default to zero. Inputs are never modified; errors
    from malformed inputs propagate. Contradictory required rows raise
    InconsistentEquations; conflicting weak preferences are ignored. This is
    the existing UI elimination algorithm, not an optimization/inequality solver.
    """
    basis = {}
    for row, value, hard in [
        *((r, v, True) for r, v in required),
        *((r, v, False) for r, v in hints),
    ]:
        row = list(row)
        for column, (other, rhs) in sorted(basis.items()):
            scale = row[column]
            row = [a - scale * b for a, b in zip(row, other, strict=True)]
            value -= scale * rhs
        pivot = next((i for i, v in enumerate(row) if abs(v) > epsilon), None)
        if pivot is None:
            if hard and abs(value) > epsilon:
                raise InconsistentEquations("Required equations conflict")
            continue
        scale = row[pivot]
        basis[pivot] = ([v / scale for v in row], value / scale)
    result = [0.0] * count
    for column, (row, value) in sorted(basis.items(), reverse=True):
        result[column] = value - sum(
            v * x for v, x in zip(row[column + 1 :], result[column + 1 :], strict=True)
        )
    return result
