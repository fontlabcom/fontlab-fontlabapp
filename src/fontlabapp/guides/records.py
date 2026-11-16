# this_file: src/fontlabapp/guides/records.py
# SPDX-License-Identifier: Apache-2.0
"""Original guide filters, width scaling and finite editable table records."""

import math
from typing import Any

from fontlabapp.guides.inspect.model import glyph_guides, guide_record

DIRECTIONS = ["Any direction", "Horizontal", "Vertical", "Angled"]


def direction_of(record: tuple) -> str:
    """Label the original horizontal, vertical and angled guide directions."""
    angle = record[2]
    return "Horizontal" if angle == 0 else "Vertical" if angle == 90 else "Angled"


def matches(record: tuple, direction: str, text: str) -> bool:
    """Match direction and case-insensitive guide-name text as in Clear Guides."""
    if direction != DIRECTIONS[0] and direction_of(record) != direction:
        return False
    return not text or text.lower() in record[3].lower()


def scaled(record: tuple, ratio: float) -> tuple:
    """Scale a guide's x while retaining the original on-screen angled direction."""
    x, y, angle, name = record
    if angle == 0:
        return record
    if angle == 90:
        return (round(x * ratio, 2), y, angle, name)
    radians = math.radians(angle)
    angle = math.degrees(math.atan2(math.sin(radians), math.cos(radians) * ratio)) % 180
    return (round(x * ratio, 2), y, round(angle, 2), name)


def target_records(
    source: Any, target: Any, replace: bool, follow_width: bool
) -> list | None:
    """Keep original merge/replace ordering; zero advance widths cannot be scaled."""
    ratio = 1.0
    if follow_width:
        if source.advanceWidth <= 0 or target.advanceWidth <= 0:
            return None
        ratio = target.advanceWidth / float(source.advanceWidth)
    copied = [scaled(guide_record(g), ratio) for g in glyph_guides(source)]
    if replace:
        return copied
    existing = [guide_record(g) for g in glyph_guides(target)]
    return existing + [record for record in copied if record not in existing]


def parse_row(cells: list[str], row: int) -> tuple[str, tuple]:
    """Parse one complete row; refuse non-finite numbers before any native write."""
    master, x, y, angle, name = cells
    try:
        x, y, angle = (float(x or 0), float(y or 0), float(angle or 0))
        if not all(math.isfinite(v) for v in (x, y, angle)):
            raise ValueError("non-finite guide")
        angle %= 180
    except ValueError as error:
        raise ValueError(
            f"row {row + 1}: X, Y and angle must be finite numbers"
        ) from error
    if angle == 0:
        x = 0.0
    elif angle == 90:
        y = 0.0
    return master, (round(x, 2), round(y, 2), round(angle, 2), name.strip())
