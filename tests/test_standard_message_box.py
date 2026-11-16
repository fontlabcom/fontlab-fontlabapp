# this_file: tests/test_standard_message_box.py
"""Owned standard messages preserve actual Qt static-call semantics."""

from types import SimpleNamespace as NS

import pytest
import fontlabapp.qt.dialogs as dialogs
from test_find_files_dialog import C, W
from test_spacing_worksheet import drain, valid

if "PyQt5" in C.__name__:
    from PyQt5.QtTest import QTest
else:
    from PySide6.QtTest import QTest


@pytest.mark.parametrize(
    "icon,buttons,default,answer",
    [
        ("Warning", "Ok", None, "Ok"),
        ("Warning", "Ok", None, "escape"),
        ("Warning", "Ok", None, "enter"),
        ("Warning", "Ok", "NoButton", "enter"),
        ("Question", "YesNo", "No", "Yes"),
        ("Question", "YesNo", "No", "No"),
        ("Question", "YesNo", "No", "escape"),
        ("Question", "YesNo", "No", "enter"),
        ("Question", "YesNo", None, "Yes"),
    ],
)
def test_owned_standard_message_matches_static_display_and_result(
    icon, buttons, default, answer
):
    helper = dialogs.run_standard_message_box
    parent = W.QWidget()
    made, flags, observations, titles = [], [], [], []
    kind = W.QMessageBox
    mask = kind.Yes | kind.No if buttons == "YesNo" else kind.Ok
    default_value = getattr(kind, default) if default else None

    class Box(kind):
        def __init__(self, owner):
            super().__init__(owner)
            made.append(self)

        def setWindowTitle(self, value):
            titles.append(value)
            super().setWindowTitle(value)

        def setWindowFlags(self, value):
            flags.append((self.windowFlags(), value))
            super().setWindowFlags(value)

    def answer_modal():
        box = W.QApplication.activeModalWidget()
        try:
            observations.append(
                (
                    box.parentWidget() is parent,
                    box.windowTitle(),
                    box.text(),
                    box.informativeText(),
                    box.icon(),
                    box.standardButtons(),
                    box.standardButton(box.defaultButton()),
                    box.windowModality(),
                    box.isModal(),
                    box.windowType(),
                    box.windowFlags(),
                )
            )
        finally:
            if answer in ("escape", "enter"):
                QTest.keyClick(
                    box, C.Qt.Key_Escape if answer == "escape" else C.Qt.Key_Return
                )
            else:
                box.button(getattr(kind, answer)).click()

    try:
        C.QTimer.singleShot(0, answer_modal)
        static_args = (parent, "Owned title", "Owned <b>text</b>", mask)
        if default_value is not None:
            static_args += (default_value,)
        expected = getattr(kind, icon.lower())(*static_args)
        C.QTimer.singleShot(0, answer_modal)
        result = helper(
            NS(QtCore=C, QtGui=NS(QMessageBox=Box)),
            parent,
            "Owned title",
            "Owned <b>text</b>",
            icon,
            mask,
            default_value,
        )
        assert result == expected
        assert titles == ["Owned title"]
        assert observations[0][:-1] == observations[1][:-1]
        assert observations[1][0] and observations[1][3] == ""
        assert observations[1][7:10] == (C.Qt.ApplicationModal, True, C.Qt.Dialog)
        assert flags and all(
            after == before | C.Qt.WindowStaysOnTopHint for before, after in flags
        )
        assert observations[1][-1] & C.Qt.WindowStaysOnTopHint
        drain()
        assert made and not valid(made[0])
    finally:
        parent.deleteLater()
        drain()


@pytest.mark.parametrize(
    "result,clicked",
    [
        (-1, "NoButton"),
        (0, "NoButton"),
        (1, "Cancel"),
        (2, "Yes"),
        (3, "No"),
        (4, "Ok"),
    ],
)
def test_static_result_mapping_uses_clicked_standard_button_and_cancel(result, clicked):
    made = []
    kind = W.QMessageBox

    class Box(kind):
        def __init__(self, parent):
            super().__init__(parent)
            made.append(self)

        def exec(self):
            return result

        def clickedButton(self):
            assert result != -1, (
                "Interrupted exec must return Cancel without reading a deleted button"
            )
            return self.button(getattr(kind, clicked))

    expected = kind.Cancel if result == -1 else getattr(kind, clicked)
    value = dialogs.run_standard_message_box(
        NS(QtCore=C, QtGui=NS(QMessageBox=Box)),
        None,
        "Title",
        "Text",
        "Question",
        kind.Yes | kind.No | kind.Cancel | kind.Ok,
        kind.No,
    )
    assert value == expected
    drain()
    assert not valid(made[0])


@pytest.mark.parametrize(
    "failure",
    [
        "setWindowTitle",
        "setText",
        "setIcon",
        "setStandardButtons",
        "setDefaultButton",
        "windowFlags",
        "setWindowFlags",
        "exec",
        "clickedButton",
        "standardButton",
    ],
)
def test_each_configuration_execution_and_result_failure_deletes_owned_box(failure):
    made = []

    class Box(W.QMessageBox):
        def __init__(self, parent):
            super().__init__(parent)
            made.append(self)

        def exec(self):
            return 0

    def fail(self, *args):
        raise RuntimeError(failure)

    setattr(Box, failure, fail)
    with pytest.raises(RuntimeError, match=failure):
        dialogs.run_standard_message_box(
            NS(QtCore=C, QtGui=NS(QMessageBox=Box)),
            None,
            "Title",
            "Text",
            "Warning",
            Box.Yes | Box.No,
            Box.No,
        )
    drain()
    assert made and not valid(made[0])


def test_unknown_icon_failure_deletes_and_helper_is_public():
    made = []

    class Box(W.QMessageBox):
        def __init__(self, parent):
            super().__init__(parent)
            made.append(self)

    with pytest.raises(AttributeError):
        dialogs.run_standard_message_box(
            NS(QtCore=C, QtGui=NS(QMessageBox=Box)),
            None,
            "Title",
            "Text",
            "MissingIcon",
            Box.Ok,
        )
    drain()
    assert made and not valid(made[0])
    assert "run_standard_message_box" in dialogs.__all__
