# this_file: src/fontlabapp/qt/safe.py
"""Keep PythonQt widget pointers alive during native list conversion.

What it does:
    ``qt_list`` converts a native QList of object pointers with cyclic GC off.
    ``main_window`` finds FontLab's main window with the same safety.

Why:
    PythonQt wraps each pointer as a Python object. That allocation can start
    the cyclic collector, which can free a Python-owned widget that is still in
    the list. The next pointer then dangles and FontLab segfaults in
    ``PythonQtPrivate::wrapPtr`` (measured on FontLab 9.0.9780).

Thread rule:
    GUI thread only, and the guard enforces it. ``gc.disable()`` is process
    wide. A call from another thread could re-enable collection while the GUI
    thread is still converting. The guard does not stop an explicit
    ``gc.collect()`` or reference-count destruction.

Missing window:
    ``main_window`` raises ``MainWindowNotFound`` when FontLab has no main
    window. It is a ``RuntimeError`` with the old text, so older callers that
    catch ``RuntimeError`` or match "main window not found" keep working. New
    callers catch the class: the off-thread refusal stays a plain
    ``RuntimeError`` and is therefore never taken for a missing host.

Cold import: stdlib only. Callers pass ``fontlab`` and ``qt`` in.
"""

import gc
import threading
from collections.abc import Callable
from typing import Any

__all__ = ["MAIN_WINDOW_CLASS", "MainWindowNotFound", "main_window", "qt_list"]

#: ``className()`` of FontLab's main window, used by the fallback scan.
MAIN_WINDOW_CLASS = "MainWindow"


class MainWindowNotFound(RuntimeError):
    """FontLab has no main window (for example, during start or quit).

    Raised by ``main_window``. The message stays "FontLab main window not
    found" for callers that still match the text.
    """


def qt_list(call: Callable[..., Any], *args: Any) -> list[Any]:
    """Convert a native widget list with cyclic GC off (GUI thread only).

    Run ``list(call(*args))`` with the collector off through the native call
    and the iteration. Restore the caller's GC state even if the call or the
    conversion raises or toggles GC. Raise ``RuntimeError`` off the main thread
    before the native call starts and before GC state changes.
    """
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("qt_list must run on the GUI thread")
    enabled = gc.isenabled()
    gc.disable()
    try:
        return list(call(*args))
    finally:
        (gc.enable if enabled else gc.disable)()


def main_window(fontlab: Any, qt: Any) -> Any:
    """Return FontLab's main window; GUI thread only.

    Prefer ``fontlab.MainWindow()``. If the module lacks it or it returns
    ``None``, scan ``QApplication.topLevelWidgets()`` through ``qt_list`` for
    the first widget whose ``className()`` is ``MainWindow``. ``fontlab`` is the
    FontLab module and ``qt`` is the ``PythonQt`` module. Raise
    ``MainWindowNotFound`` if no window exists. The result is not cached;
    callers may cache it.
    """
    getter = getattr(fontlab, "MainWindow", None)
    main = getter() if callable(getter) else None
    if main is not None:
        return main
    widgets = qt_list(qt.QtGui.QApplication.topLevelWidgets)
    for widget in widgets:
        if widget.className() == MAIN_WINDOW_CLASS:
            return widget
    raise MainWindowNotFound("FontLab main window not found")
