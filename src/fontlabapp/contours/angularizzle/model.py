# this_file: src/fontlabapp/contours/angularizzle/model.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
# Adapted from Angularizzle, Copyright 2019 Luke Prowse. See NOTICE.
"""Detached Angularizzle paths and original numerical output; no native edits.

Preserve source interpolation, duplicate/detail and collapsed-counter behavior.
A supplied absolute monotonic deadline refuses the complete plan on expiry.
"""

from dataclasses import dataclass

from fontlabapp.contours.angularizzle._sampling import (
    STEP,
    Point,
    _check_deadline,
    _deduplicate,
    _parameter,
    _samples,
    _strip,
)

MAX_POINTS = 100_000


@dataclass(frozen=True)
class Segment:
    """Detached ordered line/cubic coordinates; move records are ignored."""

    points: tuple[Point, ...]
    move: bool = False


@dataclass(frozen=True)
class Path:
    """An owned detached source path; open paths remain outside this operation."""

    segments: tuple[Segment, ...]
    closed: bool = True


@dataclass(frozen=True)
class AngularPath:
    """Source lookup length and ordered samples, before native path creation."""

    length: float
    points: tuple[Point, ...]


def angularize(
    paths: tuple[Path, ...],
    plane: int,
    *,
    keep_detail: bool = True,
    deadline: float | None = None,
) -> tuple[AngularPath, ...]:
    """Plan source samples without touching fonts; plane is an integer above4.

    Open/move/empty paths produce no result. Unsupported segments, nonfinite
    geometry, coincident lines and over100000 generated points explicitly refuse
    the whole call; these repairs replace source crashes/unbounded allocation.
    The budget applies across all paths before duplicate removal. UI and native
    adapters must supply their own selection, deadline and history contracts.
    """
    if not isinstance(plane, int) or isinstance(plane, bool) or plane <= 4:
        raise ValueError("Angularizzle minimum plane must be an integer above4.")
    remaining = MAX_POINTS
    result = []
    for path in paths:
        _check_deadline(deadline)
        if not path.closed:
            continue
        length, points = 0.0, []
        for segment in path.segments:
            _check_deadline(deadline)
            if segment.move:
                continue
            distance, samples = _samples(segment.points, plane, remaining, deadline)
            length += distance
            points.extend(samples)
            remaining -= len(samples)
        if points:
            unique = _deduplicate(points)
            result.append(
                AngularPath(
                    length, unique if keep_detail else _strip(unique, plane, deadline)
                )
            )
    _check_deadline(deadline)
    return tuple(result)


def line_nodes(path: AngularPath) -> tuple[Point, ...]:
    """Retain original closed ListToPath removal and empty-counter behavior.

    An empty tuple means the original emits an empty path, not permission for
    a future native adapter to delete a counter silently. Native acceptance must
    settle and expose that source behavior explicitly before applying anything.
    """
    points = path.points[:-1] if len(path.points) > 2 else path.points
    return points if len(points) > 2 else ()


__all__ = [
    "STEP",
    "AngularPath",
    "Path",
    "Point",
    "Segment",
    "_parameter",
    "angularize",
    "line_nodes",
]
