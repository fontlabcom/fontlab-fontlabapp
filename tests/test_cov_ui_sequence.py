# this_file: tests/test_cov_ui_sequence.py
"""Sequence preview built offscreen: text/names modes, selection, wrap and failures."""

from types import SimpleNamespace
from typing import Any

import pytest

import _cov_qt as fq


@pytest.fixture
def seq_mod(monkeypatch):
    handle = fq.install(monkeypatch)
    module = handle.load("fontlabapp.fontui.sequence")
    yield module
    fq.release()


def make(module: Any, text: str = "AV", font: Any = "default", on_select: Any = None):
    model = fq.FontModel(fq.ufo_font()) if font == "default" else font
    seq = module.Sequence(model, None, on_select)
    if text:
        seq.text_control.setText(text)
    return seq, model


def names(seq: Any) -> list[Any]:
    return [g.name for g in seq.run.glyphs]


def test_identity_when_glyph_has_naked_then_underlying_object_is_used(seq_mod):
    inner = object()
    wrapper = SimpleNamespace(naked=lambda: inner)
    assert seq_mod._identity(wrapper) is inner, "FontParts wrappers are unwrapped"
    plain = object()
    assert seq_mod._identity(plain) is plain, "objects without naked() are themselves"


def test_refresh_when_text_typed_then_run_outlines_and_status_follow(seq_mod):
    seq, _ = make(seq_mod, "AV")
    assert names(seq) == ["A", "V"], "the run holds one glyph per typed character"
    assert set(seq.outlines) == {"A", "V"}, "an outline is loaded per distinct glyph"
    assert seq.diagnostic.text == "Unicode lookup; no shaping", "the status names the lookup mode"
    assert seq.run.glyphs[1].x == 520, "group kerning of -80 moves V"


def test_refresh_when_text_empty_then_status_says_no_preview(seq_mod):
    seq, _ = make(seq_mod, "")
    assert seq.run.glyphs == (), "empty text gives an empty run"
    assert seq.diagnostic.text == "No preview text", "the status says there is no preview"


def test_refresh_when_kerning_unchecked_then_pair_not_kerned(seq_mod):
    seq, _ = make(seq_mod, "AV")
    seq.kerning_control.setChecked(False)
    assert seq.run.glyphs[1].x == 600, "kerning toggle re-lays out the run"


def test_refresh_when_names_mode_then_slash_names_resolve(seq_mod):
    seq, _ = make(seq_mod, "/V /A")
    seq.mode_control.setCurrentIndex(1)
    assert names(seq) == ["V", "A"], "slash names resolve to glyphs in order"


def test_refresh_when_char_missing_then_diagnostic_lists_it(seq_mod):
    seq, _ = make(seq_mod, "A?")
    assert names(seq) == ["A", None], "an unmapped character leaves a gap"
    assert "Missing glyph for '?'" in seq.diagnostic.text, seq.diagnostic.text


def test_refresh_when_direction_rtl_then_run_is_rtl(seq_mod):
    seq, _ = make(seq_mod, "AV")
    seq.direction_control.setCurrentIndex(1)
    assert seq.run.direction == "rtl", "the direction control re-lays out right to left"


def test_refresh_when_font_none_then_failure_shown_and_run_cleared(seq_mod):
    seq, _ = make(seq_mod, "", font=None)
    assert seq.run is None, "no font means no run"
    assert seq.diagnostic.text == "No font supplied", "the missing font is reported"
    assert seq.kerning_control.enabled is False, "kerning is disabled without a font"
    tips = [c[1][0] for c in seq.kerning_control.calls if c[0] == "setToolTip"]
    assert tips[-1] == "Kerning unavailable: No font supplied", tips
    assert seq.kerning_control.checked is False, "Apply kerning is unchecked"


def test_refresh_when_font_has_no_kerning_then_control_disabled_with_reason(seq_mod):
    model = fq.FontModel(fq.ufo_font())
    del model.kerning
    seq, _ = make(seq_mod, "A", font=model)
    assert not seq.kerning_control.enabled, "kerning is disabled when the font has none"
    tips = [c[1][0] for c in seq.kerning_control.calls if c[0] == "setToolTip"]
    assert any(t.startswith("Kerning unavailable") for t in tips), tips


