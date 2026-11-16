# this_file: tests/test_scripting_lazy_panels.py
"""Public factories defer native work and resolve current owned panel types."""

from module_paths import module_name as _module_name
import sys
from types import ModuleType

import pytest

from fontlabapp.core import scripting


@pytest.mark.parametrize(
    "factory,module,symbol",
    [
        ("features_dialog_type", "_features_dialog", "FeaturesDialog"),
        ("names_dialog_type", "_names_dialog", "NamesDialog"),
        ("kerning_dialog_type", "_kerning_dialog", "KerningDialog"),
        ("kerning_edit_dialog_type", "_kerning_edit_dialog", "KerningEditDialog"),
        ("proof_dialog_type", "_proof_dialog", "ProofDialog"),
        ("master_angles_dialog_type", "_master_angles_dialog", "ItalicAngleDialog"),
        ("masters_dialog_type", "_masters_dialog", "MastersDialog"),
        ("inspectors_dialog_type", "_inspectors_dialog", "InspectorsDialog"),
        ("components_dialog_type", "_components_dialog", "ComponentsDialog"),
        ("anchors_dialog_type", "_anchors_dialog", "AnchorsDialog"),
        ("review_dialog_type", "_review_dialog", "ReviewDialog"),
        ("interpolation_view_type", "_interpolation_view", "BlendView"),
        ("master_switcher_dialog_type", "_switcher_dialog", "SwitcherDialog"),
        ("guides_dialog_type", "_guides_dialog", "GuidesDialog"),
        ("guides_preview_type", "_guides_views", "GridPreview"),
        ("guide_rewrite_dialog_type", "_guide_rewrite_dialog", "RewriteDialog"),
        ("guide_editor_dialog_type", "_guide_editor_dialog", "GuideListDialog"),
        ("anchor_copy_dialog_type", "_anchor_copy_dialog", "CopyDialog"),
        ("canvas_rsb_dialog_type", "_canvas_rsb_dialog", "CanvasRSBDialog"),
        ("angularizzle_dialog_type", "_angularizzle_dialog", "AngularizzleDialog"),
        ("point_counts_dialog_type", "_point_counts_dialog", "PointCountsDialog"),
        (
            "vertical_metrics_dialog_type",
            "_vertical_metrics_dialog",
            "VerticalMetricsDialog",
        ),
    ],
)
def test_factory_resolves_current_type_without_native_lookup(
    monkeypatch, factory, module, symbol
):
    target = ModuleType(_module_name(module))
    owned = type(symbol, (), {})
    setattr(target, symbol, owned)
    monkeypatch.setitem(sys.modules, target.__name__, target)
    monkeypatch.setattr(
        scripting, "_native", lambda name: pytest.fail("Factory touched native APIs")
    )
    assert getattr(scripting, factory)() is owned
    replacement = type(symbol, (), {})
    setattr(target, symbol, replacement)
    assert getattr(scripting, factory)() is replacement, (
        "Reloaded panels must not retain stale types"
    )
