# this_file: src/fontlabapp/metrics/worksheet/capture.py
# SPDX-License-Identifier: Apache-2.0
"""Stage complete selected-layer advances under one two-second capture budget.

Reuse the owned selected-layer reader and tabular-width identity/value fence.
findLayer may complete a native import: full getter/cache preservation remains
pending native qualification. No font writer or cache-clearing call is used.
"""

from time import monotonic

import fontlabapp.masters.layers.selection as selection
from fontlabapp.metrics.worksheet.data import Baseline, Snapshot
from fontlabapp.metrics.tabular_width.model import _read


def capture() -> Snapshot:
    """Return plain immutable facts only after two value passes and final fence."""
    deadline = monotonic() + 2.0
    first_selection = selection.capture(deadline)
    if not first_selection.occurrences:
        raise ValueError("Select glyph layers before refreshing the worksheet.")
    first = _read(first_selection, deadline)
    second_selection = selection.capture(deadline)
    second = _read(second_selection, deadline)
    final_selection = selection.capture(deadline)
    context = selection.document_context(deadline)
    if monotonic() >= deadline:
        raise TimeoutError(
            "Worksheet capture exceeded its deadline; no partial report."
        )
    if (
        first_selection != second_selection
        or second_selection != final_selection
        or context != final_selection.context
        or first != second
    ):
        raise ValueError(
            "Font, master, selection or widths changed; refresh the worksheet."
        )
    result = Snapshot(
        tuple(context),
        tuple(
            Baseline(
                o.package_id,
                o.glyph_id,
                o.layer_id,
                o.glyph_name,
                o.layer_name,
                values[3],
            )
            for o, values in zip(final_selection.occurrences, second, strict=True)
        ),
    )
    if monotonic() >= deadline:
        raise TimeoutError("Worksheet facts exceeded the capture deadline.")
    return result