def test_refresh_when_upm_invalid_then_error_shown(seq_mod):
    seq, model = make(seq_mod, "A")
    model.info.unitsPerEm = 0
    seq.refresh()
    assert "unitsPerEm must be positive" in seq.diagnostic.text, "the invalid UPM is reported"
    assert seq.run is None, "the run is cleared on failure"
    assert seq.selected_index is None, "the selection is cleared on failure"


def test_refresh_when_closed_then_nothing_changes(seq_mod):
    seq, _ = make(seq_mod, "A")
    seq.close()
    seq.run = "kept"
    seq.refresh()
    assert seq.run == "kept", "a closed preview does not re-lay out"


def test_select_at_when_click_on_glyph_then_callback_gets_glyph_and_index(seq_mod):
    chosen = []
    seq, model = make(seq_mod, "AV", on_select=lambda g, i: chosen.append((g, i)))
    # A spans pixels 20..63; V starts at 20 + 520 * 0.072.
    seq.select_at(30, 20)
    assert seq.selected_index == 0, "a click on A selects index 0"
    assert chosen == [(model.ufo["A"], 0)], chosen
    seq.select_at(20 + 600 * 0.072, 20)
    assert seq.selected_index == 1, "overlap picks the later glyph"
    assert chosen[-1][1] == 1, "the callback gets the later index"
    assert seq.scroll.calls[-1][0] == "ensureVisible", "the selection is scrolled to"


def test_select_at_when_no_pixel_y_then_first_line_used(seq_mod):
    seq, _ = make(seq_mod, "A")
    seq.select_at(30)
    assert seq.selected_index == 0, "without a y the first line is hit-tested"


def test_select_at_when_click_misses_or_wrong_line_then_selection_unchanged(seq_mod):
    seq, _ = make(seq_mod, "A")
    seq.select_at(5000, 20)
    seq.select_at(30, 20 + 10 * seq.line_height)
    assert seq.selected_index is None, "neither a far click nor a lower line selects"


def test_select_at_when_closed_or_no_run_then_ignored(seq_mod):
    seq, _ = make(seq_mod, "A")
    seq.run = None
    seq.select_at(30, 20)
    assert seq.selected_index is None, "no run means nothing to hit"
    seq.close()
    seq.select_at(30, 20)
    assert seq.selected_index is None, "a closed preview ignores clicks"


def test_select_at_when_missing_glyph_occurrence_then_callback_gets_none(seq_mod):
    chosen = []
    seq, _ = make(seq_mod, "?", on_select=lambda g, i: chosen.append((g, i)))
    seq.select_at(30, 20)
    assert chosen == [(None, 0)], "an unmapped character still selects, with no glyph"


def test_select_occurrence_when_glyph_gone_then_failure_reported_without_callback(seq_mod):
    chosen = []
    seq, model = make(seq_mod, "A", on_select=lambda g, i: chosen.append(i))
    occurrence = seq.run.glyphs[0]
    del model.ufo["A"]
    seq._select_occurrence(occurrence)
    assert chosen == [], "the consumer is not called for a vanished glyph"
    assert seq.run is None, "the run is cleared when the glyph vanished"
    assert seq.diagnostic.text, seq.diagnostic.text


@pytest.mark.parametrize(
    "key,start,expected",
    [
        ("Key_Right", None, 0),
        ("Key_Right", 0, 1),
        ("Key_Left", 1, 0),
        ("Key_Left", 0, 0),
        ("Key_Home", 1, 0),
        ("Key_End", 0, 1),
        ("Key_Right", 1, 1),
    ],
)
def test_select_key_when_ltr_then_index_moves_and_clamps(seq_mod, key, start, expected):
    seq, _ = make(seq_mod, "AV")
    if start is not None:
        seq._select_occurrence(seq.run.glyphs[start])
    assert seq.select_key(getattr(seq_mod.QtCore.Qt, key)) is True, f"{key} is handled"
    assert seq.selected_index == expected, (key, start)


