# this_file: tests/test_completion_editor.py
"""Real owned Qt completions preserve the two source variants' whole behavior."""

import os
from types import SimpleNamespace as NS

import pytest

from fontlabapp.qt.completion.editor import CompletionEditor

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtGui, QtWidgets
else:
    from PySide6 import QtCore, QtGui, QtWidgets

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture(params=[False, True], ids=["part2", "part3"])
def editor(request):
    gui = NS(**{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
    gui.__dict__.update(
        {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
    )
    gui.QStringListModel = QtCore.QStringListModel
    gui.QSortFilterProxyModel = QtCore.QSortFilterProxyModel
    pairs, errors = [], []

    def wire(sender, slot):
        sender.activated[str].connect(slot)
        pairs.append((sender, slot))
        return slot

    def unwire(sender, slot):
        sender.activated[str].disconnect(slot)
        pairs.remove((sender, slot))

    parent = QtWidgets.QWidget()
    control = CompletionEditor(
        NS(QtCore=QtCore, QtGui=gui),
        parent,
        wire,
        unwire,
        errors.append,
        official=request.param,
    )
    control.replace_words(
        ("anchor", "Anchor.alt", "anchorage", "angle", "Äname", "zeta", "😀name")
    )
    yield control, pairs, errors
    control.close()
    assert not pairs, "Close must remove every exact activation pair"
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def key(c, key=QtCore.Qt.Key_R, text="r", modifiers=QtCore.Qt.NoModifier):
    event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, modifiers, text)
    c.widget.keyPressEvent(event)
    return event


def test_complete_vocabulary_is_qt_sorted_and_case_insensitive(editor):
    c, pairs, _ = editor
    assert (
        len(pairs) == 1
        and c.completer.modelSorting()
        == QtWidgets.QCompleter.CaseInsensitivelySortedModel
    )
    assert c.completer.caseSensitivity() == QtCore.Qt.CaseInsensitive
    c.completer.setCompletionPrefix("AN")
    assert c.completer.completionCount() == 4, (
        "All complete model matches must survive sorted lookup"
    )
    if c.official:
        assert not c.completer.wrapAround()


def test_refresh_preserves_entire_draft_and_disconnects_old_completer(editor):
    c, pairs, _ = editor
    c.widget.setPlainText("Draft /A.alt\n😀")
    old = c.completer
    c.replace_words(("newGlyph",))
    assert c.widget.toPlainText() == "Draft /A.alt\n😀"
    assert len(pairs) == 1 and pairs[0][0] is c.completer and old.widget() is None
    c.replace_words(())
    assert c.completer.model().rowCount() == 0 and len(pairs) == 1


@pytest.mark.parametrize("text", ["anc", "ANc"])
def test_activation_inserts_only_suffix_at_current_word_end(editor, text):
    c, _, _ = editor
    c.widget.setPlainText(text)
    cursor = c.widget.textCursor()
    cursor.movePosition(QtGui.QTextCursor.End)
    c.widget.setTextCursor(cursor)
    c.completer.setCompletionPrefix(text)
    c.completer.activated[str].emit("anchor")
    assert c.widget.toPlainText() == text + "hor"


def test_part2_mismatch_and_part3_wrong_widget_do_not_insert(editor):
    c, _, _ = editor
    c.widget.setPlainText("other")
    if c.official:
        c.completer.setWidget(None)
    c.insert("anchor")
    assert c.widget.toPlainText() == "other"


@pytest.mark.parametrize(
    "pressed",
    [
        QtCore.Qt.Key_Enter,
        QtCore.Qt.Key_Return,
        QtCore.Qt.Key_Escape,
        QtCore.Qt.Key_Tab,
        QtCore.Qt.Key_Backtab,
    ],
)
def test_visible_popup_owns_terminal_keys(editor, pressed):
    c, _, _ = editor
    c.widget.setPlainText("anc")
    c.completer.popup().show()
    event = key(c, pressed, "")
    assert not event.isAccepted() and c.widget.toPlainText() == "anc"


def test_ctrl_e_does_not_insert_and_triggers_short_prefix(editor):
    c, _, _ = editor
    c.widget.setPlainText("an")
    cursor = c.widget.textCursor()
    cursor.movePosition(QtGui.QTextCursor.End)
    c.widget.setTextCursor(cursor)
    key(c, QtCore.Qt.Key_E, "e", QtCore.Qt.ControlModifier)
    assert c.widget.toPlainText() == "an" and c.completer.completionPrefix() == "an"


def test_completion_popup_is_wide_enough_to_read_the_full_candidates(editor):
    c, _, _ = editor
    c.widget.parentWidget().show()
    APP.processEvents()
    c.widget.setPlainText("anc")
    cursor = c.widget.textCursor()
    cursor.movePosition(QtGui.QTextCursor.End)
    c.widget.setTextCursor(cursor)
    key(c, QtCore.Qt.Key_E, "e", QtCore.Qt.ControlModifier)
    popup = c.completer.popup()
    assert popup.isVisible() and popup.width() >= popup.sizeHintForColumn(0) > 1, (
        "Completion text must not be clipped to the caret width"
    )


def test_typing_updates_word_and_ineligible_input_hides_popup(editor):
    c, _, _ = editor
    c.widget.clear()
    for character in "anc":
        key(c, ord(character.upper()), character)
    assert c.widget.toPlainText() == "anc" and c.completer.completionPrefix() == "anc"
    key(c, QtCore.Qt.Key_Period, ".")
    assert not c.completer.popup().isVisible()


def test_focus_rebinds_official_completer_and_native_base_runs(editor):
    c, _, _ = editor
    c.completer.setWidget(None)
    c.widget.focusInEvent(QtGui.QFocusEvent(QtCore.QEvent.FocusIn))
    assert (c.completer.widget() is c.widget) == c.official


def test_close_and_late_methods_are_inert_and_repeatable(editor):
    c, pairs, errors = editor
    c.close()
    c.close()
    c.replace_words(("late",))
    c.insert("late")
    c.widget.keyPressEvent(
        QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress, QtCore.Qt.Key_A, QtCore.Qt.NoModifier, "a"
        )
    )
    c.widget.focusInEvent(QtGui.QFocusEvent(QtCore.QEvent.FocusIn))
    assert c._closed and c.completer is None and not pairs and not errors


def test_disconnect_failure_retains_live_owner_and_close_can_retry(editor):
    c, pairs, _ = editor
    old, unwire = c.completer, c._unwire

    def fail(*args):
        raise RuntimeError("disconnect failed")

    c._unwire = fail
    with pytest.raises(RuntimeError, match="disconnect failed"):
        c.close()
    assert c.completer is old and old.widget() is c.widget and len(pairs) == 1
    c._unwire = unwire
    c.close()
    assert c.completer is None and not pairs


def test_native_virtual_and_error_reporter_failures_never_escape(editor, monkeypatch):
    c, _, _ = editor

    def fail(*args):
        raise RuntimeError("report failed")

    c._report = fail
    monkeypatch.setattr(c.gui.QTextEdit, "keyPressEvent", fail)
    key(c)
    assert "report failed" in c.last_error


@pytest.mark.parametrize("words", [None, ["A"], ("",), (1,)])
def test_invalid_model_replacement_leaves_old_complete_model(editor, words):
    c, pairs, _ = editor
    old = c.completer
    with pytest.raises(TypeError, match="tuple of nonempty"):
        c.replace_words(words)
    assert c.completer is old and len(pairs) == 1


def test_same_completer_and_closed_replacement_are_inert(editor):
    c, pairs, _ = editor
    old = c.completer
    c.replace_completer(old)
    assert c.completer is old and len(pairs) == 1
    c.close()
    c.replace_completer(None)
    c._failed(ValueError("late"))
    assert not pairs


def test_wire_failure_detaches_unpublished_model_and_old_pair(editor):
    c, pairs, _ = editor
    old_wire = c._wire

    def fail(*args):
        raise RuntimeError("wire failed")

    c._wire = fail
    with pytest.raises(RuntimeError, match="wire failed"):
        c.replace_words(("replacement",))
    assert c.completer is None and not pairs
    c._wire = old_wire
    key(c, QtCore.Qt.Key_A, "a")
    assert c.widget.toPlainText() == "a", (
        "A missing completer leaves normal typing available"
    )
    c.replace_words(("restored",))
    assert len(pairs) == 1


def test_focus_handler_failure_is_contained(editor, monkeypatch):
    c, _, errors = editor

    def fail(*args):
        raise RuntimeError("focus failed")

    monkeypatch.setattr(c.gui.QTextEdit, "focusInEvent", fail)
    c.widget.focusInEvent(QtGui.QFocusEvent(QtCore.QEvent.FocusIn))
    assert len(errors) == 1 and "focus failed" in c.last_error


def test_empty_modifier_text_and_unchanged_prefix_keep_original_key_policy(editor):
    c, _, _ = editor
    c.widget.setPlainText("anc")
    cursor = c.widget.textCursor()
    cursor.movePosition(QtGui.QTextCursor.End)
    c.widget.setTextCursor(cursor)
    c.completer.setCompletionPrefix("anc")
    key(c, QtCore.Qt.Key_Shift, "", QtCore.Qt.ShiftModifier)
    key(c, QtCore.Qt.Key_E, "e", QtCore.Qt.ControlModifier)
    assert c.completer.completionPrefix() == "anc" and c.widget.toPlainText() == "anc"
    c.completer.setCompletionPrefix("anchor")
    c.insert("anchor")
    if c.official:
        assert c.widget.toPlainText() == "anc", "Zero extra characters must not insert"
