# this_file: src/fontlabapp/vfjo/nodes.py
"""Node strings of FontLab 9.1 object JSON as a small, exact model.

What: a contour in the JSON is a list of node strings such as
``"326 994  348 983  375 983 s {n:'sv01'}"``. ``Node`` parses one string,
exposes its points, flags and name, and formats it back byte for byte when
unmodified. ``moved``, ``scaled`` and ``mapped`` return new nodes and never
change the point count (hint indexes depend on it).

Grammar (verified live on FontLab 9.1): points are ``x y`` pairs; the
points of a node are separated by two spaces; then optional flags
(``s`` smooth, ``o`` TrueType off-curve, ``g2``, ``c`` close, unknown
tokens kept in order); then optional ``{...}`` attribute text kept verbatim.
One point is an on-curve; three points are off, off, on; two points with
``c`` are the closing curve's off-curves.

How to use: ``Node.parse(s)``, ``str(node)``, ``parse_nodes(list)``,
``format_nodes(list)``. Used by ``fontlabapp.vfjo`` edit helpers.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, replace

Number = int | float
Point = tuple[Number, Number]

_NUMBER = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_NAME = re.compile(r"""\bn:(?:'([^']*)'|"([^"]*)")""")
_KNOWN_FLAGS = {"s": "smooth", "o": "offcurve", "g2": "g2", "c": "close"}
_DECIMALS = 3


def _to_number(token: str) -> Number:
    """Return ``token`` as int when written as an integer, else float."""
    if re.fullmatch(r"[+-]?\d+", token):
        return int(token)
    return float(token)


def format_number(value: Number) -> str:
    """Format a coordinate: integral values as int text, else 3 decimals trimmed."""
    rounded = round(float(value), _DECIMALS)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.{_DECIMALS}f}".rstrip("0")


@dataclass(frozen=True)
class Node:
    """One contour node: points, flags and optional attribute text.

    ``flags`` holds unknown extra tokens in their original order; ``attrs``
    is the raw ``{...}`` text. Known flags format in the order s, o, g2, c,
    then unknown tokens.
    """

    points: tuple[Point, ...]
    smooth: bool = False
    g2: bool = False
    close: bool = False
    offcurve: bool = False
    flags: tuple[str, ...] = ()
    attrs: str | None = None

    @classmethod
    def parse(cls, text: str) -> Node:
        """Parse a node string; raise ValueError (with the text) if malformed."""
        head, brace, rest = text.partition("{")
        attrs = (brace + rest) if brace else None
        tokens = head.split()
        coords = 0
        while coords < len(tokens) and _NUMBER.fullmatch(tokens[coords]):
            coords += 1
        if coords == 0 or coords % 2:
            raise ValueError(f"malformed node (need x y pairs): {text!r}")
        nums = [_to_number(t) for t in tokens[:coords]]
        found = {"smooth": False, "offcurve": False, "g2": False, "close": False}
        unknown: list[str] = []
        for token in tokens[coords:]:
            if token in _KNOWN_FLAGS:
                found[_KNOWN_FLAGS[token]] = True
            else:
                unknown.append(token)
        points = tuple(zip(nums[0::2], nums[1::2], strict=True))
        return cls(points=points, flags=tuple(unknown), attrs=attrs, **found)

    def format(self) -> str:
        """Return the node string (exact for an unmodified parsed node)."""
        parts = ["  ".join(f"{format_number(x)} {format_number(y)}" for x, y in self.points)]
        for token, field in _KNOWN_FLAGS.items():
            if getattr(self, field):
                parts.append(token)
        parts.extend(self.flags)
        if self.attrs is not None:
            parts.append(self.attrs)
        return " ".join(parts)

    __str__ = format

    @property
    def name(self) -> str | None:
        """The node name from ``n:'...'`` in the attributes, else None."""
        match = _NAME.search(self.attrs or "")
        return None if match is None else (match.group(1) or match.group(2) or "")

    @property
    def on(self) -> Point | None:
        """The on-curve point; None for a closing node or a TrueType off-curve."""
        if self.close or self.offcurve:
            return None
        return self.points[-1]

    @property
    def offcurves(self) -> list[Point]:
        """The off-curve points: all for close/``o`` nodes, else all but the last."""
        if self.close or self.offcurve:
            return list(self.points)
        return list(self.points[:-1])

    def mapped(self, fn: Callable[[Number, Number], Point]) -> Node:
        """Return a new node with every point replaced by ``fn(x, y)``."""
        return replace(self, points=tuple(fn(x, y) for x, y in self.points))

    def moved(self, dx: Number, dy: Number) -> Node:
        """Return a new node translated by ``(dx, dy)``."""
        return self.mapped(lambda x, y: (x + dx, y + dy))

    def scaled(self, sx: Number, sy: Number | None = None, origin: Point = (0, 0)) -> Node:
        """Return a new node scaled by ``sx``/``sy`` (default ``sx``) around ``origin``."""
        sy = sx if sy is None else sy
        ox, oy = origin
        return self.mapped(lambda x, y: (ox + (x - ox) * sx, oy + (y - oy) * sy))


def parse_nodes(texts: list[str]) -> list[Node]:
    """Parse a contour's node strings."""
    return [Node.parse(t) for t in texts]


def format_nodes(nodes: list[Node]) -> list[str]:
    """Format nodes back to a contour's node strings."""
    return [n.format() for n in nodes]
