# this_file: tests/test_cov_ui_info.py
"""FontInfoEditor form and the lazy editor factories, built offscreen."""

from types import SimpleNamespace
from typing import Any

import pytest

import _cov_qt as fq


@pytest.fixture
def imod(monkeypatch):
    handle = fq.install(monkeypatch)
    module = handle.load("fontlabapp.fontui.fontinfo")
    yield module
    fq.release()


class Info:
    """FontParts-like info with every editable field and a batch ``apply``."""

    def __init__(self, names: Any, editable: bool = True) -> None:
        for name in names:
            setattr(self, name, None)
        self.familyName, self.styleName = "Fam", "Reg"
        self.unitsPerEm, self.ascender = 1000, 800.0
        self.note = "a note"
        self.postscriptStemSnapH = [10.0, 20.5]
        self.openTypeOS2Panose = [2, 0, 5]
        self.applied: list[tuple] = []
        if editable:
            self.apply = self._apply

    def _apply(self, changes: dict, *, undo_name: str) -> None:
        self.applied.append((dict(changes), undo_name))
        for key, value in changes.items():
            setattr(self, key, value)


def make(module: Any, editable: bool = True, on_apply: Any = None):
    info = Info(module.FontInfoEditor.FIELD_LABELS, editable)
    font = SimpleNamespace(info=info)
    return module.FontInfoEditor(font, None, on_apply), font, info


def test_display_when_values_vary_then_text_is_normalised(imod):
    assert imod._display("familyName", None) == "", "None shows as empty text"
    assert imod._display("postscriptStemSnapH", [10.0, 20.5]) == "10 20.5", (
        "stem lists are space separated with whole floats trimmed"
    )
    assert imod._display("openTypeOS2Panose", [2, 0]) == "2 0", "panose lists are space separated"
    assert imod._display("unitsPerEm", 1000.0) == "1000", "integer fields drop the float tail"
    assert imod._display("familyName", "x") == "x", "plain strings pass through"
    assert imod._number_text(3.0) == "3", "whole floats are shown as integers"
    assert imod._number_text("s") == "s", "non-numbers pass through unchanged"


@pytest.mark.parametrize("text,value", [("12", 12), (" -3 ", -3), ("٣", 3)])
def test_integer_when_decimal_digits_then_int(imod, text, value):
    assert imod._integer(text) == value, f"{text!r} parses as the integer {value}"


@pytest.mark.parametrize("text", ["1.5", "", "--1", "1e3", "x"])
def test_integer_when_not_decimal_then_value_error(imod, text):
    with pytest.raises(ValueError, match="is not an integer"):
        imod._integer(text)


def test_number_when_finite_then_int_or_float_else_error(imod):
    assert imod._number("2") == 2, "an integer string parses as that number"
    assert isinstance(imod._number("2.0"), int), "a whole float string collapses to int"
    assert imod._number("2.5") == 2.5, "a fractional string stays a float"
    with pytest.raises(ValueError, match="not a finite number"):
        imod._number("nan")


def test_parse_when_blank_or_typed_then_value_by_field_kind(imod):
    assert imod._parse("openTypeOS2Panose", " ") is None, "blank panose clears the field"
    assert imod._parse("openTypeOS2Panose", "1 2") == [1, 2], "panose parses as an int list"
    assert imod._parse("postscriptStemSnapV", "") == [], "blank stems mean none"
    assert imod._parse("postscriptStemSnapV", "5 6.5") == [5, 6.5], "stems parse as numbers"
    assert imod._parse("unitsPerEm", "") is None, "blank integer field clears it"
    assert imod._parse("openTypeOS2WeightClass", "400") == 400, "integer fields parse as int"
    assert imod._parse("ascender", "") is None, "blank metric clears it"
    assert imod._parse("ascender", "7") == 7.0, "metric fields parse as numbers"
    assert imod._parse("familyName", "Q") == "Q", "text fields pass through"


def test_init_when_built_then_fields_show_font_values(imod):
    editor, _, _ = make(imod)
    assert editor.fields["familyName"].text == "Fam", "family name shows the font value"
    assert editor.fields["unitsPerEm"].text == "1000", "units per em shows as an integer"
    assert editor.fields["ascender"].text == "800.0", "metrics keep their float text"
    assert editor.fields["note"].plain_text == "a note", "multiline fields use plain text"
    assert editor.fields["postscriptStemSnapH"].text == "10 20.5", "stems show space separated"
    assert editor.fields["openTypeOS2Panose"].text == "2 0 5", "panose shows space separated"
    assert editor.diagnostic.text.startswith("Edits are staged until Apply"), (
        "the hint explains that edits are staged"
    )
    assert editor.apply_button.enabled, "Apply is enabled for an editable font"


