# this_file: src/fontlabapp/qt/numeric.py
# SPDX-License-Identifier: MIT
"""Exact proportional integer Qt ranges shared by sliders and progress bars.

Callers retain float validation, clamping, exact-value caches, tick snapping,
nonpositive-range rules, busy state, repaint and callback policy. Setters arrive
already bound so native method lookup keeps its original evaluation order.
No Qt binding or foreign compatibility package is imported.
"""

from collections.abc import Callable

STEPS = 1_000_000


def position(value: float, minimum: float, span: float, steps: int) -> float:
    """Convert without regrouping arithmetic, rounding, clamping or zero guards."""
    return (value - minimum) * steps / span


def value_at(minimum: float, position: float, span: float, steps: int) -> float:
    """Convert integer Qt positions with the original operation association."""
    return minimum + position * span / steps


def set_step_range(set_range: Callable[[int, int], None], steps: int) -> None:
    """Set the original zero-based Qt range; zero steps also represents busy."""
    set_range(0, steps)


def set_position(set_value: Callable[[int], None], position: float) -> None:
    """Banker's-round once before a native write; preserve setter failures."""
    set_value(round(position))
