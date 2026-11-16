# this_file: tests/test_cov_ui_kerning.py
"""KerningEditor and its view built offscreen against a behavioural PythonQt fake."""

from typing import Any

import pytest

import _cov_qt as fq

PAIR = ("public.kern1.A", "public.kern2.V")


@pytest.fixture
def kerning_mod(monkeypatch):
    handle = fq.install(monkeypatch)
    module = handle.load("fontlabapp.fontui.kerning")
    yield module
    fq.release()


def make(module: Any, editable: bool = True, on_apply: Any = None):
    model = fq.FontModel(fq.ufo_font(), editable=editable)
    editor = module.KerningEditor(model, None, on_apply)
    return editor, model


def test_number_text_when_integral_or_fractional_then_shortest_form(kerning_mod):
    assert kerning_mod.number_text(-80.0) == "-80", "whole floats lose the decimal tail"
    assert kerning_mod.number_text(-0.0) == "0", "native Undo can restore -0.0"
    assert kerning_mod.number_text(2.5) == "2.5", "fractions are kept"


def test_value_text_when_absent_then_none(kerning_mod):
    assert kerning_mod._value(None) == "none", "a missing value reads as 'none'"
    assert kerning_mod._value(3.0) == "3", "a present value uses the shortest form"


def test_view_build_when_constructed_then_pairs_listed_and_controls_ready(kerning_mod):
    editor, _ = make(kerning_mod)
    assert [i.text() for i in editor.pair_list.items] == [
        "public.kern1.A | public.kern2.V | -80"
    ], "the single stored pair is listed with its value"
    assert editor.apply_button.enabled, "Apply is enabled for an editable font"
    assert not editor.delete_button.enabled, "Delete needs a selected explicit pair"
    assert editor.preview.mode_control.currentIndex == 1, (
        "the nested preview starts in glyph-name mode"
    )
    assert editor.diagnostic.text == kerning_mod.EMPTY_PAIR_TEXT, (
        "a fresh editor with no pair shows a neutral prompt, not a validation error"
    )


def test_inspect_when_only_one_side_typed_then_validation_error_shown(kerning_mod):
    editor, _ = make(kerning_mod)
    editor.left_control.setText("A")
    editor.inspect()
    assert "at least one character" in editor.diagnostic.text, (
        "a half-typed pair still reports Fontport's key validation"
    )
    assert not editor.delete_button.enabled, "Delete stays off for an invalid pair"


def test_select_when_row_chosen_then_fields_show_pair_and_delete_enabled(kerning_mod):
    editor, _ = make(kerning_mod)
    editor.pair_list.setCurrentRow(0)
    assert (editor.left_control.text, editor.right_control.text) == PAIR, (
        "the pair fields show the selected pair"
    )
    assert editor.value_control.text == "-80", "the value field shows the stored value"
    assert editor.delete_button.enabled, "an explicit pair can be deleted"
    assert editor.diagnostic.text.startswith("Explicit value: -80"), (
        editor.diagnostic.text
    )
    assert "preview /A /V" in editor.diagnostic.text, "group keys preview first members"
    assert editor.preview.text_control.text == "/A /V", "the preview shows the first members"


def test_select_when_row_out_of_range_then_ignored(kerning_mod):
    editor, _ = make(kerning_mod)
    editor.select(5)
    editor.select(-1)
    assert editor.selected is None, "out-of-range rows select nothing"


def test_select_when_pair_vanished_then_error_text_shown(kerning_mod):
    editor, model = make(kerning_mod)
    editor.rows = [("X", "Y")]
    editor.select(0)
    assert editor.diagnostic.text, "a KeyError for the gone pair is reported"


def test_fill_when_filtered_then_only_matching_rows_remain(kerning_mod):
    editor, _ = make(kerning_mod)
    editor.filter_control.setText("zzz")
    assert editor.rows == [], "a filter matching nothing empties the rows"
    assert editor.pair_list.items == [], "the list widget is emptied too"
    editor.filter_control.setText("KERN2")
    assert editor.rows == [PAIR], "filter is case-insensitive over both keys"


def test_inspect_when_typed_pair_glyphs_then_effective_value_via_groups(kerning_mod):
    editor, _ = make(kerning_mod)
    editor.left_control.setText("A")
    editor.right_control.setText("V")
    assert "No explicit pair" in editor.diagnostic.text, "the pair is reported as not explicit"
    assert "effective: -80" in editor.diagnostic.text, editor.diagnostic.text