def test_apply_when_text_field_edited_then_one_batch_and_callback(imod):
    seen = []
    editor, font, info = make(imod, on_apply=lambda f, c: seen.append((f, c)))
    editor.fields["familyName"].setText("New")
    editor.apply_button.clicked.emit()
    assert info.applied == [({"familyName": "New"}, "Font information")], (
        "one named batch carries only the changed field"
    )
    assert seen == [(font, {"familyName": "New"})], seen
    assert editor.diagnostic.text == "Applied font information.", "success message is shown"
    assert editor.source_text["familyName"] == "New", "the applied text becomes the new baseline"


def test_apply_when_multiline_and_numeric_edited_then_typed_values_applied(imod):
    editor, _, info = make(imod)
    editor.fields["note"].setPlainText("changed")
    editor.fields["unitsPerEm"].setText("2048")
    editor.fields["ascender"].setText("900.5")
    editor.fields["postscriptStemSnapH"].setText("11 12")
    assert editor.apply() is True, "valid mixed edits are applied"
    changes = info.applied[0][0]
    assert changes["note"] == "changed", "multiline text is applied"
    assert changes["unitsPerEm"] == 2048, "integer text is applied as int"
    assert changes["ascender"] == 900.5, "metric text is applied as float"
    assert changes["postscriptStemSnapH"] == [11, 12], "stem text is applied as a list"


def test_apply_when_nothing_changed_then_reports_no_changes(imod):
    editor, _, info = make(imod)
    assert editor.apply() is False, "an unchanged form is not applied"
    assert editor.diagnostic.text == "No changes to apply.", "the no-op is reported"
    assert info.applied == [], "no batch is sent for a no-op"


def test_apply_when_integer_text_invalid_then_field_named_and_focused(imod):
    editor, _, info = make(imod)
    editor.fields["unitsPerEm"].setText("abc")
    assert editor.apply() is False, "invalid integer text is refused"
    assert editor.diagnostic.text == "unitsPerEm: 'abc' is not an integer", (
        "the diagnostic names the field and the bad text"
    )
    assert any(c[0] == "setFocus" for c in editor.fields["unitsPerEm"].calls), (
        "focus moves to the offending field"
    )
    assert info.applied == [], "nothing is written for an invalid batch"


def test_apply_when_fontport_refuses_value_then_error_shown(imod):
    editor, _, info = make(imod)
    editor.fields["unitsPerEm"].setText("0")
    assert editor.apply() is False, "a refused value fails the apply"
    assert editor.diagnostic.text.startswith("unitsPerEm:"), editor.diagnostic.text
    assert info.applied == [], "a refused batch writes nothing"


def test_apply_when_backend_raises_then_message_shown(imod):
    editor, _, info = make(imod)

    def fail(changes: dict, *, undo_name: str) -> None:
        raise RuntimeError("native refused")

    info.apply = fail
    editor.fields["familyName"].setText("Z")
    assert editor.apply() is False, "a backend failure fails the apply"
    assert editor.diagnostic.text == "native refused", "the backend message is shown verbatim"


def test_apply_when_callback_raises_then_status_mentions_it(imod):
    def boom(font: Any, changes: dict) -> None:
        raise RuntimeError("consumer bug")

    editor, _, _ = make(imod, on_apply=boom)
    editor.fields["familyName"].setText("Z")
    assert editor.apply() is True, "the apply still succeeds when the callback fails"
    assert editor.diagnostic.text == (
        "Applied font information; refresh callback failed: consumer bug"
    ), "the status reports both the success and the callback failure"


def test_apply_when_model_read_only_then_fields_read_only_and_apply_refused(imod):
    editor, _, _ = make(imod, editable=False)
    assert editor.fields["familyName"].read_only, "fields are read-only without apply"
    assert not editor.apply_button.enabled, "Apply is disabled without apply"
    assert editor.diagnostic.text.startswith("Font information is read-only"), (
        "the read-only reason is shown on build"
    )
    editor.diagnostic.setText("")
    assert editor.apply() is False, "apply is refused on a read-only model"
    assert editor.diagnostic.text.startswith("Font information is read-only"), (
        "the refusal repeats the read-only reason"
    )


