# this_file: src/fontlabapp/proof/text_holder/editor.py
# SPDX-License-Identifier: Apache-2.0
"""Literal text over Qt blocks, with separator provenance in native undo data.

Qt's plaintext exporter folds NBSP/LS/PS. Block text preserves NBSP/LS;
undo-aware paragraph character formats distinguish authored PS from LF.
Paragraph-format merges cannot move a surviving separator's identity.
No original source body, shadow history or undocumented toRawText is used.
"""

import re
from typing import Any

from fontlabapp.qt.properties import value
from fontlabapp.qt.literal_text import read_text, set_mime_text, text_fragment
from fontlabapp.proof.text_holder.model import index_at, utf16_units

# QTextFormat.UserProperty begins at 0x100000; this private document owns its key.
SEPARATOR = 0x100000 + 0x5448
BREAKS = re.compile(r"(\r\n|[\r\n\u2029])")


def _segments(editor: Any) -> Any:
    """Yield document/source starts, document length and literal text per run."""
    block = editor.document().firstBlock()
    document = literal = 0
    while value(block, "isValid"):
        if document:
            separator = block.charFormat().property(SEPARATOR) or "\n"
            yield document - 1, literal, 1, separator
            literal += utf16_units(separator)
        text = value(block, "text")
        size = utf16_units(text)
        yield document, literal, size, text
        document += size + 1
        literal += size
        block = block.next()


def literal_text(editor: Any) -> str:
    """Read literal block text and its exact authored separator, never toPlainText."""
    return "".join(segment[3] for segment in _segments(editor))


def _position(editor: Any, position: int, source: bool, upper: bool = False) -> int:
    for document, literal, size, text in _segments(editor):
        start, length, target, width = (
            (literal, utf16_units(text), document, size)
            if source
            else (document, size, literal, utf16_units(text))
        )
        if start <= position <= start + length:
            offset = position - start
            if length == width:
                return target + offset
            return target + (width if offset == length or (offset and upper) else 0)
    raise ValueError("Position is outside the literal text document.")


def literal_position(editor: Any, position: int) -> int:
    """Map native cursor positions to literal UTF16; a CRLF block is atomic."""
    return _position(editor, position, False)


def document_position(editor: Any, position: int, upper: bool = False) -> int:
    """Map a literal Find boundary to Qt, highlighting an intersected CRLF block."""
    return _position(editor, position, True, upper)


def _prepare(qt: Any, text: str) -> tuple:
    parts = BREAKS.split(text)
    fragments = {
        i: text_fragment(qt, run)
        for i, run in enumerate(parts)
        if i % 2 == 0 and "\0" in run
    }
    return parts, fragments


def _insert(cursor: Any, parts: list[str], fragments: dict) -> None:
    def insert(index: int) -> None:
        if index in fragments:
            cursor.insertFragment(fragments[index])
        else:
            cursor.insertText(parts[index])

    cursor.removeSelectedText()
    insert(0)
    for index in range(1, len(parts), 2):
        separator = parts[index]
        formatting = cursor.charFormat()
        formatting.setProperty(SEPARATOR, separator)
        cursor.insertBlock(cursor.blockFormat(), formatting)
        insert(index + 1)


def editor_type(qt: Any) -> type:
    """Create an ordinary editable Qt widget whose own ingress retains literals."""
    gui = qt.QtGui

    class Editor(gui.QPlainTextEdit):
        def setPlainText(self, text: str) -> None:
            prepared = _prepare(qt, text)
            gui.QPlainTextEdit.setPlainText(self, "")
            document = self.document()
            document.setUndoRedoEnabled(False)
            cursor = self.textCursor()
            _insert(cursor, *prepared)
            cursor.setPosition(0)
            self.setTextCursor(cursor)
            document.setUndoRedoEnabled(True)

        def insertPlainText(self, text: str) -> None:
            if value(self, "isReadOnly"):
                return
            self._insert_prepared(_prepare(qt, text))

        def _replace_range(self, start: int, end: int, text: str) -> None:
            # Prepare before changing even the live selection or its direction.
            prepared = _prepare(qt, text)
            cursor = self.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(end, gui.QTextCursor.KeepAnchor)
            self.setTextCursor(cursor)
            self._insert_prepared(prepared)

        def _insert_prepared(self, prepared: tuple) -> None:
            cursor = self.textCursor()
            cursor.beginEditBlock()
            try:
                _insert(cursor, *prepared)
            finally:
                cursor.endEditBlock()
            self.setTextCursor(cursor)

        def insertFromMimeData(self, source: Any) -> None:
            self.insertPlainText(read_text(qt, value(source, "text")))

        def createMimeDataFromSelection(self) -> Any:
            cursor = self.textCursor()
            text = literal_text(self)
            start = literal_position(self, int(value(cursor, "selectionStart")))
            end = literal_position(self, int(value(cursor, "selectionEnd")))
            # The native factory returns Qt-owned data. An ownerless Python
            # QMimeData can die when PythonQt decrefs a virtual return wrapper.
            mime = gui.QPlainTextEdit.createMimeDataFromSelection(self)
            # Qt's lazy fragment would otherwise overwrite setText on first read.
            value(mime, "text")
            mime.clear()
            set_mime_text(qt, mime, text[index_at(text, start) : index_at(text, end)])
            return mime

        def keyPressEvent(self, event: Any) -> None:
            if value(self, "isReadOnly") or not event.matches(
                gui.QKeySequence.InsertParagraphSeparator
            ):
                gui.QPlainTextEdit.keyPressEvent(self, event)
                return
            cursor = self.textCursor()
            cursor.beginEditBlock()
            try:
                cursor.removeSelectedText()
                formatting = cursor.charFormat()
                formatting.setProperty(SEPARATOR, "\n")
                # A collapsed cursor changes insertion style only. Native Return
                # inserts the tagged separator as its actual final undo command.
                cursor.setCharFormat(formatting)
                self.setTextCursor(cursor)
                gui.QPlainTextEdit.keyPressEvent(self, event)
            finally:
                cursor.endEditBlock()

        def inputMethodEvent(self, event: Any) -> None:
            if value(self, "isReadOnly"):
                return
            cursor = self.textCursor()
            text = read_text(qt, value(event, "commitString"))
            # Copy before clearing the original: its const-reference aliases its
            # own QString member. The copied native value restores NUL losslessly.
            saved_event = gui.QInputMethodEvent(event) if "\0" in text else None
            start = int(value(event, "replacementStart"))
            length = int(value(event, "replacementLength"))
            prepared = _prepare(qt, text)
            cursor.beginEditBlock()
            try:
                if text or length:
                    # Qt removes selection first, then applies the relative span.
                    # Insert native undo-aware separator formats before the text,
                    # so Redo's final cursor command remains the actual insertion.
                    cursor.removeSelectedText()
                    edit = gui.QTextCursor(cursor)
                    edit.setPosition(int(value(cursor, "position")) + start)
                    edit.setPosition(
                        int(value(edit, "position")) + length,
                        gui.QTextCursor.KeepAnchor,
                    )
                    _insert(edit, *prepared)
                    self.setTextCursor(cursor)
                    event.setCommitString("", 0, 0)
                try:
                    gui.QPlainTextEdit.inputMethodEvent(self, event)
                finally:
                    event.setCommitString(
                        value(saved_event, "commitString")
                        if saved_event is not None
                        else text,
                        start,
                        length,
                    )
            finally:
                cursor.endEditBlock()

    return Editor
