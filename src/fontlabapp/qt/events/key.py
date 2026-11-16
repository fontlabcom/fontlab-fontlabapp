# this_file: src/fontlabapp/qt/events/key.py
"""Injected key-press routing for PythonQt-safe widget subclasses.

Assign the returned method as ``keyPressEvent`` on a Python subclass. The caller
keeps key, owner and callback policy; a truthy handled result accepts the event.
Other events call the supplied native base directly, because PythonQt protected
handlers cannot be resolved through super(). Imports stay host-free.
"""

from collections.abc import Callable
from typing import Any


def key_press_handler(
    base: type, handle: Callable[[Any, Any], bool]
) -> Callable[[Any, Any], None]:
    """Accept a handled key once, else call the explicit base once.

    Return values stay None. Policy, acceptance and base exceptions propagate
    unchanged; no fallback runs after a failing stage. The closure retains no
    widget or owner itself, so callers keep their existing cleanup policy.
    """

    def keyPressEvent(widget: Any, event: Any) -> None:
        if handle(widget, event):
            event.accept()
            return
        base.keyPressEvent(widget, event)

    return keyPressEvent