def test_apply_when_document_closed_after_refresh_then_controls_disabled(imod):
    editor, font, _ = make(imod)
    font.info = None
    assert editor.apply() is False, "apply fails once the document info is gone"
    assert "has no attribute" in editor.diagnostic.text, "the missing info is reported"
    assert not editor.apply_button.enabled, "Apply is disabled"
    assert not editor.fields["note"].enabled, "fields are disabled"


def test_refresh_when_font_none_then_unavailable_and_false(imod):
    editor, _, _ = make(imod)
    editor.font = None
    assert editor.refresh() is False, "refresh fails without a font"
    assert editor.diagnostic.text == "No font supplied", "the missing font is reported"
    assert not editor.fields["familyName"].enabled, "fields are disabled"


def test_revert_when_clicked_then_staged_text_discarded(imod):
    editor, _, _ = make(imod)
    editor.fields["familyName"].setText("typed")
    editor.fields["note"].setPlainText("typed note")
    editor.revert_button.clicked.emit()
    assert editor.fields["familyName"].text == "Fam", "revert restores the line edit"
    assert editor.fields["note"].plain_text == "a note", "revert restores the multiline text"


def test_changed_when_edits_staged_then_kept_and_user_told(imod):
    editor, _, info = make(imod)
    editor.fields["familyName"].setText("typed")
    info.styleName = "Bold"
    editor._changed()
    assert editor.fields["familyName"].text == "typed", "staged text is kept"
    assert editor.fields["styleName"].text == "Reg", "no reload while edits are staged"
    assert editor.diagnostic.text.startswith("Changed in FontLab; Revert reloads it"), (
        "the user is told an external change is pending"
    )


def test_changed_when_nothing_staged_then_external_change_shown(imod):
    editor, _, info = make(imod)
    info.styleName = "Bold"
    editor._changed()
    assert editor.fields["styleName"].text == "Bold", "an external change is shown"


def test_closed_editor_when_used_then_noops(imod):
    editor, _, info = make(imod, on_apply=lambda *a: None)
    editor.close()
    assert editor.on_apply is None, "the callback is dropped on close"
    assert editor.apply() is False, "a closed editor refuses apply"
    assert editor.refresh() is False, "a closed editor refuses refresh"
    info.styleName = "Bold"
    editor._changed()
    assert editor.fields["styleName"].text == "Reg", "a closed editor ignores changes"


# --- lazy factories in fontlabapp.fontui --------------------------------------------


@pytest.fixture
def ui(monkeypatch):
    handle = fq.install(monkeypatch)
    yield handle.load("fontlabapp.fontui")
    fq.release()


def test_factories_when_called_then_each_builds_its_editor(ui):
    model = fq.FontModel(fq.ufo_font())
    info = Info(
        __import__("fontlabapp.fontui.fontinfo", fromlist=["x"]).FontInfoEditor.FIELD_LABELS
    )
    model.info = info
    ufo = fq.ufo_font()
    built = {
        "FontInfoEditor": ui.font_info_editor(model),
        "GroupsEditor": ui.groups_editor(model),
        "KerningEditor": ui.kerning_editor(model),
        "TransformEditor": ui.transform_editor(ufo, "A"),
        "BatchPanel": ui.batch_panel(lambda: None, python="py"),
        "Sequence": ui.glyph_sequence(model),
    }
    for expected, editor in built.items():
        assert type(editor).__name__ == expected, (expected, type(editor))
        assert not editor.closed, f"{expected} starts open"
        assert hasattr(editor, "widget"), f"{expected} exposes its widget"
        editor.close()
        assert editor.closed, f"{expected} closes through its handle"


def test_construct_when_init_fails_after_widget_then_widget_closed_and_error_raised(ui):
    class Half:
        closed = False

        def __init__(self) -> None:
            self.widget = object()
            raise RuntimeError("half built")

        def close(self) -> None:
            Half.closed = True

    with pytest.raises(RuntimeError, match="half built"):
        ui._construct(Half)
    assert Half.closed, "a half-built owner must not leak its widget"


def test_construct_when_init_fails_before_widget_then_error_raised_without_close(ui):
    class Early:
        def __init__(self) -> None:
            raise KeyError("early")

        def close(self) -> None:
            raise AssertionError("close must not be called without a widget")

    with pytest.raises(KeyError):
        ui._construct(Early)


