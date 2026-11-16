# this_file: src/fontlabapp/masters/layers/navigation/data.py
# SPDX-License-Identifier: Apache-2.0
"""The shared ordered-layer planner used by both public native commands."""

from dataclasses import dataclass


class NavigationRefused(ValueError):
    """A verified prewrite failure; no native writer has been invoked."""


@dataclass(frozen=True)
class Plan:
    """Exact layer change with opaque source state; no invented cursor values."""

    before_layer: str
    after_layer: str
    source_token: tuple


def plan(
    current: str,
    layers: tuple[tuple[str, str], ...],
    direction: int,
    source_token: tuple,
) -> Plan:
    """Cycle within an already associated family in original native order."""
    if type(direction) is not int or direction not in (-1, 1):
        raise ValueError("Direction must be -1 or 1")
    if type(layers) is not tuple or not layers or type(source_token) is not tuple:
        raise ValueError("Missing immutable layer/source domain")
    for row in layers:
        if (
            type(row) is not tuple
            or len(row) != 2
            or any(type(v) is not str or not v for v in row)
        ):
            raise ValueError("Invalid layer identity/name")
    identities, names = zip(*layers)
    if len(set(identities)) != len(identities) or len(set(names)) != len(names):
        raise ValueError("Ambiguous layer identity/name")
    if current not in identities:
        raise ValueError("No exact active layer")
    return Plan(
        current,
        identities[(identities.index(current) + direction) % len(identities)],
        source_token,
    )


def require_current(change: Plan, token: tuple) -> None:
    """Refuse any observable source drift immediately before writing."""
    if token != change.source_token:
        raise ValueError("Navigation source changed; capture again")
