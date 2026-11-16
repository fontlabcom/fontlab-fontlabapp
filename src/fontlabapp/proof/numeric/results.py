# this_file: src/fontlabapp/proof/numeric/results.py
# SPDX-License-Identifier: Apache-2.0
"""Format complete metric estimates and Qt-local revision cutoff results.

Compare native Qt dates/times directly, including millisecond boundaries. Date,
time and instant cutoffs are independent. Unknown dates never become epoch0.
"""

from time import monotonic
from typing import Any

from fontlabapp.proof.numeric.model import Facts
from fontlabapp.qt.properties import value


def render(
    core: Any, facts: Facts, result: dict, controls: dict, deadline: float
) -> str:
    """Return a complete bounded report or raise, without publishing partial rows."""
    lines = [
        f"Captured UPM: {facts.upm}. Local candidates only.",
        "Glyph / Layer: integer candidate (units); decimal candidate (units); 12pt proof width (pt)",
    ]
    for row, width in zip(
        result["advances_units"], result["proof_widths_pt"], strict=True
    ):
        lines.append(f"{row[0]} / {row[1]}: {row[2]!r}; {row[3]!r}; {width!r}")
    lines.extend(
        (
            f"Effective proof zoom: {result['effective_zoom_percent']!r}%",
            f"Distinct selected glyph quotes: ${result['integer_quote_usd']!r}; ${result['decimal_quote_usd']!r}",
            "12pt advance-only estimate; no kerning or shaping. Automatic fits absolute total to 500pt.",
        )
    )
    date, time, instant = (
        value(controls[k], v)
        for k, v in (
            ("date", "date"),
            ("time", "time"),
            ("meeting", "dateTime"),
        )
    )
    counts, unknown = [0, 0, 0], 0
    for _, epoch in facts.revisions:
        if monotonic() >= deadline:
            raise TimeoutError("Revision calculation expired; no partial result.")
        if epoch is None:
            unknown += 1
            continue
        stamp = core.QDateTime.fromMSecsSinceEpoch(epoch).toLocalTime()
        counts[0] += value(stamp, "date") <= date
        counts[1] += value(stamp, "time") <= time
        counts[2] += epoch < instant.toMSecsSinceEpoch()
    lines.extend(
        (
            f"Whole-font revision cutoffs (independent): date≤{date.toString('yyyy-MM-dd')}: {counts[0]}; time≤{time.toString('HH:mm:ss.zzz')}: {counts[1]}; instant<{instant.toString('yyyy-MM-dd HH:mm:ss.zzz')}: {counts[2]}",
            f"Unknown revision dates: {unknown}",
        )
    )
    return "\n".join(lines)
