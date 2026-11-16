# this_file: tests/test_text_holder_dialog.py
"""Real Qt5/Qt6 editor, selection, lifetime and owned persistent recovery."""

import os
import sys
from types import SimpleNamespace as NS

import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - cold import must bypass native package fallback
import pytest
from fontlabapp.proof.text_holder.ui import dialog_type
from fontlabapp.proof.text_holder.storage import TextStore

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtGui, QtWidgets
else:
    from PySide6 import QtCore, QtGui, QtWidgets
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
GUI = NS(
    QApplication=QtWidgets.QApplication,
    QDialog=QtWidgets.QDialog,
    QPlainTextEdit=QtWidgets.QPlainTextEdit,
    QVBoxLayout=QtWidgets.QVBoxLayout,
    QGridLayout=QtWidgets.QGridLayout,
    QLabel=QtWidgets.QLabel,
    QLineEdit=QtWidgets.QLineEdit,
    QPushButton=QtWidgets.QPushButton,
    QTextCursor=QtGui.QTextCursor,
    QKeySequence=QtGui.QKeySequence,
    QCloseEvent=QtGui.QCloseEvent,
)
QT = NS(QtCore=QtCore, QtGui=GUI)


def drain():
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.fixture
def panel(tmp_path, monkeypatch):
    parent = QtWidgets.QWidget()
    alive = [True]
    parent.destroyed.connect(lambda *args: alive.__setitem__(0, False))
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: QT if name == "PythonQt" else NS(MainWindow=lambda: parent),
    )
    import fontlabapp

    monkeypatch.setattr(fontlabapp, "_native", lambda name: QT)
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    store = TextStore(tmp_path / "Text holder.txt")
    result = dialog_type(QT, store)(parent)
    result.show()
    yield result, store, parent
    if not result._closed:
        result.close()
    if alive[0]:
        parent.deleteLater()
    drain()


def select(dialog, start, end):
    cursor = dialog.editor.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(end, QtGui.QTextCursor.KeepAnchor)
    dialog.editor.setTextCursor(cursor)


def test_complete_editor_is_resizable_floating_and_has_all_original_controls(panel):
    dialog, store, _parent = panel
    frame = dialog.frameGeometry()
    extra = (frame.width() - dialog.width(), frame.height() - dialog.height())
    assert (dialog.minimumWidth() + extra[0], dialog.minimumHeight() + extra[1]) == (
        500,
        400,
    )
    assert (dialog.maximumWidth() + extra[0], dialog.maximumHeight() + extra[1]) == (
        1200,
        800,
    )
    assert dialog.windowFlags() & QtCore.Qt.WindowStaysOnTopHint
    assert not dialog.editor.isReadOnly() and not store.path.exists()
    assert [
        b.text().replace("&&", "&")
        for b in [
            dialog.find_button,
            dialog.replace_button,
            dialog.save_button,
            dialog.save_close_button,
            dialog.ignore_button,
        ]
    ] == ["Find", "Find & Replace", "Save", "Save & Close", "Ignore & Close"]
    dialog.resize(720, 550)
    dialog.editor.setPlainText("unsaved")
    expected = (dialog.frameGeometry().width(), dialog.frameGeometry().height())
    dialog.ignore_button.click()
    assert dialog._closed and not store.path.exists() and store.size() == expected


def test_find_first_highlight_with_non_bmp_prefix_and_not_found_retains_selection(
    panel,
):
    dialog, store, _parent = panel
    dialog.editor.setPlainText("😀x\n😀x")
    select(dialog, 6, 7)
    dialog.find_input.setText("x")
    dialog.find_button.click()
    cursor = dialog.editor.textCursor()
    assert (cursor.selectionStart(), cursor.selectionEnd(), cursor.selectedText()) == (
        2,
        3,
        "x",
    )
    dialog.find_input.setText("missing")
    dialog.find_button.click()
    assert (
        "not found" in dialog.status.text().lower()
        and dialog.editor.textCursor().selectedText() == "x"
    )
    dialog.find_input.clear()
    dialog.find_button.click()
    assert dialog.editor.textCursor().selectedText() == "x" and not store.path.exists()


