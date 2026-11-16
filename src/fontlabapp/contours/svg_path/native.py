# this_file: src/fontlabapp/contours/svg_path/native.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
"""Read first selected layer's own native contours and CurveEx segments.

C++ pyflcontour.cpp PenDrawer and pycurveex.cpp sequence protocol establish
2/3/4 points for line/quadratic/cubic; prose CurveEx docs have stale1/2 counts.
Reject quadratic and generated shapes; never decompose components. Map own-path
coordinates through the shape transform. Native getter/cache preservation still
requires host qualification.
"""

from time import monotonic
from typing import Any

import fontlabapp.masters.layers.selection as selection
from fontlabapp.masters.layers.compatibility._records import check
from fontlabapp.contours.svg_path.model import render


def _read(layer: Any, deadline: float) -> tuple:
    """Retain identities/closure and every segment point, excluding components."""
    paths, identities = [], []
    for shape in layer.shapes:
        check(deadline)
        if type(shape.isComponent) is not bool:
            raise ValueError("Unreadable shape role.")
        if shape.isComponent:
            identities.append((int(shape.id), "component"))
            continue
        if shape.isComposite:
            raise ValueError("Generated shapes are unsupported; no partial report.")
        transform = shape.transform
        matrix = tuple(
            getattr(transform, f"m{i}{j}")() for i in (1, 2, 3) for j in (1, 2, 3)
        )
        if (matrix[2], matrix[5], matrix[8]) != (0, 0, 1):
            raise ValueError(
                "Projective shape transforms are unsupported; no partial report."
            )
        identities.append((int(shape.id), matrix))
        for contour in shape.contours:
            check(deadline)
            if type(contour.closed) is not bool or type(contour.isTT) is not bool:
                raise ValueError("Unreadable contour topology.")
            segments = []
            for segment in contour.segments():
                check(deadline)
                if len(segment) not in (2, 4):
                    raise ValueError(
                        "Only line or cubic segments supported; no partial report."
                    )
                segments.append(
                    tuple(
                        (point.x(), point.y())
                        for point in (transform.map(p) for p in segment)
                    )
                )
            paths.append(tuple(segments))
            identities.append(
                (int(shape.id), int(contour.id), contour.closed, contour.isTT)
            )
    result = tuple(paths)
    render(result)
    check(deadline)
    return result, tuple(identities)


def capture() -> tuple:
    """Double-read first selected own-path stream with complete selection fences."""
    deadline = monotonic() + 2.0
    first = selection.capture(deadline)
    if not first.occurrences:
        raise ValueError("Select a glyph layer before dumping SVG path commands.")
    paths, identities = _read(first.occurrences[0].layer, deadline)
    second = selection.capture(deadline)
    if not second.occurrences:
        raise ValueError("Selection changed; refresh.")
    repeated = _read(second.occurrences[0].layer, deadline)
    final = selection.capture(deadline)
    context = selection.document_context(deadline)
    check(deadline)
    if (
        first != second
        or second != final
        or (paths, identities) != repeated
        or final.context != context
    ):
        raise ValueError("Font, selection or own paths changed; refresh.")
    return paths
