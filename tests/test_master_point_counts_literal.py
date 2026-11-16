# this_file: tests/test_master_point_counts_literal.py
"""Actual Qt literal readonly report selections; never touch the global clipboard."""

import os
import sys
from types import SimpleNamespace as NS

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore as C, QtGui as G, QtWidgets as W
else:
    from PySide6 import QtCore as C, QtGui as G, QtWidgets as W

import fontlabapp
import fontlabapp.masters.point_counts.ui as ui
import fontlabapp.masters.point_counts.model as model
import fontlabapp.masters.point_counts.native as api
import fontlabapp.core.scripting as scripts
from fontlabapp.contours.point_counts.model import Counts, LayerCount
from fontlabapp.proof.text_holder.editor import literal_text


class Gui:
    QCloseEvent = G.QCloseEvent
    QKeySequence = G.QKeySequence
    QTextCursor = G.QTextCursor

    def __getattr__(self, name):
        return getattr(W, name)


def test_literal_report_all_utf16_boundary_selections_and_readonly_ingress(monkeypatch):
    app = W.QApplication.instance() or W.QApplication([])
    qt = NS(QtCore=C, QtGui=Gui())
    monkeypatch.setattr(fontlabapp, "_native", lambda n: qt)
    monkeypatch.setattr(scripts, "_native", lambda n: qt)
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    name = "A\u00a0😀\u2028X\u2029Y\nZ"
    rows = (LayerCount(name, Counts(1, 1, 2, 1)),)
    monkeypatch.setattr(api, "capture", lambda: rows)
    panel = ui.dialog_type(qt)()
    panel.show()
    app.processEvents()
    editor = panel.output
    text = model.render(rows)
    destroyed = []
    panel.destroyed.connect(lambda *args: destroyed.append(True))
    try:
        # Every codepoint boundary in the adversarial name plus full report edges;
        # positions are UTF16 units, independently computed, never Python indices.
        indexes = sorted({0, len(text), *range(7, 7 + len(name) + 1)})
        positions = {i: len(text[:i].encode("utf-16-le")) // 2 for i in indexes}
        for start in indexes:
            for end in indexes:
                cursor = editor.textCursor()
                cursor.setPosition(positions[start])
                cursor.setPosition(positions[end], G.QTextCursor.KeepAnchor)
                editor.setTextCursor(cursor)
                mime = editor.createMimeDataFromSelection()
                assert mime.text() == text[min(start, end) : max(start, end)], (
                    start,
                    end,
                )
        assert literal_text(editor) == text
        editor.selectAll()
        editor.setFocus()
        for key, string in [
            (C.Qt.Key_X, "x"),
            (C.Qt.Key_Return, "\r"),
            (C.Qt.Key_Backspace, ""),
            (C.Qt.Key_Delete, ""),
        ]:
            app.sendEvent(
                editor, G.QKeyEvent(C.QEvent.KeyPress, key, C.Qt.NoModifier, string)
            )
            assert literal_text(editor) == text
        event = G.QInputMethodEvent()
        event.setCommitString("IME\u00a0\u2029", 0, 0)
        app.sendEvent(editor, event)
        assert literal_text(editor) == text, (
            "Read-only report must refuse IME mutation too"
        )
        assert editor.isReadOnly() and not editor.canPaste()
        for modifier in (C.Qt.ControlModifier, C.Qt.MetaModifier):
            for key in (C.Qt.Key_X, C.Qt.Key_V, C.Qt.Key_Z, C.Qt.Key_Y):
                app.sendEvent(editor, G.QKeyEvent(C.QEvent.KeyPress, key, modifier))
                assert literal_text(editor) == text
        app.sendEvent(editor, G.QInputMethodEvent("owned preedit", []))
        event = G.QInputMethodEvent()
        event.setCommitString("replace", -1, 1)
        app.sendEvent(editor, event)
        assert literal_text(editor) == text
        reference = W.QPlainTextEdit()
        reference.setPlainText(text)
        reference.setReadOnly(True)
        reference.selectAll()
        editor.selectAll()
        menu = editor.createStandardContextMenu()
        reference_menu = reference.createStandardContextMenu()
        try:
            edits = [
                action
                for action in menu.actions()
                if action.text().replace("&", "").split("\t")[0]
                in ("Undo", "Redo", "Cut", "Paste", "Delete")
            ]
            assert [(a.text(), a.isEnabled()) for a in menu.actions()] == [
                (a.text(), a.isEnabled()) for a in reference_menu.actions()
            ], "Native readonly context menu may omit editing actions entirely"
            for action in edits:
                assert not action.isEnabled()
                action.trigger()
                assert literal_text(editor) == text
        finally:
            menu.deleteLater()
            reference_menu.deleteLater()
            reference.deleteLater()
        mime = C.QMimeData()
        mime.setText("owned drop\u00a0\u2029")
        drag = G.QDragEnterEvent(
            C.QPoint(2, 2), C.Qt.CopyAction, mime, C.Qt.LeftButton, C.Qt.NoModifier
        )
        app.sendEvent(editor.viewport(), drag)
        drop = G.QDropEvent(
            C.QPointF(2, 2), C.Qt.CopyAction, mime, C.Qt.LeftButton, C.Qt.NoModifier
        )
        app.sendEvent(editor.viewport(), drop)
        assert literal_text(editor) == text and not drag.isAccepted()
        assert not drop.isAccepted()
    finally:
        panel.close()
        C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)
    assert destroyed == [True]


def test_literal_loss_refuses_report_before_publication(monkeypatch):
    """A native setter that loses NUL must never publish a truncated report."""
    import pytest

    app = W.QApplication.instance() or W.QApplication([])
    qt = NS(QtCore=C, QtGui=Gui())
    monkeypatch.setattr(fontlabapp, "_native", lambda n: qt)
    monkeypatch.setattr(scripts, "_native", lambda n: qt)
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    rows = (LayerCount("A\0B", Counts(1, 1, 2, 1)),)
    monkeypatch.setattr(api, "capture", lambda: rows)
    base = ui.editor_type(qt)
    destroyed = []

    class Truncating(base):
        def __init__(self, parent):
            base.__init__(self, parent)
            self.destroyed.connect(lambda *args: destroyed.append(True))

        def setPlainText(self, text):
            base.setPlainText(self, text.split("\0")[0])

    monkeypatch.setattr(ui, "editor_type", lambda qt: Truncating)
    with pytest.raises(ValueError, match="cannot preserve the complete report text"):
        ui.dialog_type(qt)()
    app.sendPostedEvents(None, C.QEvent.DeferredDelete)
    assert not sys._fontlab_samples
    assert destroyed == [True]
