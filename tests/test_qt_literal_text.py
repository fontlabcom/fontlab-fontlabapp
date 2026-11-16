# this_file: tests/test_qt_literal_text.py
"""Literal values at an intentionally truncating PythonQt-shaped boundary."""

import os
from types import SimpleNamespace as NS
import pytest

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtGui, QtWidgets
else:
    from PySide6 import QtCore, QtGui, QtWidgets
from fontlabapp.qt.literal_text import (
    read_text,
    set_mime_text,
    line_edit_type,
    text_fragment,
)
from fontlabapp.proof.text_holder.editor import editor_type, literal_text

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class Cursor(QtGui.QTextCursor):
    def insertText(self, text, *args):
        super().insertText(text.split("\0")[0], *args)


class Plain(QtWidgets.QPlainTextEdit):
    def textCursor(self):
        return Cursor(super().textCursor())


class Mime(QtCore.QMimeData):
    def setText(self, text):
        super().setText(text.split("\0")[0])


GUI = NS(
    **{
        name: getattr(QtWidgets, name)
        for name in dir(QtWidgets)
        if name.startswith("Q")
    }
)
for name in dir(QtGui):
    if name.startswith("Q"):
        setattr(GUI, name, getattr(QtGui, name))
GUI.QPlainTextEdit = Plain
GUI.QTextCursor = Cursor
CORE = NS(
    **{name: getattr(QtCore, name) for name in dir(QtCore) if name.startswith("Q")}
)
CORE.QMimeData = Mime
QT = NS(QtCore=CORE, QtGui=GUI)
VECTORS = ["", "\0", "\0A", "A\0B", "A\0", "\0\0", "é\0中", "😀\0Z", "\0😀\0中\0"]


def flush():
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize("text", VECTORS)
def test_mime_fragment_and_line_preserve_all_measured_values(text):
    mime = Mime()
    line = line_edit_type(QT)()
    target = Plain()
    try:
        set_mime_text(QT, mime, text)
        assert read_text(QT, mime.text()) == text
        line.setText(text)
        assert (
            line.text() == text
            and line.cursorPosition() == len(text.encode("utf-16-le")) // 2
        )
        cursor = target.textCursor()
        cursor.insertFragment(text_fragment(QT, text))
        assert target.toPlainText() == text
        assert cursor.position() == len(text.encode("utf-16-le")) // 2
    finally:
        for obj in [target, line, mime]:
            obj.deleteLater()
        flush()


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("mode", ["insert", "mime", "ime"])
def test_editor_nul_ls_ps_selection_one_undo_redo_exact_caret(reverse, mode):
    e = editor_type(QT)()
    text = "😀A\0\nB\u00a0C\u2028D\u2029E\0F"
    replacement = "Q\0R\u2029S\nT\u2028\0😀"
    try:
        e.setPlainText(text)
        assert literal_text(e) == text
        c = e.textCursor()
        c.setPosition(12 if reverse else 4)
        c.setPosition(4 if reverse else 12, Cursor.KeepAnchor)
        e.setTextCursor(c)
        if mode == "insert":
            e.insertPlainText(replacement)
        elif mode == "mime":
            m = Mime()
            set_mime_text(QT, m, replacement)
            e.insertFromMimeData(m)
            m.deleteLater()
        else:
            event = QtGui.QInputMethodEvent()
            event.setCommitString(replacement)
            e.inputMethodEvent(event)
            assert event.commitString() == replacement
        expected = (
            text.encode("utf-16-le")[:8].decode("utf-16-le")
            + replacement
            + text.encode("utf-16-le")[24:].decode("utf-16-le")
        )
        assert literal_text(e) == expected
        after = (e.textCursor().position(), e.textCursor().anchor())
        e.undo()
        assert literal_text(e) == text
        e.redo()
        assert literal_text(e) == expected
        assert (e.textCursor().position(), e.textCursor().anchor()) == after
        e.insertPlainText("x")
        assert "x" in literal_text(e)
    finally:
        e.deleteLater()
        flush()