def test_select_key_when_rtl_then_arrows_reverse(seq_mod):
    seq, _ = make(seq_mod, "AV")
    seq.direction_control.setCurrentIndex(1)
    seq._select_occurrence(seq.run.glyphs[0])
    assert seq.select_key(seq_mod.QtCore.Qt.Key_Right) is True, "Right is handled in RTL"
    assert seq.selected_index == 0, "Right moves toward the start in an RTL run"
    assert seq.select_key(seq_mod.QtCore.Qt.Key_Left) is True, "Left is handled in RTL"
    assert seq.selected_index == 1, "Left moves toward the end in an RTL run"


def test_select_key_when_unhandled_key_empty_run_or_closed_then_false(seq_mod):
    seq, _ = make(seq_mod, "AV")
    assert seq.select_key("Key_A") is False, "unhandled keys are declined"
    empty, _ = make(seq_mod, "")
    assert empty.select_key(seq_mod.QtCore.Qt.Key_Home) is False, "an empty run declines keys"
    seq.close()
    assert seq.select_key(seq_mod.QtCore.Qt.Key_Home) is False, "a closed preview declines keys"


def test_refresh_when_glyph_selected_then_selection_kept_for_same_glyph(seq_mod):
    seq, _ = make(seq_mod, "AV")
    seq._select_occurrence(seq.run.glyphs[1])
    seq.refresh()
    assert seq.selected_index == 1, "the same underlying glyph keeps the selection"


def test_refresh_when_glyph_replaced_under_same_name_then_selection_dropped(seq_mod):
    seq, model = make(seq_mod, "AV")
    seq._select_occurrence(seq.run.glyphs[0])
    del model.ufo["A"]
    glyph = model.ufo.newGlyph("A")
    glyph.width = 600
    glyph.unicodes = [65]
    seq.refresh()
    assert seq.selected_index is None, "detached models keep object identity"


def test_refresh_when_native_font_then_selection_kept_by_name_and_index(seq_mod):
    model = fq.FontModel(fq.ufo_font())
    model._backend = SimpleNamespace(font_id=7)
    seq, _ = make(seq_mod, "AV", font=model)
    seq._select_occurrence(seq.run.glyphs[0])
    del model.ufo["A"]
    glyph = model.ufo.newGlyph("A")
    glyph.width = 600
    glyph.unicodes = [65]
    seq.refresh()
    assert seq.selected_index == 0, "FontLab-backed fonts rewrap glyphs on every read"


def test_refresh_when_selected_font_changed_then_selection_dropped(seq_mod):
    seq, _ = make(seq_mod, "AV")
    seq._select_occurrence(seq.run.glyphs[0])
    seq.font = fq.FontModel(fq.ufo_font())
    seq.refresh()
    assert seq.selected_index is None, "a different font drops the selection"


def test_viewport_event_when_resize_then_reflow_timer_starts(seq_mod):
    seq, _ = make(seq_mod, "A")
    assert seq.scroll.viewportEvent(seq_mod.QtCore.QEvent("Resize")) is True, (
        "the resize event is accepted"
    )
    assert seq.reflow_timer.started == 1, "resizes queue a reflow"
    seq.scroll.viewportEvent(seq_mod.QtCore.QEvent("Paint"))
    assert seq.reflow_timer.started == 1, "other events do not"


def test_reflow_when_wrapping_and_viewport_width_changes_then_refreshes(seq_mod):
    seq, _ = make(seq_mod, "AVAVAV")
    seq.wrap_control.setChecked(True)
    assert seq.wrap_width == 100, "wrapping starts at the viewport width"
    seq.scroll.width = 140
    seq.reflow_timer.timeout.emit()
    assert seq.wrap_width == 140, "a new width wraps again"
    runs = seq.run
    seq.reflow_timer.timeout.emit()
    assert seq.run is runs, "an unchanged width does not re-lay out"


