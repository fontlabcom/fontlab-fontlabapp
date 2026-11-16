# this_file: tests/test_ui_kerning.py
"""B07 explicit actions validate and dispatch one borrowed-model batch."""

import importlib
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def editor_class(monkeypatch):
    importlib.import_module(
        "fontlab_fontport.kerning_edit"
    )  # [test] installs Fontport; never skip
    for name in ("kerning", "kerning_view"):
        monkeypatch.delitem(sys.modules, f"fontlabapp.fontui.{name}", raising=False)
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.lifecycle", raising=False)
    monkeypatch.setitem(sys.modules, "PythonQt", SimpleNamespace(QtGui=Mock()))
    module = importlib.import_module("fontlabapp.fontui.kerning")
    yield module.KerningEditor
    for name in ("kerning", "kerning_view"):
        sys.modules.pop(f"fontlabapp.fontui.{name}", None)
    sys.modules.pop("fontlabapp.fontui.lifecycle", None)


def fixture_editor(cls):
    editor = cls.__new__(cls)
    editor.closed = False

    class Pairs(dict):
        def apply(self, values, *, undo_name):
            self.clear()
            self.update(values)

    pairs = Pairs({("A", "V"): -12})
    pairs.apply = Mock(wraps=pairs.apply)
    editor.font = SimpleNamespace(kerning=pairs, groups={}, keys=lambda: ("A", "V"))
    editor.left_control = Mock(text="A")
    editor.right_control = Mock(text="V")
    editor.value_control = Mock(text="0")
    editor.diagnostic, editor.on_apply = Mock(), Mock()
    editor.refresh = Mock(return_value=True)
    return editor, pairs


