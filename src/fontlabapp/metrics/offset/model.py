# this_file: src/fontlabapp/metrics/offset/model.py
# SPDX-License-Identifier: Apache-2.0
"""Immutable spacing offsets and lazy public entry points for both originals."""

from dataclasses import dataclass
from math import isfinite
from threading import current_thread, main_thread
from typing import Any


@dataclass(frozen=True)
class Row:
    """One ordered selected-layer occurrence; no retained native handles."""

    package_id: int
    glyph_id: int
    layer_id: int
    name: str
    layer: str
    advance: float
    left: float | None
    right: float | None


@dataclass(frozen=True)
class Snapshot:
    """Complete detached selection with its document/master identity."""

    context: tuple
    rows: tuple[Row, ...]


def preview(facts: Snapshot, offset: int) -> tuple:
    """Translate ink locally: left+offset, right-offset, unchanged advance."""
    if type(offset) is not int or not -100 <= offset <= 100:
        raise ValueError("Offset must be an integer from -100 to 100.")
    result = []
    for row in facts.rows:
        values = (row.advance, row.left, row.right)
        if any(v is not None and not isfinite(v) for v in values):
            raise ValueError("A selected layer has non-finite spacing measurements.")
        if (row.left is None) != (row.right is None):
            raise ValueError("Both geometric margins must be available together.")
        result.append(
            (
                row.name,
                row.layer,
                None if row.left is None else row.left + offset,
                None if row.right is None else row.right - offset,
                row.advance,
            )
        )
    return tuple(result)


def _show(part: int) -> Any:
    if current_thread() is not main_thread():
        raise RuntimeError("Open spacing previews on the main UI thread.")
    from fontlabapp import _native
    from fontlabapp.core.scripting import show_script_dialog
    from fontlabapp.metrics.offset.capture import capture
    from fontlabapp.metrics.offset.ui import panel_type

    qt = _native("PythonQt")
    kind = panel_type(qt.QtCore, qt.QtGui)
    return show_script_dialog(
        lambda parent: kind(parent, capture, part), f"slider_spacing_{part}"
    )


def show() -> Any:
    """Open the three mutable slider controls from original part2."""
    return _show(2)


def show_stacked() -> Any:
    """Open both synchronized stacked slider groups from original part3."""
    return _show(3)
