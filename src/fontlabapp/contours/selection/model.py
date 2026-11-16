# this_file: src/fontlabapp/contours/selection/model.py
# SPDX-License-Identifier: Apache-2.0
"""Select complete, small or partial own contours in the first selected layer.

Behavior adapted from Pedro Arilla's Paths/Select paths.py, Select small paths.py
and Select partial path.py, copyright 2018–2022 Pedro Arilla, Apache-2.0.
This independent FontLab adaptation uses analytic FontTools area; curved results
can differ from Glyphs' flattened area. See NOTICE for exact source hashes.
No host, Qt or optional geometry dependency loads until an action needs it.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Any, Literal

Point = tuple[float, float]
Segments = tuple[tuple[Point, ...], ...]
Mode = Literal["contours", "partial", "small"]


@dataclass(frozen=True)
class Path:
    """Stored-order node selection and optional unsigned analytic contour area."""

    selected: tuple[bool, ...]
    area: float | None = None


@dataclass(frozen=True)
class Plan:
    """Complete node targets; only small-contour selection clears other items."""

    nodes: tuple[tuple[bool, ...], ...]
    paths: int
    clear_other: bool = False


def threshold(value: Any) -> float:
    """Parse finite square font units without rounding or clamping negatives."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Enter a finite numeric area in square font units.") from error
    if not isfinite(number):
        raise ValueError("Area must be finite; selection was not changed.")
    return number


def plan(paths: tuple[Path, ...], mode: Mode, limit: Any = None) -> Plan:
    """Preserve exact original order, strict comparison and cross-path toggles."""
    if mode not in ("contours", "partial", "small"):
        raise ValueError("Unknown contour selection action.")
    area_limit = threshold(limit) if mode == "small" else None
    targets, count, partial = [], 0, False
    for path in paths:
        if mode == "small":
            if path.area is None or path.area < 0 or not isfinite(path.area):
                raise ValueError("Every contour needs a finite unsigned area.")
            choose = path.area < area_limit
            target = tuple(choose for _ in path.selected)
        elif mode == "contours":
            choose = any(path.selected)
            target = tuple(choose for _ in path.selected)
        else:
            target = []
            for selected in path.selected:
                if selected:
                    partial = not partial
                target.append(selected or partial)
            target, choose = tuple(target), any(target)
        targets.append(target)
        count += choose
    return Plan(tuple(targets), count, mode == "small")


def unsigned_area(segments: Segments) -> float:
    """Integrate native line/quadratic/cubic segments and close measurement only.

    Uses the zero-dependency ``fontlab_pens.AreaPen``. Never flatten curves to
    a node polygon.
    """
    from fontlab_pens import AreaPen

    pen = AreaPen()
    previous = None
    for segment in segments:
        if len(segment) not in (2, 3, 4) or (
            previous is not None and previous != segment[0]
        ):
            raise ValueError("Contour segments must be continuous lines or Beziers.")
        if any(not isfinite(coordinate) for point in segment for coordinate in point):
            raise ValueError("Contour coordinates must be finite.")
        if previous is None:
            pen.moveTo(segment[0])
        if len(segment) == 2:
            pen.lineTo(segment[-1])
        elif len(segment) == 3:
            pen.qCurveTo(*segment[1:])
        else:
            pen.curveTo(*segment[1:])
        previous = segment[-1]
    if previous is not None:
        pen.closePath()
    return abs(pen.value)


def select_contours() -> int:
    """Expand any selected own node, including a control, to its whole contour."""
    from fontlabapp.contours.selection.native import execute

    return execute("contours")


def select_partial_contours() -> int:
    """Fill stored-order spans; the toggle state carries across contour bounds."""
    from fontlabapp.contours.selection.native import execute

    return execute("partial")


def select_small_contours(value: Any) -> int:
    """Clear first-layer selection and select own contours below a finite area."""
    from fontlabapp.contours.selection.native import execute

    return execute("small", threshold(value))


def show_small_contours() -> Any:
    """Open an owned numeric prompt bound to the opening source, without writes."""
    from fontlabapp.contours.selection.ui import SmallContoursDialog
    from fontlabapp.core.scripting import show_script_dialog

    return show_script_dialog(SmallContoursDialog, "select-small-contours")
