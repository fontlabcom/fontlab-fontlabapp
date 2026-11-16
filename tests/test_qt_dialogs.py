# this_file: tests/test_qt_dialogs.py
"""Owned dialog operations use injected Qt and preserve existing failure order."""

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import fontlabapp.qt.dialogs as dialogs
import pytest
from qt_dialogs_doubles import Dialog


@pytest.mark.parametrize("parents", [(), (None,), (object(),)])
def test_create_when_parent_arguments_supplied_then_original_constructor_and_setup(
    parents,
):
    box = dialogs.create_message_box(
        SimpleNamespace(QMessageBox=Dialog), 12, None, "Information", parents
    )
    assert box.events == [
        ("construct", parents),
        ("text", "12"),
        ("informative", "None"),
        ("icon", 1),
    ]


@pytest.mark.parametrize("detail", ["", None])
def test_create_when_detail_empty_then_no_detailed_text(detail):
    box = dialogs.create_message_box(
        SimpleNamespace(QMessageBox=Dialog), "t", "i", "Information", detail=detail
    )
    assert [name for name, *_ in box.events] == ["construct", "text", "informative", "icon"]


def test_create_when_detail_given_then_detailed_text_set_as_str():
    box = dialogs.create_message_box(
        SimpleNamespace(QMessageBox=Dialog), "t", "i", "Information", detail=42
    )
    assert box.events[-1] == ("detail", "42")


def test_create_when_detail_setter_raises_then_box_deleted_and_error_reraised():
    made = []

    def construct(*args):
        made.append(Dialog(*args))
        made[-1].fail = "detail"
        return made[-1]

    construct.Information = Dialog.Information
    with pytest.raises(ValueError, match="detail"):
        dialogs.create_message_box(
            SimpleNamespace(QMessageBox=construct), "t", "i", "Information", detail="x"
        )
    assert made[0].events[-2:] == [("detail", "x"), ("delete",)]


@pytest.mark.parametrize("failure", [None, "buttons", "exec"])
def test_run_box_when_complete_or_raises_then_delete_in_finally(failure):
    box = Dialog()
    box.fail = failure
    if failure:
        with pytest.raises(ValueError, match=failure):
            dialogs.run_message_box(box, 7)
    else:
        assert dialogs.run_message_box(box, 7) == 1
    assert box.events[-1] == ("delete",)


@pytest.mark.parametrize(
    "failure", [None, "configure", "title", "directory", "exec", "files"]
)
def test_file_dialog_when_complete_or_raises_then_setup_result_and_owned_cleanup(
    failure,
):
    box = Dialog()
    box.fail = failure
    gui = SimpleNamespace(QFileDialog=lambda *args: box)

    def configure(kind, dialog):
        assert kind is gui.QFileDialog and dialog is box
        dialog.event("configure")

    if failure:
        with pytest.raises(ValueError, match=failure):
            dialogs.run_file_dialog(gui, configure, "title", "directory", ())
    else:
        assert dialogs.run_file_dialog(gui, configure, "title", "directory", ()) == [
            "one",
            "two",
        ]
    assert box.events[-1] == ("delete",)


def test_file_dialog_when_cancelled_or_empty_options_then_no_selection_and_defaults():
    box = Dialog()
    box.accepted = 0
    assert (
        dialogs.run_file_dialog(
            SimpleNamespace(QFileDialog=lambda *args: box),
            lambda *args: None,
            None,
            None,
            (),
        )
        is None
    )
    assert ("title", "") in box.events
    assert not any(event[0] in {"directory", "files"} for event in box.events)


@pytest.mark.parametrize(
    ("kinds", "expected"),
    [
        (["ufo", ".glyphs"], ["Files (*.ufo *.glyphs)"]),
        ((".ufo",), ["Files (*.ufo)"]),
        (None, []),
        ([], []),
    ],
)
def test_name_filters_when_kinds_given_then_one_qt_filter_or_empty(kinds, expected):
    assert dialogs.name_filters(kinds) == expected


class TextDialog(Dialog):
    """Dialog double with the QInputDialog text API."""

    def __init__(self, *args):
        super().__init__(*args)
        self.text = "typed"

    def setLabelText(self, value):
        self.event("label", value)

    def setTextValue(self, value):
        self.event("value", value)

    def setOkButtonText(self, value):
        self.event("ok", value)

    def textValue(self):
        self.event("read")
        return self.text