@pytest.mark.parametrize("mode", ["insert", "mime", "ime"])
def test_readonly_refuses_before_history_or_selection_change(mode):
    e = editor_type(QT)()
    e.setPlainText("A\0B")
    e.setReadOnly(True)
    c = e.textCursor()
    c.select(Cursor.Document)
    e.setTextCursor(c)
    before = (c.position(), c.anchor())
    try:
        if mode == "insert":
            e.insertPlainText("X\0Y")
        elif mode == "mime":
            m = Mime()
            set_mime_text(QT, m, "X\0Y")
            e.insertFromMimeData(m)
            m.deleteLater()
        else:
            event = QtGui.QInputMethodEvent()
            event.setCommitString("X\0Y")
            e.inputMethodEvent(event)
        assert literal_text(e) == "A\0B"
        assert (e.textCursor().position(), e.textCursor().anchor()) == before
        assert not e.document().isUndoAvailable()
    finally:
        e.deleteLater()
        flush()


@pytest.mark.parametrize("text", ["\0\u2028\u2029", "\0\nX", "A\r\0B", "\0" * 4])
def test_line_setter_keeps_full_native_qstring_even_separators(text):
    line = line_edit_type(QT)()
    try:
        line.setText(text)
        assert line.text() == text
    finally:
        line.deleteLater()
        flush()


@pytest.mark.parametrize("mode", ["set", "insert", "ime"])
def test_staging_failure_leaves_editor_bytes_selection_and_history_exact(
    monkeypatch, mode
):
    import fontlabapp.proof.text_holder.editor as module

    e = editor_type(QT)()
    e.setPlainText("A\0B\u2029C")
    c = e.textCursor()
    c.setPosition(4)
    c.setPosition(1, Cursor.KeepAnchor)
    e.setTextCursor(c)
    before = (c.position(), c.anchor(), e.document().isUndoAvailable())

    def fail(*args):
        raise RuntimeError("owned fragment setup failure")

    monkeypatch.setattr(module, "text_fragment", fail)
    try:
        with pytest.raises(RuntimeError, match="fragment setup"):
            if mode == "set":
                e.setPlainText("X\0Y")
            elif mode == "insert":
                e.insertPlainText("X\0Y")
            else:
                event = QtGui.QInputMethodEvent()
                event.setCommitString("X\0Y")
                e.inputMethodEvent(event)
        assert literal_text(e) == "A\0B\u2029C"
        assert (
            e.textCursor().position(),
            e.textCursor().anchor(),
            e.document().isUndoAvailable(),
        ) == before
    finally:
        e.deleteLater()
        flush()


def test_native_receiver_overload_and_disconnect_are_exercised():
    calls = []

    class NativeLine(QtWidgets.QLineEdit):
        def connect(self, signal, target, slot, kind):
            calls.append((signal, slot, kind))
            self.receiver = lambda text: QtWidgets.QLineEdit.setText(target, text)
            self.textChanged.connect(self.receiver, kind)
            return True

        def disconnect(self, signal, target, slot):
            self.textChanged.disconnect(self.receiver)
            calls.append("disconnect")
            return True

    NativeLine.__module__ = "PythonQt.QtGui"
    qt = NS(QtCore=CORE, QtGui=NS(**{**vars(GUI), "QLineEdit": NativeLine}))
    line = line_edit_type(qt)()
    try:
        line.setText("A\0😀B")
        assert line.text() == "A\0😀B"
        assert calls[0][:2] == (b"textChanged(QString)", b"setText(QString)")
        assert calls[-1] == "disconnect"
    finally:
        line.deleteLater()
        flush()


@pytest.mark.parametrize("failure", ["connection", "drop", "mime", "editor"])
def test_owned_bridge_failures_destroy_temporaries(failure):
    destroyed = []

    class Line(QtWidgets.QLineEdit):
        def __init__(self):
            super().__init__()
            self.destroyed.connect(lambda *args: destroyed.append("line"))

        def connect(self, *args):
            return False

    class BrokenMime(Mime):
        def __init__(self):
            super().__init__()
            self.destroyed.connect(lambda *args: destroyed.append("mime"))

        def setData(self, *args):
            raise RuntimeError("mime failure")

    class RefusedDrop(QtGui.QDropEvent):
        def isAccepted(self):
            return False

    def broken_editor():
        raise RuntimeError("editor failure")

    Line.__module__ = "PythonQt.QtGui"
    core = NS(**vars(CORE))
    gui = NS(**vars(GUI))
    if failure == "connection":
        gui.QLineEdit = Line
    if failure == "drop":
        gui.QDropEvent = RefusedDrop
    if failure in ["mime", "editor"]:
        core.QMimeData = BrokenMime
    if failure == "editor":
        core.QMimeData = Mime
        gui.QPlainTextEdit = broken_editor
    qt = NS(QtCore=core, QtGui=gui)
    if failure == "editor":
        with pytest.raises(RuntimeError, match="editor failure"):
            text_fragment(qt, "X\0Y")
    else:
        line = line_edit_type(qt)()
        try:
            with pytest.raises(RuntimeError):
                line.setText("X\0Y")
        finally:
            line.deleteLater()
            flush()
    if failure == "connection":
        assert len(destroyed) == 2
    if failure == "mime":
        assert destroyed == ["mime"]


