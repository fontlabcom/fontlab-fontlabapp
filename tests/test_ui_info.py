# this_file: tests/test_ui_info.py
"""Staged editor boundaries; real Qt/document proof lives in native receipts."""

import importlib
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def editor_class(monkeypatch):
    importlib.import_module(
        "fontlab_fontport.info"
    )  # [test] installs Fontport; never skip
    for name in ("fontinfo",):
        monkeypatch.delitem(sys.modules, f"fontlabapp.fontui.{name}", raising=False)
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.lifecycle", raising=False)
    monkeypatch.setitem(sys.modules, "PythonQt", SimpleNamespace(QtGui=Mock()))
    module = importlib.import_module("fontlabapp.fontui.fontinfo")
    yield module.FontInfoEditor
    for name in ("fontinfo",):
        sys.modules.pop(f"fontlabapp.fontui.{name}", None)
    sys.modules.pop("fontlabapp.fontui.lifecycle", None)


def editor_fixture(cls, **overrides):
    editor = cls.__new__(cls)
    editor.closed = False
    values = dict.fromkeys(cls.FIELD_LABELS, None)
    values.update(
        familyName="Original",
        unitsPerEm=1000,
        ascender=800,
        italicAngle=0,
        versionMajor=1,
        versionMinor=0,
        note="",
    )
    values.update(overrides)
    info = SimpleNamespace(**values, apply=Mock())
    editor.font = SimpleNamespace(info=info)
    editor.on_apply = Mock()
    editor.fields = {name: Mock(text="") for name in values}
    editor.apply_button, editor.revert_button, editor.diagnostic = (
        Mock(),
        Mock(),
        Mock(),
    )
    editor.refresh()
    # Model Qt's property text and multiline method after programmatic refresh.
    for name, widget in editor.fields.items():
        text = editor.source_text[name]
        widget.text = text
        widget.toPlainText.return_value = text
    return editor, info


def test_namespace_when_imported_then_remains_host_and_fontport_free():
    code = """
import sys
from fontlabapp.fontui import font_info_editor
assert callable(font_info_editor)
assert 'PythonQt' not in sys.modules
assert not [m for m in sys.modules if m.startswith('fontlabapp.fontui.') and m != 'fontlabapp.fontui.model']
"""
    subprocess.run([sys.executable, "-c", code], check=True)


def test_apply_when_mixed_valid_invalid_then_focuses_and_mutates_nothing(editor_class):
    editor, info = editor_fixture(editor_class)
    editor.fields["familyName"].text = "Changed"
    editor.fields["unitsPerEm"].text = "0"
    assert editor.apply() is False, "Invalid UPM must reject the complete batch"
    info.apply.assert_not_called()
    editor.fields["unitsPerEm"].setFocus.assert_called_once()
    editor.on_apply.assert_not_called()


@pytest.mark.parametrize(
    "name,text",
    [
        ("ascender", "nan"),
        ("italicAngle", "no"),
        ("versionMinor", "1.5"),
        ("descender", ""),
    ],
)
def test_apply_when_numeric_input_invalid_then_keeps_staging(editor_class, name, text):
    editor, info = editor_fixture(editor_class, descender=-200)
    editor.fields[name].text = text
    assert editor.apply() is False, "Bad numeric input cannot reach the native batch"
    info.apply.assert_not_called()
    editor.fields[name].setFocus.assert_called_once()


def test_apply_when_valid_then_calls_one_batch_and_callback(editor_class):
    editor, info = editor_fixture(editor_class)
    editor.fields["familyName"].text = "Family Ω"
    editor.fields["ascender"].text = "0"
    editor.fields["note"].toPlainText.return_value = "日本語\nSecond line"
    changes = {"familyName": "Family Ω", "ascender": 0.0, "note": "日本語\nSecond line"}
    assert editor.apply() is True, "Validated changes must reach one batch"
    info.apply.assert_called_once_with(changes, undo_name="Font information")
    editor.on_apply.assert_called_once_with(editor.font, changes)


def test_apply_when_unchanged_absent_then_does_not_write_none(editor_class):
    editor, info = editor_fixture(editor_class)
    assert editor.apply() is False, "An unchanged form is a no-op"
    info.apply.assert_not_called()
    editor.on_apply.assert_not_called()


def test_refresh_when_native_integer_is_double_then_displays_integer(editor_class):
    editor, info = editor_fixture(editor_class, unitsPerEm=1000.0, xHeight=0.0)
    assert editor.source_text["unitsPerEm"] == "1000", (
        "Native double UPM must be editable as an integer"
    )
    assert editor.source_text["xHeight"] == "0.0", (
        "Zero must remain visibly distinct from absence"
    )
    assert editor.source_text["copyright"] == "", (
        "An absent value remains blank with a placeholder"
    )
    assert not editor.apply()
    info.apply.assert_not_called()


def test_revert_when_staged_then_reads_actual_without_writes(editor_class):
    editor, info = editor_fixture(editor_class)
    editor.fields["familyName"].text = "Staged"
    info.familyName = "External Ω"
    assert editor.refresh() is True, "Refresh must reload the borrowed model"
    editor.fields["familyName"].setText.assert_called_with("External Ω")
    info.apply.assert_not_called()


