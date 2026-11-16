# this_file: src/fontlabapp/masters/layers/navigation/model.py
# SPDX-License-Identifier: Apache-2.0
"""Next/previous current occurrence candidates; native qualification is pending.

Import via ``from fly.ap.masters.layers.navigation.model import next_layer, previous_layer``.
A failed result may follow a native write; it is never reported as a refusal.
"""

from dataclasses import dataclass
from typing import Any, Literal

from fontlabapp.masters.layers.navigation.data import (
    NavigationRefused,
    plan,
    require_current,
)


@dataclass(frozen=True)
class NavigationResult:
    """Structured menu outcome; occurrence_index is a source-symbol index."""

    status: Literal["changed", "unchanged", "refused", "failed"]
    reason: str
    before_layer: str | None = None
    after_layer: str | None = None
    occurrence_index: int | None = None


def _backend() -> Any:
    from fontlabapp.masters.layers.navigation.native import Backend

    return Backend()


def _navigate(direction: int) -> NavigationResult:
    try:
        backend = _backend()
        before = backend.capture()
        change = plan(before.layer, before.layers, direction, before.token)
        target = change.after_layer
        require_current(change, backend.capture().token)
    except Exception as error:  # noqa: BLE001 - native/UI boundary returns structured failures.
        return NavigationResult("refused", str(error))
    if target == before.layer:
        return NavigationResult(
            "unchanged", "Only one associated layer", target, target, before.index
        )
    try:
        backend.replace(before, target)
        backend.verify(before, target)
    except NavigationRefused as error:
        return NavigationResult(
            "refused", str(error), before.layer, target, before.index
        )
    except Exception as error:  # noqa: BLE001 - native/UI boundary returns structured failures.
        return NavigationResult(
            "failed",
            f"Native operation possibly partial: {error}",
            before.layer,
            target,
            before.index,
        )
    return NavigationResult(
        "changed",
        "Current occurrence layer changed; native qualification pending",
        before.layer,
        target,
        before.index,
    )


def next_layer() -> NavigationResult:
    """Display the next same-associated-master layer of the current occurrence."""
    return _navigate(1)


def previous_layer() -> NavigationResult:
    """Display the previous same-associated-master layer of the current occurrence."""
    return _navigate(-1)
