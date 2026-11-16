# this_file: src/fontlabapp/masters/point_counts/native.py
# SPDX-License-Identifier: Apache-2.0
"""Capture each selected occurrence's stored master layers, with no font writers."""

from time import monotonic

import fontlabapp.masters.layers.selection as selection
import fontlabapp.contours.point_counts.native as reader
from fontlabapp.contours.point_counts.model import LayerCount


def _read(selected: selection.LayerSelection, deadline: float) -> tuple:
    """Reuse established own-contour counts; never inspect auxiliary contours."""
    rows = []
    for occurrence in selected.occurrences:
        reader._check(deadline)
        glyph, chosen = occurrence.glyph, occurrence.layer
        if (
            glyph.isNull
            or chosen.isNull
            or int(glyph.id) != occurrence.glyph_id
            or int(chosen.id) != occurrence.layer_id
            or str(glyph.name) != occurrence.glyph_name
            or str(chosen.name) != occurrence.layer_name
            or int(glyph.package.id) != occurrence.package_id
        ):
            raise ValueError(
                "Selected glyph or layer changed; run Point Counter again."
            )
        states = []
        for layer in glyph.layers:
            reader._check(deadline)
            master = layer.isMasterLayer
            if type(master) is not bool:
                raise ValueError("Unreadable master layer property; no partial report.")
            if not master:
                states.append((int(layer.id), False))
                continue
            if not layer.isValid:
                raise ValueError("Invalid master layer; no partial report.")
            count, shapes = reader._layer(layer, deadline)
            states.append((int(layer.id), True, count, shapes))
        rows.append((occurrence.glyph_id, tuple(states)))
    reader._check(deadline)
    return tuple(rows)


def capture() -> tuple[LayerCount, ...]:
    """Double-read the full master domain and fence selection within two seconds.

    Empty selections and glyphs without masters yield the original empty report.
    Repeated occurrences are preserved. Blocking native getters are not preempted;
    compiled-host read/order/preservation qualification remains pending.
    """
    deadline = monotonic() + 2.0
    first = selection.capture(deadline)
    rows = _read(first, deadline)
    second = selection.capture(deadline)
    repeated = _read(second, deadline)
    final = selection.capture(deadline)
    context = selection.document_context(deadline)
    reader._check(deadline)
    if (
        first != second
        or second != final
        or rows != repeated
        or context != final.context
    ):
        raise ValueError(
            "Font, selection, masters or nodes changed; run Point Counter again."
        )
    return tuple(state[2] for _, states in rows for state in states if state[1])
