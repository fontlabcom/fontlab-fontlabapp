# this_file: src/fontlabapp/masters/background/model.py
# SPDX-License-Identifier: Apache-2.0
"""Pedro Arilla's complete background operations, independently implemented.

Scale changes path nodes about origin; Shift also moves component positions.
Replacement copies selected whole paths to first-layer and all-font current-
master backgrounds. See NOTICE. Native installed/history qualification pending.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Any


def numeric(value: Any) -> float:
    """Accept the original float-valued field, rejecting nonfinite input."""
    if isinstance(value, bool):
        raise ValueError("Enter a finite number.")  # noqa: TRY004 - one numeric-field error contract
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Enter a finite number.") from error
    if not isfinite(result):
        raise ValueError("Enter a finite number.")
    return result


@dataclass(frozen=True)
class Transform:
    """One exact ordered occurrence operation, with no component scaling."""

    mode: str
    value: float

    def __post_init__(self) -> None:
        if self.mode not in ("scale", "shift"):
            raise ValueError("Unknown background operation.")
        object.__setattr__(self, "value", numeric(self.value))

    def point(self, point: tuple[float, float]) -> tuple[float, float]:
        x, y = map(numeric, point)
        factor = self.value * 0.01
        return (
            (numeric(x * factor), numeric(y * factor))
            if self.mode == "scale"
            else (numeric(x + self.value), y)
        )

    def points(self, points: tuple, *, repeat: int = 1) -> tuple:
        result = tuple(points)
        for _ in range(repeat):
            result = tuple(self.point(point) for point in result)
        return result

    def component(self, matrix: tuple) -> tuple:
        if self.mode == "scale":
            return matrix
        a, b, p, c, d, q, x, y, w = map(numeric, matrix)
        if (p, q, w) != (0, 0, 1):
            raise ValueError("Component shift requires an affine transform.")
        return a, b, p, c, d, q, numeric(x + self.value), y, w


def selected_paths(paths: tuple[tuple[bool, ...], ...]) -> tuple[int, ...]:
    """Glyphs selects a path exactly when every node belongs to the selection."""
    return tuple(i for i, nodes in enumerate(paths) if all(nodes))


def run(mode: str, value: Any = None) -> dict:
    """Capture, stage, recheck and apply a complete operation through native App."""
    from fontlabapp.masters.background.native import Backend

    operation = None if mode == "replace" else Transform(mode, numeric(value))
    backend = Backend()
    return backend.apply(backend.capture(mode), operation)


def show(mode: str) -> Any:
    """Open complete numeric controls, or run the original immediate replacement."""
    if mode == "replace":
        return run(mode)
    if mode not in ("scale", "shift"):
        raise ValueError("Unknown background operation.")
    from fontlabapp.masters.background.ui import show_dialog

    return show_dialog(mode)