def test_all_when_listed_then_matches_public_factories(ui):
    assert sorted(set(ui.__all__) - {
        "BrowserState", "FontListState", "designspace_panel", "features_editor",
        "font_browser", "glyph_browser", "glyph_preview", "outline", "viewport",
        "app_shell", "glyph_table", "layer_is_hinted",
        "current_font", "follow_history", "kerning_snapshot", "metrics_preview", "write_kerning",
        "metrics_window", "remove_hints", "glyph_view",
        "anchor_component_studio", "category_report", "owned_panel_type",
        "hint_tools_window", "raise_ascender_tab", "outline_generators_backends",
        "cleanup_failed_window", "show_outline_compatibility", "outline_studio", "show_node_editor", "duplicate_nodes",
        "identity_panel", "identity_route", "identity_studio",
    }) == [
        "batch_panel",
        "core_pythonqt_lab",
        "font_info_editor",
        "glyph_sequence",
        "groups_editor",
        "kerning_editor",
        "transform_editor",
    ], "__all__ lists exactly the seven public factories"
    assert all(callable(getattr(ui, name)) for name in ui.__all__), (
        "every exported name is callable"
    )



@pytest.mark.parametrize(
    "case",
    ["ordinary-pair", "setup-keyboardinterrupt", "setup-systemexit", "cleanup-keyboardinterrupt", "cleanup-systemexit", "cleanup-false-refusal"],
)
def test_construct_when_cleanup_fails_then_exact_ordered_errors_and_owner_survive(ui, case):
    original = KeyboardInterrupt("setup interruption") if case == "setup-keyboardinterrupt" else SystemExit(17) if case == "setup-systemexit" else ValueError("setup failure")
    cleanup = KeyboardInterrupt("cleanup interruption") if case == "cleanup-keyboardinterrupt" else SystemExit(23) if case == "cleanup-systemexit" else RuntimeError("cleanup failure")
    original.add_note("original setup note")
    cleanup.add_note("original cleanup note")
    allocated, close_calls = [], []

    class Half:
        def __init__(self):
            allocated.append(self)
            self.widget = fq.FakeWidget()
            raise original

        def close(self):
            close_calls.append(self)
            if case == "cleanup-false-refusal":
                return False
            raise cleanup

    captured = None
    try:
        ui._construct(Half)
    except BaseException as caught:
        captured = caught
    assert isinstance(captured, BaseExceptionGroup), "real construction must retain ordered setup and cleanup errors"
    expected_type = BaseExceptionGroup if isinstance(original, (KeyboardInterrupt, SystemExit)) or (case != "cleanup-false-refusal" and isinstance(cleanup, (KeyboardInterrupt, SystemExit))) else ExceptionGroup
    assert type(captured) is expected_type
    assert len(captured.exceptions) == 2 and captured.exceptions[0] is original
    if case == "cleanup-false-refusal":
        assert type(captured.exceptions[1]) is RuntimeError
        assert str(captured.exceptions[1]) == "Owned widget refused factory failure cleanup"
    else:
        assert captured.exceptions[1] is cleanup
        assert cleanup.__notes__ == ["original cleanup note"]
    assert original.__notes__ == ["original setup note"]
    assert len(allocated) == 1 and captured.owner is allocated[0]
    assert close_calls == allocated
    assert captured.__cause__ is None and captured.__suppress_context__
    if isinstance(original, SystemExit):
        assert original.code == 17
    if case == "cleanup-systemexit":
        assert cleanup.code == 23


@pytest.mark.parametrize(
    "answer,original_type",
    [(None, KeyboardInterrupt), (0, SystemExit)],
    ids=["cleanup-none-original-keyboardinterrupt", "cleanup-zero-original-systemexit"],
)
def test_construct_when_cleanup_acknowledged_then_exact_public_error_reraised(ui, answer, original_type):
    original = original_type(17)
    original.add_note("public setup note")
    allocated, close_calls = [], []

    class Half:
        def __init__(self):
            allocated.append(self)
            self.widget = fq.FakeWidget()
            raise original

        def close(self):
            close_calls.append(self)
            self.widget.hide()
            self.widget.deleteLater()
            return answer

    captured = None
    try:
        ui._construct(Half)
    except BaseException as caught:
        captured = caught
    assert captured is original, "normal None or numeric0 cleanup reraises the exact public error"
    assert captured.__notes__ == ["public setup note"]
    assert len(allocated) == 1 and close_calls == allocated
    assert not allocated[0].widget.shown and allocated[0].widget.deleted
    if isinstance(original, SystemExit):
        assert original.code == 17



