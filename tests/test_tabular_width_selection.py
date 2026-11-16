# this_file: tests/test_tabular_width_selection.py
"""Check exact widths through the real shared ordered selected-layer reader."""

import pytest
import test_layer_selection

import fontlabapp.metrics.tabular_width.model as api

source = test_layer_selection.source


def test_editor_first_occurrence_width_and_repeated_mixed_layers_are_preserved(source):
    source.workspace.activeFontPanel = None
    source.regular.advanceWidth, source.bold.advanceWidth = 500.125, 600.125
    result = api.capture()
    assert [row.name for row in result.rows] == ["A", "A", "A"]
    assert [row.width for row in result.rows] == [600.125, 500.125, 600.125]
    assert [row.matches for row in result.rows] == [True, False, True]
    assert result.same == 2 and result.different == 1


def test_font_window_uses_actual_selection_and_current_master(source):
    source.regular.advanceWidth = 500.125
    result = api.capture()
    assert len(result.rows) == 1 and result.rows[0].width == 500.125


def test_no_editor_selection_never_falls_back_to_current_glyph(source):
    source.workspace.activeFontPanel = None
    for record in source.records:
        record.isActive = record.isSelected = False
    with pytest.raises(ValueError, match="Select"):
        api.capture()


def test_wrong_font_carrier_refuses_before_any_width_reads(source):
    source.legacy.font.file_name = "/f/other.vfj"
    source.package.findName = lambda name: pytest.fail("Wrong carrier reached widths")
    with pytest.raises(ValueError, match="carrier"):
        api.capture()


@pytest.mark.parametrize(
    "changed", ["glyph", "layer", "glyph_name", "layer_name", "package"]
)
def test_bound_identity_changes_before_width_read_refuse_the_whole_snapshot(
    source, monkeypatch, changed
):
    original = api.selection.capture
    source.regular.advanceWidth = 500.125

    def selected(deadline):
        result = original(deadline)
        if changed == "glyph":
            source.glyph.id += 1
        if changed == "layer":
            source.regular.id += 1
        if changed == "glyph_name":
            source.glyph.name = "Changed"
        if changed == "layer_name":
            source.regular.name = "Changed"
        if changed == "package":
            source.glyph.package.id += 1
        return result

    monkeypatch.setattr(api.selection, "capture", selected)
    with pytest.raises(ValueError, match="identity changed"):
        api.capture()
