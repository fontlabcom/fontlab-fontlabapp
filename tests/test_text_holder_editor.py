# this_file: tests/test_text_holder_editor.py
"""Literal Unicode oracles independent of Qt's lossy plaintext export."""

import os
from types import SimpleNamespace as NS

import pytest
from fontlabapp.proof.text_holder.editor import (
    document_position,
    editor_type,
    literal_position,
    literal_text,
)

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtGui, QtTest, QtWidgets
else:
    from PySide6 import QtCore, QtGui, QtTest, QtWidgets
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
GUI = NS(
    QPlainTextEdit=QtWidgets.QPlainTextEdit,
    QTextCursor=QtGui.QTextCursor,
    QKeySequence=QtGui.QKeySequence,
)
QT = NS(QtCore=QtCore, QtGui=GUI)
SAMPLE = "😀A\nB\u00a0C\u2028D\u2029E\nF"


@pytest.fixture
def editor():
    e = editor_type(QT)()
    e.setPlainText(SAMPLE)
    yield e
    e.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize(
    "text",
    [
        SAMPLE,
        "\u2029\n\u2029",
        "x\rY\r\nZ\n",
        "\u00a0\u2028\u2029\x00\u202f\x0b\x0c\x85\u2060\ufeff\u200b\xad",
    ],
)
def test_set_read_and_utf16_positions_preserve_original_literal_text(editor, text):
    editor.setPlainText(text)
    assert literal_text(editor) == text
    for q in range(editor.document().characterCount()):
        assert document_position(editor, literal_position(editor, q)) == q


def test_unrelated_real_typing_undo_redo_preserves_distinct_ps_lf_nbsp_ls(editor):
    editor.show()
    editor.setFocus()
    QtTest.QTest.keyClicks(editor, "typed")
    assert literal_text(editor) == "typed" + SAMPLE
    editor.undo()
    assert literal_text(editor) == SAMPLE
    editor.redo()
    assert literal_text(editor) == "typed" + SAMPLE


def test_return_inside_ps_block_adds_lf_and_undo_restores_provenance(editor):
    editor.setPlainText("A\u2029BC")
    c = editor.textCursor()
    c.setPosition(3)
    editor.setTextCursor(c)
    QtTest.QTest.keyClick(editor, QtCore.Qt.Key_Return)
    assert literal_text(editor) == "A\u2029B\nC"
    editor.undo()
    assert literal_text(editor) == "A\u2029BC"
    editor.redo()
    assert literal_text(editor) == "A\u2029B\nC"


def test_local_mime_paste_copy_selection_and_history_preserve_literal_domain(editor):
    c = editor.textCursor()
    c.select(QtGui.QTextCursor.Document)
    editor.setTextCursor(c)
    mime = QtCore.QMimeData()
    mime.setText(SAMPLE)
    editor.insertFromMimeData(mime)
    assert literal_text(editor) == SAMPLE
    c = editor.textCursor()
    c.select(QtGui.QTextCursor.Document)
    editor.setTextCursor(c)
    assert editor.createMimeDataFromSelection().text() == SAMPLE
    editor.insertPlainText("Z\u2029Q\nT")
    assert literal_text(editor) == "Z\u2029Q\nT"
    editor.undo()
    assert literal_text(editor) == SAMPLE
    editor.redo()
    assert literal_text(editor) == "Z\u2029Q\nT"


def test_selection_delete_merge_and_undo_do_not_move_ps_identity(editor):
    editor.setPlainText("A\u2029B\nC\u2029D")
    c = editor.textCursor()
    c.setPosition(1)
    c.setPosition(4, QtGui.QTextCursor.KeepAnchor)
    editor.setTextCursor(c)
    editor.insertPlainText("X")
    assert literal_text(editor) == "AXC\u2029D"
    editor.undo()
    assert literal_text(editor) == "A\u2029B\nC\u2029D"
    editor.redo()
    assert literal_text(editor) == "AXC\u2029D"


def test_ime_commit_and_shift_enter_preserve_separators_without_clipboard(editor):
    editor.setPlainText("A\u2029B")
    c = editor.textCursor()
    c.setPosition(3)
    editor.setTextCursor(c)
    ev = QtGui.QInputMethodEvent()
    ev.setCommitString("X\u2029Y\nZ")
    editor.inputMethodEvent(ev)
    assert literal_text(editor) == "A\u2029BX\u2029Y\nZ"
    editor.undo()
    assert literal_text(editor) == "A\u2029B"
    editor.redo()
    assert literal_text(editor) == "A\u2029BX\u2029Y\nZ"
    QtTest.QTest.keyClick(editor, QtCore.Qt.Key_Return, QtCore.Qt.ShiftModifier)
    assert literal_text(editor) == "A\u2029BX\u2029Y\nZ\u2028"