def test_apply_when_backend_fails_then_reports_and_stays_usable(editor_class):
    editor, info = editor_fixture(editor_class)
    editor.fields["familyName"].text = "Changed"
    info.apply.side_effect = RuntimeError("Document closed")
    assert editor.apply() is False
    assert "Document closed" in editor.diagnostic.setText.call_args.args[0]
    editor.on_apply.assert_not_called()
    info.apply.side_effect = None
    assert editor.apply() is True, "A failed batch must not break the control"


def test_apply_when_callback_fails_then_preserves_success_diagnostic(editor_class):
    editor, info = editor_fixture(editor_class)
    editor.fields["familyName"].text = "Changed"
    editor.on_apply.side_effect = RuntimeError("Refresh failed")
    assert editor.apply() is True, "Consumer failure must not undo a successful batch"
    info.apply.assert_called_once()
    assert "Applied" in editor.diagnostic.setText.call_args.args[0]


def test_refresh_when_no_batch_capability_then_disables_apply(editor_class):
    editor, info = editor_fixture(editor_class)
    info.apply = None
    assert editor.refresh() is True
    editor.apply_button.setEnabled.assert_called_with(False)
    assert "read-only" in editor.diagnostic.setText.call_args.args[0]
    assert editor.apply() is False


def test_methods_when_closed_then_never_dereference_widgets(editor_class):
    editor, _ = editor_fixture(editor_class)
    editor.closed = True
    editor.diagnostic.reset_mock()
    assert editor.apply() is False and editor.refresh() is False
    editor.diagnostic.setText.assert_not_called()


DESCRIPTIVE = (
    "trademark",
    "openTypeNameDesigner",
    "openTypeNameDesignerURL",
    "openTypeNameManufacturer",
    "openTypeNameManufacturerURL",
    "openTypeNameLicense",
    "openTypeNameLicenseURL",
)


def test_form_when_built_then_offers_every_fontport_text_field(editor_class):
    from fontlab_fontport.info import TEXT_FIELDS

    assert set(editor_class.FIELD_LABELS) >= TEXT_FIELDS
    assert {"openTypeNameLicense", "trademark"} <= editor_class.MULTILINE


def test_apply_when_descriptive_text_changes_then_one_text_batch(editor_class):
    editor, info = editor_fixture(editor_class)
    for name in DESCRIPTIVE:
        if name in editor_class.MULTILINE:
            editor.fields[name].toPlainText.return_value = f"{name} Ω\nline 2"
        else:
            editor.fields[name].text = f"{name} Ω"
    assert editor.apply() is True
    (changes,), kwargs = info.apply.call_args
    assert set(changes) == set(DESCRIPTIVE) and kwargs == {
        "undo_name": "Font information"
    }
    assert all(isinstance(v, str) and "Ω" in v for v in changes.values())


def test_external_change_when_unstaged_then_reloads(editor_class):
    editor, info = editor_fixture(editor_class)
    info.familyName = "Changed in FontLab"
    editor._changed()
    assert editor.source_text["familyName"] == "Changed in FontLab"


def test_external_change_when_staged_then_keeps_edits_and_says_so(editor_class):
    editor, info = editor_fixture(editor_class)
    editor.fields["familyName"].text = "Typed, not applied"
    info.familyName = "Changed in FontLab"
    editor._changed()
    assert editor.source_text["familyName"] == "Original"
    assert editor.fields["familyName"].text == "Typed, not applied"
    assert "Revert" in editor.diagnostic.setText.call_args.args[0]
    info.apply.assert_not_called()


STRUCTURED = {
    "openTypeOS2WeightClass": ("500", 500),
    "openTypeOS2WidthClass": ("6", 6),
    "openTypeOS2Panose": ("2 0 5 3 0 0 0 0 0 0", [2, 0, 5, 3, 0, 0, 0, 0, 0, 0]),
    "postscriptStemSnapH": ("20.5 80", [20.5, 80]),
    "postscriptStemSnapV": ("70.25", [70.25]),
}


def test_form_offers_structured_fields_but_not_name_records(editor_class):
    assert set(STRUCTURED) <= set(editor_class.FIELD_LABELS)
    assert "openTypeNameRecords" not in editor_class.FIELD_LABELS
    for name in STRUCTURED:
        assert "key master" in editor_class.FIELD_LABELS[name]


def test_apply_when_structured_text_then_typed_values_in_one_batch(editor_class):
    editor, info = editor_fixture(editor_class)
    for name, (text, _) in STRUCTURED.items():
        editor.fields[name].text = text
    assert editor.apply() is True
    (changes,), _ = info.apply.call_args
    assert changes == {name: value for name, (_, value) in STRUCTURED.items()}
    assert all(type(v) is int for v in changes["openTypeOS2Panose"])
    assert type(changes["openTypeOS2WeightClass"]) is int
    assert (
        changes["postscriptStemSnapH"] == [20.5, 80]
        and type(changes["postscriptStemSnapH"][1]) is int
    )


