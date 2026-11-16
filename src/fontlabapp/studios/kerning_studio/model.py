# this_file: src/fontlabapp/studios/kerning_studio/model.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Studio data rules: pure functions over one master's pairs and groups.

What: one master is ``MasterData(pairs, groups)`` in UFO key space (classes are
``public.kern1.<name>`` on the left side and ``public.kern2.<name>`` on the
right). These functions find class sides, effective values and the record an
edit targets, plan deletes, compute Kern To Max and the Steal gap value, parse
preview text into pairs, and list a glyph's pairs and group peers.
Why: the tabs stay thin and every rule is testable without Qt or FontLab.
Used by ``session`` (native reads) and the four tab modules.

Behaviour credits: Delete Kerning Pair From All Masters, Kern To Max and Steal
Kerning From Next Pair are independent rewrites after Alex Slobzheninov,
Glyphs-Scripts (Apache-2.0, https://github.com/slobzheninov/Glyphs-Scripts);
no code copied. Same Kerning Groups follows Reza Bohloul's workflow; its
source has no licence and its body is not redistributed.
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, NamedTuple

LEFT, RIGHT = "public.kern1.", "public.kern2."
PREFIXES = (LEFT, RIGHT)
NATIVE_SIDES = {"left": (0,), "right": (1,), "both": (0, 1)}
CURVE_STEPS = 12
Pair = tuple[str, str]


class MasterData(NamedTuple):
    """One master's explicit pairs and its kerning groups, in UFO key space."""

    pairs: dict[Pair, float]
    groups: dict[str, tuple[str, ...]]


def from_native(pairs: Mapping[Pair, float], classes: Mapping[str, tuple[Any, str]]) -> MasterData:
    """Convert ``core.scripting`` reads (``@class`` keys, side roles) to UFO keys.

    Class names map as Fontport's native groups do: the side prefix is added
    unless the native name already carries it.
    """
    groups: dict[str, tuple[str, ...]] = {}
    for name, (members, role) in classes.items():
        for side in NATIVE_SIDES.get(role, ()):
            groups[_prefixed(name, side)] = tuple(members)
    converted = {}
    for (left, right), value in pairs.items():
        converted[(_ufo_side(left, 0), _ufo_side(right, 1))] = value
    return MasterData(converted, groups)


def _prefixed(name: str, side: int) -> str:
    return name if name.startswith(PREFIXES[side]) else PREFIXES[side] + name


def _ufo_side(name: str, side: int) -> str:
    return _prefixed(name[1:], side) if name.startswith("@") else name


def display(name: str) -> str:
    """``public.kern1.A`` -> ``@A``; glyph names unchanged."""
    for prefix in PREFIXES:
        if name.startswith(prefix):
            return "@" + name[len(prefix) :]
    return name


def parse_side(text: str, side: int) -> str:
    """User text (``A`` or ``@A``) -> a UFO key for ``side``; blank refused."""
    text = text.strip()
    if not text or text == "@":
        raise ValueError("Enter a left and a right glyph or @group.")
    return _prefixed(text[1:], side) if text.startswith("@") else text


def is_group(name: str) -> bool:
    return name.startswith(PREFIXES)


def side_groups(groups: Mapping[str, Sequence[str]], glyph: str) -> tuple[str | None, str | None]:
    """The ``(kern1, kern2)`` groups containing ``glyph``; more than one per side refused."""
    found: list[str | None] = []
    for prefix in PREFIXES:
        names = [name for name, members in groups.items() if name.startswith(prefix) and glyph in members]
        if len(names) > 1:
            raise ValueError(f"Glyph {glyph} has multiple kerning groups on one side.")
        found.append(names[0] if names else None)
    return found[0], found[1]


def candidates(data: MasterData, left: str, right: str) -> list[Pair]:
    """Possible records for a pair, most specific first (glyph/glyph ... class/class)."""
    lefts = [left] if is_group(left) else [left, side_groups(data.groups, left)[0]]
    rights = [right] if is_group(right) else [right, side_groups(data.groups, right)[1]]
    keys = [(a, b) for a in lefts for b in rights if a and b]
    return sorted(keys, key=lambda key: (is_group(key[0]) and is_group(key[1]), is_group(key[0])))


def effective(data: MasterData, left: str, right: str) -> tuple[float, Pair | None]:
    """The value the pair gets and the record it comes from (``(0, None)`` if none)."""
    for key in candidates(data, left, right):
        if key in data.pairs:
            return data.pairs[key], key
    return 0, None


def class_key(data: MasterData, left: str, right: str) -> Pair:
    """The pair's class-level record: each glyph side replaced by its group, if any."""
    keys = candidates(data, left, right)
    return keys[-1]


def target_key(data: MasterData, left: str, right: str) -> Pair:
    """The record an edit writes: the most specific existing one, else the class record."""
    found = effective(data, left, right)[1]
    return found if found is not None else class_key(data, left, right)


def overrides(data: MasterData, key: Pair, left: str, right: str) -> list[tuple[Pair, float]]:
    """Existing records more specific than ``key`` that keep overriding it."""
    keys = candidates(data, left, right)
    return [(k, data.pairs[k]) for k in keys[: keys.index(key)] if k in data.pairs]


def kern_to_max(left_width: float, right_width: float) -> int:
    """Minus half the narrower advance, truncated toward zero."""
    widths = (left_width, right_width)
    if not all(isinstance(w, (int, float)) and math.isfinite(w) and w >= 0 for w in widths):
        raise ValueError("Both advance widths must be finite and nonnegative.")
    return -int(min(widths) / 2)


def check_range(value: float, upm: Any, master: str, pair: Pair) -> None:
    """Refuse a value outside FontLab's save/reopen range of twice units per em."""
    if not isinstance(upm, (int, float)) or upm <= 0:
        raise ValueError("The font needs valid positive units per em before editing kerning.")
    limit = 2 * upm
    if abs(value) > limit:
        left, right = (display(name) for name in pair)
        raise ValueError(
            f"Kerning on {master}: {left} {right} = {value:g} exceeds FontLab’s save/reopen "
            f"range of ±{limit:g} units (twice units per em); no changes applied."
        )


def parse_text(text: str, cmap: Mapping[int, str]) -> list[list[str]]:
    """Split preview text into words of glyph names; ``/name`` tokens end at space or ``/``."""
    words: list[list[str]] = []
    for chunk in text.split():
        word: list[str] = []
        index = 0
        while index < len(chunk):
            if chunk[index] == "/" and index + 1 < len(chunk):
                end = chunk.find("/", index + 1)
                end = len(chunk) if end < 0 else end
                word.append(chunk[index + 1 : end])
                index = end
                continue
            name = cmap.get(ord(chunk[index]))
            if name:
                word.append(name)
            index += 1
        if word:
            words.append(word)
    return words


def text_pairs(words: Iterable[Sequence[str]]) -> list[Pair]:
    """Adjacent pairs inside each word, first occurrence order, no repeats."""
    seen: dict[Pair, None] = {}
    for word in words:
        for pair in zip(word, word[1:], strict=False):
            seen.setdefault(pair, None)
    return list(seen)


def glyph_pairs(masters: Mapping[str, MasterData], glyph: str) -> list[Pair]:
    """Every record, on any master, whose left or right side is ``glyph`` or its group."""
    keys: dict[Pair, None] = {}
    for data in masters.values():
        left, right = side_groups(data.groups, glyph)
        for key in data.pairs:
            if key[0] in (glyph, left) or key[1] in (glyph, right):
                keys.setdefault(key, None)
    return sorted(keys, key=lambda key: (display(key[0]), display(key[1])))


def group_peers(groups: Mapping[str, Sequence[str]], glyph: str, order: Sequence[str]) -> dict[str, list[str]]:
    """Other members of the glyph's visual-side groups, in font order.

    ``L`` is the left side of the glyph (its ``kern2`` group, used when it is a
    pair's second glyph); ``R`` is its right side (``kern1``).
    """
    kern1, kern2 = side_groups(groups, glyph)
    rank = {name: index for index, name in enumerate(order)}
    peers = {}
    for label, group in (("L", kern2), ("R", kern1)):
        members = [m for m in groups.get(group, ()) if m != glyph] if group else []
        peers[label] = sorted(members, key=lambda name: rank.get(name, len(rank)))
    return peers


def extents(recording: Sequence[tuple[str, tuple]], height: float, name: str, layer: str) -> tuple[tuple[float, float], int]:
    """Min/max x where closed contours cross ``height``; also the open-contour count."""
    xs: list[float] = []
    open_count = 0
    for contour, closed in _contours(recording):
        if not closed:
            open_count += 1
            continue
        for (x0, y0), (x1, y1) in zip(contour, contour[1:] + contour[:1], strict=False):
            if y0 == y1 == height:
                xs += [x0, x1]
            elif min(y0, y1) <= height <= max(y0, y1) and y0 != y1:
                xs.append(x0 + (height - y0) * (x1 - x0) / (y1 - y0))
    if not xs:
        raise ValueError(f"{name}: No closed outline crossing at height {height:g} in {layer}.")
    return (min(xs), max(xs)), open_count


def _contours(recording: Sequence[tuple[str, tuple]]) -> list[tuple[list[tuple[float, float]], bool]]:
    """Flatten a recording into point lists; quadratic spans elevated, curves 12 steps."""
    from fontTools.pens.basePen import decomposeQuadraticSegment

    contours: list[tuple[list[tuple[float, float]], bool]] = []
    points: list[tuple[float, float]] = []
    for operator, args in recording:
        if operator == "moveTo":
            points = [tuple(args[0])]
        elif operator == "lineTo":
            points.append(tuple(args[0]))
        elif operator == "curveTo" and len(args) == 3 and points:
            points += _cubic(points[-1], *args)
        elif operator == "qCurveTo" and args and args[-1] is not None and points:
            for control, end in decomposeQuadraticSegment(args):
                start = points[-1]
                c1 = (start[0] + 2 * (control[0] - start[0]) / 3, start[1] + 2 * (control[1] - start[1]) / 3)
                c2 = (end[0] + 2 * (control[0] - end[0]) / 3, end[1] + 2 * (control[1] - end[1]) / 3)
                points += _cubic(start, c1, c2, end)
        elif operator in ("closePath", "endPath"):
            contours.append((points, operator == "closePath"))
            points = []
        elif operator in ("curveTo", "qCurveTo"):
            raise ValueError(f"Unsupported {operator} segment; Steal needs on-curve contour starts.")
    return contours


def _cubic(p0: Any, p1: Any, p2: Any, p3: Any) -> list[tuple[float, float]]:
    out = []
    for step in range(1, CURVE_STEPS + 1):
        t = step / CURVE_STEPS
        u = 1 - t
        out.append(tuple(u**3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t**3 * d for a, b, c, d in zip(p0, p1, p2, p3, strict=True)))
    return out


def steal_value(widths: Sequence[float], spans: Sequence[tuple[float, float]], reference: float) -> tuple[int, float, float]:
    """Kerning for pair 1 so its gap matches pair 2 (kerned by ``reference``)."""
    gap1 = widths[0] - spans[0][1] + spans[1][0]
    gap2 = widths[2] - spans[2][1] + spans[3][0]
    return int(gap2 - gap1 + reference), gap1, gap2
