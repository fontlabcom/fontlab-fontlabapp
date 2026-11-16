# this_file: src/fontlabapp/glyphs/character_map/model.py
# SPDX-License-Identifier: Apache-2.0
"""Detached FontLab Unicode coverage beside the two reference-font pickers."""

from dataclasses import dataclass
from threading import current_thread, main_thread
from typing import Any
from unicodedata import category


@dataclass(frozen=True)
class Glyph:
    """One real glyph, including unencoded and multiply encoded glyphs."""

    id: int
    name: str
    unicodes: tuple[int, ...]


@dataclass(frozen=True)
class Snapshot:
    """Complete immutable source font; no native wrappers are retained."""

    context: tuple
    rows: tuple[Glyph, ...]


def codepoint_at(part: int, x: int, y: int, cell: int) -> int | None:
    """Map the original 16-column BMP grids without wrapping outside them."""
    if part not in (2, 3):
        raise ValueError("Choose character map part2 or part3.")
    if cell <= 0 or x < 0 or y < 0:
        return None
    column, row = int(x) // cell, int(y) // cell
    if column >= 16 or row >= 4096:
        return None
    return row * 16 + column


def selectable(part: int, code: int, in_font: bool = True) -> bool:
    """Retain the two source filters, with the approved part3 Cs refusal."""
    if part not in (2, 3):
        raise ValueError("Choose character map part2 or part3.")
    return (
        0 <= code <= 65535
        and category(chr(code)) not in {"Cn", "Cs"}
        and (part == 3 or in_font)
    )


def coverage(facts: Snapshot) -> dict[int, tuple[str, ...]]:
    """Keep every assignment in source order; duplicate encodings are useful."""
    result: dict[int, tuple[str, ...]] = {}
    for row in facts.rows:
        for code in row.unicodes:
            result[code] = (*result.get(code, ()), row.name)
    return result


def proof(facts: Snapshot, text: str) -> tuple:
    """Report ordered scalar occurrences, including non-BMP and repeats."""
    assignments = coverage(facts)
    return tuple(
        (index, ord(char), assignments.get(ord(char), ()))
        for index, char in enumerate(text)
    )


def scalar_text(text: str) -> bool:
    """A QLineEdit limit can leave a lone surrogate; never copy it silently."""
    return not any(0xD800 <= ord(char) <= 0xDFFF for char in text)


def _show(part: int) -> Any:
    if current_thread() is not main_thread():
        raise RuntimeError("Open character maps on the main UI thread.")
    from fontlabapp import _native
    from fontlabapp.glyphs.character_map.capture import capture
    from fontlabapp.glyphs.character_map.ui import panel_type
    from fontlabapp.core.scripting import show_script_dialog

    qt = _native("PythonQt")
    kind = panel_type(qt.QtCore, qt.QtGui, part)
    return show_script_dialog(
        lambda parent: kind(parent, capture), f"character_map_{part}"
    )


def show() -> Any:
    """Open part2's fixed styles, size spin box and append-at-end picker."""
    return _show(2)


def show_official() -> Any:
    """Open part3's database styles/sizes and cursor-aware reference picker."""
    return _show(3)
