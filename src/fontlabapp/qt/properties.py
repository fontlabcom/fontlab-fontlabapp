# this_file: src/fontlabapp/qt/properties.py
# SPDX-License-Identifier: MIT
"""Read an explicit known Qt property across value and method bindings.

Import no binding. Callers select known names; this is not a property scanner.
"""

from typing import Any


def value(owner: Any, name: str) -> Any:
    """Get once and call once if callable; preserve values and access errors."""
    item = getattr(owner, name)
    return item() if callable(item) else item


_DEFAULT_DRAG_DISTANCE = 10


def start_drag_distance(application: Any) -> int:
    """Return Qt's drag threshold, read from the instance first.

    FontLab PythonQt exposes ``startDragDistance`` as ``None`` on the
    ``QApplication`` class and as a number only on ``QApplication.instance()``
    (A2 report 15 section 2b). Fall back to the class value, then to Qt's
    default of 10, when no instance or number is available.
    """
    finder = getattr(application, "instance", None)
    instance = finder() if callable(finder) else None
    for owner in (instance, application):
        if owner is None:
            continue
        found = getattr(owner, "startDragDistance", None)
        found = found() if callable(found) else found
        if isinstance(found, int) and not isinstance(found, bool):
            return found
    return _DEFAULT_DRAG_DISTANCE
