# this_file: tests/test_qt_document_raw_text.py
"""document_raw_text matches toRawText when PythonQt lacks it (issue 253)."""

import pytest

QtGui = pytest.importorskip("PySide6.QtGui")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from fontlabapp.qt.literal_text import document_raw_text


class _NoRaw:
    """A QTextDocument view without toRawText, like FontLab 9.1.9813 PythonQt."""

    def __init__(self, document):
        self._document = document

    def begin(self):
        return self._document.begin()

    def blockCount(self):
        return self._document.blockCount()


class _BrokenRaw(_NoRaw):
    """Exposes toRawText but cannot call it."""

    def toRawText(self):
        raise RuntimeError("wrapper cannot call toRawText")


@pytest.mark.parametrize(
    "text",
    ["", "A", "A\nB", "A B", "line\u2028break", "nb\u00a0sp\ttab", "x\n\n", "\n", "\u0105\u0119 \u4e2d \U0001f642"],
)
def test_document_raw_text_when_toRawText_missing_then_blocks_match_it(text):
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    document = QtGui.QTextDocument()
    document.setDocumentLayout(QtWidgets.QPlainTextDocumentLayout(document))
    document.setPlainText(text)
    expected = document.toRawText()
    assert document_raw_text(None, document) == expected, "direct path uses toRawText"
    assert document_raw_text(None, _NoRaw(document)) == expected, f"block fallback differs for {text!r}"


def test_document_raw_text_when_toRawText_call_fails_then_block_fallback_used():
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    document = QtGui.QTextDocument()
    document.setDocumentLayout(QtWidgets.QPlainTextDocumentLayout(document))
    document.setPlainText("A\nB\u2028C")
    assert document_raw_text(None, _BrokenRaw(document)) == document.toRawText()