@pytest.mark.parametrize(
    "name,text",
    [
        ("openTypeOS2Panose", "2 0 5"),
        ("openTypeOS2Panose", "2 0 5 3 0 0 0 0 0 x"),
        ("openTypeOS2WeightClass", "500.5"),
        ("openTypeOS2WidthClass", "wide"),
        ("postscriptStemSnapH", "20 nan"),
    ],
)
def test_apply_when_structured_text_invalid_then_nothing_applied(
    editor_class, name, text
):
    editor, info = editor_fixture(editor_class)
    editor.fields["familyName"].text = "Must not apply"
    editor.fields[name].text = text
    assert editor.apply() is False
    info.apply.assert_not_called()
    editor.fields[name].setFocus.assert_called()


def test_refresh_shows_structured_values_as_space_separated_text(editor_class):
    editor, _ = editor_fixture(
        editor_class,
        openTypeOS2Panose=(2, 0, 5, 3, 0, 0, 0, 0, 0, 0),
        postscriptStemSnapH=[20.5, 80.0],
        openTypeOS2WeightClass=500.0,
    )
    assert editor.source_text["openTypeOS2Panose"] == "2 0 5 3 0 0 0 0 0 0"
    assert editor.source_text["postscriptStemSnapH"] == "20.5 80"
    assert editor.source_text["openTypeOS2WeightClass"] == "500"


def test_apply_when_stems_cleared_then_empty_list(editor_class):
    editor, info = editor_fixture(editor_class, postscriptStemSnapV=[70.25])
    editor.fields["postscriptStemSnapV"].text = ""
    assert editor.apply() is True
    (changes,), _ = info.apply.call_args
    assert changes == {"postscriptStemSnapV": []}


@pytest.mark.parametrize(
    "name,text",
    [
        ("openTypeOS2WeightClass", "500.00000000000001"),
        ("unitsPerEm", "-1e-999"),
        ("openTypeOS2Panose", "2.0000000000000001 0 5 3 0 0 0 0 0 0"),
        ("openTypeOS2WidthClass", "6.0"),
        ("versionMajor", "+3"),
        ("openTypeOS2WeightClass", "5e2"),
    ],
)
def test_integer_text_is_parsed_exactly_or_refused(editor_class, name, text):
    editor, info = editor_fixture(editor_class)
    editor.fields[name].text = text
    assert editor.apply() is False
    info.apply.assert_not_called()


def test_integer_text_accepts_unicode_decimal_digits_and_leading_minus(editor_class):
    editor, info = editor_fixture(editor_class)
    editor.fields["openTypeOS2WeightClass"].text = "٥٠٠"  # noqa: RUF001 - Arabic-Indic 500
    editor.fields["versionMinor"].text = " 7 "
    assert editor.apply() is True
    (changes,), _ = info.apply.call_args
    assert changes["openTypeOS2WeightClass"] == 500 and changes["versionMinor"] == 7


def _diagnostic(editor):
    return editor.diagnostic.setText.call_args.args[0]


def test_refresh_when_backend_reports_metric_clearing_unsupported_then_hint_quotes_reason(editor_class):
    editor, _ = editor_fixture(editor_class)
    editor.font.capabilities = lambda: {
        "info.clearOptionalMetric": {"supported": False, "reason": "None is refused"}
    }
    editor.refresh()
    assert "can't clear a blank metric" in _diagnostic(editor)
    assert "None is refused" not in _diagnostic(editor), "technical reason is tooltip only"
    editor.diagnostic.setToolTip.assert_called_with("None is refused")


def test_refresh_when_backend_reports_metric_clearing_supported_then_no_unset_warning(editor_class):
    editor, _ = editor_fixture(editor_class)
    editor.font.capabilities = lambda: {
        "info.clearOptionalMetric": {"supported": True}
    }
    editor.refresh()
    assert "clear a blank metric" not in _diagnostic(editor)
    assert "staged until Apply" in _diagnostic(editor)
    editor.diagnostic.setToolTip.assert_called_with("")


def test_refresh_when_capabilities_missing_or_failing_then_keeps_generic_hint(editor_class):
    editor, _ = editor_fixture(editor_class)
    assert "can't clear a blank metric" in _diagnostic(editor), "model without capabilities()"
    def boom():
        raise RuntimeError("closed")
    editor.font.capabilities = boom
    editor.refresh()
    assert "can't clear a blank metric" in _diagnostic(editor), "failing capabilities()"


def test_refresh_when_capability_entry_not_a_mapping_then_keeps_generic_hint(editor_class):
    editor, _ = editor_fixture(editor_class)
    editor.font.capabilities = lambda: {"info.clearOptionalMetric": "no"}
    editor.refresh()
    assert "can't clear a blank metric" in _diagnostic(editor)


def test_apply_when_failure_replaces_diagnostic_then_clears_stale_tooltip(editor_class):
    editor, info = editor_fixture(editor_class)
    editor.fields["familyName"].text = "Changed"
    info.apply.side_effect = RuntimeError("boom")
    editor.diagnostic.setToolTip.reset_mock()
    assert editor.apply() is False
    editor.diagnostic.setToolTip.assert_called_with("")