def test_selected_replacement_is_unicode_correct_and_whole_replacement_uses_no_selection(
    panel,
):
    dialog, store, _parent = panel
    dialog.editor.setPlainText("😀abc abc\nאבabc")
    select(dialog, 5, 2)  # reversed selection must still target first abc only
    dialog.find_input.setText("abc")
    dialog.replace_input.setText("👩\u200d💻")
    dialog.replace_button.click()
    assert dialog.editor.toPlainText() == "😀👩\u200d💻 abc\nאבabc"
    dialog.editor.undo()
    assert dialog.editor.toPlainText() == "😀abc abc\nאבabc"
    select(dialog, 2, 2)
    dialog.replace_input.clear()
    dialog.replace_button.click()
    assert dialog.editor.toPlainText() == "😀 \nאב"
    before = dialog.editor.toPlainText()
    dialog.find_input.clear()
    dialog.replace_button.click()
    assert dialog.editor.toPlainText() == before and not store.path.exists()


def test_save_stays_open_saveclose_recovers_and_ignore_discards_only_unsaved_draft(
    panel,
):
    dialog, store, parent = panel
    dialog.editor.setPlainText("saved😀\nאב")
    dialog.save_button.click()
    assert not dialog._closed and dialog.isVisible() and store.load() == "saved😀\nאב"
    dialog.editor.setPlainText("second e\u0301")
    dialog.save_close_button.click()
    assert (
        dialog._closed and not dialog._connections and store.load() == "second e\u0301"
    )
    count = (
        dialog.save_button.receivers(dialog.save_button.clicked)
        if os.environ.get("FONTLABAPP_TEST_QT5") == "1"
        else dialog.save_button.receivers("2clicked(bool)")
    )
    assert count == 0, "Owned button callbacks must disconnect before deferred deletion"
    second = dialog_type(QT, store)(parent)
    second.show()
    assert second.editor.toPlainText() == "second e\u0301"
    second.editor.setPlainText("discard")
    second.ignore_button.click()
    assert second._closed and store.load() == "second e\u0301"


def test_save_failure_keeps_editor_and_saved_content_and_saveclose_never_closes(
    panel, monkeypatch
):
    dialog, store, _parent = panel
    store.save("before")
    dialog.editor.setPlainText("draft😀")
    monkeypatch.setattr(
        store,
        "save",
        lambda text: (_ for _ in ()).throw(PermissionError("owned failure")),
    )
    dialog.save_close_button.click()
    assert (
        not dialog._closed
        and dialog.editor.toPlainText() == "draft😀"
        and store.load() == "before"
    )
    assert "owned failure" in dialog.status.text()


def test_escape_and_parent_destruction_disconnect_and_late_handlers_are_inert(panel):
    dialog, store, parent = panel
    lifetime = dialog._completion_lifetime
    dialog.reject()
    assert (
        dialog._closed
        and lifetime.closed
        and not lifetime.hooks
        and not dialog._connections
    )
    dialog.save()
    dialog.find()
    dialog.replace()
    dialog.save_close()
    dialog.ignore()
    assert not store.path.exists()
    other = dialog_type(QT, store)(parent)
    other.show()
    parent.deleteLater()
    drain()
    assert (
        other._closed and other._completion_lifetime.closed and not other._connections
    )
    other.save()
    assert not store.path.exists()


def test_public_show_recovers_text_with_explicit_store_and_default_route_is_injected_owned(
    panel, monkeypatch, tmp_path
):
    dialog, store, _parent = panel
    dialog.close()
    store.save("recovered😀")
    import fontlabapp.proof.text_holder.model as api

    explicit = api.show(path=store.path, qt=QT)
    assert (
        explicit.editor.toPlainText() == "recovered😀"
        and sys._fontlab_samples[api.KEY] is explicit
    )
    explicit.ignore_button.click()
    root = tmp_path / "default-owned"
    paths = NS(AppDataLocation=17, writableLocation=lambda kind: str(root))
    ownedqt = NS(QtCore=NS(Qt=QtCore.Qt, QStandardPaths=paths), QtGui=GUI)
    import fontlabapp

    monkeypatch.setattr(fontlabapp, "_native", lambda name: ownedqt)
    default = api.show()
    default.editor.setPlainText("owned default")
    default.save_button.click()
    default.close()
    assert (
        root / "Text holder.txt"
    ).read_text() == "owned default" and not sys._fontlab_samples


def test_saved_read_error_aborts_before_a_blank_editor_can_overwrite_content(panel):
    _dialog, store, parent = panel
    store.path.write_bytes(b"\xff")
    with pytest.raises(UnicodeError):
        dialog_type(QT, store)(parent)
    assert store.path.read_bytes() == b"\xff"