def test_positions_refuse_outside_document_and_crlf_rounds_atomically(editor):
    editor.setPlainText("A\r\nB")
    assert document_position(editor, 2) == 1
    assert document_position(editor, 2, True) == 2
    for fn in [literal_position, document_position]:
        with pytest.raises(ValueError):
            fn(editor, 99)


def test_copy_returns_native_base_allocation_and_clears_lazy_normalized_formats():
    calls = []

    class NativeBase(QtWidgets.QPlainTextEdit):
        def createMimeDataFromSelection(self):
            result = QtWidgets.QPlainTextEdit.createMimeDataFromSelection(self)
            calls.append(result)
            return result

    # A Python-owned constructor must never supply a C++ virtual return pointer.
    guarded_core = NS(Qt=QtCore.Qt)
    gui = NS(
        QPlainTextEdit=NativeBase,
        QTextCursor=QtGui.QTextCursor,
        QKeySequence=QtGui.QKeySequence,
    )
    e = editor_type(NS(QtCore=guarded_core, QtGui=gui))()
    try:
        e.setPlainText(SAMPLE)
        c = e.textCursor()
        c.select(QtGui.QTextCursor.Document)
        e.setTextCursor(c)
        result = e.createMimeDataFromSelection()
        assert calls and result is calls[0]
        assert result.text() == SAMPLE
        assert result.formats() == ["text/plain"]
        result.deleteLater()
    finally:
        e.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize(
    "mode", ["insert", "paste", "typing", "ime", "backspace", "delete", "return"]
)
@pytest.mark.parametrize("reverse", [False, True])
def test_cross_block_selected_edit_preserves_left_boundary_and_one_undo(
    editor, mode, reverse
):
    text = "A\nB\u00a0C\u2028D\u2029EF😀\nG"
    editor.setPlainText(text)
    cursor = editor.textCursor()
    cursor.setPosition(12 if reverse else 2)
    cursor.setPosition(2 if reverse else 12, QtGui.QTextCursor.KeepAnchor)
    editor.setTextCursor(cursor)
    replacement = "X\nY\u2028Z\u00a0😀"
    if mode == "insert":
        editor.insertPlainText(replacement)
    elif mode == "paste":
        mime = QtCore.QMimeData()
        mime.setText(replacement)
        editor.insertFromMimeData(mime)
    elif mode == "ime":
        event = QtGui.QInputMethodEvent()
        event.setCommitString(replacement)
        QtWidgets.QApplication.sendEvent(editor, event)
    else:
        key, replacement = {
            "typing": (QtCore.Qt.Key_X, "x"),
            "backspace": (QtCore.Qt.Key_Backspace, ""),
            "delete": (QtCore.Qt.Key_Delete, ""),
            "return": (QtCore.Qt.Key_Return, "\n"),
        }[mode]
        event = QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress,
            key,
            QtCore.Qt.NoModifier,
            replacement if mode == "typing" else "",
        )
        QtWidgets.QApplication.sendEvent(editor, event)
    expected = "A\n" + replacement + "\nG"
    assert literal_text(editor) == expected, mode
    editor.undo()
    assert literal_text(editor) == text, mode
    editor.redo()
    assert literal_text(editor) == expected, mode


