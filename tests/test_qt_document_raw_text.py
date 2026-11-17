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


@pytest.mark.parametrize(
    "text",
    ["", "A", "A\nB", "A B", "line break", "nb sp\ttab", "x\n\n", "\n", "ąę 中 🙂"],
)
def test_document_raw_text_when_toRawText_missing_then_blocks_match_it(text):
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    document = QtGui.QTextDocument()
    document.setDocumentLayout(QtWidgets.QPlainTextDocumentLayout(document))
    document.setPlainText(text)
    expected = document.toRawText()
    assert document_raw_text(None, document) == expected, "direct path uses toRawText"
    assert document_raw_text(None, _NoRaw(document)) == expected, f"block fallback differs for {text!r}"