def test_inspect_when_read_only_then_prefix_and_delete_disabled(kerning_mod):
    editor, _ = make(kerning_mod, editable=False)
    editor.left_control.setText("A")
    editor.right_control.setText("V")
    assert editor.diagnostic.text.startswith("Read-only. "), editor.diagnostic.text
    assert not editor.delete_button.enabled, "Delete is disabled on a read-only model"
    assert not editor.apply_button.enabled, "Apply is disabled on a read-only model"
    assert editor.left_control.read_only, "the pair fields are read-only"


def test_inspect_when_font_breaks_then_error_shown_in_preview(kerning_mod):
    editor, _ = make(kerning_mod)
    editor.font.groups = None
    editor.inspect()
    assert editor.diagnostic.text, "the failure is shown"
    assert not editor.delete_button.enabled, "Delete is disabled after the failure"


def test_edit_when_apply_then_pair_written_selected_and_callback_called(kerning_mod):
    seen = []
    editor, model = make(kerning_mod, on_apply=lambda f, p: seen.append(p))
    editor.left_control.setText("A")
    editor.right_control.setText("V")
    editor.value_control.setText("-30")
    editor.apply_button.clicked.emit()
    assert model.kerning[("A", "V")] == -30, "the typed pair is written"
    assert model.kerning.undo_names == ["Edit font kerning"], "one named undo step is made"
    assert seen, "the callback is called"
    assert seen[0][("A", "V")] == -30, seen
    assert editor.diagnostic.text.startswith("Explicit value: -30"), (
        "the new pair is shown as explicit"
    )


def test_edit_when_delete_then_explicit_pair_removed(kerning_mod):
    editor, model = make(kerning_mod)
    editor.pair_list.setCurrentRow(0)
    editor.delete_button.clicked.emit()
    assert model.kerning == {}, "the explicit pair is gone"


def test_edit_when_no_change_then_reports_and_skips_write(kerning_mod):
    editor, model = make(kerning_mod)
    editor.pair_list.setCurrentRow(0)
    assert editor.edit("apply") is False, "an unchanged pair is not applied"
    assert editor.diagnostic.text == "No changes to apply.", "the no-op is reported"
    assert model.kerning.undo_names == [], "no batch is sent for a no-op"


def test_edit_when_value_not_a_number_then_error_shown(kerning_mod):
    editor, model = make(kerning_mod)
    editor.left_control.setText("A")
    editor.right_control.setText("V")
    editor.value_control.setText("abc")
    assert editor.edit("apply") is False, "a non-numeric value is refused"
    assert "could not convert" in editor.diagnostic.text, "the conversion error is shown"
    assert model.kerning.undo_names == [], "a refused edit writes nothing"


def test_edit_when_unknown_glyph_then_fontport_refuses(kerning_mod):
    editor, model = make(kerning_mod)
    editor.left_control.setText("Nope")
    editor.right_control.setText("V")
    editor.value_control.setText("5")
    assert editor.edit("apply") is False, "an unknown glyph is refused"
    assert model.kerning.undo_names == [], "a refused edit writes nothing"


def test_edit_when_read_only_then_type_error_text(kerning_mod):
    editor, _ = make(kerning_mod, editable=False)
    assert editor.edit("apply") is False, "a read-only model refuses edits"
    assert editor.diagnostic.text == "Read-only: model has no kerning.apply", (
        "the read-only reason is shown"
    )


def test_edit_when_readback_differs_then_runtime_error_shown(kerning_mod):
    editor, model = make(kerning_mod)
    model.kerning.apply = lambda values, *, undo_name: None
    editor.left_control.setText("A")
    editor.right_control.setText("V")
    editor.value_control.setText("7")
    assert editor.edit("apply") is False, "a lost write is reported as failure"
    assert "readback differs" in editor.diagnostic.text, "the readback mismatch is shown"


def test_edit_when_callback_raises_then_status_mentions_it(kerning_mod):
    def boom(font, pairs):
        raise RuntimeError("consumer bug")

    editor, _ = make(kerning_mod, on_apply=boom)
    editor.left_control.setText("A")
    editor.right_control.setText("V")
    editor.value_control.setText("9")
    assert editor.edit("apply") is True, "the edit still applies when the callback fails"
    assert "refresh callback failed: consumer bug" in editor.diagnostic.text, (
        "the callback failure is surfaced"
    )


