# this_file: tests/test_wp03_scripting_facades.py
"""Keep studio-accessible lazy facades bound to current modules and arguments."""

import sys
from types import ModuleType

import pytest

from fontlabapp.core import scripting


@pytest.mark.parametrize(
    "factory,module",
    [
        ("kerning_editor_api", "kerning.edit.model"),
        ("kerning_selection_api", "kerning.selection"),
        ("proof_api", "proof.inspect.model"),
        ("context_proof_api", "proof.context"),
        ("kerning_proof_api", "kerning.proofs"),
        ("layer_selection_api", "masters.layers.selection"),
        ("proof_view_types", "proof.inspect.views"),
        ("master_angles_api", "masters.angles.model"),
        ("master_angles_view_types", "masters.angles.ui"),
        ("masters_api", "masters.inspect.model"),
        ("masters_view_types", "masters.inspect.views"),
        ("inspectors_api", "proof.inspectors.model"),
        ("inspectors_view_types", "proof.inspectors.views"),
        ("components_api", "components.inspect.model"),
        ("components_view_types", "components.inspect.views"),
        ("anchors_api", "anchors.inspect.model"),
        ("anchors_view_types", "anchors.inspect.views"),
        ("interpolation_api", "masters.interpolation.model"),
        ("node_coordinates_api", "contours.nodes.coordinates"),
        ("master_switcher_api", "masters.switcher.model"),
        ("guides_api", "guides.inspect.model"),
        ("guide_rewrite_api", "guides.rewrite.model"),
        ("anchor_copy_api", "anchors.copy.model"),
        ("canvas_rsb_api", "metrics.canvas_rsb.model"),
        ("canvas_anchor_rings_api", "anchors.canvas_rings.model"),
        ("kerning_persistence_api", "kerning.persistence.model"),
        ("revision_compare_api", "fonts.revisions.model"),
        ("anchors_coordinates_api", "anchors.coordinates.model"),
    ],
)
def test_public_module_facade_when_reloaded_then_returns_current_backend(
    monkeypatch, factory, module
):
    """A fresh lookup must return the replacement backend module."""
    name = f"fontlabapp.{module}"
    monkeypatch.setattr(
        scripting, "_native", lambda name: pytest.fail("Lazy lookup touched the host")
    )
    for _ in range(2):
        backend = ModuleType(name)
        monkeypatch.setitem(sys.modules, name, backend)
        assert getattr(scripting, factory)() is backend


@pytest.mark.parametrize(
    "factory,module,symbol",
    [
        ("kerning_editor_refresh", "kerning.edit.ui", "editor_refresh"),
        ("kerning_editor_apply", "kerning.edit.ui", "editor_apply"),
        ("proof_snapshot_refresh", "proof.inspect.ui", "snapshot_refresh"),
        ("masters_snapshot_refresh", "masters.inspect.ui", "snapshot_refresh"),
        ("inspectors_snapshot_refresh", "proof.inspectors.ui", "snapshot_refresh"),
        ("components_snapshot_refresh", "components.inspect.ui", "snapshot_refresh"),
        ("components_action", "components.inspect.ui", "action"),
        ("anchors_snapshot_refresh", "anchors.inspect.ui", "snapshot_refresh"),
        ("anchors_action", "anchors.inspect.ui", "action"),
        ("review_snapshot_refresh", "anchors.inspect.ui", "snapshot_refresh"),
        ("review_action", "components.inspect.ui", "action"),
        ("anchor_copy_snapshot_refresh", "anchors.copy.ui", "snapshot_refresh"),
    ],
)
def test_public_guard_when_decorating_then_preserves_method_identity_and_errors(
    monkeypatch, factory, module, symbol
):
    """The facade must neither call a callback early nor swallow guard failures."""
    backend = ModuleType(f"fontlabapp.{module}")
    calls = []
    result = object()

    def callback():
        pytest.fail("The guard facade executed a native callback while decorating")

    def guard(method):
        calls.append(method)
        return result

    setattr(backend, symbol, guard)
    monkeypatch.setitem(sys.modules, backend.__name__, backend)
    assert getattr(scripting, factory)(callback) is result
    assert calls == [callback]

    def refuse(method):
        raise RuntimeError("Stale captured source")

    setattr(backend, symbol, refuse)
    with pytest.raises(RuntimeError, match="Stale captured source"):
        getattr(scripting, factory)(callback)


def test_master_table_facades_when_called_then_keep_order_identity_and_highlights(
    monkeypatch,
):
    backend = ModuleType("fontlabapp.masters.inspect.ui")
    calls = []
    table, highlight = object(), object()
    headers, rows = ["Master", "Value"], [["Regular", 0], ["Bold", None]]
    backend.make_table = lambda *args: calls.append(args) or table
    backend.fill_table = lambda *args: calls.append(args)
    monkeypatch.setitem(sys.modules, backend.__name__, backend)
    assert scripting.masters_make_table(headers, 420) is table
    assert scripting.masters_fill_table(table, rows, highlight) is None
    assert calls == [(headers, 420), (table, rows, highlight)]
    assert calls[0][0] is headers and calls[1][1] is rows
    scripting.masters_make_table(headers)
    scripting.masters_fill_table(table, rows)
    assert calls[-2:] == [(headers, 280), (table, rows, None)]


@pytest.mark.parametrize(
    "factory,module,symbol",
    [
        ("canvas_anchor_rings_dialog_type", "anchors.canvas_rings.ui", "CanvasAnchorRingsDialog"),
        ("kerning_persistence_dialog_type", "kerning.persistence.ui", "KerningPersistenceDialog"),
        ("revision_compare_dialog_type", "fonts.revisions.ui", "RevisionCompareDialog"),
        ("tabular_width_dialog_type", "metrics.tabular_width.ui", "TabularWidthDialog"),
        ("component_recipes_dialog_type", "components.recipes.ui", "ComponentRecipesDialog"),
    ],
)
def test_report_type_when_replaced_then_factory_returns_replacement_type(
    monkeypatch, factory, module, symbol
):
    backend = ModuleType(f"fontlabapp.{module}")
    monkeypatch.setitem(sys.modules, backend.__name__, backend)
    for _ in range(2):
        panel = type(symbol, (), {})
        setattr(backend, symbol, panel)
        assert getattr(scripting, factory)() is panel


def test_kerning_table_facade_when_called_then_preserves_exact_headers(monkeypatch):
    backend = ModuleType("fontlabapp.kerning.edit.ui")
    headers, result, calls = ["Left", "Right", "Value"], object(), []
    backend.make_table = lambda value: calls.append(value) or result
    monkeypatch.setitem(sys.modules, backend.__name__, backend)
    assert scripting.kerning_editor_make_table(headers) is result
    assert calls == [headers] and calls[0] is headers
