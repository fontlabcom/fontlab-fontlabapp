# this_file: src/fontlabapp/contours/angularizzle/_sampling.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
# Adapted from Angularizzle, Copyright 2019 Luke Prowse. See NOTICE.
"""Private source-exact sampling and cooperative deadline checkpoints."""

from itertools import pairwise
from math import ceil, floor, hypot, isfinite
from time import monotonic

Point = tuple[float, float]
STEP = 1.0 / 130


def _check_deadline(deadline: float | None) -> None:
    """Diagnose expiry inside Python loops; never publish a partial plan."""
    if deadline is not None and monotonic() >= deadline:
        raise TimeoutError("Angularizzle exceeded its deadline; no partial plan.")


def _point(points: tuple[Point, ...], t: float) -> Point:
    """Use the original repeated linear interpolation, including its rounding."""
    while len(points) > 1:
        points = tuple(
            (a[0] * (1 - t) + b[0] * t, a[1] * (1 - t) + b[1] * t)
            for a, b in pairwise(points)
        )
    return points[0]


def _lookup(points: tuple[Point, ...], deadline: float | None = None) -> list[float]:
    """Keep accumulated floating steps; replacing with i/130 changes samples."""
    sampled = []
    t = 0.0
    while t < 1:
        _check_deadline(deadline)
        sampled.append(_point(points, t))
        t += STEP
    distances = [0.0]
    for a, b in pairwise(sampled):
        distances.append(distances[-1] + hypot(b[0] - a[0], b[1] - a[1]))
    return distances


def _parameter(lookup: list[float], distance: float) -> float:
    """Preserve original first-interval zero and percentage arithmetic."""
    for i, (a, b) in enumerate(pairwise(lookup)):
        if a <= distance <= b:
            if a == 0:
                return 0.0
            percent = (100 / (b - a)) * (distance - a)
            return i * STEP + STEP * (percent / 100)
    raise ValueError("Angularizzle lookup cannot locate the requested distance.")


def _samples(
    points: tuple[Point, ...], plane: int, remaining: int, deadline: float | None = None
) -> tuple[float, list[Point]]:
    """Return an entire segment or refuse; never allocate an unbounded prefix."""
    if len(points) not in (2, 4) or not all(
        len(p) == 2 and all(isfinite(v) for v in p) for p in points
    ):
        raise ValueError("Angularizzle requires finite line or cubic coordinates.")
    lookup = _lookup(points, deadline) if len(points) == 4 else []
    length = (
        lookup[-1]
        if lookup
        else hypot(points[1][0] - points[0][0], points[1][1] - points[0][1])
    )
    if not isfinite(length):
        raise ValueError("Angularizzle segment length is not finite.")
    if len(points) == 2 and length == 0:
        raise ValueError("Angularizzle refuses a coincident line before division.")
    count = (
        ceil(length / plane)
        if not lookup
        else (floor(length / plane) + 1 if length > plane else 2)
    )
    if count > remaining:
        raise ValueError("Angularizzle point budget exceeded; no partial result.")
    if not lookup:
        return length, _line(points, count, deadline)
    if length <= plane:
        return length, [points[0], points[-1]]
    return length, _curve(points, lookup, count, deadline)


def _line(
    points: tuple[Point, ...], count: int, deadline: float | None = None
) -> list[Point]:
    """Accumulate source line increments without adding an endpoint."""
    x, y = points[0]
    dx, dy = (points[1][0] - x) / count, (points[1][1] - y) / count
    result = []
    for _ in range(count):
        _check_deadline(deadline)
        result.append((x, y))
        x, y = x + dx, y + dy
    return result


def _curve(
    points: tuple[Point, ...],
    lookup: list[float],
    count: int,
    deadline: float | None = None,
) -> list[Point]:
    """Preserve both cubic endpoints and increment the source arc distance."""
    increment, distance = lookup[-1] / (count - 1), 0.0
    result = []
    for i in range(count):
        _check_deadline(deadline)
        t = 0.0 if i == 0 else (1.0 if i == count - 1 else _parameter(lookup, distance))
        result.append(_point(points, t))
        distance += increment
    return result


def _deduplicate(points: list[Point]) -> tuple[Point, ...]:
    """Remove global repeats in order, then append the original final point."""
    return (*dict.fromkeys(points), points[-1])


def _strip(
    points: tuple[Point, ...], plane: int, deadline: float | None = None
) -> tuple[Point, ...]:
    """Keep original strict threshold, previous accepted point and endpoint loss."""
    previous = points[0]
    result = []
    for point in points[1:-1]:
        _check_deadline(deadline)
        if hypot(point[0] - previous[0], point[1] - previous[1]) > plane:
            result.append(previous)
            previous = point
    return tuple(result)