def test_reader_value_reference_and_rejected_unknown_type():
    class Matcher:
        def __init__(self, raw):
            self.pattern = raw.text

    qt = NS(QtCore=NS(QStringMatcher=Matcher))
    assert read_text(qt, NS(text="\0😀")) == "\0😀"
    assert read_text(qt, "") == ""
    with pytest.raises(TypeError):
        read_text(qt, NS(text=42))
    with pytest.raises(ValueError):
        text_fragment(QT, "A\0\nB")


def test_public_workflow_find_selected_replace_save_reload_and_copy(
    tmp_path, monkeypatch
):
    import sys
    import fontlabapp
    import fontlabapp.core.scripting as scripting
    from fontlabapp.proof.text_holder.model import show

    path = tmp_path / "owned-text.txt"
    original = "😀A\0\nB\u00a0C\u2028D\u2029E\0F"
    path.write_text(original, encoding="utf-8")
    parent = QtWidgets.QWidget()
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: QT if name == "PythonQt" else NS(MainWindow=lambda: parent),
    )
    monkeypatch.setattr(fontlabapp, "_native", lambda name: QT)
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    d = show(path=path, qt=QT)
    try:
        assert literal_text(d.editor) == original
        d.find_input.setText("\0")
        d.find_button.click()
        assert (
            d.editor.textCursor().selectionStart(),
            d.editor.textCursor().selectionEnd(),
        ) == (3, 4)
        d.replace_input.setText("X\0Y")
        d.replace_button.click()
        expected = "😀AX\0Y\nB\u00a0C\u2028D\u2029E\0F"
        assert literal_text(d.editor) == expected
        d.editor.undo()
        assert literal_text(d.editor) == original
        d.editor.redo()
        assert literal_text(d.editor) == expected
        c = d.editor.textCursor()
        c.select(Cursor.Document)
        d.editor.setTextCursor(c)
        mime = d.editor.createMimeDataFromSelection()
        assert (
            mime.text() == expected
            and bytes(mime.data("text/plain")) == expected.encode()
        )
        mime.deleteLater()
        d.save_button.click()
        assert path.read_bytes() == expected.encode() and not d._closed
        d.ignore_button.click()
        flush()
        d = show(path=path, qt=QT)
        assert literal_text(d.editor) == expected
        d.editor.setReadOnly(True)
        d.find_input.setText("\0")
        d.replace_input.setText("bad")
        before = (d.editor.textCursor().position(), d.editor.textCursor().anchor())
        d.replace_button.click()
        assert literal_text(d.editor) == expected
        assert (
            d.editor.textCursor().position(),
            d.editor.textCursor().anchor(),
        ) == before
    finally:
        if not d._closed:
            d.close()
        parent.deleteLater()
        flush()


