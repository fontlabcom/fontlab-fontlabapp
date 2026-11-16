# this_file: src/fontlabapp/kerning/cutoff.py
# SPDX-License-Identifier: Apache-2.0
"""Clamp every master's explicit kerning through the qualified batch writer.

Independent implementation of Vassil Kateliev/Karandash Type Foundry's Science
Gothic Kerning Cutoff Filter v1.1 (2025). The reference has no declared licence;
its body is neither imported nor copied. Preserve all explicit pair kinds and
inclusive limits. Repair its final-master-only notification by staging every
master in one snapshot-bound transaction, including earlier-only changes.
"""

import math
from collections.abc import Mapping
from time import monotonic
from typing import Any

from fontlabapp.kerning.identity import Edits, Pair

LOWER, UPPER = -250, 100
TITLE = "Kerning Cutoff"


def plan(
    pairs: Mapping[str, Mapping[Pair, float]], *, deadline: float = math.inf
) -> Edits:
    """Retain stored master/pair order; stage only strict outliers, never absence."""
    edits: Edits = {}
    for master, values in pairs.items():
        edits[master] = {}
        for pair, value in values.items():
            if monotonic() >= deadline:
                raise TimeoutError("Kerning Cutoff exceeded its scan deadline.")
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError(
                    "Kerning Cutoff requires finite numeric source values."
                )
            if value < LOWER:
                edits[master][pair] = LOWER
            elif value > UPPER:
                edits[master][pair] = UPPER
    if monotonic() >= deadline:
        raise TimeoutError("Kerning Cutoff exceeded its scan deadline.")
    return edits


def apply(package: Any, *, expected: Any = None) -> dict[str, int]:
    """Preflight all masters/classes/pairs and write one complete native batch.

    Reuse the existing fractional-history, persistence-range and stale-source
    refusals. No-op adds no history. A failed native writer reports potentially
    partial edits with Undo guidance; no success counts escape that failure.
    No UpdateAll, glyph/cache notifications or active-master switching occurs.
    """
    from fontlabapp.kerning.batch import snapshot_kerning, write_kerning

    snapshot = snapshot_kerning(package, typed=True) if expected is None else expected
    edits = plan(snapshot.pairs)
    write_kerning(package, edits, TITLE, expected=snapshot)
    return {master: len(changes) for master, changes in edits.items()}


def run() -> dict[str, int]:
    """Execute the complete menu action and print each master's processed count.

    Open a font first. Existing Output content is preserved. This action has no
    options or subset scope, matching the original immediate all-master filter.
    Native full-font history/save/reopen qualification remains a separate gate.
    """
    from fontlabapp.core.scripting import current_package

    package = current_package()
    if package is None:
        raise ValueError("Open a font before running Kerning Cutoff.")
    counts = apply(package)
    for master, count in counts.items():
        print(
            f"{TITLE}: {master}: {count} pairs changed; inclusive [{LOWER}, {UPPER}]."
        )
    return counts
