# this_file: tests/test_cov_ui_groups.py
"""GroupsEditor and its view built offscreen against a behavioural PythonQt fake."""

from typing import Any

import pytest

import _cov_qt as fq


@pytest.fixture
def groups_mod(monkeypatch):
    handle = fq.install(monkeypatch)
    module = handle.load("fontlabapp.fontui.groups")
    yield module
    fq.release()


def make(module: Any, editable: bool = True, on_apply: Any = None):
    model = fq.FontModel(fq.ufo_font(), editable=editable)
    model.groups.clear()
    model.groups.update({"one": ("A",), "two": ("A", "V")})
    editor = module.GroupsEditor(model, None, on_apply)
    return editor, model


def test_view_build_when_constructed_then_five_actions_and_lists_exist(groups_mod):
    editor, _ = make(groups_mod)
    assert set(editor.buttons) == {
        "add",
        "rename",
        "delete",
        "add_members",
        "remove_members",
    }, "every explicit group action needs its own button"
    names = [name for name, _ in editor.group_list.calls if name == "setAccessibleName"]
    assert names == ["setAccessibleName"], "the group list is labelled for screen readers"
    assert [i.text() for i in editor.group_list.items] == ["one", "two"], (
        "groups are listed sorted"
    )
    assert editor.diagnostic.text.startswith("Select a group"), editor.diagnostic.text
    assert editor.buttons["add"].enabled, "Add is available before any group is selected"
    assert not editor.buttons["rename"].enabled, "Rename needs a selected group"


def test_button_click_when_emitted_then_edit_runs_with_its_action(groups_mod):
    editor, model = make(groups_mod)
    editor.name_control.setText("fresh")
    editor.buttons["add"].clicked.emit()
    assert model.groups["fresh"] == (), "Add creates an empty group"
    assert editor.diagnostic.text == "Applied font groups.", "success message is shown"
    assert [i.text() for i in editor.group_list.items] == ["fresh", "one", "two"], (
        "the new group appears in the sorted list"
    )
    assert editor.selected == "fresh", "the new group stays selected"


def test_select_when_row_chosen_then_members_and_name_show(groups_mod):
    editor, _ = make(groups_mod)
    editor.group_list.setCurrentRow(1)
    assert editor.selected == "two", "the chosen row selects its group"
    assert editor.name_control.text == "two", "the name field shows the selected group"
    assert [i.text() for i in editor.member_list.items] == ["A", "V"], (
        "member list shows the group's glyphs"
    )
    assert editor.buttons["rename"].enabled, "a selection enables rename"
    assert editor.preview.__class__.__name__ == "Preview", "a preview widget is attached"


def test_preview_member_when_item_selected_then_preview_follows(groups_mod):
    editor, _ = make(groups_mod)
    editor.group_list.setCurrentRow(0)
    editor.member_list.itemSelectionChanged.emit()
    assert editor.member_list.selectedItems()[0].text() == "A", (
        "the first member is selected for preview"
    )
    editor.member_list.selected = []
    editor.preview_member()
    editor.close()
    editor.preview_member()  # closed editors ignore it


def test_select_when_row_out_of_range_then_selection_clears(groups_mod):
    editor, _ = make(groups_mod)
    editor.group_list.setCurrentRow(0)
    editor.select(99)
    assert editor.selected is None, "an out-of-range row clears the selection"
    assert editor.name_control.text == "", "the name field is emptied"
    assert not editor.buttons["delete"].enabled, "Delete needs a selected group"


def test_edit_when_rename_then_group_moves_and_callback_gets_copy(groups_mod):
    seen = []
    editor, model = make(groups_mod, on_apply=lambda font, g: seen.append((font, g)))
    editor.group_list.setCurrentRow(0)
    editor.name_control.setText("renamed")
    assert editor.edit("rename") is True, "rename is applied"
    assert "renamed" in model.groups, "the new name exists"
    assert "one" not in model.groups, "the old name is gone"
    assert seen[0][0] is model, "the callback receives the font"
    assert seen[0][1] == dict(model.groups), seen
    assert model.groups.undo_names == ["Edit font groups"], "one named undo step is made"


def test_edit_when_add_members_then_members_appended(groups_mod):
    editor, model = make(groups_mod)
    editor.group_list.setCurrentRow(0)
    editor.members_control.setText("V")
    assert editor.edit("add_members") is True, "adding a member is applied"
    assert tuple(model.groups["one"]) == ("A", "V"), model.groups


