# this_file: tests/test_fontui_events.py
"""Exercise real event methods while replacing only their native Qt boundary."""

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fontlabapp.fontui.model import BrowserState


@pytest.fixture
def event_classes(monkeypatch):
    modules = ("lifecycle", "preview", "native")
    for name in modules:
        monkeypatch.delitem(sys.modules, f"fontlabapp.fontui.{name}", raising=False)
    monkeypatch.setitem(
        sys.modules, "PythonQt", SimpleNamespace(QtCore=Mock(), QtGui=Mock())
    )
    native = importlib.import_module("fontlabapp.fontui.native")
    yield native.Browser, native.Preview
    for name in modules:
        sys.modules.pop(f"fontlabapp.fontui.{name}", None)


class Font(dict):
    """An available model that can fail at either backend activation read."""

    failure = None

    def __contains__(self, key):
        if self.failure == "contains":
            raise RuntimeError("Font is closed")
        return super().__contains__(key)

    def __getitem__(self, key):
        if self.failure == "lookup":
            raise OSError("Glyph read failed")
        return super().__getitem__(key)


def browser_fixture(browser_class):
    browser = browser_class.__new__(browser_class)
    browser.closed = False
    browser.state = BrowserState(Font(A=object()))
    browser.state.select(["A"])
    browser.on_activate = Mock()
    browser.count_label = Mock()
    browser.glyph_list = Mock()
    browser.preview = Mock()
    browser.thumbnail = Mock()
    return browser


@pytest.mark.parametrize(
    ("failure", "message"),
    [("contains", "Font is closed"), ("lookup", "Glyph read failed")],
)
def test_activate_when_backend_fails_then_clears_and_recovers(
    event_classes, failure, message
):
    browser = browser_fixture(event_classes[0])
    item = SimpleNamespace(text=lambda: "A")
    browser.state.font.failure = failure
    browser.activate(item)
    assert browser.state.error == message, "Backend errors must remain visible"
    assert (
        browser.state.names == browser.state.original == browser.state.selected == ()
    ), "An unavailable model must leave no stale glyph selection"
    browser.glyph_list.setEnabled.assert_called_with(False)
    browser.preview.set_glyph.assert_called_with(None)
    browser.preview.diagnostic.setText.assert_called_with(message)
    browser.on_activate.assert_not_called()
    browser.filter("")
    assert browser.state.names == (), "Filtering must not restore unavailable rows"
    browser.state.font = Font(A=object())
    browser.refresh()
    assert browser.state.error is None and browser.state.names == ("A",), (
        "Explicit replacement and refresh must recover the view"
    )
    assert browser.preview.font is browser.state.font, (
        "Preview must use the refreshed model"
    )
    browser.glyph_list.setEnabled.assert_called_with(True)
    browser.activate(item)
    browser.on_activate.assert_called_once_with(browser.state.font["A"])


def test_activate_when_glyph_removed_then_shows_diagnostic(event_classes):
    browser = browser_fixture(event_classes[0])
    del browser.state.font["A"]
    browser.activate(SimpleNamespace(text=lambda: "A"))
    assert "A" in browser.state.error, (
        "Missing glyph diagnostic must identify the glyph"
    )
    browser.glyph_list.setEnabled.assert_called_with(False)
    browser.on_activate.assert_not_called()


def test_activate_when_consumer_raises_then_propagates_without_backend_diagnostic(
    event_classes,
):
    browser = browser_fixture(event_classes[0])
    browser.on_activate.side_effect = RuntimeError("Consumer callback failed")
    with pytest.raises(RuntimeError, match="Consumer callback failed"):
        browser.activate(SimpleNamespace(text=lambda: "A"))
    assert browser.state.error is None, (
        "Consumer errors must not be labelled backend errors"
    )
    browser.glyph_list.clear.assert_not_called()


@pytest.mark.parametrize(
    "closed,item,callback",
    [(True, True, True), (False, False, True), (False, True, False)],
)
def test_activate_when_inactive_then_does_not_deliver(
    event_classes, closed, item, callback
):
    browser = browser_fixture(event_classes[0])
    browser.closed = closed
    delivered = browser.on_activate
    browser.on_activate = delivered if callback else None
    browser.activate(SimpleNamespace(text=lambda: "A") if item else None)
    delivered.assert_not_called()


class CheckBox:
    def __init__(self, callback, blocked):
        self.callback, self.blocked, self.checked = callback, blocked, False

    def blockSignals(self, value):
        previous, self.blocked = self.blocked, value
        return previous

    def setChecked(self, value):
        changed, self.checked = self.checked != value, value
        if changed and not self.blocked:
            self.callback(value)


@pytest.mark.parametrize("blocked", [False, True])
def test_set_option_when_programmatic_then_syncs_without_duplicate_redraw(
    event_classes, blocked
):
    preview = event_classes[1].__new__(event_classes[1])
    preview.closed, preview.options, preview.canvas = False, {"anchors": False}, Mock()
    box = CheckBox(lambda value: preview.set_option("anchors", value), blocked)
    preview.option_controls = {"anchors": box}
    preview.set_option("anchors", True)
    assert box.checked and preview.options["anchors"], "Setter and checkbox must agree"
    assert box.blocked is blocked, "Setter must preserve pre-existing signal blocking"
    preview.canvas.update.assert_called_once_with()
    box.blocked = False
    preview.canvas.update.reset_mock()
    box.setChecked(False)
    assert not preview.options["anchors"], "The first user toggle must hide the overlay"
    preview.canvas.update.assert_called_once_with()


def test_set_option_when_invalid_or_closed_then_fails_before_redraw(event_classes):
    preview = event_classes[1].__new__(event_classes[1])
    preview.closed, preview.options, preview.canvas = False, {}, Mock()
    with pytest.raises(ValueError, match="Unknown overlay"):
        preview.set_option("unknown", True)
    preview.closed = True
    with pytest.raises(RuntimeError, match="Preview is closed"):
        preview.set_option("anchors", True)
    preview.canvas.update.assert_not_called()
