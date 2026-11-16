# this_file: tests/test_fontui_unicode_order.py
"""Actual sequence occurrence and failure transitions stay linked to metadata."""

import importlib
from copy import deepcopy
import pytest
import test_fontui_glyph_metrics as _fixtures
from test_fontui_glyph_metrics import owned_font, choose

composition_env = _fixtures.composition_env


def test_records_when_order_repeats_and_non_bmp_then_preserves_all_values():
    module = importlib.import_module("fontlabapp.fontui.unicode_order")
    font = owned_font()
    font.glyphOrder = ["V", "A", "V"]
    font["V"].unicodes = [0x1F600, 86]
    font["A"].unicodes = []
    rows = module.records(font)
    assert [(r.index, r.name, r.unicodes) for r in rows] == [
        (0, "V", (0x1F600, 86)),
        (1, "A", ()),
        (2, "V", (0x1F600, 86)),
    ]


@pytest.mark.parametrize("route", ["refresh", "key", "at", "reflow", "control", "host"])
def test_unicode_when_real_sequence_failure_then_metadata_and_preview_clear(
    composition_env, monkeypatch, route
):
    env = composition_env
    font = owned_font()
    before = deepcopy(font)
    c = env.modules[2].show(font, env.parent)
    assert c.sequence.mode_control.currentIndex == 1
    assert [g.name for g in c.sequence.run.glyphs] == ["A", "V"]
    c.sequence.text_control.setText("/A /V /A")
    c.sequence.select_key(env.qt.QtCore.Qt.Key_End)
    assert c.occurrence_index == 2 and c.browser.preview.name == "A"
    if route == "reflow":
        c.sequence.wrap_control.setChecked(True)
    if route in ["key", "at"]:
        original = type(font).__getitem__

        def broken(self, name):
            if self is font:
                raise RuntimeError("unavailable read")
            return original(self, name)

        monkeypatch.setattr(type(font), "__getitem__", broken)
        if route == "key":
            c.sequence.select_key(env.qt.QtCore.Qt.Key_Left)
        else:
            c.sequence.select_at(30, 20)
    else:
        font.info.unitsPerEm = 0
        if route == "refresh":
            c.sequence.refresh()
        elif route == "control":
            c.sequence.text_control.setText("/V")
        elif route == "host":
            c.browser._changed()
        else:
            c.sequence.scroll.width += 1
            c.sequence.reflow_timer.timeout.emit()
    assert c.occurrence_index is None and c.selected_rows == ()
    assert c.browser.preview.name is None and c.sequence.diagnostic.text
    if route not in ["key", "at"]:
        font.info.unitsPerEm = 1000
    assert font == before


def test_unicode_when_repeated_non_bmp_selected_then_occurrence_and_identical_refresh_preserved(
    composition_env,
):
    env = composition_env
    font = owned_font()
    font["A"].unicodes = [65, 0x1F600]
    c = env.modules[2].show(font, env.parent)
    c.sequence.text_control.setText("/A /V /A")
    c.sequence.select_key(env.qt.QtCore.Qt.Key_End)
    assert c.occurrence_index == 2 and "U+1F600" in str(c.selected_rows)
    c.browser._changed()
    assert c.sequence.text_control.text == "/A /V /A" and c.occurrence_index == 2
    choose(c.browser, ["V"])
    assert [g.name for g in c.sequence.run.glyphs] == ["V"]
    assert c.occurrence_index == 0 and c.browser.preview.name == "V"
    c.browser.filter("absent")
    assert c.selected_rows == () and c.sequence.run.glyphs == ()
    assert c.release()


@pytest.mark.parametrize("role", ["browser", "preview", "sequence"])
@pytest.mark.parametrize("stage", ["hide", "deleteLater"])
def test_unicode_order_when_child_stage_strands_then_later_release_refuses(
    composition_env, monkeypatch, role, stage
):
    _fixtures._assert_stranded_cleanup(composition_env, monkeypatch, 2, role, stage)


@pytest.mark.parametrize("stage", ["hide", "deleteLater"])
@pytest.mark.parametrize("trigger", ["queued", "parent_after_failure"])
def test_unicode_order_when_terminal_signal_after_stranding_then_owner_stays(
    composition_env, monkeypatch, stage, trigger
):
    _fixtures._assert_stranded_cleanup(
        composition_env, monkeypatch, 2, "sequence", stage, trigger
    )


@pytest.mark.parametrize("role", ["browser", "preview", "sequence"])
def test_unicode_order_when_close_refuses_before_entry_then_retry_completes(
    composition_env, monkeypatch, role
):
    _fixtures._assert_preclose_retry(composition_env, monkeypatch, 2, role)


@pytest.mark.parametrize("setup_route", ["plain", "group", "interrupt", "exit"])
@pytest.mark.parametrize("cleanup_kind", ["interrupt", "exit"])
def test_unicode_order_when_setup_cleanup_interrupts_then_original_is_retained(
    composition_env, monkeypatch, setup_route, cleanup_kind
):
    _fixtures._assert_setup_cleanup_interruption(
        composition_env, monkeypatch, 2, setup_route, cleanup_kind
    )


@pytest.mark.parametrize("cleanup_kind", ["interrupt", "exit"])
def test_unicode_order_when_outer_cleanup_interrupts_then_original_group_is_retained(
    composition_env, monkeypatch, cleanup_kind
):
    _fixtures._assert_setup_cleanup_interruption(
        composition_env, monkeypatch, 2, "group", cleanup_kind, "outer"
    )


@pytest.mark.parametrize("cleanup_kind", ["interrupt", "exit"])
def test_unicode_order_when_public_release_interrupts_then_same_interrupt_escapes(
    composition_env, monkeypatch, cleanup_kind
):
    _fixtures._assert_public_release_interruption(
        composition_env, monkeypatch, 2, cleanup_kind
    )


def test_unicode_order_when_release_succeeds_then_children_are_collectible(
    composition_env,
):
    _fixtures._assert_clean_release_collects_children(composition_env, 2)
