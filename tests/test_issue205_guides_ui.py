# this_file: tests/test_issue205_guides_ui.py
"""Owned guide previews and editable proposals refuse unsafe native sources."""

import importlib
from types import SimpleNamespace as NS

import pytest
from issue205_panels import (
    QtCore,
    QtGui,
    QtWidgets,
    Edit,
    combo,
    panels as panels,
    legacy_qt as legacy_qt,
    owned as owned,
)


def test_guide_sources_when_values_and_font_names_are_read_then_hints_and_missing_layers_are_handled(
    panels,
):
    sources = importlib.import_module("fontlabapp.guides.inspect.sources")

    class Unreadable:
        @property
        def name(self):
            raise RuntimeError("native wrapper gone")

    panels.package.guidelines = [NS(name="cap"), NS(name=""), Unreadable()]
    panels.layer.guidelines = [
        NS(
            centerPoint=QtCore.QPointF(11, 22),
            angle=0.125,
            name="diagonal",
            isHint=False,
        ),
        NS(isHint=True),
    ]
    assert sources.font_guide_names(panels.package) == ["cap", "(unnamed)", "?"]
    assert [
        master
        for master, _ in sources.master_layers(panels.glyph, ["Regular", "missing"])
    ] == ["Regular"]
    values = sources.source_values(
        panels.package, ["A"], ["Regular"], font_guides=True, geometry=True
    )
    assert values[1] == (("A", "Regular", ((11.0, 22.0, 0.125, "diagonal"),)),)
    assert dict(values[2][0][1]) == {
        "Baseline": 0,
        "x-height": 500,
        "Cap height": 700,
        "Ascender": 800,
        "Descender": -200,
    }
    assert (
        values[4] == ("cap", "(unnamed)", "?")
        and ("metrics", "Regular") in panels.owned.events
    )
    assert sources.source_values(panels.package, [], [], font_guides=False)[4] is None
    with pytest.raises(ValueError, match="Glyph source changed"):
        sources.source_values(panels.package, ["missing"], ["Regular"])


def test_guide_panel_when_preview_and_selection_change_then_results_and_callbacks_are_released(
    panels,
):
    module = panels.modules["guides.inspect.ui"]
    panel = panels.make(module.GuidesDialog, "guides_grid_generator")
    panel.option_values = lambda: (panel.scope.currentIndex,)
    paints = []
    panel.preview = NS(
        path=QtGui.QPainterPath(),
        records=[(0, 10, 0, "x")],
        advance=500,
        update=lambda: paints.append("clear"),
    )
    panel.font_guides = QtWidgets.QLabel("stale")
    refresh = panels.modules["masters"].snapshot_refresh(
        lambda self: setattr(self, "rows", [("A", 1)])
    )
    refresh(panel)
    assert panel.names == ["A"] and panel.scope.itemText(1) == "All masters (2)"
    assert panel.source_values() == panel.source_values(cached=True)
    panel.check_preview()
    panel.fill_guide_rows(
        [("A", "2", "text", "add"), ("B", "-1", "3", "keep")], {1, 2}, accent_column=3
    )
    assert panel.table.item(0, 3).foreground().color() == panel.palette.color(
        QtGui.QPalette.Link
    )
    assert panel.table.item(1, 1).textAlignment() & QtCore.Qt.AlignRight
    panel.fill_guide_rows([("A", "2", "text")], {1, 2})
    assert panel.table.item(0, 1).textAlignment() & QtCore.Qt.AlignRight
    assert not panel.table.item(0, 2).textAlignment() & QtCore.Qt.AlignRight
    spin = panel._spin(-20, 30, 12)
    assert (spin.minimum(), spin.maximum(), spin.value(), spin.suffix()) == (
        -20,
        30,
        12,
        " units",
    )
    panels.state.selection = ["acute"]
    with pytest.raises(ValueError, match="Selection changed"):
        panel.source_values()
    panel.invalidate()
    assert (
        panel.last_result is None
        and panel.preview.path is None
        and panel.preview.records == []
    )
    assert (
        panel.preview.frame == (-250.0, 750.0)
        and paints == ["clear"]
        and panel.font_guides.text() == ""
    )
    panel.invalidate()
    assert paints == ["clear"]
    panel.check_preview()
    assert panel.source_values() is None
    panel.teardown()
    assert (
        panel.preview.before_draw
        is panel.preview.failure_cleanup
        is panel.preview.on_error
        is None
    )


def test_guide_apply_when_automatic_dependants_exist_then_the_whole_action_is_disabled_before_history(
    panels,
):
    module = panels.modules["guides.inspect.ui"]
    panel = panels.make(module.GuidesDialog, "guides_grid_generator")
    panel.package = panels.package
    panel.pending_targets = {"A"}
    panel.guard_apply(0)
    assert panel.blocked == []
    for index in range(9):
        glyph, layer = panels.owned.glyph(f"auto{index}")
        layer.autoLayer = True
        layer.shapes = [NS(isComponent=True, shapeData=NS(componentGlyph="A"))]
        panels.state.names.append(glyph.name)
    before = list(panels.owned.events)
    panel.guard_apply(2)
    assert (
        panel.blocked == [f"auto{i}" for i in range(9)]
        and not panel.apply_button.isEnabled()
    )
    assert (
        "+1 more" in panel.status.text() and "Cannot safely undo" in panel.status.text()
    )
    assert panels.owned.events == before
    panel.package = None
    panel.guard_apply(2)
    assert panel.blocked == []