@pytest.mark.parametrize("leading", ["\n", "\u2029", "\r\n"])
@pytest.mark.parametrize("trailing", ["\n", "\u2029"])
def test_selected_boundary_matrix_keeps_prefix_suffix_and_native_history(
    editor, leading, trailing
):
    text = "A" + leading + "B\u00a0\u2028" + trailing + "C😀\nG"
    editor.setPlainText(text)
    start = document_position(editor, len(("A" + leading).encode("utf-16-le")) // 2)
    end = document_position(editor, len(text[:-2].encode("utf-16-le")) // 2)
    c = editor.textCursor()
    c.setPosition(end)
    c.setPosition(start, QtGui.QTextCursor.KeepAnchor)
    editor.setTextCursor(c)
    editor.insertPlainText("x\u2029y\nz")
    expected = "A" + leading + "x\u2029y\nz\nG"
    assert literal_text(editor) == expected
    editor.undo()
    assert literal_text(editor) == text
    editor.redo()
    assert literal_text(editor) == expected


def test_selection_navigation_and_native_undo_redo_do_not_rewrite_boundaries(editor):
    text = "A\nB\u2029C\nG"
    editor.setPlainText(text)
    c = editor.textCursor()
    c.setPosition(2)
    c.setPosition(5, QtGui.QTextCursor.KeepAnchor)
    editor.setTextCursor(c)
    QtTest.QTest.keyClick(editor, QtCore.Qt.Key_Left)
    assert literal_text(editor) == text and not editor.document().isUndoAvailable()
    editor.insertPlainText("x")
    c = editor.textCursor()
    c.setPosition(0)
    c.setPosition(6, QtGui.QTextCursor.KeepAnchor)
    editor.setTextCursor(c)
    undo = QtGui.QKeySequence(QtGui.QKeySequence.Undo)[0]
    redo = QtGui.QKeySequence(QtGui.QKeySequence.Redo)[0]
    if hasattr(undo, "toCombined"):
        undo, redo = undo.toCombined(), redo.toCombined()
    QtTest.QTest.keySequence(editor, QtGui.QKeySequence(undo))
    assert literal_text(editor) == text
    c = editor.textCursor()
    c.setPosition(0)
    c.setPosition(5, QtGui.QTextCursor.KeepAnchor)
    editor.setTextCursor(c)
    QtTest.QTest.keySequence(editor, QtGui.QKeySequence(redo))
    assert literal_text(editor) == text[:2] + "x" + text[2:]


def test_ime_offset_replacement_without_selection_preserves_untouched_boundary(editor):
    text = "A\nB\u00a0C\u2028D\u2029EF😀\nG"
    editor.setPlainText(text)
    c = editor.textCursor()
    c.setPosition(12)
    editor.setTextCursor(c)
    event = QtGui.QInputMethodEvent()
    event.setCommitString("x\u2029y\nz", -10, 10)
    QtWidgets.QApplication.sendEvent(editor, event)
    expected = "A\nx\u2029y\nz\nG"
    assert literal_text(editor) == expected
    editor.undo()
    assert literal_text(editor) == text
    editor.redo()
    assert literal_text(editor) == expected


@pytest.mark.parametrize(
    "position,offset,length", [(10, -6, 6), (2, 2, 6), (12, -10, 10)]
)
def test_ime_effective_offsets_preserve_distinct_untouched_prefix(
    editor, position, offset, length
):
    text = "A\nB\u00a0C\u2028D\u2029EF😀\nG"
    commit = "Q\u2029R\nS"
    editor.setPlainText(text)
    c = editor.textCursor()
    c.setPosition(position)
    editor.setTextCursor(c)
    event = QtGui.QInputMethodEvent()
    event.setCommitString(commit, offset, length)
    QtWidgets.QApplication.sendEvent(editor, event)
    # All offsets are UTF16 boundaries; build the expected scalar slices separately.
    raw = text.encode("utf-16-le")
    start, end = position + offset, position + offset + length
    expected = (
        raw[: start * 2].decode("utf-16-le")
        + commit
        + raw[end * 2 :].decode("utf-16-le")
    )
    assert literal_text(editor) == expected
    editor.undo()
    assert literal_text(editor) == text
    editor.redo()
    assert literal_text(editor) == expected


def test_ime_two_phase_selection_then_earlier_replacement_keeps_both_boundaries(editor):
    text = "A\nBC\u2029DE\nFG\u2029HI\nJ"
    editor.setPlainText(text)
    c = editor.textCursor()
    c.setPosition(8)
    c.setPosition(13, QtGui.QTextCursor.KeepAnchor)
    editor.setTextCursor(c)
    event = QtGui.QInputMethodEvent()
    event.setCommitString("x\u2029y\nz", -6, 4)
    QtWidgets.QApplication.sendEvent(editor, event)
    without_selection = text[:8] + text[13:]
    expected = without_selection[:2] + "x\u2029y\nz" + without_selection[6:]
    assert literal_text(editor) == expected
    editor.undo()
    assert literal_text(editor) == text
    editor.redo()
    assert literal_text(editor) == expected


def test_preedit_updates_without_commits_leave_no_spurious_undo(editor):
    text = "A\nB\u2029C\nG"
    editor.setPlainText(text)
    c = editor.textCursor()
    c.setPosition(2)
    editor.setTextCursor(c)
    for preedit in ("中", "中", ""):
        event = QtGui.QInputMethodEvent(preedit, [])
        QtWidgets.QApplication.sendEvent(editor, event)
        assert literal_text(editor) == text
        assert not editor.document().isUndoAvailable()


@pytest.mark.parametrize("reverse", [False, True])
def test_native_cursor_delete_without_python_key_handler_preserves_separator(
    editor, reverse
):
    text = "A\nB\u00a0C\u2028D\u2029EF😀\nG"
    editor.setPlainText(text)
    c = editor.textCursor()
    c.setPosition(12 if reverse else 2)
    c.setPosition(2 if reverse else 12, QtGui.QTextCursor.KeepAnchor)
    # This is the C++ removal used by native Cut/Delete, without clipboard access.
    c.removeSelectedText()
    assert literal_text(editor) == "A\n\nG"
    editor.undo()
    assert literal_text(editor) == text
    editor.redo()
    assert literal_text(editor) == "A\n\nG"


def test_ime_event_commit_fields_restored_even_when_native_preedit_handler_raises():
    class FailingBase(QtWidgets.QPlainTextEdit):
        def inputMethodEvent(self, event):
            raise RuntimeError("owned native-handler fault")

    qt = NS(
        QtCore=QtCore,
        QtGui=NS(
            QPlainTextEdit=FailingBase,
            QTextCursor=QtGui.QTextCursor,
            QKeySequence=QtGui.QKeySequence,
        ),
    )
    e = editor_type(qt)()
    try:
        e.setPlainText("A\nB\u2029C")
        c = e.textCursor()
        c.setPosition(2)
        e.setTextCursor(c)
        event = QtGui.QInputMethodEvent()
        event.setCommitString("X\u2029Y\nZ", 0, 1)
        with pytest.raises(RuntimeError, match="owned native-handler fault"):
            e.inputMethodEvent(event)
        assert (
            event.commitString(),
            event.replacementStart(),
            event.replacementLength(),
        ) == ("X\u2029Y\nZ", 0, 1)
        assert literal_text(e) == "A\nX\u2029Y\nZ\u2029C"
        e.undo()
        assert literal_text(e) == "A\nB\u2029C"
    finally:
        e.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(e, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize("reverse", [False, True])
def test_selected_return_redo_caret_and_subsequent_typing_match_native_qt(
    editor, reverse
):
    text = "P\nA\nB\u2029C\nQ"
    editor.setPlainText(text)
    native = QtWidgets.QPlainTextEdit()
    native.setPlainText(text)
    try:
        for widget in (editor, native):
            cursor = widget.textCursor()
            cursor.setPosition(7 if reverse else 2)
            cursor.setPosition(2 if reverse else 7, QtGui.QTextCursor.KeepAnchor)
            widget.setTextCursor(cursor)
            event = QtGui.QKeyEvent(
                QtCore.QEvent.KeyPress, QtCore.Qt.Key_Return, QtCore.Qt.NoModifier
            )
            QtWidgets.QApplication.sendEvent(widget, event)
            widget.undo()
            widget.redo()
        assert literal_text(editor) == "P\n\n\nQ"
        assert (editor.textCursor().position(), editor.textCursor().anchor()) == (
            native.textCursor().position(),
            native.textCursor().anchor(),
        )
        QtTest.QTest.keyClick(editor, QtCore.Qt.Key_X)
        assert literal_text(editor) == "P\n\nx\nQ"
    finally:
        native.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(native, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize("key_name", ["Key_Return", "Key_Enter"])
@pytest.mark.parametrize(
    "modifier_name",
    [
        "NoModifier",
        "ShiftModifier",
        "ControlModifier",
        "AltModifier",
        "MetaModifier",
        "KeypadModifier",
    ],
)
@pytest.mark.parametrize("selected", [False, True])
@pytest.mark.parametrize("read_only", [False, True])
def test_paragraph_key_routing_caret_history_and_readonly_match_native(
    editor, key_name, modifier_name, selected, read_only
):
    text = "P\nA\nB\u2029C\nQ"
    editor.setPlainText(text)
    native = QtWidgets.QPlainTextEdit()
    native.setPlainText(text)
    try:
        for widget in (editor, native):
            widget.setReadOnly(read_only)
            cursor = widget.textCursor()
            cursor.setPosition(2)
            if selected:
                cursor.setPosition(7, QtGui.QTextCursor.KeepAnchor)
            widget.setTextCursor(cursor)
            event = QtGui.QKeyEvent(
                QtCore.QEvent.KeyPress,
                getattr(QtCore.Qt, key_name),
                getattr(QtCore.Qt, modifier_name),
            )
            QtWidgets.QApplication.sendEvent(widget, event)

        def state(widget):
            cursor = widget.textCursor()
            return (
                widget.toPlainText(),
                cursor.position(),
                cursor.anchor(),
                widget.document().isUndoAvailable(),
                widget.document().isRedoAvailable(),
            )

        assert state(editor) == state(native)
        if not native.document().isUndoAvailable():
            assert literal_text(editor) == text
        else:
            editor.undo()
            native.undo()
            assert state(editor) == state(native)
            assert literal_text(editor) == text
            editor.redo()
            native.redo()
            assert state(editor) == state(native)
    finally:
        native.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(native, QtCore.QEvent.DeferredDelete)