def test_kerning_factory_import_stays_host_and_fontport_free():
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from fontlabapp.fontui import kerning_editor
assert callable(kerning_editor)
assert 'PythonQt' not in sys.modules
assert not [m for m in sys.modules if m.startswith('fontlabapp.fontui.') and m != 'fontlabapp.fontui.model']
""",
        ],
        check=True,
    )


@pytest.mark.parametrize(
    "action,expected", [("apply", {("A", "V"): 0}), ("delete", {})]
)
def test_explicit_action_is_one_batch_with_readback_and_callback(
    editor_class, action, expected
):
    editor, pairs = fixture_editor(editor_class)
    assert editor.edit(action) is True
    assert dict(pairs) == expected
    pairs.apply.assert_called_once()
    editor.on_apply.assert_called_once_with(editor.font, expected)


@pytest.mark.parametrize("value", ["nan", "inf", "", "not a number"])
def test_bad_value_never_mutates_or_calls_back(editor_class, value):
    editor, pairs = fixture_editor(editor_class)
    editor.value_control.text = value
    assert editor.edit("apply") is False
    assert dict(pairs) == {("A", "V"): -12}
    pairs.apply.assert_not_called()
    editor.on_apply.assert_not_called()


def test_unknown_glyph_and_backend_precision_refusal_are_visible(editor_class):
    editor, pairs = fixture_editor(editor_class)
    editor.left_control.text = "missing"
    assert editor.edit("apply") is False
    pairs.apply.assert_not_called()
    editor.left_control.text = "A"
    editor.value_control.text = "-3.75"
    pairs.apply.side_effect = NotImplementedError(
        "Native history rounds fractional values"
    )
    assert editor.edit("apply") is False
    assert "fractional" in editor.diagnostic.setText.call_args.args[0]
    editor.on_apply.assert_not_called()


def test_ignored_native_write_never_claims_success(editor_class):
    editor, pairs = fixture_editor(editor_class)
    pairs.apply = Mock(return_value=None)
    assert editor.edit("apply") is False
    editor.on_apply.assert_not_called()
    assert "readback" in editor.diagnostic.setText.call_args.args[0]


def test_closed_handle_and_noop_never_dispatch(editor_class):
    editor, pairs = fixture_editor(editor_class)
    editor.value_control.text = "-12"
    assert editor.edit("apply") is False
    pairs.apply.assert_not_called()
    editor.closed = True
    assert editor.edit("delete") is False
    pairs.apply.assert_not_called()


@pytest.mark.parametrize(
    "value,text",
    [(-0.0, "0"), (0, "0"), (-82.0, "-82"), (12, "12"), (-3.5, "-3.5")],
)
def test_number_text_hides_signed_zero_and_integral_fraction(editor_class, value, text):
    from fontlabapp.fontui.kerning import number_text

    assert number_text(value) == text


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot):
        self.slots.remove(slot)

    def emit(self, *args):
        for slot in list(self.slots):
            slot(*args)


def test_history_actions_refresh_until_close(monkeypatch):
    actions = {
        "actionUndo": SimpleNamespace(triggered=Signal()),
        "actionRedo": SimpleNamespace(triggered=Signal()),
    }
    window = SimpleNamespace(findChild=lambda cls, name: actions.get(name))
    monkeypatch.setitem(
        sys.modules, "fontlab", SimpleNamespace(MainWindow=lambda: window)
    )
    monkeypatch.setitem(sys.modules, "PythonQt", SimpleNamespace(QtGui=Mock()))
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.lifecycle", raising=False)
    lifecycle = importlib.import_module("fontlabapp.fontui.lifecycle")
    owner = lifecycle.Owned.__new__(lifecycle.Owned)
    owner.closed, owner.connections, owner.destroying = False, [], False
    owner._closing = False
    owner._close_complete = False
    owner._child_closed = False
    owner._hidden = False
    owner._delete_scheduled = False
    owner._close_error = None
    owner._parent_dead = False
    owner._own_observer = None
    owner._parent_observer = None
    owner.widget, calls = Mock(), []
    lifecycle.follow_history(owner, lambda: calls.append(1))
    actions["actionUndo"].triggered.emit(False)
    actions["actionRedo"].triggered.emit(False)
    assert calls == [1, 1]
    owner.close()
    actions["actionUndo"].triggered.emit(False)
    assert calls == [1, 1] and not actions["actionUndo"].triggered.slots
    sys.modules.pop("fontlabapp.fontui.lifecycle", None)


def test_history_follow_is_optional_outside_fontlab(monkeypatch):
    monkeypatch.setitem(sys.modules, "PythonQt", SimpleNamespace(QtGui=Mock()))
    monkeypatch.setitem(sys.modules, "fontlab", None)
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.lifecycle", raising=False)
    lifecycle = importlib.import_module("fontlabapp.fontui.lifecycle")
    owner = SimpleNamespace(connect=Mock())
    assert lifecycle.follow_history(owner, lambda: None) == 0
    owner.connect.assert_not_called()
    sys.modules.pop("fontlabapp.fontui.lifecycle", None)


def staged_kerning(editor, typed, shown):
    controls = (editor.left_control, editor.right_control, editor.value_control)
    for control, text in zip(controls, typed, strict=True):
        control.text = text
        control.setText.side_effect = lambda v, c=control: setattr(c, "text", v)

    def refresh():  # a real refresh shows the selected pair from the font
        for control, text in zip(controls, shown, strict=True):
            control.text = text
        editor._shown = shown
        return True

    editor.refresh = Mock(side_effect=refresh)
    editor.inspect = Mock()
    editor._shown = shown
    editor.diagnostic = Mock(text="")


def test_external_change_when_typed_over_shown_pair_then_kept(editor_class):
    editor, _ = fixture_editor(editor_class)
    editor.selected = ("A", "V")
    staged_kerning(editor, ("A", "V", "-40"), ("A", "V", "-12"))
    editor._changed()
    editor.refresh.assert_called_once_with()  # the pair list follows FontLab
    assert editor.value_control.text == "-40" and editor._shown == ("A", "V", "-12")
    assert "Reload" in editor.diagnostic.setText.call_args.args[0]


def test_external_change_when_shown_pair_untouched_then_refreshes(editor_class):
    editor, _ = fixture_editor(editor_class)
    editor.selected, editor._shown = ("A", "V"), ("A", "V", "0")
    editor._changed()
    editor.refresh.assert_called_once_with()


def test_external_change_when_new_pair_typed_then_kept(editor_class):
    editor, _ = fixture_editor(editor_class)
    editor.selected = None
    staged_kerning(editor, ("A", "V", "0"), ("", "", ""))
    editor._changed()
    assert (editor.left_control.text, editor.value_control.text) == ("A", "0")


def test_reload_when_typed_pair_is_stored_then_shows_its_value(editor_class):
    editor, pairs = fixture_editor(editor_class)
    editor.selected = None
    pairs[("A", "V")] = -12
    staged_kerning(editor, ("A", "V", "-40"), ("", "", ""))
    editor.refresh = Mock(
        side_effect=lambda selected=None: (
            editor._show(selected, pairs[selected]) or True
        )
    )
    assert editor.reload() is True
    assert (
        editor.left_control.text,
        editor.right_control.text,
        editor.value_control.text,
    ) == ("A", "V", "-12")
    assert not editor._staged()


def test_reload_when_typed_pair_not_stored_then_clears_draft(editor_class):
    editor, _ = fixture_editor(editor_class)
    editor.selected = None
    staged_kerning(editor, ("B", "W", "-40"), ("", "", ""))
    editor.refresh = Mock(return_value=True)
    assert editor.reload() is True
    assert (
        editor.left_control.text,
        editor.right_control.text,
        editor.value_control.text,
    ) == ("", "", "")
    assert not editor._staged()
