# this_file: tests/test_issue205_proof_ui.py
"""Complete read-only proof, inspector and interpolation publication guards."""

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


def test_proof_when_optional_controls_and_failed_scan_then_cached_paints_are_disabled(
    panels,
):
    module = panels.modules["proof"]
    panel = panels.make(module.ProofDialog, "proof-owned")
    panel.add_proof_footer(copy_words=True, reload_selection=True)
    view = QtWidgets.QWidget()
    panel.add_proof_view(view, background=True, horizontal_off=True)
    assert panel.scroll_area.widget() is view and panel.scroll_area.autoFillBackground()
    assert panel.scroll_area.horizontalScrollBarPolicy() == QtCore.Qt.ScrollBarAlwaysOff
    assert (
        panel.copy_button.text() == "Copy words"
        and panel.reload_button.text() == "Reload selection"
    )
    panel.grid = NS(
        cells=["cached"], masters=["Regular"], painted=1, update=lambda: None
    )
    panel.view = NS(run=["cached"], sizes=[12], width_units=500, update=lambda: None)
    panel.result_view = QtWidgets.QPlainTextEdit()
    panel.result_view.setPlainText("cached")
    panel._snapshot_valid = True
    panel.drawing_failed("owned paint failure")
    assert not panel._snapshot_valid and panel.grid.cells == [] and panel.view.run == []
    assert panel.result_view.toPlainText() == "" and not panel.copy_button.isEnabled()
    assert "owned paint failure" in panel.status.text()
    panel.refresh = lambda: (_ for _ in ()).throw(ValueError("owned source failure"))
    panel.initial_refresh()
    assert "owned source failure" in panel.slot_error
    panel.close()
    assert (
        panel.package is None and panel.grid.before_draw is panel.view.on_error is None
    )


@pytest.mark.parametrize(
    "key",
    [
        "metrics_width_table",
        "outlines_node_statistics",
        "outlines_contour_order_view",
        "metrics_spacing_string_preview",
    ],
)
def test_inspectors_when_raw_values_or_scope_drift_then_all_actions_and_cached_geometry_clear(
    panels, key
):
    module = panels.modules["proof.inspectors.ui"]
    panel = panels.make(module.InspectorsDialog, key)
    panel.master, panel.glyph_combo = combo(["Regular", "Bold"]), combo(["A"])
    panel.text = Edit("/A /acute")
    panel.chosen_master = lambda: panel.master.currentText
    panel.view = NS(columns=[], update=lambda: None, paint_error="")

    def calculate(self):
        if key == "metrics_width_table":
            self.rows = module.api.report(self.require_glyphs(self.names), self.masters)
        elif key == "outlines_node_statistics":
            self.source.setCurrentIndex(1)
            self._scope_whole, self._scope_names = True, tuple(panels.state.names)
            self.data = {
                n: module.api.glyph_counts(self.package.findName(n), self.masters)
                for n in self._scope_names
            }
        elif key == "outlines_contour_order_view":
            self.view.columns = [
                (m, module.api.contour_info(layer))
                for m, layer in module.api.master_layers(
                    panels.glyph, self.masters
                ).items()
            ]
        else:
            self.rows = module.api.layout(
                self.package, ["A", "acute"], self.chosen_master()
            )
            self._outline_sources = {
                (n, self.chosen_master()): module.api.outline_source(
                    self.package.findName(n).findLayer(self.chosen_master())
                )
                for n, *_ in self.rows
            }

    refresh = module.snapshot_refresh(calculate)
    refresh(panel)
    assert panel._snapshot_valid and panel.source_values() == panel.source_values(
        cached=True
    )
    panel.ensure_snapshot()
    panel.draw_guard()
    if key == "metrics_width_table":
        selected = []
        panel.select_flagged = lambda: selected.append("guarded selection")
        module.InspectorsDialog.apply(panel)
        assert selected == ["guarded selection"]
        panels.layer.advanceWidth += 0.25
    elif key == "outlines_node_statistics":
        panels.state.names.append("new glyph")
    elif key == "outlines_contour_order_view":
        panel.view.columns.append(("unexpected", []))
    else:
        panels.package.ascender_value += 1
    with pytest.raises(ValueError, match="changed"):
        panel.ensure_snapshot()
    assert (
        not panel._snapshot_valid
        and panel.package is None
        and panel.paths == panel.info == {}
    )
    panel.draw_guard()
    panel.paint_cleanup()
    panel.close()
    assert panel.view.report is panel.view.failure_cleanup is None


