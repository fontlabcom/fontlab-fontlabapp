# this_file: src/fontlabapp/qt/layouts/stack.py
# SPDX-License-Identifier: MIT
"""Binding-free, one-axis stack arithmetic shared by Cocoa and Vanilla adapters.

Callers retain orientation, insets, hidden-view policy, natural-size caching,
constraint parsing, widget placement and teardown. This is the existing frame
layout algorithm; it does not solve Auto Layout or hugging priorities.
"""

from typing import Literal

Distribution = Literal["fixed", "equal", "proportional", "spacing", "centering"]


def distribute(
    sizes: list[float], length: float, spacing: float, mode: Distribution
) -> list[float]:
    """Update sizes in place and return axis offsets, in input order.

    Supply finite sizes, length and spacing. Equal/proportional modes clamp
    resized sizes at zero; proportional all-zero sizes stay zero. Spacing is
    a minimum, so overcrowded fixed/spacing stacks can overflow. Centering
    keeps endpoint centers and can overlap. Negative spacing remains allowed.
    Fixed mode leaves sizes unchanged. Empty input returns no offsets.
    Foreign enum mapping belongs to the caller. Unknown modes raise before
    any mutation. See Glyport's NSStackView and Vanilla VerticalStackView.
    """
    if mode not in ("fixed", "equal", "proportional", "spacing", "centering"):
        raise ValueError(f"Unknown stack distribution: {mode!r}")
    count = len(sizes)
    if not count:
        return []
    if mode == "equal":
        sizes[:] = [max(0.0, (length - spacing * (count - 1)) / count)] * count
    elif mode == "proportional" and sum(sizes) > 0:
        scale = (length - spacing * (count - 1)) / sum(sizes)
        sizes[:] = [max(0.0, size * scale) for size in sizes]
    elif mode == "spacing" and count > 1:
        spacing = max(spacing, (length - sum(sizes)) / (count - 1))
    elif mode == "centering" and count > 1:
        first, last = sizes[0] / 2, length - sizes[-1] / 2
        step = (last - first) / (count - 1)
        return [first + step * i - size / 2 for i, size in enumerate(sizes)]
    starts, position = [], 0.0
    for size in sizes:
        starts.append(position)
        position += size + spacing
    return starts
