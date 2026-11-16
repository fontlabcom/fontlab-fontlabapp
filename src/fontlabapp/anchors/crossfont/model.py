# this_file: src/fontlabapp/anchors/crossfont/model.py
# SPDX-License-Identifier: Apache-2.0
"""Literal TypeRig cross-font anchor-copy policies without importing the host.

Independent implementation; original and maintained TypeRig stay read-only.
Retain ordered duplicate names, first-hit collisions, literal suffixes, exact
width ratios and Python ties-even italic offsets. Native qualification is separate.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from itertools import count
from math import isfinite, radians, tan

ALL_MASTERS = "*All masters*"
TITLE = "Copy Anchors Between Fonts"


@dataclass(frozen=True)
class Pin:
    """One identity's complete explicitly bound native pin metadata in order."""

    identity: int
    name: str
    x: float
    y: float
    metadata: tuple


@dataclass(frozen=True)
class Options:
    """Every original radio/checkbox/input alternative, not a reduced copy mode."""

    relative: bool = False
    italic: bool = False
    angle: int = 10
    rename: bool = True
    rename_destination: bool = True
    suffix: str = ".bak"
    specific: str | None = None


@dataclass(frozen=True)
class Edit:
    """An ordered remove, rename or new detached pin attachment."""

    action: str
    identity: int
    pin: Pin
    source: int | None = None


@dataclass(frozen=True)
class Result:
    """All retained destination pins, operations and zero-width fallback notices."""

    pins: tuple[Pin, ...]
    edits: tuple[Edit, ...]
    copied: int
    zero_advance: tuple[str, ...]


def layer_pairs(
    source: tuple[str, ...],
    destination: tuple[str, ...],
    source_choice: str,
    destination_choice: str,
) -> tuple[tuple[str, str], ...]:
    """Preserve original wildcard/count/common-name/single-layer mapping rules."""
    a = source if "*" in source_choice else (source_choice,)
    b = destination if "*" in destination_choice else (destination_choice,)
    if len(a) != len(b):
        raise ValueError("Unequal Source to Destination layers count!")
    if not a:
        raise ValueError("The chosen fonts have no available master layers.")
    return (
        tuple((name, name) for name in a if name in b)
        if len(a) > 1
        else ((a[0], b[0]),)
    )


def copy_layer(
    source: tuple[Pin, ...],
    destination: tuple[Pin, ...],
    source_width: float,
    destination_width: float,
    options: Options,
    *,
    normalize_insertion: Callable[[str, tuple[str, ...]], str] | None = None,
) -> Result:
    """Simulate ordered actual identity operations, including same-layer aliasing.

    The original materializes a list of source anchor handles before copying.
    Destination renames can change a later source handle when both layers are
    the same. Removed handles remain valid source inputs for the rest of that list.
    The Backend supplies the native insertion helper; omitting it isolates only
    the original script-level policy for callers testing that component.
    """
    if not 0 <= options.angle <= 20 or not isinstance(options.angle, int):
        raise ValueError("Italic angle must be an integer from 0 to 20 degrees.")
    if not all(isfinite(v) for v in (source_width, destination_width)):
        raise ValueError("Anchor widths must be finite.")
    # TypeRig pGlyph.getAdvance truncates each metric to int before copying.
    # Raw float widths remain in capture snapshots for stale-state checks.
    source_width, destination_width = int(source_width), int(destination_width)
    pool = {p.identity: p for p in (*source, *destination)}
    if any(pool[p.identity] != p for p in (*source, *destination)):
        raise ValueError("Shared anchor identity has conflicting captured values.")
    wanted = (
        None
        if options.specific is None
        else {v.strip() for v in options.specific.strip().split(",")}
    )
    selected = [p.identity for p in source if wanted is None or p.name in wanted]
    current = [p.identity for p in destination]
    serial = count(min([0, *pool]) - 1, -1)
    edits, zero = [], []
    for identity in selected:
        pin = pool[identity]
        if not isfinite(pin.x) or not isfinite(pin.y):
            raise ValueError("Anchor coordinates must be finite.")
        x = pin.x
        if options.relative:
            if source_width:
                x = (x / source_width) * destination_width
            else:
                zero.append(pin.name)
        if options.italic and options.angle > 0:
            x += round(pin.y * tan(radians(options.angle)))
        if not isfinite(x):
            raise ValueError("Transformed anchor coordinates must be finite.")
        incoming = replace(pin, identity=next(serial), x=x)
        collision = next(
            (key for key in current if pool[key].name == incoming.name), None
        )
        if collision is not None:
            if options.rename:
                if options.rename_destination:
                    renamed = replace(
                        pool[collision],
                        name=pool[collision].name + options.suffix.strip(),
                    )
                    pool[collision] = renamed
                    edits.append(Edit("rename", collision, renamed))
                else:
                    incoming = replace(
                        incoming, name=incoming.name + options.suffix.strip()
                    )
            else:
                current.remove(collision)
                edits.append(Edit("remove", collision, pool[collision]))
        if normalize_insertion is not None:
            incoming = replace(
                incoming,
                name=normalize_insertion(
                    incoming.name, tuple(pool[key].name for key in current)
                ),
            )
        pool[incoming.identity] = incoming
        current.append(incoming.identity)
        edits.append(Edit("add", incoming.identity, incoming, identity))
    return Result(
        tuple(pool[key] for key in current), tuple(edits), len(selected), tuple(zero)
    )


def show() -> object:
    """Open the complete owned nonmodal cross-font copy dialog through Fly."""
    from fontlabapp.anchors.crossfont.ui import show_dialog

    return show_dialog()
