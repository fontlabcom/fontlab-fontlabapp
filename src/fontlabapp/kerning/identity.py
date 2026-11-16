# this_file: src/fontlabapp/kerning/identity.py
# SPDX-License-Identifier: Apache-2.0
"""Keep PyGate explicit kerning side identifiers and modes lossless.

PyGate fgkerning.cxx items/set/remove retain (identifier, mode) sides. Legacy
@notation cannot express a glyph whose literal name starts with @; typed reads
and writes support that complete domain without changing existing string keys.
"""

from typing import Any, Literal

Mode = Literal["glyphMode", "groupMode"]
NativeSide = tuple[str, Mode]
Side = str | NativeSide
Pair = tuple[Side, Side]
Pairs = dict[Pair, float]
Edits = dict[str, dict[Pair, int | None]]


def native_side(side: Side) -> NativeSide:
    """Decode legacy @notation or validate an explicit native side unchanged."""
    if isinstance(side, str):
        name, mode = (
            (side[1:], "groupMode") if side.startswith("@") else (side, "glyphMode")
        )
    elif isinstance(side, tuple) and len(side) == 2:
        name, mode = side
    else:
        raise ValueError("Kerning side needs a name or typed (identifier, mode) tuple")
    if mode not in ("glyphMode", "groupMode"):
        raise ValueError(f"Unknown kerning side mode: {mode}")
    if not isinstance(name, str) or not name:
        raise ValueError("Kerning pair names must not be blank")
    return name, mode


def read_pairs(package: Any, master: str, *, typed: bool = False) -> dict[Pair, float]:
    """Read every explicit pair; refuse lossy legacy encoding before returning it."""
    result = {}
    for pair, value in package.kerning(master).items():
        sides = []
        for side in (pair.left, pair.right):
            name, mode = native_side((side.id, side.mode))
            if typed:
                sides.append((name, mode))
            elif mode == "glyphMode" and name.startswith("@"):
                raise ValueError(
                    "Literal @ glyph names require typed kerning pairs; no legacy alias is returned"
                )
            else:
                sides.append(("@" if mode == "groupMode" else "") + name)
        result[tuple(sides)] = value
    return result


def pair_key(pair: Pair, *, typed: bool) -> Pair:
    """Canonicalize either public input form to the snapshot's representation."""
    if not isinstance(pair, tuple) or len(pair) != 2:
        raise ValueError("Kerning key must be a tuple of two names or typed sides")
    sides = tuple(native_side(side) for side in pair)
    if typed:
        return sides
    if any(mode == "glyphMode" and name.startswith("@") for name, mode in sides):
        raise ValueError("Literal @ glyph names require a typed kerning snapshot")
    return tuple(("@" if mode == "groupMode" else "") + name for name, mode in sides)