@pytest.mark.parametrize("case", ['nested-original'])
def test_construct_when_nested_original_group_and_cleanup_fail_then_exact_members_owner_notes_survive(ui, case):
    original = BaseExceptionGroup("nested setup", [ValueError("first"), KeyboardInterrupt("second")])
    original.add_note("keep nested original")
    cleanup = RuntimeError("cleanup exact")
    cleanup.add_note("keep cleanup")
    allocated, calls = [], []
    class Half:
        def __init__(self):
            allocated.append(self)
            self.widget = fq.FakeWidget()
            raise original
        def close(self):
            calls.append(self)
            raise cleanup
    captured = None
    try:
        ui._construct(Half)
    except BaseException as caught:
        captured = caught
    assert isinstance(captured, BaseExceptionGroup)
    assert captured.exceptions == (original, cleanup) and captured.owner is allocated[0]
    assert original.__notes__ == ["keep nested original"] and cleanup.__notes__ == ["keep cleanup"]
    assert calls == allocated and len(calls) == 1



@pytest.mark.parametrize("case", ['restored-owner'])
def test_construct_when_retained_owner_recovers_then_original_group_is_unchanged(ui, case):
    original, cleanup = ValueError("setup owner retained"), RuntimeError("cleanup pending")
    original.add_note("retain setup note")
    allocated, calls = [], []
    pending = [True]
    class Half:
        def __init__(self):
            allocated.append(self)
            self.widget = fq.FakeWidget()
            raise original
        def close(self):
            calls.append(self)
            if pending[0]:
                raise cleanup
            self.widget.hide()
            self.widget.deleteLater()
    captured = None
    try:
        ui._construct(Half)
    except BaseException as caught:
        captured = caught
    assert isinstance(captured, BaseExceptionGroup)
    assert captured.owner is allocated[0] and captured.exceptions == (original, cleanup)
    pending[0] = False
    captured.owner.close()
    assert calls == [allocated[0], allocated[0]]
    assert not allocated[0].widget.shown and allocated[0].widget.deleted
    assert captured.exceptions == (original, cleanup) and original.__notes__ == ["retain setup note"]



@pytest.mark.parametrize("case", ['normal-construction', 'normal-cleanup', 'grouped-cleanup'])
def test_construct_when_cold_cleanup_branch_runs_then_no_host_or_peer_import_occurs(ui, tmp_path, case):
    import subprocess
    import sys
    from pathlib import Path
    code = """import sys
from pathlib import Path
forbidden = ('PythonQt', 'fontlab', 'FL', 'fontgate', 'fontpr', 'fontlab_fontport', 'fontlab_glyport')
assert not any(n == p or n.startswith(p + '.') for n in sys.modules for p in forbidden)
from fontlabapp.fontui import _construct
assert Path(sys.modules['fontlabapp.fontui'].__file__).resolve() == Path(sys.argv[2])
route = sys.argv[1]
original, cleanup = ValueError('setup'), RuntimeError('cleanup')
allocated = []
class Half:
    def __init__(self):
        allocated.append(self)
        self.widget = object()
        if route != 'normal-construction':
            raise original
    def close(self):
        if route == 'normal-construction':
            raise AssertionError('normal construction never cleans up')
        if route == 'grouped-cleanup':
            raise cleanup
captured = None
try:
    built = _construct(Half)
except BaseException as caught:
    captured = caught
if route == 'normal-construction':
    assert captured is None and built is allocated[0]
    assert 'fontlabapp.qt.widgets' not in sys.modules
elif route == 'normal-cleanup':
    assert captured is original
else:
    assert isinstance(captured, BaseExceptionGroup)
    assert captured.exceptions == (original, cleanup) and captured.owner is allocated[0]
assert not any(n == p or n.startswith(p + '.') for n in sys.modules for p in forbidden)
print('cold actual factory import/cleanup PASS')
"""
    import os

    # Resolve fontlabapp exactly as this process did, whatever editable install exists.
    env = {**os.environ, "PYTHONPATH": str(Path(ui.__file__).resolve().parents[2])}
    done = subprocess.run([sys.executable, "-s", "-B", "-c", code, case, str(Path(ui.__file__).resolve())], cwd=tmp_path, env=env, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.strip() == "cold actual factory import/cleanup PASS"