def test_size_write_error_does_not_block_ignore_or_save_the_draft(panel, monkeypatch):
    dialog, store, _parent = panel
    store.save("saved")
    dialog.editor.setPlainText("discard")

    def failure(size):
        raise PermissionError("size write failed")

    monkeypatch.setattr(store, "save_size", failure)
    dialog.ignore_button.click()
    assert (
        dialog._closed
        and store.load() == "saved"
        and "size write failed" in dialog.slot_error
    )


def test_missing_match_in_selection_and_unicode_half_boundary_never_changes_editor(
    panel,
):
    dialog, _store, _parent = panel
    dialog.editor.setPlainText("😀abc xyz")
    select(dialog, 6, 9)
    dialog.find_input.setText("abc")
    dialog.replace_input.setText("WRONG")
    dialog.replace_button.click()
    assert dialog.editor.toPlainText() == "😀abc xyz"
    select(dialog, 1, 3)
    dialog.replace_button.click()
    assert (
        dialog.editor.toPlainText() == "😀abc xyz"
        and "boundary" in dialog.status.text()
    )


def test_repeated_close_event_is_accepted_without_reading_deleted_children(panel):
    dialog, store, _parent = panel
    dialog.close()
    event = QtGui.QCloseEvent()
    event.ignore()
    type(dialog).closeEvent(dialog, event)
    assert event.isAccepted() and dialog._closed and not store.path.exists()


def test_original_ampersands_are_literal_in_actual_qt_button_text_layout(panel):
    dialog, _store, _parent = panel
    for button, expected in (
        (dialog.replace_button, "Find & Replace"),
        (dialog.save_close_button, "Save & Close"),
        (dialog.ignore_button, "Ignore & Close"),
    ):
        metrics = button.fontMetrics()
        rendered = metrics.size(QtCore.Qt.TextShowMnemonic, button.text())
        literal = metrics.size(QtCore.Qt.TextSingleLine, expected)
        assert rendered == literal, (
            "Qt button rendering must retain the original literal ampersand"
        )


def test_original_frame_constraints_cocoa_origin_and_saved_frame_recovery(panel):
    dialog, store, parent = panel
    screen = QtWidgets.QApplication.screens()[0].geometry()
    frame = dialog.frameGeometry()
    assert (dialog.width(), dialog.height()) == (500, 400), (
        "Original initial dimensions describe content"
    )
    assert frame.left() == screen.left() and screen.bottom() - frame.bottom() == 500, (
        "Original absolute Cocoa frame origin uses full screen geometry"
    )
    dialog.resize(1, 1)
    assert (dialog.frameGeometry().width(), dialog.frameGeometry().height()) == (
        500,
        400,
    ), "Original minimum constrains decorated frame"
    dialog.resize(9999, 9999)
    assert (dialog.frameGeometry().width(), dialog.frameGeometry().height()) == (
        1200,
        800,
    ), "Original maximum constrains decorated frame"
    dialog.ignore()
    assert store.size() == (1200, 800)
    store.save_size((700, 500))
    recovered = dialog_type(QT, store)(parent)
    recovered.show()
    assert (recovered.frameGeometry().width(), recovered.frameGeometry().height()) == (
        700,
        500,
    )
    assert (
        recovered.frameGeometry().left() == screen.left()
        and screen.bottom() - recovered.frameGeometry().bottom() == 500
    )
    recovered.move(80, 90)
    position = recovered.pos()
    recovered.hide()
    recovered.show()
    assert recovered.pos() == position, (
        "Raising an existing window must not reset its manual position"
    )
    recovered.close()
    recovered.showEvent(QtGui.QShowEvent())  # late handler must not call native base


def test_missing_screen_is_a_contained_geometry_diagnosis_not_a_native_exception(
    panel, monkeypatch
):
    _dialog, store, parent = panel
    monkeypatch.setattr(GUI, "QApplication", NS(screens=list))
    other = dialog_type(QT, store)(parent)
    other.show()
    assert "screen geometry is unavailable" in other.status.text()
    other.ignore()
    assert other._closed