def test_review_when_interpolated_then_exact_nodes_options_and_invalidated_results_match(
    panels,
):
    module = panels.modules["proof.review.ui"]
    anchor_module = panels.modules["anchors.inspect.ui"]
    panel = panels.make(module.ReviewDialog, "outlines_interpolation")
    panel.glyph_combo, panel.first, panel.second = (
        combo(["A"]),
        combo(["Regular", "Bold"]),
        combo(["Regular", "Bold"]),
    )
    panel.slider = NS(value=50)
    panel.view = NS(a=[], b=[], mix=[], panels=[], message="", update=lambda: None)
    for master, size in (("Regular", 100), ("Bold", 200)):
        points = [(0, 0), (size, 0), (size, size)]
        nodes = [NS(x=x, y=y, isOn=lambda: True) for x, y in points]
        contour = NS(closed=True, nodes=lambda nodes=nodes: nodes)
        panels.glyph.findLayer(master).shapes = [
            NS(
                isComponent=False,
                contours=[contour],
                transform=QtGui.QTransform(),
                getContours=lambda c=contour: [c],
            )
        ]

    def calculate(self):
        layers = module.interpolation.master_layers(panels.glyph, self.masters)
        self.view.a, self.view.b = (
            module.interpolation.outline(layers["Regular"]),
            module.interpolation.outline(layers["Bold"]),
        )
        self.mix = self.view.mix = module.interpolation.blend(
            self.view.a, self.view.b, 0.5
        )

    refresh = anchor_module.snapshot_refresh(calculate)
    refresh(panel)
    assert panel.view.mix[0][1] == (150, 0, True) and panel.geometry_names() == ["A"]
    assert panel.option_values() == ("A", "Regular", "Bold", 50)
    assert panel.describe_selection() and "1 glyph: A" == panel.subtitle.text()
    panel.refresh = lambda: refresh(panel)
    panel.initial_refresh()
    panel.view.on_error("owned failure")
    assert panel.last_error == "Drawing failed: owned failure"
    panel.view.mix = [[(999, 0, True)]]
    with pytest.raises(ValueError, match="Interpolation results changed"):
        panel.ensure_snapshot()
    assert panel.mix == panel.view.mix == [] and not panel.apply_button.isEnabled()
    panel.close()
    assert panel.view.report is None


def test_review_when_cleanup_candidates_or_selection_change_then_source_and_subtitle_stay_exact(
    panels, monkeypatch
):
    module = panels.modules["proof.review.ui"]
    anchor_module = panels.modules["anchors.inspect.ui"]

    class Groups(dict):
        def getAsClassRecords(self):
            return []

    font = NS(
        glyphs=[panels.glyph, panels.mark],
        groups=Groups(),
        features=NS(get_prefix=lambda: "", keys=lambda: []),
    )
    monkeypatch.setattr(panels.owned.native, "CurrentFont", lambda: font)
    monkeypatch.setattr(
        module.cleanup, "font_glyph_names", lambda: list(panels.state.names)
    )
    monkeypatch.setattr(
        module.cleanup, "names_font_glyphs", lambda: [("A", [65]), ("acute", [])]
    )
    for glyph in (panels.glyph, panels.mark):
        for master in panels.package.masters:
            glyph.findLayer(master).name = master
    panel = panels.make(module.ReviewDialog, module.CLEANUP)
    refresh = anchor_module.snapshot_refresh(
        lambda self: setattr(self, "rows", module.cleanup.unreferenced(self.package))
    )
    refresh(panel)
    assert (
        panel.rows == [("acute", "")]
        and panel.geometry_names() == []
        and panel.option_values() == ()
    )
    panel.ensure_snapshot()
    panel.names = []
    assert not panel.describe_selection() and "Select glyphs" in panel.subtitle.text()
    panel.names = [str(n) for n in range(9)]
    assert panel.describe_selection("candidate") and panel.subtitle.text().endswith(
        "7 …"
    )
    panel.rows = []
    with pytest.raises(ValueError, match="Candidate results changed"):
        panel.ensure_snapshot()
    assert (
        panel.package is None
        and not panel.describe_selection()
        and panel.subtitle.text() == "Open a font first."
    )
    assert panel.source_values() is None
    panel.check_results()
    panel._reopen_required = True
    with pytest.raises(ValueError, match="reopen"):
        panel.load_initial()
