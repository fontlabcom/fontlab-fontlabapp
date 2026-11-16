# this_file: tests/test_text_holder_ime_binding.py
"""Measured QString-return seam over real Qt IME, cursor and undo operations."""

from types import SimpleNamespace

import pytest
from fontlabapp.proof.text_holder.editor import editor_type, literal_text
from test_text_holder_editor import APP, QT, QtCore, QtGui

TEXT = "A😀B\nC\u2029D"
COMMIT = "中\u2029X\nY\u2028Z\u00a0😀"


class QString:
    """Native pointer return exposes string conversion, not Python regex input."""

    def __init__(self, text):
        self.text = text

    def __str__(self):
        return self.text or "QString (C++ Object 0xowned)"


class NativeCore:
    """Model the measured native value return; standalone Qt omits this class."""

    def QStringMatcher(self, raw):
        assert isinstance(raw, QString), "Python strings must bypass the bridge"
        return SimpleNamespace(pattern=lambda: raw.text)

    def __getattr__(self, name):
        return getattr(QtCore, name)


WRAPPED_QT = SimpleNamespace(QtCore=NativeCore(), QtGui=QT.QtGui)


class WrappedEvent(QtGui.QInputMethodEvent):
    def commitString(self):
        return QString(super().commitString())

    def preeditString(self):
        return QString(super().preeditString())


def close(editor):
    editor.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize(
    "anchor,position,start,length,commit,expected",
    [
        (3, 3, 0, 0, COMMIT, "A😀" + COMMIT + "B\nC\u2029D"),
        (3, 6, 0, 0, COMMIT, "A😀" + COMMIT + "\u2029D"),
        (6, 3, 0, 0, COMMIT, "A😀" + COMMIT + "\u2029D"),
        (6, 6, -3, 3, COMMIT, "A😀" + COMMIT + "\u2029D"),
        (3, 3, 1, 2, COMMIT, "A😀B" + COMMIT + "\u2029D"),
        (3, 3, 0, 3, "", "A😀\u2029D"),
    ],
)
def test_wrapped_commit_preserves_literals_selection_relative_range_and_history(
    anchor, position, start, length, commit, expected
):
    editors = [editor_type(WRAPPED_QT)(), editor_type(WRAPPED_QT)()]
    results = []
    try:
        for editor, event_type in zip(
            editors, (QtGui.QInputMethodEvent, WrappedEvent), strict=True
        ):
            editor.setPlainText(TEXT)
            cursor = editor.textCursor()
            cursor.setPosition(anchor)
            cursor.setPosition(position, QtGui.QTextCursor.KeepAnchor)
            editor.setTextCursor(cursor)
            formatting = QtGui.QTextCharFormat()
            formatting.setFontUnderline(True)
            attributes = [
                QtGui.QInputMethodEvent.Attribute(
                    QtGui.QInputMethodEvent.TextFormat, 0, 1, formatting
                ),
                QtGui.QInputMethodEvent.Attribute(
                    QtGui.QInputMethodEvent.Cursor, 1, 1, None
                ),
            ]
            event = event_type("次", attributes)
            event.setCommitString(commit, start, length)
            editor.inputMethodEvent(event)
            assert literal_text(editor) == expected
            assert QtGui.QInputMethodEvent.commitString(event) == commit
            assert QtGui.QInputMethodEvent.preeditString(event) == "次"
            assert (event.replacementStart(), event.replacementLength()) == (
                start,
                length,
            )
            assert len(event.attributes()) == 2
            cursor = editor.textCursor()
            states = [(cursor.position(), cursor.anchor())]
            # Clear preedit natively before asking for the committed undo step.
            editor.inputMethodEvent(event_type("", []))
            editor.undo()
            assert literal_text(editor) == TEXT
            states.append(
                (editor.textCursor().position(), editor.textCursor().anchor())
            )
            editor.redo()
            assert literal_text(editor) == expected
            states.append(
                (editor.textCursor().position(), editor.textCursor().anchor())
            )
            results.append(states)
        assert results[0] == results[1], "Wrapping must not change the native caret"
    finally:
        for editor in editors:
            close(editor)


def test_empty_wrapped_commit_keeps_preedit_out_of_document_and_undo():
    editor = editor_type(WRAPPED_QT)()
    try:
        editor.setPlainText(TEXT)
        cursor = editor.textCursor()
        cursor.setPosition(3)
        editor.setTextCursor(cursor)
        for preedit in ("中", "次😀", ""):
            event = WrappedEvent(preedit, [])
            editor.inputMethodEvent(event)
            assert literal_text(editor) == TEXT
            assert not editor.document().isUndoAvailable()
            assert editor.textCursor().position() == 3
            assert QtGui.QInputMethodEvent.preeditString(event) == preedit
        APP.processEvents()
    finally:
        close(editor)