def test_reflow_when_not_wrapping_closed_or_no_run_then_nothing(seq_mod):
    seq, _ = make(seq_mod, "A")
    seq.scroll.width = 300
    run = seq.run
    seq._reflow()
    assert seq.run is run, "wrap off: nothing happens"
    seq.wrap_control.setChecked(True)
    seq.run = None
    seq._reflow()
    assert seq.run is None, "no run: nothing to re-lay out"
    seq.close()
    seq._reflow()


def test_wrap_when_narrow_then_second_line_exists(seq_mod):
    seq, _ = make(seq_mod, "AVAVAV")
    seq.size_control.setValue(200)
    seq.wrap_control.setChecked(True)
    assert max(line for _, line in seq.positions) >= 1, seq.positions


def test_close_when_called_then_callbacks_and_selection_released(seq_mod):
    seq, _ = make(seq_mod, "A", on_select=lambda *a: None)
    seq._select_occurrence(seq.run.glyphs[0])
    seq.close()
    assert seq.on_select is None, "the selection callback is dropped"
    assert seq._selected_glyph is None, "the selected glyph is released"
    assert seq._selected_font is None, "the selected font is released"
    assert seq.closed, "the preview is marked closed"


def test_update_when_initial_before_assignment_then_passes_complete_owner(seq_mod):
    events = []
    model = fq.FontModel(fq.ufo_font())
    seq = seq_mod.Sequence(
        model,
        None,
        None,
        lambda owner: events.append((owner, owner.run, owner.selected_index)),
    )
    assert len(events) == 1 and events[0][0] is seq
    assert events[0][1] is seq.run and events[0][2] is None


@pytest.mark.parametrize("route", ["refresh", "fail", "key", "at", "reflow", "control"])
def test_update_when_actual_failure_route_then_cleared_once(
    seq_mod, monkeypatch, route
):
    seq, model = make(seq_mod, "AV")
    seq.select_at(30, 20)
    assert seq.selected_index == 0
    if route == "reflow":
        seq.wrap_control.setChecked(True)
    events = []
    seq.on_update = lambda owner: events.append(
        (owner.run, owner.selected_index, str(owner.diagnostic.text))
    )
    if route in ("key", "at"):

        def unavailable(self, name):
            raise RuntimeError("glyph unavailable")

        monkeypatch.setattr(type(model), "__getitem__", unavailable)
        if route == "key":
            seq.select_key(seq_mod.QtCore.Qt.Key_Right)
        else:
            seq.select_at(30, 20)
    elif route == "fail":
        seq.fail(ValueError("layout failed"))
    else:
        model.info.unitsPerEm = 0
        if route == "refresh":
            seq.refresh()
        elif route == "control":
            seq.text_control.setText("VA")
        else:
            seq.scroll.width += 1
            seq.reflow_timer.timeout.emit()
    assert len(events) == 1
    assert events[0][0] is None and events[0][1] is None
    assert events[0][2]


def test_update_when_callback_raises_then_no_recursive_fail_and_next_refresh_recovers(
    seq_mod,
):
    seq, _ = make(seq_mod, "AV")
    calls = []

    def failure(owner):
        calls.append(owner)
        raise ValueError("update consumer")

    seq.on_update = failure
    seq.refresh()
    assert calls == [seq] and seq.run is not None
    assert "Update callback failed: update consumer" in seq.diagnostic.text
    seq.on_update = calls.append
    seq.refresh()
    assert len(calls) == 2 and "callback failed" not in seq.diagnostic.text
    seq.close()
    assert seq.on_update is None
    seq.fail(ValueError("late"))
    assert len(calls) == 2