def test_guide_copy_when_masters_targets_and_widths_change_then_controls_bind_the_exact_plan(
    panels,
):
    module = panels.modules["guides.rewrite.ui"]
    panel = panels.make(module.RewriteDialog, "guides_copy_between_masters")
    del panel.scope
    panel.target_checks, panel.targets_grid = {}, QtWidgets.QGridLayout()
    panel.mode, panel.follow_width = combo(["Append", "Replace"]), QtWidgets.QCheckBox()
    panel.follow_width.setChecked(True)
    calls = []
    panel.refresh = lambda: calls.append("refresh")
    panel.prepare_initial()
    assert panel.source.currentText == "Regular" and list(panel.target_checks) == [
        "Regular",
        "Bold",
    ]
    assert all(check.isChecked() for check in panel.target_checks.values())
    panel.target_checks["Bold"].setChecked(False)
    assert calls == ["refresh"]
    assert panel.option_values() == (
        "Regular",
        0,
        True,
        (("Regular", True), ("Bold", False)),
    )
    values = panel.source_values()
    assert values[1] == (("A", "Regular", 600.0), ("A", "Bold", 600.0))
    panels.layer.advanceWidth += 25
    assert panel.source_values() != values
    panel.load_initial()
    assert panel.targets_grid.count() == 2
    panels.package.masters.reverse()
    with pytest.raises(ValueError, match="Masters changed"):
        panel.load_initial()
    panel.clear_initial_state()
    assert (
        panel.glyph is None
        and not panel.source.isEnabled()
        and panel.source.currentText == ""
    )
    assert all(not check.isEnabled() for check in panel.target_checks.values())
    panel.package = None
    assert panel.source_values() is None


def test_guide_clear_when_filters_change_then_scope_and_proposal_options_are_captured(
    panels,
):
    module = panels.modules["guides.rewrite.ui"]
    panel = panels.make(module.RewriteDialog, "guides_clear")
    panel.direction, panel.name_filter = combo(["All", "Horizontal"]), Edit("Grid *")
    panel.prepare_initial()
    assert panel.glyph is panels.glyph and panel.option_values() == (0, 0, "Grid *")
    original = panel.source_values()
    panel.direction.setCurrentIndex(1)
    assert panel.source_values() != original and panel.option_values() == (
        0,
        1,
        "Grid *",
    )
    panel.clear_initial_state()
    assert panel.glyph is None and panel.glyphs == []


def test_guide_list_when_rows_are_added_parsed_and_removed_then_native_guides_wait_for_apply(
    panels, monkeypatch
):
    module = panels.modules["guides.rewrite.editor_ui"]
    monkeypatch.setattr(
        module,
        "QtCore",
        NS(
            Qt=NS(
                ItemIsEditable=QtCore.Qt.ItemIsEditable.value,
                AlignRight=QtCore.Qt.AlignRight,
                AlignVCenter=QtCore.Qt.AlignVCenter,
            )
        ),
    )
    panel = panels.make(module.GuideListDialog, "guides_list_editor")
    panel.add_button, panel.delete_button = (
        QtWidgets.QPushButton(),
        QtWidgets.QPushButton(),
    )
    refresh = panels.modules["masters"].snapshot_refresh(lambda self: None)
    refresh(panel)
    assert panel.option_values() == (0,) and panel.editable_masters() == ["Regular"]
    panel.add_row()
    assert panel.table.rowCount == 1 and panel.table.currentColumn() == 2
    assert panel.table_records() == {"Regular": [(0.0, 0.0, 0.0, "new guide")]}
    assert not panel.table.item(0, 0).flags() & QtCore.Qt.ItemIsEditable.value
    panel.table.item(0, 2).setText("12.5")
    assert (
        panel.table_records()["Regular"][0][1] == 12.5 and panels.layer.guidelines == []
    )
    panel.table.item(0, 0).setText("unknown")
    with pytest.raises(ValueError, match="master changed"):
        panel.table_records()
    panel.table.item(0, 0).setText("Regular")
    panel.table.takeItem(0, 2)
    assert panel.table_records()["Regular"][0][1] == 0.0
    panel.table.item(0, 3).setText("inf")
    with pytest.raises(ValueError, match="row 1"):
        panel.table_records()
    panel.delete_row()
    assert panel.table.rowCount == 0
    panel.delete_row()
    panels.layer.autoLayer = True
    assert panel.editable_masters() == []
    panel._source = panel.source_values()
    panel.add_row()
    assert panel.table.rowCount == 0 and panels.layer.guidelines == []
    panel.invalidate()
    assert panel.layers() == [] and not panel.table.isEnabled()
    assert not panel.add_button.isEnabled() and not panel.delete_button.isEnabled()
