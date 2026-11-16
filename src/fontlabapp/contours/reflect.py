# this_file: src/fontlabapp/contours/reflect.py
# SPDX-License-Identifier: Apache-2.0
"""Detached plans for both Slobzheninov Reflect actions.

The caller supplies the complete original selection bounds, including selected
component extents and anchors. A native ownership/writer adapter is a separate
required boundary; this module does not claim to apply edits in FontLab.
"""

from dataclasses import dataclass, replace
from math import isfinite
from typing import Literal

Axis = Literal["horizontal", "vertical"]


@dataclass(frozen=True)
class Element:
    """One positioned element, preserving opaque detached topology/metadata.

    For a component, scale and rotation are its source-engine decomposed values,
    not guessed matrix diagonal entries. All other kinds retain their scale data.
    """

    kind: str
    position: tuple[float, float]
    selected: bool = True
    scale: tuple[float, float] | None = None
    rotation: float = 0.0
    retained: tuple = ()


@dataclass(frozen=True)
class Plan:
    """Complete ordered result; metrics is requested even for empty selection."""

    elements: tuple[Element, ...]
    update_metrics: bool = True


def _finite(values: tuple) -> None:
    if not all(isfinite(value) for value in values):
        raise ValueError("Reflect requires finite coordinates and transforms.")


def _element(element: Element, mid: float, index: int) -> Element:
    if not element.selected:
        return element
    _finite((*element.position, element.rotation))
    position = list(element.position)
    position[index] = mid - position[index] + mid
    _finite(tuple(position))
    scale = element.scale
    if element.kind == "component":
        if scale is None or len(scale) != 2:
            raise ValueError("A component requires both source scale values.")
        _finite(scale)
        scale = tuple(-value if i == index else value for i, value in enumerate(scale))
    return replace(element, position=tuple(position), scale=scale)


def plan(
    elements: tuple[Element, ...], bounds: tuple[float, float, float, float], axis: Axis
) -> Plan:
    """Reflect selected positions, then component scale, retaining source order.

    Bounds are (left, bottom, width, height) in the original layer coordinate space.
    Do not replace them with a box of component origins or the complete glyph box.
    The exact source arithmetic order is retained, including floating-point effects.
    """
    if axis not in ("horizontal", "vertical"):
        raise ValueError("Reflect mode must be horizontal or vertical.")
    if len(bounds) != 4:
        raise ValueError("Reflect requires four selection bounds values.")
    _finite(bounds)
    index = 0 if axis == "horizontal" else 1
    mid = bounds[index] + bounds[index + 2] / 2
    _finite((mid,))
    return Plan(tuple(_element(element, mid, index) for element in elements))
