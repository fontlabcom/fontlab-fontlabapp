# this_file: src/fontlabapp/metrics/vertical/model.py
# SPDX-License-Identifier: Apache-2.0
"""Complete vertical-metric comparison, adapted from Pedro Arilla (see NOTICE).

Compare every font/master value, including unset versus explicit zero. Native
capture uses stored FontLab settings rather than imported Glyphs metadata or
simulated export results. Keep the original eight-key order and report text.
"""

from dataclasses import dataclass
from math import isfinite

Scalar = int | float | None
KEYS = (
    "typoAscender",
    "typoDescender",
    "typoLineGap",
    "hheaAscender",
    "hheaDescender",
    "hheaLineGap",
    "winDescent",
    "winAscent",
)


@dataclass(frozen=True)
class MasterMetrics:
    """One master; repeated display labels remain separate native identities."""

    font_id: int
    document: str
    master: str
    values: tuple[Scalar, ...]

    def __post_init__(self) -> None:
        """Reject incomplete or non-finite rows before any report is published."""
        if len(self.values) != len(KEYS) or any(
            value is not None
            and not (type(value) is int or (type(value) is float and isfinite(value)))
            for value in self.values
        ):
            raise ValueError("Every master needs eight finite numeric/unset metrics.")


@dataclass(frozen=True)
class MetricsReport:
    """One complete immutable snapshot, including its display time."""

    rows: tuple[MasterMetrics, ...]
    time: str

    def __post_init__(self) -> None:
        """Correct the source's misleading empty-domain eight-success report."""
        if not self.rows:
            raise ValueError(
                "Open fonts with masters before reporting vertical metrics."
            )

    @property
    def fonts(self) -> int:
        """Count native documents, not distinct display names."""
        return len({row.font_id for row in self.rows})


def render(report: MetricsReport) -> str:
    """Show all values for a mismatched metric, including reference/matching rows."""
    lines = ["Vertical metrics reporter @ " + report.time]
    for index, key in enumerate(KEYS):
        values = [row.values[index] for row in report.rows]
        matches = values[1:] == values[:-1]
        lines.append("\t" + ("✅ " if matches else "❌ ") + key)
        if not matches:
            lines.extend(
                f"\t\t{row.values[index]} @ {row.document}/{row.master}"
                for row in report.rows
            )
    return "\n".join([*lines, "Vertical metrics reported.", ""])