def test_original_nswindow_class_and_minimize_zoom_close_controls_are_preserved(panel):
    dialog, _store, _parent = panel
    flags = dialog.windowFlags()
    assert flags & QtCore.Qt.WindowType_Mask == QtCore.Qt.Window, (
        "Original uses normal NSWindow, not a deactivating NSPanel/Qt.Tool"
    )
    for hint in (
        QtCore.Qt.WindowStaysOnTopHint,
        QtCore.Qt.WindowTitleHint,
        QtCore.Qt.WindowSystemMenuHint,
        QtCore.Qt.WindowCloseButtonHint,
        QtCore.Qt.WindowMinimizeButtonHint,
        QtCore.Qt.WindowMaximizeButtonHint,
    ):
        assert flags & hint, "Original floating NSWindow controls must remain available"


@pytest.mark.parametrize(
    "needle,expected_range",
    [("\u00a0", (5, 6)), ("\u2028", (7, 8)), ("\u2029", (9, 10)), ("\n", (3, 4))],
)
def test_literal_find_selected_replace_save_and_reopen_use_independent_expected_text(
    panel, needle, expected_range
):
    dialog, store, parent = panel
    original = "😀A\nB\u00a0C\u2028D\u2029E\nF"
    dialog.editor.setPlainText(original)
    dialog.find_input.setText(needle)
    dialog.find_button.click()
    c = dialog.editor.textCursor()
    assert (c.selectionStart(), c.selectionEnd()) == expected_range
    # Reverse exactly that first selected occurrence; later same literals stay.
    select(dialog, expected_range[1], expected_range[0])
    dialog.replace_input.setText("replacement\u2029line\nnext\u00a0\u2028")
    dialog.replace_button.click()
    expected = original.replace(needle, "replacement\u2029line\nnext\u00a0\u2028", 1)
    dialog.save_button.click()
    assert store.path.read_bytes().decode("utf-8") == expected
    dialog.editor.undo()
    dialog.save_button.click()
    assert store.path.read_bytes().decode("utf-8") == original
    dialog.editor.redo()
    dialog.save_close_button.click()
    assert store.path.read_bytes().decode("utf-8") == expected
    reopened = dialog_type(QT, store)(parent)
    reopened.save_button.click()
    assert store.path.read_bytes().decode("utf-8") == expected
    reopened.close()


@pytest.mark.parametrize("needle", ["\u00a0", "\u2028", "\u2029", "\n"])
def test_literal_whole_replacement_changes_only_requested_character(panel, needle):
    dialog, store, _parent = panel
    original = "😀A\nB\u00a0C\u2028D\u2029E\nF" * 2
    dialog.editor.setPlainText(original)
    dialog.find_input.setText(needle)
    dialog.replace_input.setText("Q")
    select(dialog, 0, 0)
    dialog.replace_button.click()
    dialog.save_button.click()
    assert store.path.read_bytes().decode("utf-8") == original.replace(needle, "Q")


@pytest.mark.parametrize(
    "text",
    [
        "A\u00a0B",
        "A\u2028B",
        "A\u2029B",
        "\u202f\t\v\f\x85\u2060\ufeff\u200b\xad\0\n😀",
    ],
)
def test_literal_save_preserves_each_normalization_counterexample_and_controls(
    panel, text
):
    dialog, store, _parent = panel
    dialog.editor.setPlainText(text)
    dialog.save_button.click()
    assert store.path.read_bytes().decode("utf-8") == text


@pytest.mark.parametrize("reverse", [False, True])
def test_mixed_selected_ps_replacement_preserves_untouched_lf_and_history(
    panel, reverse
):
    """N123: removing a cross-block selection must not adopt its right format."""
    from fontlabapp.proof.text_holder.editor import literal_text

    dialog, store, _ = panel
    text = "A\nB\u00a0C\u2028D\u2029EF😀\nG"
    replacement = "X\nY\u2028Z\u00a0😀"
    dialog.editor.setPlainText(text)
    select(dialog, *((12, 2) if reverse else (2, 12)))
    dialog.find_input.setText("\u2029")
    dialog.replace_input.setText(replacement)
    dialog.replace_button.click()
    expected = "A\nB\u00a0C\u2028DX\nY\u2028Z\u00a0😀EF😀\nG"
    for step, wanted in enumerate((expected, text, expected)):
        assert literal_text(dialog.editor) == wanted
        dialog.save_button.click()
        assert store.path.read_bytes() == wanted.encode("utf-8")
        if step == 0:
            dialog.editor.undo()
        elif step == 1:
            dialog.editor.redo()
