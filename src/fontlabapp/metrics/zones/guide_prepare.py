# this_file: src/fontlabapp/metrics/zones/guide_prepare.py
# SPDX-License-Identifier: Apache-2.0
"""Prepare owned zone roots using the native decoder and opaque payload checks.

Root identity checks and restoration witnesses are necessary diagnostics, not
proof that every linked native object is detached. Only dedicated owned native
qualification can establish that. Never use a legacy serializer declaration.
"""

from collections.abc import Callable
from typing import Any

from fontlabapp.metrics.zones.native_rules import is_top
from fontlabapp.metrics.zones.rows import number
from fontlabapp.metrics.zones.write_plan import WriteRow


def decoder(native: Any) -> Callable:
    """Require the source-verified one-argument QByteArray decoder declaration."""
    method = native.flModelProducer.getObjectsFromData
    if "getObjectsFromData(QByteArray *data)" not in (method.__doc__ or ""):
        raise RuntimeError(
            "Zone preparation requires the native one-argument data decoder."
        )
    return method


def identities(guide: Any) -> tuple[int, ...]:
    """Read known root/node/marker IDs, without reflecting arbitrary properties."""
    values = (
        guide.id,
        guide.center.id,
        guide.vector.id,
        *(m.id for m in guide.markers),
    )
    if any(type(value) is not int or value <= 0 for value in values):
        raise ValueError("Unreadable native guide identity graph.")
    return values


def claim(native: Any, value: Any, protected: set[int], seen: set[int]) -> Any:
    """Reject known source/reused IDs before modifying any decoded guide."""
    if native.flGuideLine.isGuideLine(value) is not True:
        raise ValueError("Native zone decoder did not return one guide.")
    guide = native.flGuideLine(value)
    identifiers = set(identities(guide))
    if identifiers & (protected | seen):
        raise ValueError(
            "Prepared guide identity aliases a source or another live root."
        )
    seen.update(identifiers)
    return guide


def unpack(
    native: Any,
    qt: Any,
    method: Callable,
    payload: bytes,
    protected: set[int],
    seen: set[int],
) -> Any:
    """Decode one original native root; do not parse/rewrite the binary format."""
    values = method(qt.QByteArray(payload))
    if not isinstance(values, (list, tuple)) or len(values) != 1:
        raise ValueError("Native zone decoder did not return exactly one guide.")
    return claim(native, values[0], protected, seen)


def visible(guide: Any) -> tuple[float, float, float, str]:
    """Copy only the explicitly edited native fields; keep raw values exact."""
    return (
        number(guide.centerPoint.x()),
        number(guide.centerPoint.y()),
        number(guide.extPosition),
        guide.name,
    )


def set_visible(guide: Any, qt: Any, values: tuple) -> None:
    """Change owned center/width/name only, retaining its other native fields."""
    x, y, width, name = values
    guide.center.position = qt.QPointF(x, y)
    guide.extPosition = width
    guide.name = name


def matches(guide: Any, row: WriteRow) -> bool:
    """Refuse constraints, rounding or kind changes before returning prepared data."""
    _x, y, width, name = visible(guide)
    return (
        guide.isZone is True
        and guide.isHorizontal()
        and (y, abs(width), name) == (row.zone.position, row.zone.width, row.zone.name)
        and is_top(width, name, y) == (row.kind == "Top")
    )


def new(
    native: Any, qt: Any, row: WriteRow, protected: set[int], seen: set[int]
) -> Any:
    """Use the actual four-position constructor and native enum dictionaries."""
    guide = native.flGuideLine(
        0.0,
        qt.QPointF(0, row.zone.position),
        native.flSnaps.SnapLineFlags["Horizontal"],
        native.SnapObjectsStyle["gsCustomFontGuideline"],
    )
    return claim(native, guide, protected, seen)
