# this_file: src/fontlabapp/qt/choices.py
# SPDX-License-Identifier: MIT
"""Injected Qt editable-choice and line-edit commit mechanics.

Keep Qt5's overload filtering and user-modified commit acknowledgement together.
Callers own signal connections, continuous/quiet callback policy, conversion and
widget lifetime. No Qt binding is imported; native signals are never blocked.
"""
from typing import Any


def configure_combo(widget: Any, no_insert_policy: Any) -> None:
    """Create the editable line edit before installing the existing NoInsert policy."""
    widget.setEditable(True)
    widget.setInsertPolicy(no_insert_policy)


def accept_activation(widget: Any, args: tuple) -> bool:
    """Ignore Qt5's string overload; acknowledge the other user activation once.

    Clear the line edit's modified flag before the caller reports its callback.
    A Return matching a choice can emit both activation and editingFinished;
    the following commit then observes an already acknowledged edit.
    """
    if args and isinstance(args[0], str):
        return False
    widget.lineEdit().setModified(False)
    return True


def consume_commit(line_edit: Any) -> bool:
    """Consume one user-modified edit; a repeated Return/focus loss is silent."""
    if not line_edit.isModified():
        return False
    line_edit.setModified(False)
    return True


def set_combo_text(widget: Any, text: str) -> None:
    """Write the caller's exact text, then acknowledge its programmatic change.

    Preserve native signal timing: edit-text listeners run before the explicit
    acknowledgement. Errors propagate and no callback scope is changed here.
    """
    widget.setEditText(text)
    widget.lineEdit().setModified(False)
