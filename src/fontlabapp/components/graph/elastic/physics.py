# this_file: src/fontlabapp/components/graph/elastic/physics.py
# SPDX-License-Identifier: Apache-2.0
"""Host-free ordered graphs and the two distinct rescued elastic force laws."""

import math
from dataclasses import dataclass
from time import monotonic

Point = tuple[float, float]


@dataclass(frozen=True)
class Graph:
    """Font order, repeated directed references and unresolved bases stay explicit."""

    names: tuple[str, ...]
    edges: tuple[tuple[int, int], ...]
    points: tuple[Point, ...]
    missing: tuple[str, ...] = ()

    @classmethod
    def from_rows(cls, rows: tuple, *, deadline: float | None = None) -> "Graph":
        """Include every glyph, then missing bases in first-reference order."""
        names = [name for name, _ in rows]
        if any(not isinstance(n, str) or not n for n in names) or len(
            set(names)
        ) != len(names):
            raise ValueError("Glyph names must be nonempty and unique.")
        missing, edges = [], []
        indices = {name: i for i, name in enumerate(names)}
        for i, (_, bases) in enumerate(rows):
            if deadline is not None and monotonic() >= deadline:
                raise TimeoutError(
                    "Component graph assembly expired; no partial graph."
                )
            for base in bases:
                if not isinstance(base, str) or not base:
                    raise ValueError("A component base name is unreadable.")
                if base not in indices:
                    indices[base] = len(names)
                    names.append(base)
                    missing.append(base)
                edges.append((i, indices[base]))
        count = len(names)
        points = tuple(
            (140 * math.cos(i * math.tau / count), 140 * math.sin(i * math.tau / count))
            for i in range(count)
        )
        return cls(tuple(names), tuple(edges), points, tuple(missing))


def fixed(part: int) -> Graph:
    """Return each original's exact ordered nine-node graph and initial layout."""
    if part == 2:
        edges = tuple((i, i + 1) for i in range(9) if i % 3 < 2) + tuple(
            (i, i + 3) for i in range(6)
        )
        points = tuple(((i % 3 - 1) * 105.0, (i // 3 - 1) * 100.0) for i in range(9))
    else:
        edges = (
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
        points = tuple(((i % 3 - 1) * 50.0, (i // 3 - 1) * 50.0) for i in range(9))
    return Graph(tuple(f"Node {i + 1}" for i in range(9)), edges, points)


def step(
    points: tuple[Point, ...],
    edges: tuple,
    part: int,
    held: int | None = None,
    *,
    deadline: float | None = None,
) -> tuple[Point, ...]:
    """Compute synchronously from one complete position snapshot; hold dragged node."""
    output = []
    for i, (x, y) in enumerate(points):
        if deadline is not None and monotonic() >= deadline:
            raise TimeoutError(
                "Graph force step expired; motion stopped without partial positions."
            )
        if held == i:
            output.append((x, y))
            continue
        vx = vy = 0.0
        for j, (a, b) in enumerate(points):
            if i == j:
                continue
            dx, dy = x - a, y - b
            distance = dx * dx + dy * dy
            if part == 2:
                distance = max(1.0, distance)
                if distance == 1 and dx == dy == 0:
                    dx, dy = math.cos(i * 2.4), math.sin(i * 2.4)
                vx += dx * 170 / distance
                vy += dy * 170 / distance
            elif distance:
                vx += dx * 75 / distance
                vy += dy * 75 / distance
        neighbours = [b if a == i else a for a, b in edges if a == i or b == i]
        if part == 3:
            neighbours += [i for a, b in edges if a == b == i]
        rate = 0.015 if part == 2 else 1 / ((len(neighbours) + 1) * 10.0)
        for other in neighbours:
            vx += (points[other][0] - x) * rate
            vy += (points[other][1] - y) * rate
        if part == 2:
            vx, vy = max(-5, min(5, vx)), max(-5, min(5, vy))
            settled = abs(vx) + abs(vy) < 0.2
        else:
            settled = abs(vx) < 0.1 and abs(vy) < 0.1
        if settled:
            vx = vy = 0.0
        bx, by = (275, 225) if part == 2 else (190, 190)
        output.append((max(-bx, min(bx, x + vx)), max(-by, min(by, y + vy))))
    return tuple(output)


def zoom_factor(
    part: int, zoom: float, *, key: int = 0, wheel: int | None = None
) -> float:
    """Retain original zoom direction and endpoint inclusivity per profile."""
    if wheel is not None:
        factor = (
            (1.15 if wheel > 0 else 1 / 1.15) if part == 2 else 2 ** (-wheel / 240.0)
        )
    else:
        factor = (1.15 if part == 2 else 1.2) ** key
    proposed = zoom * factor
    allowed = 0.1 < proposed < 5 if part == 2 else 0.07 <= proposed <= 100
    return factor if allowed else 1.0


def geometry(source: Point, dest: Point, part: int) -> tuple | None:
    """Return clipped endpoints and original directional triangle vertices."""
    x, y = source
    dx, dy = dest[0] - x, dest[1] - y
    length = math.hypot(dx, dy)
    if length < 0.001 or (part == 3 and length <= 20):
        return None
    ux, uy = dx / length, dy / length
    offset = 17 if part == 2 else 10
    a, b = (
        (x + ux * offset, y + uy * offset),
        (dest[0] - ux * offset, dest[1] - uy * offset),
    )
    if part == 2:
        return (
            a,
            b,
            (
                (
                    b,
                    (b[0] - ux * 12 + uy * 5, b[1] - uy * 12 - ux * 5),
                    (b[0] - ux * 12 - uy * 5, b[1] - uy * 12 + ux * 5),
                ),
            ),
        )
    angle = math.acos(max(-1.0, min(1.0, ux)))
    if dy >= 0:
        angle = math.tau - angle
    triangles = []
    for point, sign in ((a, 1), (b, -1)):
        triangles.append(
            (
                point,
                *(
                    (
                        point[0] + math.sin(angle + sign * shift) * 10,
                        point[1] + math.cos(angle + sign * shift) * 10,
                    )
                    for shift in (math.pi / 3, math.pi - math.pi / 3)
                ),
            )
        )
    return a, b, tuple(triangles)