def test_edit_when_remove_members_then_selected_items_removed(groups_mod):
    editor, model = make(groups_mod)
    editor.group_list.setCurrentRow(1)
    editor.member_list.selected = [editor.member_list.items[1]]
    assert editor.edit("remove_members") is True, "removing the selected member is applied"
    assert tuple(model.groups["two"]) == ("A",), model.groups


def test_edit_when_delete_then_group_removed(groups_mod):
    editor, model = make(groups_mod)
    editor.group_list.setCurrentRow(0)
    assert editor.edit("delete") is True, "deleting the selected group is applied"
    assert "one" not in model.groups, "the deleted group is gone from the model"


def test_edit_when_nothing_changes_then_reports_no_changes(groups_mod):
    editor, model = make(groups_mod)
    editor.group_list.setCurrentRow(0)
    editor.members_control.setText("A")
    assert editor.edit("add_members") is False, "an already present member is a no-op"
    assert editor.diagnostic.text == "No changes to apply.", "the no-op is reported"
    assert model.groups.undo_names == [], "no batch is sent for a no-op"


def test_edit_when_invalid_input_then_error_text_and_no_write(groups_mod):
    editor, model = make(groups_mod)
    editor.group_list.setCurrentRow(0)
    editor.members_control.setText("NoSuchGlyph")
    assert editor.edit("add_members") is False, "an unknown glyph is refused"
    assert editor.diagnostic.text, "the refusal reason is shown"
    assert model.groups.undo_names == [], "a refused edit writes nothing"


def test_edit_when_readback_differs_then_runtime_error_shown(groups_mod):
    editor, model = make(groups_mod)
    editor.group_list.setCurrentRow(0)
    model.groups.apply = lambda values, *, undo_name: None
    editor.members_control.setText("V")
    assert editor.edit("add_members") is False, "a lost write is reported as failure"
    assert "readback differs" in editor.diagnostic.text, editor.diagnostic.text


def test_edit_when_model_read_only_then_refusal_shown(groups_mod):
    editor, _ = make(groups_mod, editable=False)
    assert editor.editable is False, "a model without apply is not editable"
    assert editor.diagnostic.text == "Read-only: model has no groups.apply.", (
        "the read-only reason is shown on build"
    )
    assert editor.name_control.read_only, "the name field is read-only"
    assert editor.members_control.read_only, "the members field is read-only"
    assert editor.edit("add") is False, "edits are refused on a read-only model"
    assert "Read-only" in editor.diagnostic.text, "the refusal names read-only"


def test_edit_when_callback_raises_then_status_mentions_it(groups_mod):
    def boom(font, groups):
        raise RuntimeError("consumer bug")

    editor, _ = make(groups_mod, on_apply=boom)
    editor.group_list.setCurrentRow(0)
    editor.members_control.setText("V")
    assert editor.edit("add_members") is True, "the edit still applies when the callback fails"
    assert "refresh callback failed: consumer bug" in editor.diagnostic.text, (
        "the callback failure is surfaced"
    )


def test_edit_when_closed_then_nothing_happens(groups_mod):
    editor, model = make(groups_mod)
    editor.close()
    assert editor.edit("add") is False, "a closed editor refuses edits"
    assert editor.reload() is False, "a closed editor refuses reload"
    assert editor.refresh() is False, "a closed editor refuses refresh"
    editor.select(0)
    editor._changed()
    assert model.groups.undo_names == [], "a closed editor writes nothing"
    assert editor.on_apply is None, "the callback is dropped on close"


def test_edit_when_font_vanishes_then_controls_disabled(groups_mod):
    editor, _ = make(groups_mod)
    editor.font = None
    assert editor.edit("add") is False, "no font means no edit"
    assert editor.diagnostic.text == "No font supplied", "the missing font is reported"
    assert not editor.group_list.enabled, "the group list is disabled"
    assert not editor.buttons["add"].enabled, "the Add button is disabled"
    assert editor.refresh() is False, "refresh fails without a font"
    editor.select(0)
    assert editor.selected is None, "nothing can be selected without a font"


def test_reload_when_typed_text_present_then_cleared(groups_mod):
    editor, _ = make(groups_mod)
    editor.group_list.setCurrentRow(0)
    editor.members_control.setText("V")
    editor.reload_button.clicked.emit()
    assert editor.members_control.text == "", "reload clears the typed members"
    assert editor.name_control.text == "one", "reload restores the selected group's name"


