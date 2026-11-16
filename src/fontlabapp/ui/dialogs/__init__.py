# this_file: src/fontlabapp/ui/dialogs/__init__.py
"""Owned dialogs and injected Qt dialog execution.

Usage inside FontLab::

    from fly.ap.ui.dialogs import run_standard_message_box
    from fly.qt import QtGui
    qt = ...  # the host PythonQt module
    parent = ...  # an existing FontLab window
    answer = run_standard_message_box(qt, parent, "Ready?", "Continue?",
                                      "Question", QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
"""

from importlib import import_module
from typing import Any

__all__ = [
    "create_dialog",
    "create_message_box",
    "run_owned_dialog",
    "run_standard_message_box",
    "run_file_dialog",
    "run_text_dialog",
    "name_filters",
]
_EXPORTS = {
    "create_dialog": "fontlabapp.qt.widgets",
    "create_message_box": "fontlabapp.qt.dialogs",
    "run_owned_dialog": "fontlabapp.qt.dialogs",
    "run_standard_message_box": "fontlabapp.qt.dialogs",
    "run_file_dialog": "fontlabapp.qt.dialogs",
    "run_text_dialog": "fontlabapp.qt.dialogs",
    "name_filters": "fontlabapp.qt.dialogs",
}


def __getattr__(name: str) -> Any:
    """Resolve one original public object only when it is requested."""
    try:
        source = _EXPORTS[name]
    except KeyError as error:
        raise AttributeError(name) from error
    value = getattr(import_module(source), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """List only the names published by this facade."""
    return sorted(__all__)
