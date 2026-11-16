# this_file: tests/test_component_recipe_selection.py
"""Use the real shared selection reader with owned FontLab-shaped carriers."""

from types import SimpleNamespace as NS

import pytest
import test_layer_selection

import fontlabapp.components.recipes.model as api

source = test_layer_selection.source


def components(*names):
    return [
        NS(id=index + 30, isComponent=True, shapeData=NS(componentGlyph=name))
        for index, name in enumerate(names)
    ]


def test_editor_report_preserves_repeated_occurrences_and_each_slots_layer(source):
    source.workspace.activeFontPanel = None
    source.regular.shapes = components("A", "acute")
    source.bold.shapes = components("B", "acute")
    report = api.capture()
    assert api.recipes(report.layers) == "B+acute=A\nA+acute=A\nB+acute=A\n"
    assert report.context[2] == "editor"


def test_shared_font_window_report_still_reads_actual_selection_on_current_master(
    source,
):
    source.regular.shapes = components("A", "acute")
    report = api.capture()
    assert api.recipes(report.layers) == "A+acute=A\n"
    assert report.context[2] == "font"


def test_empty_editor_selection_has_no_current_glyph_fallback(source):
    source.workspace.activeFontPanel = None
    source.regular.shapes = source.bold.shapes = components("A")
    for record in source.records:
        record.isSelected = record.isActive = False
    with pytest.raises(ValueError, match="Select"):
        api.capture()


def test_selected_slot_with_a_missing_layer_refuses_the_complete_report(source):
    source.workspace.activeFontPanel = None
    source.regular.shapes = source.bold.shapes = components("A")
    source.records[1].symbol.layerName = "missing"
    with pytest.raises(ValueError, match="missing"):
        api.capture()


def test_wrong_legacy_font_carrier_is_refused_before_any_component_reads(source):
    source.legacy.font.file_name = "/f/other.vfj"
    source.package.findName = lambda name: pytest.fail(
        "Wrong carrier reached glyph reads"
    )
    with pytest.raises(ValueError, match="carrier"):
        api.capture()


@pytest.mark.parametrize(
    "changed", ["glyph", "layer", "glyph_name", "layer_name", "package"]
)
def test_bound_occurrence_cannot_change_between_provider_and_component_read(
    source, monkeypatch, changed
):
    original = api.selection.capture
    source.regular.shapes = components("A")

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
