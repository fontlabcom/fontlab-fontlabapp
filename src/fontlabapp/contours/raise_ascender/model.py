# this_file: src/fontlabapp/contours/raise_ascender/model.py
# SPDX-License-Identifier: MIT AND Apache-2.0
"""Simon Cozens' complete ordered Raise Ascender node algorithm.

Keep repeated layer occurrences: a negative move may put a node below the strict
threshold before the next occurrence. Native capture/history live separately.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from time import monotonic
from typing import Any


@dataclass(frozen=True)
class Point:
    """One own-path node in layer coordinates, regardless of curve role."""

    x: float
    y: float


@dataclass(frozen=True)
class Layer:
    """One original occurrence; None association stays an explicit domain gap."""

    key: str
    x_height: float | None
    points: tuple[Point, ...]


@dataclass(frozen=True)
class Step:
    """A distinct original per-occurrence Undo scope, including unchanged steps."""

    key: str
    before: tuple[Point, ...]
    after: tuple[Point, ...]
    changed: int


def check(deadline: float | None) -> None:
    """Bound Python work; a native call itself cannot be preempted."""
    if deadline is not None and monotonic() >= deadline:
        raise TimeoutError("Raise Ascender deadline exceeded; no partial plan.")


def number(value: Any) -> float:
    """Reject unsafe nonfinite native coordinates without silently normalizing."""
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError("Enter a finite numeric amount.") from error
    if not isfinite(result):
        raise ValueError("Raise Ascender requires finite input and output coordinates.")
    return result


def associated_master(name: str, masters: Mapping[str, float]) -> str | None:
    """Decode exact master or source-imported masterName.auxName, never fallback.

    FontGate glyphs_read.cpp preserves associatedMasterId as this name prefix.
    Ambiguous dotted master names cannot prove a unique original association.
    """
    if name in masters:
        return name
    matches = [master for master in masters if name.startswith(master + ".")]
    return matches[0] if len(matches) == 1 else None


def plan(
    layers: tuple[Layer, ...], amount: Any, deadline: float | None = None
) -> tuple[Step, ...]:
    """Preflight full ordered action and simulate sequential threshold evaluation."""
    check(deadline)
    delta = number(amount)
    originals: dict[str, Layer] = {}
    current: dict[str, tuple[Point, ...]] = {}
    steps = []
    for layer in layers:
        check(deadline)
        if layer.key in originals and originals[layer.key] != layer:
            raise ValueError("Repeated layer snapshot changed during capture.")
        originals[layer.key] = layer
        before = current.get(layer.key, layer.points)
        threshold = None
        if before:
            if layer.x_height is None:
                raise ValueError("An own-path layer has no proven associated master.")
            threshold = number(number(layer.x_height) + 10)
        after = []
        for point in before:
            check(deadline)
            x, y = number(point.x), number(point.y)
            after.append(Point(x, number(y + delta) if y > threshold else y))
        output = tuple(after)
        steps.append(
            Step(
                layer.key,
                before,
                output,
                sum(a != b for a, b in zip(before, output, strict=True)),
            )
        )
        current[layer.key] = output
    check(deadline)
    return tuple(steps)


def show() -> Any:
    """Open the original two-action modeless FontLab workflow through Fly/App."""
    from fontlabapp.contours.raise_ascender.ui import show as open_panel

    return open_panel()
