# this_file: tests/test_cov_fontui_features.py
"""Coverage for ``fontlabapp.fontui.features``: constructor wiring, refusals and error paths."""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from fontlabapp.fontui.features_state import PREFIX

PREFIX_TEXT = "languagesystem DFLT dflt;\n"
LIGA = "feature liga {\n  sub f i by f_i;\n} liga;\n"


@pytest.fixture
def features_module(monkeypatch: pytest.MonkeyPatch):
    """Import ``features`` against a mocked PythonQt, outside FontLab."""
    from _feature_source_qt import owned_application, dispose_controls
    widgets = []
    with owned_application():
        for name in ("features", "lifecycle"):
            monkeypatch.delitem(sys.modules, f"fontlabapp.fontui.{name}", raising=False)
        monkeypatch.setitem(sys.modules, "PythonQt", SimpleNamespace(QtGui=Mock()))
        monkeypatch.setitem(sys.modules, "fontlab", None)
        module = importlib.import_module("fontlabapp.fontui.features")
        module._source_widgets = widgets
        module.FeaturesEditor._source_widgets = widgets
        try:
            yield module
        finally:
            dispose_controls(widgets)
        for name in ("features", "lifecycle"):
            sys.modules.pop(f"fontlabapp.fontui.{name}", None)


class Blocks:
    """Fontport-like structured features model."""

    def __init__(self) -> None:
        self.value = {"prefix": PREFIX_TEXT, "features": [("liga", LIGA)]}
        self.calls: list[tuple[Any, str]] = []

    @property
    def text(self) -> str:
        return self.value["prefix"] + "".join(code for _, code in self.value["features"])

    def get_blocks(self) -> dict:
        return {"prefix": self.value["prefix"], "features": list(self.value["features"])}

    def set_blocks(self, values: dict, *, undo_name: str) -> None:
        self.calls.append((values, undo_name))
        self.value = {"prefix": values["prefix"], "features": list(values["features"])}


class TextControl:
    """QPlainTextEdit stand-in with LF-normalised text."""

    def __init__(self) -> None:
        self.value, self.readOnly = "", False
        self.textChanged = Mock()

    def setPlainText(self, text: str) -> None:
        self.value = text.replace("\r\n", "\n").replace("\r", "\n")

    def toPlainText(self) -> str:
        return self.value

    def setReadOnly(self, flag: bool) -> None:
        self.readOnly = flag

    def setEnabled(self, flag: bool) -> None:
        self.enabled = flag


class Combo:
    """QComboBox stand-in."""

    def __init__(self) -> None:
        self.items: list[str] = []
        self.currentIndex = -1
        self.currentIndexChanged = Mock()
        self.enabled = True

    def blockSignals(self, flag: bool) -> bool:
        return False

    def clear(self) -> None:
        self.items = []

    def addItems(self, items: Any) -> None:
        self.items += list(items)

    def setCurrentIndex(self, index: int) -> None:
        self.currentIndex = index

    def setEnabled(self, flag: bool) -> None:
        self.enabled = flag


def _install_controls(editor: Any) -> None:
    from _feature_source_qt import TextAdapter
    editor.text_control, editor.block_control = TextAdapter(editor, type(editor)._source_widgets), Combo()
    editor.tag_control = SimpleNamespace(text="", setText=Mock(), setEnabled=Mock())
    for name in ("status", "diagnostic", "apply_button", "revert_button", "add_button", "remove_button"):
        setattr(editor, name, Mock())


def make(module: Any, features: Any, *, font: Any = None, refresh: bool = True) -> Any:
    """An editor built without running ``__init__`` (as the existing suite does)."""
    editor = module.FeaturesEditor.__new__(module.FeaturesEditor)
    editor.closed, editor.key, editor.state = False, PREFIX, None
    editor.blocks, editor.editable = False, False
    editor.font = font if font is not None else SimpleNamespace(features=features)
    editor.connections, editor.destroying, editor.widget = [], False, Mock()
    editor._closing = False
    editor._close_complete = False
    editor._child_closed = False
    editor._hidden = False
    editor._delete_scheduled = False
    editor._close_error = None
    editor._parent_dead = False
    editor._own_observer = None
    editor._parent_observer = None
    editor._source_widgets = module._source_widgets
    _install_controls(editor)
    editor.on_apply = Mock()
    if refresh:
        assert editor.refresh(), "fixture model must load"
    return editor


