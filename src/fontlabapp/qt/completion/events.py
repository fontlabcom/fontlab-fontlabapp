# this_file: src/fontlabapp/qt/completion/events.py
# SPDX-License-Identifier: Apache-2.0
"""Keep the distinct archived completion key, cursor and focus policies.

Called by injected QTextEdit subclasses in completion_editor. Use native base
handlers explicitly for PythonQt protected methods. No original script runs.
"""

from typing import Any

from fontlabapp.qt.calendars.classic.controls import value


def under_cursor(control: Any) -> str:
    """Read Qt's complete WordUnderCursor selection without changing the draft."""
    cursor = control.widget.textCursor()
    cursor.select(control.gui.QTextCursor.WordUnderCursor)
    return str(value(cursor, "selectedText"))


def insert(control: Any, word: str) -> None:
    """Preserve each source's suffix rule and insertion point."""
    completer = control.completer
    if control._closed or completer is None:
        return
    cursor, mode = control.widget.textCursor(), control.gui.QTextCursor
    if control.official:
        if value(completer, "widget") is not control.widget:
            return
        extra = len(word) - len(str(value(completer, "completionPrefix")))
        if extra <= 0:
            return
        cursor.movePosition(mode.Left)
        cursor.movePosition(mode.EndOfWord)
        cursor.insertText(word[-extra:])
    else:
        cursor.select(mode.WordUnderCursor)
        prefix = str(value(cursor, "selectedText"))
        if not word.casefold().startswith(prefix.casefold()):
            return
        cursor.clearSelection()
        cursor.movePosition(mode.EndOfWord)
        cursor.insertText(word[len(prefix) :])
    control.widget.setTextCursor(cursor)


def key_press(control: Any, event: Any) -> None:
    """Forward popup terminal keys, else run the complete original trigger rule."""
    if control._closed:
        return
    qt, completer = control.core.Qt, control.completer
    popup = completer.popup() if completer is not None else None
    key, modifiers, text = event.key(), event.modifiers(), str(event.text())
    if (
        popup is not None
        and popup.isVisible()
        and key
        in {qt.Key_Enter, qt.Key_Return, qt.Key_Escape, qt.Key_Tab, qt.Key_Backtab}
    ):
        event.ignore()
        return
    shortcut = key == qt.Key_E and bool(modifiers & qt.ControlModifier)
    if completer is None or not shortcut:
        control.gui.QTextEdit.keyPressEvent(control.widget, event)
    if completer is None:
        return
    prefix = under_cursor(control)
    control.prefix = prefix
    if control.official:
        ctrl_shift = modifiers & (qt.ControlModifier | qt.ShiftModifier)
        if ctrl_shift and not text:
            return
        disallowed = modifiers != qt.NoModifier and not ctrl_shift
        ending = bool(text) and text[-1] in "~!@#$%^&*()_+{}|:\"<>?,./;'[]\\-="
    else:
        disallowed = modifiers & (qt.ControlModifier | qt.AltModifier | qt.MetaModifier)
        ending = bool(text) and not text[-1].isalpha()
    if not shortcut and (len(prefix) < 3 or disallowed or not text or ending):
        popup.hide()
        return
    if not control.official or prefix != str(value(completer, "completionPrefix")):
        completer.setCompletionPrefix(prefix)
        if control.official:
            popup.setCurrentIndex(completer.completionModel().index(0, 0))
    rect = control.widget.cursorRect()
    # QTextEdit cursor rectangles are caret-wide; both popups need content width.
    rect.setWidth(
        popup.sizeHintForColumn(0)
        + value(popup.verticalScrollBar(), "sizeHint").width()
    )
    completer.complete(rect)
