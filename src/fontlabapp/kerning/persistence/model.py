# this_file: src/fontlabapp/kerning/persistence/model.py
# SPDX-License-Identifier: Apache-2.0
"""Read explicit kerning against the measured FontLab 9.0.9784 VFJ load clamp.

Only values outside +/-2*UPM are flagged by this particular check. A row within
the range is not a universal persistence guarantee. No font/master activation,
save, history initialization or mutation is performed.
"""

import math
from dataclasses import dataclass
from typing import Any

from fontlabapp.core.scripting import current_package, kerning_pairs


@dataclass(frozen=True)
class AuditSnapshot:
    """Immutable complete master/pair values and bound font identity."""

    package_id: int
    masters: tuple[str, ...]
    master: str
    upm: int | float
    pairs: tuple[tuple[str, tuple[tuple[str, str, int | float], ...]], ...]


@dataclass(frozen=True)
class AuditRow:
    """One explicit pair, including safe endpoints and explicit zero."""

    master: str
    upm: int | float
    left: str
    right: str
    value: int | float
    at_risk: bool
    reason: str


def _finite(value: Any, message: str) -> None:
    try:
        valid = (
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(value)
        )
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(message)


def _read(package: Any) -> AuditSnapshot:
    if package is None or current_package(package.id) is None:
        raise ValueError("The original font is no longer current; reopen this tool.")
    masters, master, upm = tuple(package.masters), package.master, package.upm
    _finite(upm, "UPM must be a finite positive number with a finite twice-UPM limit.")
    _finite(2 * upm, "UPM needs a finite twice-UPM limit.")
    if upm <= 0:
        raise ValueError("UPM must be positive with a finite twice-UPM limit.")
    if (
        not masters
        or any(not isinstance(name, str) or not name for name in masters)
        or len(set(masters)) != len(masters)
        or master not in masters
    ):
        raise ValueError("The font has an invalid or unknown master domain.")
    pairs = []
    for name in masters:
        values = kerning_pairs(package, name)
        for pair, value in values.items():
            if (
                not isinstance(pair, tuple)
                or len(pair) != 2
                or any(
                    not isinstance(side, str) or not side or side == "@"
                    for side in pair
                )
            ):
                raise ValueError(f"Invalid explicit kerning pair on {name}: {pair!r}")
            _finite(
                value,
                f"Invalid finite kerning value on {name}: {pair[0]} {pair[1]} = {value!r}",
            )
        pairs.append(
            (
                name,
                tuple(
                    (left, right, value)
                    for (left, right), value in sorted(values.items())
                ),
            )
        )
    if current_package(package.id) is None or (
        tuple(package.masters),
        package.master,
        package.upm,
    ) != (masters, master, upm):
        raise ValueError("Font, masters or UPM changed during the audit; refresh.")
    return AuditSnapshot(package.id, masters, master, upm, tuple(pairs))


def capture(package: Any) -> AuditSnapshot:
    """Read/recheck every explicit master pair before publishing any result."""
    before = _read(package)
    if _read(package) != before:
        raise ValueError("Kerning source changed during the audit; refresh.")
    return before


def ensure_snapshot(package: Any, expected: AuditSnapshot) -> None:
    """Refuse changed font, active/master domain, UPM, pair membership or values."""
    if expected is None or capture(package) != expected:
        raise ValueError("Kerning results are stale; refresh or reopen this tool.")


def report(
    snapshot: AuditSnapshot, *, all_masters: bool = False
) -> tuple[AuditRow, ...]:
    """Report all explicit pairs; absence is never synthesized as a zero pair."""
    limit = 2 * snapshot.upm
    rows = []
    for master, pairs in snapshot.pairs:
        if not all_masters and master != snapshot.master:
            continue
        for left, right, value in pairs:
            risk = abs(value) > limit
            if risk:
                clipped = limit if value > 0 else -limit
                reason = f"FontLab 9.0.9784 VFJ load: outside +/-{limit:g} (2*UPM); clips to {clipped:+g} and marks the pair."
            else:
                reason = f"Within FontLab 9.0.9784 measured +/-{limit:g} VFJ load range; this check finds no clipping risk."
            rows.append(
                AuditRow(master, snapshot.upm, left, right, value, risk, reason)
            )
    return tuple(rows)
