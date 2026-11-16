# this_file: src/fontlabapp/metrics/offset/capture.py
# SPDX-License-Identifier: Apache-2.0
"""Capture geometric selected-layer margins without using glyph-level metrics.

Reuse ordered selection and identity/advance reads. boundingBox may populate a
native cache; complete native preservation remains an explicit acceptance gate.
No font writer, master switch, history, preference or Output operation is used.
"""

from threading import current_thread, main_thread
from time import monotonic

import fontlabapp.masters.layers.selection as selection
from fontlabapp.qt.properties import value
from fontlabapp.metrics.offset.model import Row, Snapshot, preview
from fontlabapp.metrics.tabular_width.model import _read


def check(deadline: float) -> None:
    if monotonic() >= deadline:
        raise TimeoutError("Spacing capture expired; no partial selection.")


def read(selected: selection.LayerSelection, deadline: float) -> tuple[Row, ...]:
    """Read all occurrences, including repeats and per-slot alternate layers."""
    widths = _read(selected, deadline)
    rows = []
    for occurrence, width in zip(selected.occurrences, widths, strict=True):
        check(deadline)
        layer = occurrence.layer
        left = right = None
        if int(value(layer, "shapesCount")):
            box = value(layer, "boundingBox")
            if not value(box, "isNull"):
                left, right = (
                    float(value(box, "left")),
                    width[3] - float(value(box, "right")),
                )
        rows.append(
            Row(
                occurrence.package_id,
                occurrence.glyph_id,
                occurrence.layer_id,
                occurrence.glyph_name,
                occurrence.layer_name,
                width[3],
                left,
                right,
            )
        )
        check(deadline)
    return tuple(rows)


def capture() -> Snapshot:
    """Publish complete equal scalar passes under one two-second deadline."""
    if current_thread() is not main_thread():
        raise RuntimeError("Capture selected layers on the main UI thread.")
    deadline = monotonic() + 2.0
    first = selection.capture(deadline)
    if not first.occurrences:
        raise ValueError("Select glyph layers before refreshing the spacing preview.")
    a = read(first, deadline)
    second = selection.capture(deadline)
    b = read(second, deadline)
    final = selection.capture(deadline)
    context = selection.document_context(deadline)
    check(deadline)
    if first != second or second != final or context != final.context or a != b:
        raise ValueError(
            "Selected layers, context or spacing changed; refresh all facts."
        )
    facts = Snapshot(tuple(context), b)
    preview(facts, 0)
    check(deadline)
    return facts
