# this_file: src/fontlabapp/qt/events/resize.py
"""Injected resize forwarding for PythonQt-safe QWidget subclasses.

Call the supplied native base explicitly: PythonQt protected handlers cannot
be resolved through super(). The caller supplies its owner lookup and method
name. No Qt binding, foreign API or widget instance is imported or retained.
"""

from collections.abc import Callable
from typing import Any


def resize_event_handler(
    base: type, owner: Callable[[Any], Any], method: str
) -> Callable[[Any, Any], None]:
    """Forward event dimensions after the base handler, when an owner exists.

    Preserve the existing adapters' lookup order: test the current owner after
    base dispatch, read the event size, resolve the current owner's method,
    then read width and height. Re-read the owner because size retrieval can
    change it. Exceptions propagate unchanged; this adds no recovery policy.
    """

    def resizeEvent(widget: Any, event: Any) -> None:
        base.resizeEvent(widget, event)
        if owner(widget) is not None:
            size = event.size()
            getattr(owner(widget), method)(size.width(), size.height())

    return resizeEvent
