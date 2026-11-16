# this_file: src/fontlabapp/core/signals/connections.py
"""Track exact Qt signal/slot pairs and drain them before owner destruction.

Cocoa and Vanilla adapters supply their existing mutable pair list and error
route. This module imports no Qt binding, wraps no callback and owns no widget.
Call it on the signal owner's UI thread. Callers retain callback/close policy
and must supply slots supported by their Qt binding; this does not repair a
native wrapper that is already invalid or cancel queued callback delivery.
"""

from collections.abc import Callable
from typing import Any

Connections = list[tuple[Any, Callable[..., Any]]]


def track_connection(
    connections: Connections, signal: Any, slot: Callable[..., Any]
) -> None:
    """Connect first, then retain the exact pair; preserve duplicates and order.

    Connection errors propagate without recording a pair. Binding-specific
    return values remain ignored, as in the original compatibility adapters.
    """
    signal.connect(slot)
    connections.append((signal, slot))


def disconnect_connections(
    connections: Connections, report: Callable[[Exception], Any]
) -> None:
    """Pop in reverse order; report ordinary failures and continue draining.

    Only the specified slots are disconnected. A failed pair is already popped,
    matching the compatibility callers' existing behavior. A report failure or
    BaseException propagates immediately, leaving unattempted pairs available.
    A report that adds pairs makes them part of the same drain; callers must not
    continually reconnect while closing. Repeated teardown of an empty list is
    harmless. Widget ownership and callback guards remain the caller's policy.
    """
    while connections:
        signal, slot = connections.pop()
        try:
            signal.disconnect(slot)
        except Exception as error:  # noqa: BLE001 - caller owns the error route
            report(error)