@pytest.mark.parametrize(
    "failure", [None, "title", "label", "value", "ok", "exec", "read"]
)
def test_text_dialog_when_complete_or_raises_then_text_and_owned_cleanup(failure):
    box = TextDialog()
    box.fail = failure
    gui = SimpleNamespace(QInputDialog=lambda *args: box)
    if failure:
        with pytest.raises(ValueError, match=failure):
            dialogs.run_text_dialog(gui, "Name?", "old", "Rename", "Go")
    else:
        assert dialogs.run_text_dialog(gui, "Name?", "old", "Rename", "Go") == "typed"
        assert [e for e in box.events if e[0] != "construct"][:5] == [
            ("title", "Rename"),
            ("label", "Name?"),
            ("value", "old"),
            ("ok", "Go"),
            ("exec",),
        ]
    assert box.events[-1] == ("delete",)


def test_text_dialog_when_cancelled_then_none_without_reading_text():
    box = TextDialog()
    box.accepted = 0
    result = dialogs.run_text_dialog(
        SimpleNamespace(QInputDialog=lambda *args: box), "m", "v", "t"
    )
    assert result is None
    assert ("read",) not in box.events and box.events[-1] == ("delete",)


def test_text_dialog_when_empty_options_then_blank_text_and_no_ok_label():
    box = TextDialog()
    dialogs.run_text_dialog(
        SimpleNamespace(QInputDialog=lambda *args: box), None, None, None, None
    )
    assert ("title", "") in box.events
    assert ("label", "") in box.events
    assert ("value", "") in box.events
    assert not any(event[0] == "ok" for event in box.events)


def test_text_dialog_when_parent_args_then_positional_constructor():
    seen = []

    def make(*args):
        seen.append(args)
        return TextDialog()

    parent = object()
    dialogs.run_text_dialog(
        SimpleNamespace(QInputDialog=make), "m", "v", "t", parent_args=(parent,)
    )
    assert seen == [(parent,)]


@pytest.mark.parametrize("failure", [None, "modal", "show"])
def test_show_when_retained_then_kept_before_show_even_if_show_fails(failure):
    box, boxes = Dialog(), []
    box.fail = failure
    if failure:
        with pytest.raises(ValueError, match=failure):
            dialogs.show_message_box(box, boxes)
    else:
        dialogs.show_message_box(box, boxes)
    assert boxes == [box], "ownership starts before the modeless show calls"
    box.fail = None
    dialogs.close_message_boxes(boxes)
    assert boxes == [] and box.events[-2:] == [("close",), ("delete",)]
    dialogs.close_message_boxes(boxes)


@pytest.mark.parametrize("exit_failure", [False, True])
def test_close_when_failures_then_every_box_attempted_and_exit_priority_preserved(
    exit_failure,
):
    seen = []
    ordinary = ValueError("ordinary")
    urgent = KeyboardInterrupt("interrupt") if exit_failure else RuntimeError("later")

    def box(name, error):
        def close():
            seen.append(name)
            raise error

        return SimpleNamespace(close=close, deleteLater=lambda: seen.append("delete"))

    boxes = [box("second", urgent), box("first", ordinary)]
    with pytest.raises(type(urgent) if exit_failure else ValueError) as caught:
        dialogs.close_message_boxes(boxes)
    assert caught.value is (urgent if exit_failure else ordinary)
    assert seen == ["first", "second"] and boxes == [], (
        "retain the original LIFO attempt and failure order"
    )


def test_close_when_delete_fails_then_continue_other_box():
    first, second = Dialog(), Dialog()
    first.fail = "delete"
    boxes = [second, first]
    with pytest.raises(ValueError, match="delete"):
        dialogs.close_message_boxes(boxes)
    assert boxes == [] and second.events[-1] == ("delete",)


def test_import_when_cold_then_only_stdlib_dependencies():
    script = """
import importlib.abc,sys
class StdlibOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] not in sys.stdlib_module_names | {'fontlabapp'}:
            raise AssertionError('Foreign import: ' + fullname)
sys.meta_path.insert(0, StdlibOnly())
sys.path.insert(0, sys.argv[1])
import fontlabapp.qt.dialogs
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            script,
            str((Path(__file__).resolve().parents[1] / "src")),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
