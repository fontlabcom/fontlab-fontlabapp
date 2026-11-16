# this_file: tests/test_fontui_anchor_components.py
"""Direct ordered anchor/component data and actual linked selection."""

import importlib
from copy import deepcopy
import pytest
from ufoLib2.objects import Anchor, Component
import test_fontui_glyph_metrics as _fixtures
from test_fontui_glyph_metrics import owned_font, choose

composition_env = _fixtures.composition_env


def test_details_when_duplicates_and_missing_component_then_raw_rows_and_diagnostic():
    module = importlib.import_module("fontlabapp.fontui.anchor_components")
    font = owned_font()
    font["A"].anchors = [
        Anchor(1.25, 2.5, None),
        Anchor(3, 4, "top"),
        Anchor(5, 6, "top"),
    ]
    font["A"].components = [Component("missing", (1, 0, 0, 1, 10.5, 20))]
    value = module.details(font, "A")
    assert value.anchors == ((None, 1.25, 2.5), ("top", 3, 4), ("top", 5, 6))
    assert value.components == (("missing", (1, 0, 0, 1, 10.5, 20)),)
    assert "Missing component" in value.diagnostic


def test_inspector_when_selection_and_clear_then_both_tables_and_preview_follow(
    composition_env,
):
    env = composition_env
    font = owned_font()
    font["A"].anchors = [Anchor(1, 2, "top")]
    before = deepcopy(font)
    c = env.modules[1].show(font, env.parent)
    choose(c.browser, ["A"])
    assert c.anchor_rows == (("top", 1, 2),)
    assert c.browser.preview.name == "A" and c.browser.preview.options["anchors"]
    c.browser.filter("missing")
    assert c.anchor_rows == c.component_rows == ()
    assert c.browser.preview.name is None and font == before
    assert c.release()


def test_details_when_cyclic_then_direct_component_kept():
    module = importlib.import_module("fontlabapp.fontui.anchor_components")
    font = owned_font()
    font["A"].components = [Component("A", (1, 0, 0, 1, 0, 0))]
    value = module.details(font, "A")
    assert value.components[0][0] == "A" and "Cyclic" in value.diagnostic


@pytest.mark.parametrize("role", ["browser", "preview"])
@pytest.mark.parametrize("stage", ["hide", "deleteLater"])
def test_anchor_components_when_child_stage_strands_then_later_release_refuses(
    composition_env, monkeypatch, role, stage
):
    _fixtures._assert_stranded_cleanup(composition_env, monkeypatch, 1, role, stage)


@pytest.mark.parametrize("stage", ["hide", "deleteLater"])
@pytest.mark.parametrize("trigger", ["queued", "parent_after_failure"])
def test_anchor_components_when_terminal_signal_after_stranding_then_owner_stays(
    composition_env, monkeypatch, stage, trigger
):
    _fixtures._assert_stranded_cleanup(
        composition_env, monkeypatch, 1, "preview", stage, trigger
    )


@pytest.mark.parametrize("role", ["browser", "preview"])
def test_anchor_components_when_close_refuses_before_entry_then_retry_completes(
    composition_env, monkeypatch, role
):
    _fixtures._assert_preclose_retry(composition_env, monkeypatch, 1, role)


@pytest.mark.parametrize("setup_route", ["plain", "group", "interrupt", "exit"])
@pytest.mark.parametrize("cleanup_kind", ["interrupt", "exit"])
def test_anchor_components_when_setup_cleanup_interrupts_then_original_is_retained(
    composition_env, monkeypatch, setup_route, cleanup_kind
):
    _fixtures._assert_setup_cleanup_interruption(
        composition_env, monkeypatch, 1, setup_route, cleanup_kind
    )


@pytest.mark.parametrize("cleanup_kind", ["interrupt", "exit"])
def test_anchor_components_when_outer_cleanup_interrupts_then_original_group_is_retained(
    composition_env, monkeypatch, cleanup_kind
):
    _fixtures._assert_setup_cleanup_interruption(
        composition_env, monkeypatch, 1, "group", cleanup_kind, "outer"
    )


@pytest.mark.parametrize("cleanup_kind", ["interrupt", "exit"])
def test_anchor_components_when_public_release_interrupts_then_same_interrupt_escapes(
    composition_env, monkeypatch, cleanup_kind
):
    _fixtures._assert_public_release_interruption(
        composition_env, monkeypatch, 1, cleanup_kind
    )


def test_anchor_components_when_release_succeeds_then_children_are_collectible(
    composition_env,
):
    _fixtures._assert_clean_release_collects_children(composition_env, 1)