def test_pending_when_invalidated_twice_then_read_free_and_consumed_once(seq_mod, monkeypatch):
    seq, _ = make(seq_mod, "AVA")
    seq.select_key(seq_mod.QtCore.Qt.Key_End)
    selected = seq.run.glyphs[2]
    old_run = seq.run
    events = []
    seq.on_update = lambda owner: events.append(owner._pending_selection)
    capability = seq._kerning_capability
    monkeypatch.setattr(seq, "_kerning_capability", lambda: pytest.fail("invalidation read"))
    seq._invalidate_for_refresh()
    seq._invalidate_for_refresh()
    assert seq._pending_selection is selected
    assert (seq.run, seq.outlines, seq.selected_index) == (None, {}, None)
    assert events == []
    monkeypatch.setattr(seq, "_kerning_capability", capability)
    seq.refresh()
    assert seq.run is not old_run and seq.selected_index == 2
    assert seq._pending_selection is None and events == [None]
    seq.refresh()
    assert seq.selected_index == 2 and events == [None, None]


@pytest.mark.parametrize("ending", ["fail", "layout", "close"])
def test_pending_when_failure_or_close_then_discarded_before_callback(seq_mod, ending):
    seq, model = make(seq_mod, "AVA")
    seq.select_key(seq_mod.QtCore.Qt.Key_End)
    seq._invalidate_for_refresh()
    assert seq._pending_selection.index == 2
    observed = []
    seq.on_update = lambda owner: observed.append(owner._pending_selection)
    if ending == "fail":
        seq.fail(ValueError("owned failure"))
    elif ending == "layout":
        model.info.unitsPerEm = 0
        seq.refresh()
        model.info.unitsPerEm = 1000
    else:
        seq.close()
    assert seq._pending_selection is None
    assert observed == ([] if ending == "close" else [None])
    seq.refresh()
    assert seq.selected_index is None
    seq._invalidate_for_refresh()
    assert seq._pending_selection is None


def test_pending_when_visible_unselected_run_replaces_old_then_no_resurrection(seq_mod):
    seq, _ = make(seq_mod, "AVA")
    seq.select_key(seq_mod.QtCore.Qt.Key_End)
    run = seq.run
    seq._invalidate_for_refresh()
    seq.run = run
    seq.selected_index = None
    seq._invalidate_for_refresh()
    assert seq._pending_selection is None
    seq.refresh()
    assert seq.selected_index is None


def test_pending_when_font_identity_changes_then_selection_dropped(seq_mod):
    seq, _ = make(seq_mod, "AVA")
    seq.select_key(seq_mod.QtCore.Qt.Key_End)
    seq._invalidate_for_refresh()
    seq.font = fq.FontModel(fq.ufo_font())
    seq.refresh()
    assert seq._pending_selection is None and seq.selected_index is None


@pytest.mark.parametrize("callback", ["refresh", "fail", "close"])
def test_pending_when_update_reenters_then_slot_already_consumed(seq_mod, callback):
    seq, _ = make(seq_mod, "AVA")
    seq.select_key(seq_mod.QtCore.Qt.Key_End)
    seq._invalidate_for_refresh()
    seen = []

    def update(owner):
        seen.append(owner._pending_selection)
        owner.on_update = None
        getattr(owner, callback)(*([] if callback != "fail" else [ValueError("callback")]))

    seq.on_update = update
    seq.refresh()
    assert seen == [None] and seq._pending_selection is None


def test_pending_when_close_cleanup_fails_then_discarded_before_retry(seq_mod, monkeypatch):
    seq, _ = make(seq_mod, "AVA")
    seq.select_key(seq_mod.QtCore.Qt.Key_End)
    seq._invalidate_for_refresh()
    hide = seq.widget.hide
    monkeypatch.setattr(seq.widget, "hide", lambda: False)
    with pytest.raises(RuntimeError, match="hide refused"):
        seq.close()
    assert seq.closed and seq._pending_selection is None and not seq._close_complete
    monkeypatch.setattr(seq.widget, "hide", hide)
    seq.close()
    assert seq._close_complete and seq._pending_selection is None


def test_window_when_created_then_compact_panel_metrics(seq_mod):
    window = make(seq_mod)[0]
    assert [a for c, a in window.layout.calls if c == "setContentsMargins"] == [(6, 6, 6, 6)]
    assert [a for c, a in window.layout.calls if c == "setSpacing"] == [(4,)]