def test_changed_when_nothing_staged_then_lists_refresh(groups_mod):
    editor, model = make(groups_mod)
    model.groups["zzz"] = ("A",)
    editor._changed()
    assert "zzz" in [i.text() for i in editor.group_list.items], (
        "a group added elsewhere appears after a change notification"
    )


def test_changed_when_text_staged_then_typed_text_survives_refresh(groups_mod):
    editor, model = make(groups_mod)
    editor.group_list.setCurrentRow(0)
    editor.name_control.setText("typed")
    editor.members_control.setText("V")
    model.groups["zzz"] = ("A",)
    editor._changed()
    assert editor.name_control.text == "typed", "the typed name survives the refresh"
    assert editor.members_control.text == "V", "the typed members survive the refresh"
    assert "zzz" in [i.text() for i in editor.group_list.items], (
        "the list still refreshes around staged text"
    )


def test_changed_when_model_closed_then_typed_text_left_alone(groups_mod):
    editor, _ = make(groups_mod)
    editor.group_list.setCurrentRow(0)
    editor.members_control.setText("V")
    editor.font = None
    editor._changed()
    assert editor.members_control.text == "V", "typed text is not wiped when the font is gone"
    assert editor.diagnostic.text == "No font supplied", "the missing font is reported"


def test_close_when_called_twice_then_preview_closed_and_callback_dropped(groups_mod):
    editor, _ = make(groups_mod, on_apply=lambda *a: None)
    editor.close()
    editor.close()
    assert editor.closed, "the editor is marked closed"
    assert editor.on_apply is None, "the callback is dropped"
    assert editor.widget.deleted, "the root widget is scheduled for deletion"



def test_close_when_actual_preview_hide_fails_then_parent_work_is_fenced(groups_mod, monkeypatch):
    from fontlabapp.fontui.preview import Preview

    editor, model = make(groups_mod, on_apply=lambda *args: None)
    child = editor.preview
    assert isinstance(child, Preview), "use the actual Groups Preview"
    borrowed = (model.ufo, tuple(model.keys()), dict(model.groups), dict(model.kerning), tuple(model.groups.undo_names), tuple(model.kerning.undo_names))
    before = (editor.closed, child.closed, child.widget.shown, child.widget.deleted)
    error = RuntimeError("controlled actual Preview hide failure")

    def fail_hide():
        raise error

    monkeypatch.setattr(child.widget, "hide", fail_hide)
    captured = None
    try:
        editor.close()
    except BaseException as caught:
        captured = caught
    after = (editor.closed, child.closed, child.widget.shown, child.widget.deleted)
    assert captured is error
    assert editor.on_apply is None
    assert editor.closed, "parent work must be fenced before actual Preview cleanup can fail"
    assert editor.preview is child and editor.font is model and child.font is model
    assert before == (False, False, True, False)
    assert after == (True, True, True, False)
    assert borrowed == (model.ufo, tuple(model.keys()), dict(model.groups), dict(model.kerning), tuple(model.groups.undo_names), tuple(model.kerning.undo_names))


def test_window_when_created_then_compact_panel_metrics(groups_mod):
    window = make(groups_mod)[0]
    assert [a for c, a in window.layout.calls if c == "setContentsMargins"] == [(6, 6, 6, 6)]
    assert [a for c, a in window.layout.calls if c == "setSpacing"] == [(4,)]


def test_select_and_edit_when_run_then_groups_are_read_in_one_pass(groups_mod):
    """``dict(mapping)`` is one native snapshot per key on Fontport groups; ``items()`` is one total."""
    from collections.abc import Mapping

    class Counting(Mapping):
        """A fontParts-like mapping: not a dict, so ``dict(m)`` goes through ``__getitem__`` per key."""

        def __init__(self, data):
            self.data, self.getitems = dict(data), 0

        def __getitem__(self, key):
            self.getitems += 1
            return self.data[key]

        def __iter__(self):
            return iter(self.data)

        def __len__(self):
            return len(self.data)

        def items(self):
            return self.data.items()

        def apply(self, values, *, undo_name):
            self.data = dict(values)

    editor, model = make(groups_mod)
    model.groups = Counting(model.groups)
    editor.select(1)
    editor.members_control.setText("V")
    editor.name_control.setText("one")
    editor.edit("add_members")
    assert model.groups.getitems == 0, "no per-key __getitem__ reads of the borrowed groups"
