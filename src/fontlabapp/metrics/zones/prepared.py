# this_file: src/fontlabapp/metrics/zones/prepared.py
# SPDX-License-Identifier: Apache-2.0
"""Owned preparation results, never attached to a font by their construction.

These values retain live native handles. Dropping them releases Python ownership;
do not call native release/delete on a source object. Frozen containers do not
make the native objects immutable or prove graph isolation. Native acceptance
must qualify ownership, payload coverage and complete source preservation.
"""

from dataclasses import dataclass
from typing import Any

from fontlabapp.metrics.zones.write_plan import WritePlan


@dataclass(frozen=True)
class PreparedMaster:
    """One complete master's prepared rows and their exact current payloads."""

    master: str
    guides: tuple[Any, ...]
    payloads: tuple[bytes, ...]


@dataclass(frozen=True)
class PreparedBatch:
    """Whole prepared batch with its complete source/operation plan; no commit."""

    plan: WritePlan
    masters: tuple[PreparedMaster, ...]
