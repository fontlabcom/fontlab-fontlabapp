# this_file: tests/test_issue205_masters_ui.py
"""Owned master reports reject domain drift and preserve exact button targets."""

import pytest
from types import SimpleNamespace as NS
from issue205_panels import (
    QtWidgets,
    panels as panels,
    legacy_qt as legacy_qt,
    owned as owned,
)


def test_master_overview_when_published_then_exact_rows_tables_and_scope_are_retained(
    panels,
):
    module = panels.modules["masters"]
    panel = panels.make(module.MastersDialog, "masters_overview")

    def calculate(self):
        self.rows = module.overview(self.package)
        return len(self.rows)

    assert module.snapshot_refresh(calculate)(panel) == 2
    assert panel._snapshot_valid and panel.package.master == "Regular"
    assert [row[0] for row in panel.rows] == ["Regular", "Bold"]
    panel.ensure_snapshot()
    assert panel.describe_selection() and "1 glyph: A" == panel.subtitle.text()
    assert panel.chosen_masters() == ["Regular"]
    panel.scope.setCurrentIndex(1)
    assert panel.chosen_masters() == ["Regular", "Bold"]
    assert panel.glyphs() == [panels.glyph]
    panel.names = ["missing", "A"]
    assert panel.glyphs() == [panels.glyph]
    panel.names = [f"G{i}" for i in range(9)]
    assert panel.describe_selection("item") and panel.subtitle.text().endswith(" …")
    panel.names = []
    assert not panel.describe_selection() and "Select glyphs" in panel.subtitle.text()
    module.fill_table(
        panel.table,
        [("A", "note"), ("B", "1", "2", "3", "4")],
        highlight=lambda r, c, text: text == "2",
    )
    assert panel.table.columnSpan(0, 1) == 4 and panel.table.item(1, 2).font().bold()
    table = module.make_table(["Master", "Value"], min_height=150)
    assert table.columnCount() == 2 and table.minimumHeight() == 150
    assert panel.form().count() == 0
    calls = []
    panel.refresh = lambda: calls.append("refresh")
    scope = panel.scope_combo()
    scope.setCurrentIndex(1)
    assert calls == ["refresh"]
    panel.package = None
    assert (
        not panel.describe_selection() and panel.subtitle.text() == "Open a font first."
    )


def test_master_compatibility_when_scope_or_font_changes_then_old_signatures_are_refused(
    panels,
):
    module = panels.modules["masters"]
    panel = panels.make(module.MastersDialog, "masters_compatibility_check")
    panel.prepare_initial()
    panel.source.setCurrentIndex(1)
    panel._scope_whole, panel._scope_names = True, tuple(panels.state.names)
    panel._structures = {"A": module.check_glyph(panels.glyph, panel.masters)[0]}
    assert panel.source_values() == panel.source_values(cached=True)
    panels.state.names.append("new glyph")
    with pytest.raises(ValueError, match="glyph order changed"):
        panel.source_values()
    panels.state.package = None
    with pytest.raises(ValueError, match="no longer current"):
        panel.ensure_snapshot()
    assert panel.package is None and not panel._snapshot_valid
    panel.refresh = lambda: (_ for _ in ()).throw(ValueError("owned scan failure"))
    panel.initial_refresh()
    assert "owned scan failure" in panel.last_error and "Error:" in panel.status.text()
    panel.paint_report("owned painter failure")
    assert panel.last_error == "owned painter failure"


@pytest.mark.parametrize(
    "drift", ["none", "master-order", "location", "label", "incomplete"]
)
def test_master_switcher_when_buttons_drift_then_targets_are_disabled_before_switching(
    panels, drift
):
    module = panels.modules["masters.switcher.ui"]
    panel = panels.make(module.SwitcherDialog, "masters_switcher")
    panel.buttons = {}

    def populate(values):
        panel.buttons = {
            master: NS(
                text=master + ("\n" + label if label else ""),
                setEnabled=lambda flag, m=master: disabled.append(m),
            )
            for master, label in values
        }

    disabled = []
    panel.populate_buttons = populate
    panel.prepare_initial()
    panel._source = panel.source_values(cached=True)
    panel._display_masters = tuple(panel.masters)
    panel._snapshot_valid = drift != "incomplete"
    assert panel.source_values() == panel._button_values
    if drift == "master-order":
        panels.package.masters.reverse()
    elif drift == "location":
        panel._source = ("different",)
    elif drift == "label":
        panel.buttons["Regular"].text = "wrong"
    if drift == "none":
        panels.package.master = "Bold"
        panel.ensure_snapshot()
        assert panel.package is panels.package and not disabled
    else:
        with pytest.raises(ValueError, match="changed|incomplete"):
            panel.ensure_snapshot()
        assert set(disabled) == {"Regular", "Bold"} and panel.package is None
    panel.package = None
    assert panel.source_values() is None
