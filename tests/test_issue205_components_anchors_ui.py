# this_file: tests/test_issue205_components_anchors_ui.py
"""Whole component/anchor snapshots, explicit rescans and unsafe copy refusals."""

from types import SimpleNamespace as NS

import pytest
from issue205_panels import (
    QtCore,
    QtWidgets,
    Edit,
    combo,
    panels as panels,
    legacy_qt as legacy_qt,
    owned as owned,
)


@pytest.mark.parametrize(
    "key",
    [
        "components_report",
        "components_where_used",
        "components_missing_bases",
        "components_count_badges",
        "components_compatibility",
    ],
)
def test_components_when_complete_then_results_bind_to_font_domain_and_raw_values(
    panels, key
):
    module = panels.modules["components.inspect.ui"]
    panel = panels.make(module.ComponentsDialog, key)
    panel.search, panel.scroll_area = Edit("A"), QtWidgets.QScrollArea()
    panel.grid_height_hint = lambda: 180
    updates = []
    panel.grid = NS(cards=["old"], update=lambda: updates.append("update"))
    panel.prepare_initial()
    assert panel.names == ["A", "acute"] and panel.masters == ["Regular", "Bold"]
    assert panel.package is panels.package

    def calculate(self):
        if key == "components_report":
            self.rows = module.api.report(self.package, self.names, self.masters)
        elif key == "components_where_used":
            self.index = module.api.usage_index(self.package, self.names, self.masters)
        elif key == "components_missing_bases":
            self.groups = module.api.missing(
                self.package, self.names, self.masters, None
            )
        return "published"

    refresh = module.snapshot_refresh(calculate)
    assert refresh(panel) == "published" and panel._snapshot_valid
    panel.ensure_snapshot()
    if key == "components_count_badges":
        assert panel.selection == ["A"] and panel.scroll_area.minimumHeight() == 180
        panels.layer.advanceWidth += 1
    else:
        panels.state.names.reverse()
    with pytest.raises(ValueError, match="source changed|glyph order changed"):
        panel.ensure_snapshot()
    assert panel.package is None and not panel.copy_button.isEnabled()
    assert panel.grid.cards == [] and updates == ["update"]


def test_component_actions_when_callback_fails_then_visible_error_and_outputs_are_cleared(
    panels,
):
    module = panels.modules["components.inspect.ui"]
    panel = panels.make(module.ComponentsDialog, "components_compatibility")
    panel.prepare_initial()
    panel._source, panel._snapshot_valid = panel.source_values(), True
    with pytest.raises(ValueError, match="owned refusal"):
        module.action(lambda self: (_ for _ in ()).throw(ValueError("owned refusal")))(
            panel
        )
    assert not panel._snapshot_valid and panel.rows == []
    panel._connect(
        panel.copy_button.clicked,
        lambda: (_ for _ in ()).throw(ValueError("owned signal")),
    )
    panel.copy_button.setEnabled(True)
    panel.copy_button.click()
    assert "owned signal" in panel.last_error and "owned signal" in panel.status.text()
    panel.rescan = lambda: (_ for _ in ()).throw(ValueError("owned opening"))
    panel.initial_refresh()
    assert "owned opening" in panel.last_error
    panel.paint_failed("owned paint")
    assert panel.last_error == "owned paint" and not panel._snapshot_valid
    panel.close()
    assert panel._bound_id is None and panel.package is None