def test_ime_native_const_reference_copy_restores_nul_event_and_full_attributes():
    class Reference:
        def __init__(self, event):
            self.event = event

    class Matcher:
        def __init__(self, ref):
            self.pattern = QtGui.QInputMethodEvent.commitString(ref.event)

    class Event(QtGui.QInputMethodEvent):
        def commitString(self):
            return Reference(self)

        def setCommitString(self, text, start=0, length=0):
            if isinstance(text, Reference):
                text = QtGui.QInputMethodEvent.commitString(text.event)
            else:
                text = text.split("\0")[0]
            QtGui.QInputMethodEvent.setCommitString(self, text, start, length)

    class Copy(QtGui.QInputMethodEvent):
        def commitString(self):
            return Reference(self)

    core = NS(**{**vars(CORE), "QStringMatcher": Matcher})
    gui = NS(**{**vars(GUI), "QInputMethodEvent": Copy})
    qt = NS(QtCore=core, QtGui=gui)
    e = editor_type(qt)()
    e.setPlainText("A\0B\nC\u2029D")
    c = e.textCursor()
    c.setPosition(3)
    e.setTextCursor(c)
    formatting = QtGui.QTextCharFormat()
    formatting.setFontUnderline(True)
    attribute = QtGui.QInputMethodEvent.Attribute(
        QtGui.QInputMethodEvent.TextFormat, 0, 1, QtGui.QTextFormat(formatting)
    )
    event = Event("次", [attribute])
    commit = "Q\0R\u2029S"
    QtGui.QInputMethodEvent.setCommitString(event, commit, -2, 2)
    before = [
        (a.type, a.start, a.length, a.value.properties()) for a in event.attributes()
    ]
    try:
        e.inputMethodEvent(event)
        assert QtGui.QInputMethodEvent.commitString(event) == commit
        assert (
            event.preeditString() == "次"
            and event.replacementStart() == -2
            and event.replacementLength() == 2
        )
        assert [
            (a.type, a.start, a.length, a.value.properties())
            for a in event.attributes()
        ] == before
        expected = "AQ\0R\u2029S\nC\u2029D"
        assert literal_text(e) == expected
        after = (e.textCursor().position(), e.textCursor().anchor())
        e.undo()
        assert literal_text(e) == "A\0B\nC\u2029D"
        e.redo()
        assert literal_text(e) == expected
        assert (e.textCursor().position(), e.textCursor().anchor()) == after
    finally:
        e.deleteLater()
        flush()


@pytest.mark.parametrize("limit", [4, 40000])
def test_line_maxlength_matches_ordinary_native_setter(limit):
    line = line_edit_type(QT)()
    ordinary = QtWidgets.QLineEdit()
    text = "A\0" + "x" * 33000 + "😀"
    try:
        line.setMaxLength(limit)
        ordinary.setMaxLength(limit)
        line.setText(text)
        ordinary.setText(text)
        assert line.text() == ordinary.text()
        assert line.cursorPosition() == ordinary.cursorPosition()
        assert line.isUndoAvailable() == ordinary.isUndoAvailable()
    finally:
        line.deleteLater()
        ordinary.deleteLater()
        flush()


@pytest.mark.parametrize("selection", [(2, 2), (3, 1)])
def test_public_replace_staging_failure_preserves_full_selection_direction(
    tmp_path, monkeypatch, selection
):
    import sys
    import fontlabapp
    import fontlabapp.core.scripting as scripting
    import fontlabapp.proof.text_holder.editor as module
    from fontlabapp.proof.text_holder.model import show

    path = tmp_path / "owned.txt"
    path.write_bytes(b"A\0BC")
    parent = QtWidgets.QWidget()
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: QT if name == "PythonQt" else NS(MainWindow=lambda: parent),
    )
    monkeypatch.setattr(fontlabapp, "_native", lambda name: QT)
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    d = show(path=path, qt=QT)
    try:
        d.find_input.setText("\0")
        d.replace_input.setText("X\0Y")
        c = d.editor.textCursor()
        c.setPosition(selection[0])
        c.setPosition(selection[1], Cursor.KeepAnchor)
        d.editor.setTextCursor(c)
        before = (c.position(), c.anchor())

        def fail(*args):
            raise RuntimeError("public fragment setup failure")

        monkeypatch.setattr(module, "text_fragment", fail)
        d.replace_button.click()
        assert "public fragment setup failure" in d.slot_error
        assert literal_text(d.editor) == "A\0BC" and path.read_bytes() == b"A\0BC"
        assert not d.editor.document().isUndoAvailable()
        assert (
            d.editor.textCursor().position(),
            d.editor.textCursor().anchor(),
        ) == before
    finally:
        d.close()
        parent.deleteLater()
        flush()