def test_edit_when_font_gone_then_controls_disabled(kerning_mod):
    editor, _ = make(kerning_mod)
    editor.font = None
    assert editor.edit("apply") is False, "no font means no edit"
    assert editor.diagnostic.text == "No font supplied", "the missing font is reported"
    for control in (editor.pair_list, editor.apply_button, editor.delete_button):
        assert not control.enabled, "every control is disabled without a font"
    assert editor.refresh() is False, "refresh fails without a font"
    editor.fill()
    assert editor.editable is False, "the editor is no longer editable"


def test_closed_editor_when_used_then_everything_is_a_no_op(kerning_mod):
    editor, model = make(kerning_mod)
    editor.close()
    assert editor.edit("apply") is False, "a closed editor refuses edits"
    assert editor.reload() is False, "a closed editor refuses reload"
    assert editor.refresh() is False, "a closed editor refuses refresh"
    editor.fill()
    editor.inspect()
    editor._changed()
    editor.select(0)
    assert model.kerning.undo_names == [], "a closed editor writes nothing"
    assert editor.on_apply is None, "the callback is dropped on close"


def test_reload_when_typed_pair_is_stored_then_it_is_shown(kerning_mod):
    editor, _ = make(kerning_mod)
    editor.left_control.setText(PAIR[0])
    editor.right_control.setText(PAIR[1])
    editor.value_control.setText("1234")
    assert editor.reload() is True, "reload succeeds for a stored pair"
    assert editor.value_control.text == "-80", "the stored value replaces the draft"


def test_reload_when_typed_pair_not_stored_then_fields_cleared(kerning_mod):
    editor, _ = make(kerning_mod)
    editor.left_control.setText("A")
    editor.right_control.setText("A")
    editor.value_control.setText("5")
    editor.reload_button.clicked.emit()
    assert (editor.left_control.text, editor.value_control.text) == ("", ""), (
        "an unstored pair is cleared from the fields"
    )
    assert editor.selected is None, "nothing stays selected"


def test_reload_when_model_closed_then_refresh_reports_it(kerning_mod):
    editor, _ = make(kerning_mod)
    editor.font = None
    assert editor.reload() is False, "reload fails without a font"
    assert editor.diagnostic.text == "No font supplied", "the missing font is reported"


def test_changed_when_nothing_staged_then_list_refreshes(kerning_mod):
    editor, model = make(kerning_mod)
    model.kerning[("A", "A")] = 4
    editor._changed()
    assert len(editor.pair_list.items) == 2, "the externally added pair appears"


def test_changed_when_draft_typed_then_draft_kept_and_noted(kerning_mod):
    editor, model = make(kerning_mod)
    editor.left_control.setText("A")
    editor.right_control.setText("A")
    editor.value_control.setText("11")
    model.kerning[("V", "V")] = 4
    editor._changed()
    assert editor.value_control.text == "11", "the typed value survives the refresh"
    assert editor.left_control.text == "A", "the typed left glyph survives the refresh"
    assert editor.diagnostic.text.startswith("Changed in FontLab; typed pair kept"), (
        "the user is told the typed pair was kept"
    )
    assert len(editor.pair_list.items) == 2, "the list still refreshes around the draft"


def test_changed_when_draft_typed_and_model_closed_then_draft_untouched(kerning_mod):
    editor, _ = make(kerning_mod)
    editor.left_control.setText("A")
    editor.font = None
    editor._changed()
    assert editor.left_control.text == "A", "the draft is not wiped when the font is gone"
    assert editor.diagnostic.text == "No font supplied", "the missing font is reported"



def test_close_when_actual_sequence_hide_fails_then_parent_work_is_fenced(kerning_mod, monkeypatch):
    from fontlabapp.fontui.sequence import Sequence

    editor, model = make(kerning_mod, on_apply=lambda *args: None)
    child = editor.preview
    assert isinstance(child, Sequence), "Kerning preview is the actual Sequence"
    borrowed = (model.ufo, tuple(model.keys()), dict(model.groups), dict(model.kerning), tuple(model.groups.undo_names), tuple(model.kerning.undo_names))
    before = (editor.closed, child.closed, child.widget.shown, child.widget.deleted)
    error = RuntimeError("controlled actual Sequence hide failure")

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
    assert editor.closed, "parent work must be fenced before actual Sequence cleanup can fail"
    assert editor.preview is child and editor.font is model and child.font is model
    assert child.on_update is None and child.on_select is None
    assert child._selected_font is None and child._selected_glyph is None
    assert before == (False, False, True, False)
    assert after == (True, True, True, False)
    assert borrowed == (model.ufo, tuple(model.keys()), dict(model.groups), dict(model.kerning), tuple(model.groups.undo_names), tuple(model.kerning.undo_names))