@pytest.mark.parametrize(
    "key",
    [
        "anchors_cloud_view",
        "anchors_compatibility_report",
        "anchors_mark_attachment_preview",
    ],
)
def test_anchors_when_options_or_coordinates_change_then_rescan_policy_and_results_are_exact(
    panels, key
):
    module = panels.modules["anchors.inspect.ui"]
    panel = panels.make(module.AnchorsDialog, key)
    panel.name, panel.base, panel.mark, panel.family = (
        combo(["top"]),
        combo(["A"]),
        combo(["acute"]),
        combo(["top"]),
    )
    updates = []
    panel.view = NS(panels=["old"], update=lambda: updates.append("update"))
    panel.prepare_initial()

    def rescan(self):
        if key == "anchors_compatibility_report":
            self.rows = module.api.anchor_sets(self.package, self.names, self.masters)
        elif key == "anchors_cloud_view":
            self.points = {
                m: module.api.cloud(self.glyphs, m, self.name.currentText)
                for m in self.masters
            }
        else:
            self.offsets = {
                m: module.api.attachment(
                    self.package.findName("A").findLayer(m),
                    self.package.findName("acute").findLayer(m),
                    "top",
                )
                for m in self.masters
            }
        return "complete"

    refresh = module.snapshot_refresh(rescan)
    assert refresh(panel) == "complete" and panel._ever_published
    panel.refresh = panel.rescan = panel.pair_changed = lambda: refresh(panel)
    panel.initial_refresh()
    assert panel.view.before_draw == panel.draw_guard
    panel.check_results()
    panel.draw_guard()
    if key == "anchors_cloud_view":
        assert panel.points["Regular"] == [("A", 100, 700)]
    if key == "anchors_mark_attachment_preview":
        assert panel.offsets == {"Regular": (50, 700), "Bold": (50, 700)}
    panels.layer.anchors[0].point = NS(x=lambda: 101, y=lambda: 700)
    if key == "anchors_compatibility_report":
        assert refresh(panel) == "complete" and panel._snapshot_valid
        panel.scope.setCurrentIndex(1)
    else:
        with pytest.raises(ValueError, match="source changed"):
            panel.ensure_snapshot()
        assert panel._reopen_required
        with pytest.raises(ValueError, match="reopen"):
            panel.load_initial()
    if panel._snapshot_valid:
        with pytest.raises(ValueError, match="options changed"):
            panel.draw_guard()
    assert panel.view.panels == [] and not panel._snapshot_valid
    panel.close()
    assert (
        panel.view.before_draw
        is panel.view.on_error
        is panel.view.failure_cleanup
        is None
    )


def test_anchor_copy_when_controls_change_then_complete_source_and_origin_auto_refusals_hold(
    panels,
):
    module = panels.modules["anchors.copy.ui"]
    panel = panels.make(module.CopyDialog, "anchors_copy")
    panel.source, panel.mode, panel.scale = (
        Edit("acute"),
        combo(["replace", "merge"]),
        QtWidgets.QCheckBox(),
    )
    panel.completion_model = QtCore.QStringListModel()
    panel.rebuild_label = QtWidgets.QLabel()
    panel.source_glyph = lambda: panel.package.findName(panel.source.text.strip())
    panel.prepare_initial()
    assert panel.completion_model.stringList() == ["A", "acute"]
    rows = [(["A", "Regular", "50", "100"], True), (["A", "Bold", "50", "50"], False)]

    def refresh(self):
        self.fill_rows(rows)

    module.snapshot_refresh(refresh)(panel)
    assert (
        panel._source_names == ["A", "acute"] and panel.table.item(0, 3).font().bold()
    )
    assert not panel.table.item(1, 3).font().bold()
    panel.ensure_snapshot()
    panel.mode.setCurrentIndex(1)
    panel.ensure_snapshot(options=False)
    with pytest.raises(ValueError, match="Options changed"):
        panel.ensure_snapshot()
    assert panel.package is None and panel.completion_model.stringList() == []
    panel.package = panels.package
    dependent, body = panels.owned.glyph("dependent", auto=True)
    body.shapes = [NS(isComponent=True, shapeData=NS(componentGlyph="A"))]
    panels.state.names.append("dependent")
    panel.pending_targets, panel.pending_origins = {"A"}, []
    panel.guard_apply()
    assert panel.rebuilds == ["dependent"] and not panel.apply_button.isEnabled()
    assert "automatic dependants" in panel.rebuild_label.text()
    panel.pending_origins = ["top"]
    panel.guard_apply()
    assert panel.rebuild_label.text() == module.ORIGIN_ERROR
    assert not any(
        event[0] in {"init-layer", "notify"} for event in panels.owned.events
    )