def message(editor: Any) -> str:
    return editor.diagnostic.setText.call_args.args[0]


# ------------------------------------------------------------ constructor


def test_init_when_built_then_wires_every_control_to_its_action(
    features_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each signal is connected, history and change followers are armed, and the model loads."""
    followed: list[str] = []

    def build(editor: Any) -> None:
        _install_controls(editor)

    monkeypatch.setattr(features_module, "build", build)
    monkeypatch.setattr(features_module, "follow_history", lambda owner, cb: followed.append("history"))
    monkeypatch.setattr(features_module, "follow_changes", lambda owner, cb, fonts: followed.append("changes"))
    font = SimpleNamespace(features=Blocks())
    editor = features_module.FeaturesEditor(font, None, on_apply=Mock())
    assert followed == ["history", "changes"], f"followers armed in the wrong order: {followed}"
    assert editor.state is not None and editor.editable and editor.blocks, "constructor must load the model"
    wired = {id(signal): callback for signal, callback in editor.connections}
    for signal, action in (
        (editor.text_control.textChanged, "_mark"),
        (editor.block_control.currentIndexChanged, "_switch"),
        (editor.add_button.clicked, "add_feature"),
        (editor.remove_button.clicked, "remove_feature"),
        (editor.apply_button.clicked, "apply"),
        (editor.revert_button.clicked, "refresh"),
    ):
        assert id(signal) in wired, f"{action} is not connected"
        setattr(editor, action, Mock())
        wired[id(signal)](1, 2)  # signals pass arguments; the lambdas drop them
        handler = getattr(editor, action)
        assert handler.call_count == 1, f"{action} must run once per signal emission"
        assert handler.call_args == ((), {}), f"{action} must receive none of the signal arguments"


# ------------------------------------------------------------ _changed / dirty


def test_changed_when_closed_then_does_nothing(features_module: Any) -> None:
    """A closed editor ignores FontLab change notifications."""
    editor = make(features_module, Blocks())
    editor.closed = True
    editor.refresh = Mock()
    editor._changed()
    assert editor.refresh.call_count == 0, "a closed editor must not reload"


def test_changed_when_dirty_then_keeps_staged_text_and_warns(features_module: Any) -> None:
    """Staged edits survive a FontLab change; the user is told to use Revert."""
    editor = make(features_module, Blocks())
    editor.text_control.value = "edited;\n"
    editor.refresh = Mock()
    editor._changed()
    assert editor.refresh.call_count == 0, "staged edits must not be overwritten by a reload"
    assert "Revert reloads it" in message(editor), "the user is pointed at Revert"


def test_changed_when_clean_then_reloads_from_the_font(features_module: Any) -> None:
    """A clean editor simply reloads."""
    editor = make(features_module, Blocks())
    editor.refresh = Mock()
    editor._changed()
    assert editor.refresh.call_count == 1, "a clean editor reloads exactly once"
    assert editor.refresh.call_args == ((), {}), "the reload takes no arguments"


def test_dirty_when_closed_or_not_loaded_then_false(features_module: Any) -> None:
    """Closed or never-loaded editors are never dirty."""
    editor = make(features_module, Blocks())
    editor.text_control.value = "changed"
    editor.closed = True
    assert editor.dirty is False, "closed editor must not report dirty"
    editor.closed, editor.state = False, None
    assert editor.dirty is False, "editor without state must not report dirty"


def test_dirty_when_state_staged_or_widget_text_differs_then_true(features_module: Any) -> None:
    """Dirty comes from the staged state or from unstashed widget text."""
    editor = make(features_module, Blocks())
    assert editor.dirty is False, "a freshly loaded editor is clean"
    editor.text_control.value = "different"
    assert editor.dirty is True, "unstashed widget text counts as dirty"
    editor.text_control.value = editor.state.text(editor.key)
    editor.state.add("kern")
    assert editor.dirty is True, "a staged new block counts as dirty"


# ------------------------------------------------------------ _features / _read


def test_features_when_font_missing_then_value_error(features_module: Any) -> None:
    """No font is a hard error raised to the caller."""
    editor = make(features_module, None, refresh=False)
    editor.font = None
    with pytest.raises(ValueError, match="No font supplied"):
        editor._features()


def test_read_when_model_has_no_blocks_then_wraps_whole_text(features_module: Any) -> None:
    """Whole-text models read as a prefix with no features; ``None`` text becomes empty."""
    editor = make(features_module, SimpleNamespace(text=None, apply=lambda *a, **k: None))
    assert editor._read(SimpleNamespace(text=None)) == {
        "prefix": "",
        "features": [],
    }, "None text reads as an empty prefix"
    assert editor._read(SimpleNamespace(text="a;\n")) == {
        "prefix": "a;\n",
        "features": [],
    }, "whole text reads as the prefix"


# ------------------------------------------------------------ _switch / _mark


def test_switch_when_closed_or_unloaded_then_returns_quietly(features_module: Any) -> None:
    """The combo signal is ignored once closed or before a model loaded."""
    editor = make(features_module, Blocks())
    editor._show = Mock()
    editor.closed = True
    editor._switch()
    editor.closed, editor.state = False, None
    editor._switch()
    assert editor._show.call_count == 0, "no block is shown when closed or unloaded"


def test_switch_when_staged_text_has_mixed_endings_then_reports_and_still_switches(
    features_module: Any,
) -> None:
    """Refused mixed-ending stash retains the exact draft and selected block."""
    from copy import deepcopy
    from PySide6.QtGui import QTextCursor
    from _feature_source_qt import snapshot

    model = Blocks()
    model.value["prefix"] = "a;\r\nb;\n"
    editor = make(features_module, model)
    editor.state.set_text("liga", LIGA + "# sibling\n")
    staged = deepcopy(editor.state.staged)
    editor.text_control.value = "a;\nc;\n"
    cursor = editor.text_control.textCursor()
    cursor.setPosition(1)
    cursor.setPosition(4, QTextCursor.KeepAnchor)
    editor.text_control.setTextCursor(cursor)
    before = snapshot(editor.text_control)
    editor.block_control.currentIndex = editor.state.keys().index("liga")
    editor._switch()
    assert "Mixed" in message(editor), "the stash failure names the mixed line endings"
    assert editor.key == PREFIX and editor.block_control.currentIndex == 0
    assert snapshot(editor.text_control) == before
    assert editor.state.staged == staged
    assert not model.calls
    editor.on_apply.assert_not_called()


def test_mark_when_closed_then_leaves_status_untouched(features_module: Any) -> None:
    """A closed editor does not update its status."""
    editor = make(features_module, Blocks())
    editor.status.reset_mock()
    editor.closed = True
    editor._mark()
    assert editor.status.setText.call_count == 0, "a closed editor leaves its status alone"


def test_mark_when_dirty_then_reports_modified_and_enables_apply(features_module: Any) -> None:
    """Edits flip the status and enable Apply for editable models."""
    editor = make(features_module, Blocks())
    editor.text_control.value = "x;\n"
    editor._mark()
    assert editor.status.setText.call_args == (("Modified, not applied",), {}), "status reports the edit"
    assert editor.apply_button.setEnabled.call_args == ((True,), {}), "Apply is enabled after an edit"


def test_mark_when_clean_then_reports_unmodified_and_disables_apply(features_module: Any) -> None:
    """A clean editor shows Unmodified and keeps Apply disabled."""
    editor = make(features_module, Blocks())
    editor._mark()
    assert editor.status.setText.call_args == (("Unmodified",), {}), "status reports no edit"
    assert editor.apply_button.setEnabled.call_args == ((False,), {}), "Apply stays disabled when clean"


# ------------------------------------------------------------ unavailable / refresh


def test_refresh_when_closed_then_false_without_reading_the_font(features_module: Any) -> None:
    """Closed editors do not touch the font."""
    editor = make(features_module, Blocks())
    editor.closed = True
    editor._features = Mock()
    assert editor.refresh() is False, "refresh fails when the document is gone"
    assert editor._features.call_count == 0, "a closed editor must not read the font"


def test_refresh_when_font_access_fails_then_disables_controls_and_shows_error(features_module: Any) -> None:
    """A document that went away disables every control and shows the error text."""
    editor = make(features_module, Blocks())
    editor.font = SimpleNamespace(features=Mock(get_blocks=Mock(side_effect=RuntimeError("document closed"))))
    assert editor.refresh() is False, "refresh reports failure when the document is gone"
    assert editor.editable is False, "the editor stops being editable"
    assert editor.text_control.enabled is False, "the text control is disabled"
    for control in (editor.apply_button, editor.revert_button, editor.add_button, editor.remove_button):
        assert control.setEnabled.call_args == ((False,), {}), "every button is disabled"
    assert editor.block_control.enabled is False, "the block combo is disabled"
    assert message(editor) == "document closed", "the error text is shown"


def test_refresh_when_model_read_only_then_text_is_read_only_with_explanation(features_module: Any) -> None:
    """Models with neither set_blocks nor apply are shown but cannot be edited."""
    editor = make(features_module, SimpleNamespace(text=LIGA))
    assert editor.text_control.readOnly is True, "the text control is read-only"
    assert editor.editable is False, "the editor is not editable"
    assert message(editor).startswith("Feature code is read-only"), "the read-only reason is explained"


# ------------------------------------------------------------ add / remove


def test_add_feature_when_tag_duplicate_then_reports_and_returns_false(features_module: Any) -> None:
    """Adding an existing tag is refused with the state's message."""
    editor = make(features_module, Blocks())
    editor.tag_control.text = "liga"
    assert editor.add_feature() is False, "a duplicate tag is refused"
    assert "already exists" in message(editor), "the refusal names the duplicate"


def test_add_feature_when_not_loaded_then_reports_and_returns_false(features_module: Any) -> None:
    """With no loaded state the attribute error is reported rather than raised."""
    editor = make(features_module, Blocks())
    editor.state = None
    assert editor.add_feature() is False, "a missing state is reported, not raised"
    assert message(editor), "a diagnostic must be shown"


def test_remove_feature_when_prefix_selected_then_reports_and_returns_false(features_module: Any) -> None:
    """The prefix block cannot be removed."""
    editor = make(features_module, Blocks())
    assert editor.key == PREFIX, "the prefix block is selected initially"
    assert editor.remove_feature() is False, "the prefix cannot be removed"
    assert "prefix" in message(editor), "the refusal mentions the prefix"


def test_remove_feature_when_not_loaded_then_reports_and_returns_false(features_module: Any) -> None:
    """With no loaded state the attribute error is reported."""
    editor = make(features_module, Blocks())
    editor.state = None
    assert editor.remove_feature() is False, "a missing state is reported, not raised"
    assert message(editor), "a diagnostic must be shown"


# ------------------------------------------------------------ apply


def test_apply_when_closed_or_not_loaded_then_false(features_module: Any) -> None:
    """Closed or unloaded editors never write."""
    model = Blocks()
    editor = make(features_module, model)
    editor.closed = True
    assert editor.apply() is False, "a closed editor never writes"
    editor.closed, editor.state = False, None
    assert editor.apply() is False, "an unloaded editor never writes"
    assert model.calls == [], "the model must not be written"


def test_apply_when_document_closed_since_refresh_then_unavailable(features_module: Any) -> None:
    """Reading ``features.text`` fails for a closed document; Apply disables the editor."""

    class Gone:
        def __init__(self) -> None:
            self.live = True

        get_blocks = Blocks().get_blocks
        set_blocks = staticmethod(lambda *a, **k: None)

        @property
        def text(self) -> str:
            if not self.live:
                raise RuntimeError("document is closed")
            return PREFIX_TEXT

    model = Gone()
    editor = make(features_module, model)
    model.live = False
    assert editor.apply() is False, "apply fails when the document went away"
    assert editor.editable is False, "the editor becomes uneditable"
    assert message(editor) == "document is closed", "the error text is shown"


def test_apply_when_model_read_only_then_refuses_with_explanation(features_module: Any) -> None:
    """A read-only model produces the read-only diagnostic and no write."""
    editor = make(features_module, SimpleNamespace(text=LIGA))
    assert editor.apply() is False, "a read-only model refuses to apply"
    assert message(editor).startswith("Feature code is read-only"), "the read-only reason is explained"


def test_apply_when_readback_differs_then_reports_backend_mismatch(features_module: Any) -> None:
    """A backend that stores something else than was applied is reported."""
    model = Blocks()
    model.set_blocks = lambda values, *, undo_name: None  # silently ignores the write
    editor = make(features_module, model)
    editor.text_control.value = "changed;\n"
    assert editor.apply() is False, "a mismatching read-back fails the apply"
    assert message(editor) == "Backend feature code differs from the applied code", "mismatch is named"


def test_apply_when_callback_fails_then_apply_still_succeeds_with_notice(features_module: Any) -> None:
    """A failing consumer callback is contained and reported after a successful write."""
    model = Blocks()
    editor = make(features_module, model)
    editor.on_apply = Mock(side_effect=RuntimeError("consumer bug"))
    editor.text_control.value = "changed;\n"
    assert editor.apply() is True, "a failing callback does not undo the apply"
    assert len(model.calls) == 1, "the write itself must have happened"
    assert message(editor) == "Applied; refresh callback failed: consumer bug", "callback failure is reported after the write"


def test_apply_when_callback_fails_after_close_then_notice_is_suppressed(features_module: Any) -> None:
    """If the callback closed the editor, no diagnostic is written to dead widgets."""
    editor = make(features_module, Blocks())

    def callback(font: Any, text: str) -> None:
        editor.closed = True
        raise RuntimeError("late")

    editor.on_apply = callback
    editor.text_control.value = "changed;\n"
    assert editor.apply() is True, "the apply succeeds despite the late callback failure"
    assert message(editor) == "Applied feature code (not compiled).", "late callback failure is not shown"


def test_apply_when_no_callback_then_applies_without_notifying(features_module: Any) -> None:
    """``on_apply=None`` is allowed."""
    model = Blocks()
    editor = make(features_module, model)
    editor.on_apply = None
    editor.text_control.value = "changed;\n"
    assert editor.apply() is True, "apply works without a callback"
    assert len(model.calls) == 1, "exactly one write happens"
    assert message(editor) == "Applied feature code (not compiled).", "no callback means a plain success notice"


def test_add_and_remove_feature_when_valid_then_stage_block_and_show_it(features_module: Any) -> None:
    """A new tag becomes the shown block and the tag field is cleared; removal returns to the prefix."""
    editor = make(features_module, Blocks())
    editor.tag_control.text = " kern "
    assert editor.add_feature() is True, "a trimmed new tag is accepted"
    assert editor.key == "kern", "the new block is shown"
    assert editor.block_control.items == [PREFIX, "liga", "kern"], "the combo lists the new block last"
    assert editor.tag_control.setText.call_args == (("",), {}), "the tag field is cleared"
    assert editor.remove_feature() is True, "the staged block can be removed"
    assert editor.key == PREFIX, "removal returns to the prefix"
    assert "kern" not in editor.state.keys(), "the removed block is gone from the state"


def test_apply_when_nothing_changed_then_says_so_and_does_not_write(features_module: Any) -> None:
    """An untouched editor reports that there is nothing to apply."""
    model = Blocks()
    editor = make(features_module, model)
    assert editor.apply() is False, "nothing to apply returns False"
    assert message(editor) == "No changes to apply.", "the user is told nothing changed"
    assert model.calls == [], "the model must not be written"


def test_apply_when_whole_text_model_then_writes_with_undo_name(features_module: Any) -> None:
    """Models with only ``apply`` receive the whole text and the undo name."""
    calls: list[tuple[str, str]] = []

    class Whole:
        text = "a;\n"

        def apply(self, text: str, *, undo_name: str) -> None:
            calls.append((text, undo_name))
            self.text = text

    editor = make(features_module, Whole())
    editor.text_control.value = "b;\n"
    assert editor.apply() is True, "a whole-text model applies"
    assert calls == [("b;\n", features_module.UNDO_NAME)], "text and undo name reach the model"


# ------------------------------------------------------------ close


def test_close_when_called_then_drops_callback_and_releases_widget(features_module: Any) -> None:
    """Closing forgets the callback, disconnects, hides and schedules deletion."""
    editor = make(features_module, Blocks())
    signal = Mock()
    handler = lambda *a: None
    editor.connections.append((signal, handler))
    editor.close()
    assert editor.on_apply is None, "the callback is dropped"
    assert editor.closed is True, "the editor is marked closed"
    assert signal.disconnect.call_args == ((handler,), {}), "the recorded handler is disconnected"
    assert editor.widget.hide.call_count == 1, "the widget is hidden"
    assert editor.widget.deleteLater.call_count == 1, "deletion is scheduled"
    editor.close()  # idempotent
    assert editor.widget.hide.call_count == 1, "a second close must not hide again"
