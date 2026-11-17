# this_file: src/fontlabapp/qt/literal_text.py
# SPDX-License-Identifier: Apache-2.0
"""Lossless Qt text values without PythonQt's no-length QString ingress.

Native MIME decoding and direct QObject setter connections were measured on
FontLab 9.0.9787. All temporary objects are detached, unshown and destroyed;
no clipboard, global application state or sentinel encoding is involved.
"""

from typing import Any
from fontlabapp.qt.properties import value


def read_text(qt: Any, raw: Any) -> str:
    """Read a known QString value/const-reference, preserving empty and NUL."""
    text = (
        raw if isinstance(raw, str) else value(qt.QtCore.QStringMatcher(raw), "pattern")
    )
    if not isinstance(text, str):
        raise TypeError("Qt text value did not return a string.")
    return text


_PARAGRAPH = "\u2029"


def document_raw_text(qt: Any, document: Any) -> str:
    """Return ``QTextDocument.toRawText()``, or its block equivalent.

    FontLab's PythonQt (9.1.9813) does not wrap ``toRawText``; joining every
    block's literal text with U+2029 gives the same string for plain-text
    documents (issue 253 native check, Features Editor).
    """
    if hasattr(document, "toRawText"):
        try:
            return read_text(qt, value(document, "toRawText"))
        except Exception:  # noqa: BLE001 - a wrapper that exposes but cannot call it
            pass
    parts = []
    block = value(document, "begin")
    for _ in range(value(document, "blockCount")):  # bounded: never loop on a bad wrapper
        if not value(block, "isValid"):
            break
        parts.append(read_text(qt, value(block, "text")))
        block = value(block, "next")
    return _PARAGRAPH.join(parts)


def set_mime_text(qt: Any, mime: Any, text: str) -> None:
    """Fill an existing MIME object; its allocator and ownership stay unchanged."""
    if "\0" in text:
        mime.setData("text/plain", qt.QtCore.QByteArray(text.encode("utf-8")))
    else:
        mime.setText(text)


def _dispose(qt: Any, obj: Any) -> None:
    obj.deleteLater()
    qt.QtCore.QCoreApplication.sendPostedEvents(obj, qt.QtCore.QEvent.DeferredDelete)


def text_fragment(qt: Any, text: str) -> Any:
    """Stage one literal run (no CR/LF/PS) as a detached native cursor value.

    Paragraph identity belongs to the caller. A QTextDocumentFragment retains
    its selected native text after the staging document is destroyed. Prepare
    fragments before removing a live selection so setup failures leave it intact.
    """
    if any(separator in text for separator in ("\r", "\n", "\u2029")):
        raise ValueError("A literal fragment must contain one paragraph run.")
    mime = qt.QtCore.QMimeData()
    editor = None
    try:
        set_mime_text(qt, mime, text)
        editor = qt.QtGui.QPlainTextEdit()
        qt.QtGui.QPlainTextEdit.insertFromMimeData(editor, mime)
        cursor = editor.textCursor()
        cursor.select(qt.QtGui.QTextCursor.Document)
        return cursor.selection()
    finally:
        try:
            if editor is not None:
                _dispose(qt, editor)
        finally:
            _dispose(qt, mime)


def _set_line(qt: Any, target: Any, text: str) -> None:
    """Deliver genuine QString through the measured native receiver overload."""
    core, gui = qt.QtCore, qt.QtGui
    carrier = gui.QLineEdit()
    mime = None
    event = None
    connected = False
    native = gui.QLineEdit.__module__.split(".")[0] == "PythonQt"
    try:
        mime = core.QMimeData()
        carrier.setMaxLength(int(value(target, "maxLength")))
        set_mime_text(qt, mime, text)
        if native:
            connected = bool(
                carrier.connect(
                    b"textChanged(QString)",
                    target,
                    b"setText(QString)",
                    core.Qt.DirectConnection,
                )
            )
            if not connected:
                raise RuntimeError("Native Qt text connection failed.")
        else:
            # Standard Qt test/standalone bindings already use explicit lengths.
            carrier.textChanged.connect(
                target._literal_native_set, core.Qt.DirectConnection
            )
            connected = True
        event = gui.QDropEvent(
            core.QPointF(0, 0),
            core.Qt.CopyAction,
            mime,
            core.Qt.NoButton,
            core.Qt.NoModifier,
        )
        gui.QLineEdit.dropEvent(carrier, event)
        if not value(event, "isAccepted"):
            raise RuntimeError("Native Qt literal drop was refused.")
        # Empty text never reaches this NUL-only route: a drop must emit once.
    finally:
        try:
            if connected:
                if native:
                    if not carrier.disconnect(
                        b"textChanged(QString)", target, b"setText(QString)"
                    ):
                        raise RuntimeError("Native Qt text disconnection failed.")
                else:
                    carrier.textChanged.disconnect(target._literal_native_set)
        finally:
            event = None
            try:
                _dispose(qt, carrier)
            finally:
                if mime is not None:
                    _dispose(qt, mime)


def line_edit_type(qt: Any) -> type:
    """An ordinary line edit whose programmatic setter also accepts NUL."""
    gui = qt.QtGui

    class LineEdit(gui.QLineEdit):
        def _literal_native_set(self, text: str) -> None:
            gui.QLineEdit.setText(self, text)

        def setText(self, text: str) -> None:
            if "\0" in text:
                _set_line(qt, self, text)
            else:
                gui.QLineEdit.setText(self, text)

    return LineEdit