@pytest.mark.parametrize(
    "failure", ["stage", "insert", "late-build", "refuse", "raise"]
)
def test_public_reopen_failure_preserves_unsaved_old_and_disposes_hidden_candidate(
    tmp_path, monkeypatch, failure
):
    import sys
    import fontlabapp
    import fontlabapp.core.scripting as scripting
    import fontlabapp.proof.text_holder.editor as module
    from fontlabapp.proof.text_holder.model import show, KEY
    from fontlabapp.proof.text_holder.storage import TextStore

    path = tmp_path / "owned.txt"
    path.write_bytes(b"FILE\0CONTENT")
    created = []

    class DialogBase(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            proof = []
            self.destroyed.connect(lambda *args: proof.append(True))
            created.append((self, proof))

    gui = NS(**{**vars(GUI), "QDialog": DialogBase})
    qt = NS(QtCore=CORE, QtGui=gui)
    parent = QtWidgets.QWidget()
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: qt if name == "PythonQt" else NS(MainWindow=lambda: parent),
    )
    monkeypatch.setattr(fontlabapp, "_native", lambda name: qt)
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    old = show(path=path, qt=qt)
    old.editor.insertPlainText("UNSAVED\0DRAFT")
    c = old.editor.textCursor()
    c.setPosition(3)
    c.setPosition(1, Cursor.KeepAnchor)
    old.editor.setTextCursor(c)
    old.resize(760, 520)
    before = (
        literal_text(old.editor),
        c.position(),
        c.anchor(),
        old.editor.document().isUndoAvailable(),
    )
    load = TextStore.load
    reads = []

    def counted(store):
        reads.append(store.path)
        return load(store)

    monkeypatch.setattr(TextStore, "load", counted)
    original_close = old.close
    if failure == "stage":

        def failed(*args):
            raise RuntimeError("reopen stage failure")

        monkeypatch.setattr(module, "text_fragment", failed)
    elif failure == "insert":

        def failed(*args):
            raise RuntimeError("reopen native insert failure")

        monkeypatch.setattr(Cursor, "insertFragment", failed)
    elif failure == "late-build":

        class FailedButton(QtWidgets.QPushButton):
            def __init__(self, label, parent=None):
                super().__init__(label, parent)
                raise RuntimeError("reopen late button construction failure")

        monkeypatch.setattr(gui, "QPushButton", FailedButton)
    elif failure == "refuse":
        monkeypatch.setattr(old, "close", lambda: False)
    else:

        def failed():
            raise RuntimeError("old close failure")

        monkeypatch.setattr(old, "close", failed)
    try:
        if failure == "refuse":
            assert show(path=path, qt=qt) is old
        else:
            with pytest.raises(RuntimeError):
                show(path=path, qt=qt)
        flush()
        assert reads == [path], "Snapshot must be loaded exactly once before oldclose"
        assert not old._closed and old.isVisible() and sys._fontlab_samples[KEY] is old
        assert (
            literal_text(old.editor),
            old.editor.textCursor().position(),
            old.editor.textCursor().anchor(),
            old.editor.document().isUndoAvailable(),
        ) == before
        assert (
            path.read_bytes() == b"FILE\0CONTENT"
            and not path.with_suffix(".window.json").exists()
        )
        assert created[0][1] == [] and len(created) == 2 and created[1][1] == [True]
    finally:
        monkeypatch.setattr(old, "close", original_close)
        if not created[0][1]:
            old.close()
        parent.deleteLater()
        flush()


def test_successful_reopen_retains_current_frame_and_exact_once_content_snapshot(
    tmp_path, monkeypatch
):
    import sys
    import fontlabapp
    import fontlabapp.core.scripting as scripting
    from fontlabapp.proof.text_holder.model import show
    from fontlabapp.proof.text_holder.storage import TextStore

    path = tmp_path / "owned.txt"
    path.write_bytes(b"FILE\0CONTENT")
    parent = QtWidgets.QWidget()
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: QT if name == "PythonQt" else NS(MainWindow=lambda: parent),
    )
    monkeypatch.setattr(fontlabapp, "_native", lambda name: QT)
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    old = show(path=path, qt=QT)
    old.resize(760, 520)
    frame = old.frameGeometry()
    expected = (frame.width(), frame.height())
    reads = []
    load = TextStore.load

    def counted(store):
        reads.append(store.path)
        return load(store)

    monkeypatch.setattr(TextStore, "load", counted)
    new = show(path=path, qt=QT)
    try:
        assert reads == [path] and old._closed
        assert literal_text(new.editor) == "FILE\0CONTENT"
        assert (new.frameGeometry().width(), new.frameGeometry().height()) == expected
    finally:
        new.close()
        parent.deleteLater()
        flush()
