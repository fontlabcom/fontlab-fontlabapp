# this_file: tests/test_borrowed_message_box.py
"""Generic message-box ownership and borrowed Qt widgets, without foreign APIs."""

from types import SimpleNamespace as NS

import fontlabapp.qt.dialogs as api
import pytest
from qt_dialogs_doubles import Dialog


class Widget:
    def __init__(self, parent=None, property_parent=False):
        self.parent = parent
        self.parentWidget = parent if property_parent else lambda: self.parent
        self.events = []

    def setParent(self, parent):
        self.events.append(parent)
        self.parent = parent


class Box(Dialog):
    AcceptRole = 7

    def __init__(self, buttons, clicked=1, fail=None):
        super().__init__()
        self.buttons, self.clicked, self.fail = buttons, clicked, fail

    def addButton(self, button, role):
        button.setParent(self)
        self.event("add", button, role)

    def layout(self):
        self.event("layout")
        return self

    def rowCount(self):
        self.event("row")
        return 3

    def columnCount(self):
        self.event("columns")
        return 4

    def addWidget(self, widget, *args):
        widget.setParent(self)
        self.event("accessory", widget, args)

    def clickedButton(self):
        self.event("clicked")
        return self.buttons[self.clicked] if self.clicked is not None else None

    def deleteLater(self):
        assert all(button.parent is not self for button in self.buttons)
        super().deleteLater()


@pytest.mark.parametrize("accessory", [False, True])
@pytest.mark.parametrize("clicked", [None, 0, 1])
@pytest.mark.parametrize("property_parent", [False, True])
def test_borrowed_box_restores_original_parents_and_returns_index(
    accessory, clicked, property_parent
):
    parent = object()
    buttons = [Widget(parent, property_parent), Widget(None, property_parent)]
    extra = Widget(parent, property_parent) if accessory else None
    box = Box(buttons, clicked)
    assert api.run_button_message_box(box, buttons, extra) == clicked
    assert buttons[0].parent is parent and buttons[1].parent is None
    if extra is not None:
        assert extra.parent is parent
        assert ("accessory", extra, (3, 0, 1, 4)) in box.events, (
            "span every real grid column"
        )
    assert box.events[-1] == ("delete",)


@pytest.mark.parametrize(
    "failure", ["add", "layout", "row", "columns", "accessory", "exec", "clicked"]
)
def test_borrowed_box_restores_widgets_after_partial_configuration_or_execution(
    failure,
):
    parent = object()
    buttons, extra = [Widget(parent), Widget()], Widget(parent)
    box = Box(buttons, fail=failure)
    with pytest.raises(ValueError, match=failure):
        api.run_button_message_box(box, buttons, extra)
    assert buttons[0].parent is parent and buttons[1].parent is None
    assert extra.parent is parent and box.events[-1] == ("delete",)


@pytest.mark.parametrize("failure", ["text", "informative", "icon"])
def test_create_failure_deletes_its_unreturned_owned_box(failure):
    box = Dialog()
    box.fail = failure

    def factory():
        return box

    factory.Information = 1
    with pytest.raises(ValueError, match=failure):
        api.create_message_box(
            NS(QMessageBox=factory), "text", "details", "Information"
        )
    assert box.events[-1] == ("delete",), "unreturned dialog must not leak"


def test_release_closed_removes_only_hidden_boxes_and_keeps_visible_owners():
    visible, hidden = Dialog(), Dialog()
    visible.isVisible = lambda: True
    hidden.isVisible = lambda: False
    boxes = [hidden, visible]
    api.release_closed_message_boxes(boxes)
    assert boxes == [visible] and hidden.events[-1] == ("delete",)
    assert visible.events == [("construct", ())]


def test_modeless_configuration_failure_is_retained_before_callback():
    boxes, box = [], Dialog()

    def configure(current):
        assert boxes == [current]
        raise RuntimeError("configure")

    with pytest.raises(RuntimeError, match="configure"):
        api.show_message_box(box, boxes, configure)
    assert boxes == [box] and box.events == [("construct", ())]
    api.close_message_boxes(boxes)


def test_parent_lookup_failure_deletes_box_without_borrowing_any_widget():
    class BadParent:
        @property
        def parentWidget(self):
            raise RuntimeError("parent lookup")

    box = Dialog()
    with pytest.raises(RuntimeError, match="parent lookup"):
        api.run_button_message_box(box, [BadParent()])
    assert box.events[-1] == ("delete",)


def test_restore_failure_propagates_before_owned_box_deletion():
    button = Widget()
    box = Box([button], clicked=0)

    def restore(parent):
        if parent is None:
            raise RuntimeError("restore")
        button.parent = parent

    button.setParent = restore
    with pytest.raises(RuntimeError, match="restore"):
        api.run_button_message_box(box, [button])
    assert ("delete",) not in box.events, (
        "do not delete borrowed child on restore failure"
    )
