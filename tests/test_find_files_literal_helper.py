# this_file: tests/test_find_files_literal_helper.py
"""Complete admitted helper API controls on the Find Files binding namespace."""

from types import SimpleNamespace as NS

import pytest
from fontlabapp.qt.literal_text import (
    line_edit_type,
    read_text,
    set_mime_text,
    text_fragment,
)
from test_find_files_literal import C, W
from test_find_files_literal import (
    panel as panel,  # noqa: PLC0414 - pytest fixture export
)


@pytest.mark.parametrize("text", ["", "\0", "A\0B", "\0中😀\u2028\0é"])
def test_native_mime_fragment_owns_exact_literal_after_staging_cleanup(panel, text):
    _, _, qt = panel
    mime = C.QMimeData()
    editor = W.QPlainTextEdit()
    try:
        set_mime_text(qt, mime, text)
        assert read_text(qt, mime.text()) == text
        fragment = text_fragment(qt, text)
        cursor = editor.textCursor()
        cursor.insertFragment(fragment)
        # QTextDocument's ordinary plain getter converts LS to LF; characterAt
        # reads the actual stored literal positions without that export policy.
        doc = editor.document()
        chars = "".join(
            str(doc.characterAt(i)) for i in range(doc.characterCount() - 1)
        )
        expected_units = text.encode("utf-16-le")
        assert chars.encode("utf-16-le", "surrogatepass") == expected_units
    finally:
        for obj in (editor, mime):
            obj.deleteLater()
            C.QCoreApplication.sendPostedEvents(obj, C.QEvent.DeferredDelete)


@pytest.mark.parametrize("separator", ["\r", "\n", "\u2029"])
def test_fragment_refuses_paragraphs_before_any_staging_widget(panel, separator):
    _, _, qt = panel
    with pytest.raises(ValueError, match="one paragraph"):
        text_fragment(qt, "A\0" + separator + "B")


def test_value_reader_uses_by_value_matcher_and_refuses_nonstring():
    raw = object()
    qt = NS(QtCore=NS(QStringMatcher=lambda value: NS(pattern=lambda: "\0😀")))
    assert read_text(qt, raw) == "\0😀"
    qt.QtCore.QStringMatcher = lambda value: NS(pattern=23)
    with pytest.raises(TypeError, match="did not return a string"):
        read_text(qt, raw)


@pytest.mark.parametrize("failure", [None, "connect", "disconnect"])
def test_line_bridge_uses_native_receiver_and_releases_temporaries(panel, failure):
    _, _, qt = panel
    destroyed, calls = [], []

    class NativeLine(W.QLineEdit):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.destroyed.connect(lambda *args: destroyed.append(True))

        def connect(self, signal, target, slot, kind):
            calls.append((signal, slot))
            if failure == "connect":
                return False
            self._owned_receiver = lambda text: W.QLineEdit.setText(target, text)
            self.textChanged.connect(self._owned_receiver, kind)
            return True

        def disconnect(self, signal, target, slot):
            self.textChanged.disconnect(self._owned_receiver)
            calls.append("disconnected")
            return failure != "disconnect"

    NativeLine.__module__ = "PythonQt.QtGui"
    qt.QtGui.QLineEdit = NativeLine
    line = line_edit_type(qt)()
    try:
        if failure:
            with pytest.raises(RuntimeError, match="connection|disconnection"):
                line.setText("A\0😀B")
        else:
            line.setText("A\0😀B")
            assert line.text() == "A\0😀B"
        assert calls[0] == (b"textChanged(QString)", b"setText(QString)")
        assert destroyed == [True]
    finally:
        line.deleteLater()
        C.QCoreApplication.sendPostedEvents(line, C.QEvent.DeferredDelete)
    assert destroyed == [True, True]
