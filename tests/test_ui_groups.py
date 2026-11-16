# this_file: tests/test_ui_groups.py
"""B06 explicit actions dispatch one backend batch and contain UI errors."""

import importlib
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def editor_class(monkeypatch):
    importlib.import_module(
        "fontlab_fontport.groups"
    )  # [test] installs Fontport; never skip
    for name in ("groups", "groups_view"):
        monkeypatch.delitem(sys.modules, f"fontlabapp.fontui.{name}", raising=False)
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.lifecycle", raising=False)
    monkeypatch.setitem(sys.modules, "PythonQt", SimpleNamespace(QtGui=Mock()))
    module = importlib.import_module("fontlabapp.fontui.groups")
    yield module.GroupsEditor
    for name in ("groups", "groups_view"):
        sys.modules.pop(f"fontlabapp.fontui.{name}", None)
    sys.modules.pop("fontlabapp.fontui.lifecycle", None)


def editor_fixture(cls):
    editor = cls.__new__(cls)
    editor.closed = False
    values = {"g": ("A",)}

    class Groups(dict):
        def apply(self, values, *, undo_name):
            self.clear()
            self.update(values)

    groups = Groups(values)
    groups.apply = Mock(wraps=groups.apply)
    editor.font = SimpleNamespace(groups=groups, keys=lambda: ("A", "V"))
    editor.selected = "g"
    editor.name_control = Mock(text="new")
    editor.members_control = Mock(text="A V A")
    editor.member_list = Mock()
    editor.member_list.selectedItems.return_value = [SimpleNamespace(text=lambda: "A")]
    editor.diagnostic = Mock()
    editor.refresh = Mock(return_value=True)
    editor.on_apply = Mock()
    return editor, groups


def test_groups_factory_when_imported_then_stays_host_and_fontport_free():
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from fontlabapp.fontui import groups_editor
assert callable(groups_editor)
assert 'PythonQt' not in sys.modules
assert not [m for m in sys.modules if m.startswith('fontlabapp.fontui.') and m != 'fontlabapp.fontui.model']
""",
        ],
        check=True,
    )


@pytest.mark.parametrize(
    "action,expected",
    [
        ("add", {"g": ("A",), "new": ()}),
        ("rename", {"new": ("A",)}),
        ("delete", {}),
        ("add_members", {"g": ("A", "V")}),
        ("remove_members", {"g": ()}),
    ],
)
def test_explicit_action_when_valid_then_one_batch_and_callback(
    editor_class, action, expected
):
    editor, groups = editor_fixture(editor_class)
    assert editor.edit(action) is True
    assert dict(groups) == expected
    groups.apply.assert_called_once()
    editor.on_apply.assert_called_once_with(editor.font, expected)


def test_unknown_member_when_added_then_error_and_no_native_dispatch(editor_class):
    editor, groups = editor_fixture(editor_class)
    editor.members_control.text = "V missing"
    assert editor.edit("add_members") is False
    assert dict(groups) == {"g": ("A",)}
    groups.apply.assert_not_called()
    editor.on_apply.assert_not_called()
    assert "missing" in editor.diagnostic.setText.call_args.args[0]


def test_backend_reference_refusal_when_deleting_then_visible_and_usable(editor_class):
    editor, groups = editor_fixture(editor_class)
    groups.apply.side_effect = ValueError("Dependent kerning pairs")
    assert editor.edit("delete") is False
    assert dict(groups) == {"g": ("A",)}
    editor.on_apply.assert_not_called()
    groups.apply.side_effect = None
    assert editor.edit("delete") is True


def test_closed_handle_when_action_requested_then_never_touches_widgets(editor_class):
    editor, groups = editor_fixture(editor_class)
    editor.closed = True
    assert editor.edit("add") is False
    groups.apply.assert_not_called()
    editor.diagnostic.setText.assert_not_called()


def test_noop_backend_when_edit_requested_then_never_reports_success(editor_class):
    editor, groups = editor_fixture(editor_class)
    groups.apply = Mock(return_value=None)
    assert editor.edit("add") is False
    assert dict(groups) == {"g": ("A",)}
    editor.on_apply.assert_not_called()
    assert "readback differs" in editor.diagnostic.setText.call_args.args[0]


@pytest.mark.parametrize("name,members", [("TypedRename", ""), ("g", "A V"), ("", "")])
def test_external_change_when_input_staged_then_kept_with_reload_notice(
    editor_class, name, members
):
    editor, _ = editor_fixture(editor_class)
    editor.name_control = Mock(text=name)
    editor.members_control = Mock(text=members)

    def refresh():  # a real refresh resets the name field from the selection
        editor.name_control.text, editor.members_control.text = "g", members
        return True

    editor.refresh = Mock(side_effect=refresh)
    editor.name_control.setText.side_effect = lambda v: setattr(
        editor.name_control, "text", v
    )
    editor.members_control.setText.side_effect = lambda v: setattr(
        editor.members_control, "text", v
    )
    editor._changed()
    editor.refresh.assert_called_once_with()  # lists follow FontLab
    assert (editor.name_control.text, editor.members_control.text) == (name, members)
    assert "Reload" in editor.diagnostic.setText.call_args.args[0]


def test_external_change_when_nothing_staged_then_refreshes(editor_class):
    editor, _ = editor_fixture(editor_class)
    editor.name_control.text, editor.members_control.text = "g", "  "
    editor._changed()
    editor.refresh.assert_called_once_with()


def test_reload_discards_typed_name_and_members(editor_class):
    editor, _ = editor_fixture(editor_class)
    editor.members_control = Mock(text="A V")
    editor.members_control.setText.side_effect = lambda v: setattr(
        editor.members_control, "text", v
    )
    editor.name_control.text = "TypedRename"
    editor.name_control.setText.side_effect = lambda v: setattr(
        editor.name_control, "text", v
    )
    editor.refresh = Mock(side_effect=lambda: editor.name_control.setText("g") or True)
    assert editor.reload() is True
    assert (editor.name_control.text, editor.members_control.text) == ("g", "")
    assert not editor._staged()
