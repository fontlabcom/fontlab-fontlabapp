# this_file: tests/test_fontui_tglyph_embed.py
"""Embedded TGlyph: controls=False, overlay, highlights, label prefix and hint guard."""

from _tglyph_fakes import editable_font
from test_cov_ui_tglyph import _painted, at, calls, make, tg_mod  # noqa: F401 - fixture

from fontlabapp.fontui.hinting import HintState


def drag(window):
    x, y = at(window, 0, 4)
    window.press(x, y, "LeftButton", 0)
    window.move(x + 30, y)
    window.release(x + 30, y)


def test_controls_false_when_embedded_then_controls_hidden(tg_mod):  # noqa: F811
    window = tg_mod.TGlyph(editable_font(), "a", None, None, controls=False)
    assert window.control_widgets and all(not w.shown for w in window.control_widgets)
    assert window.diagnostic.shown


def test_controls_default_then_visible(tg_mod):  # noqa: F811
    window = make(tg_mod)
    assert all(w.shown for w in window.control_widgets)


def test_label_prefix_when_dragged_then_undo_name_names_app(tg_mod):  # noqa: F811
    font = editable_font()
    window = tg_mod.TGlyph(font, "a", None, None, label_prefix="Contour Studio")
    window.canvas.width, window.canvas.height = 400, 400
    window.fit()
    drag(window)
    assert font.edits == [("a", "public.default", "Contour Studio: Move a")]


def test_overlay_when_set_then_ghost_drawn_and_cleared(tg_mod):  # noqa: F811
    window = make(tg_mod)
    plain = len(calls(_painted(window), "drawPath"))
    window.set_overlay(window.model.data)
    assert window.overlay is window.model.data
    assert len(calls(_painted(window), "drawPath")) > plain
    window.set_overlay(None)
    assert len(calls(_painted(window), "drawPath")) == plain


def test_highlight_when_points_segments_anchors_then_marked(tg_mod):  # noqa: F811
    window = make(tg_mod)
    base = _painted(window)
    ellipses, lines = len(calls(base, "drawEllipse")), len(calls(base, "drawLine"))
    anchors = [a.name for a in window.model.data.anchors]
    window.highlight(points=[(0, 0), (9, 9)], segments=[(0, 1)], anchors=anchors + ["nope"])
    painter = _painted(window)
    assert len(calls(painter, "drawEllipse")) == ellipses + 2 + len(anchors)
    assert len(calls(painter, "drawLine")) == lines + 1
    window.highlight()
    assert window.highlights == {"points": frozenset(), "segments": frozenset(), "anchors": frozenset()}


def test_hint_guard_when_layer_hinted_then_status_and_no_write(tg_mod):  # noqa: F811
    font = editable_font()
    state = HintState(False, True, False)
    seen = []
    window = tg_mod.TGlyph(font, "a", None, None, hint_check=lambda name, layer: seen.append((name, layer)) or state)
    window.canvas.width, window.canvas.height = 400, 400
    window.fit()
    assert window.diagnostic.text == state.text()
    drag(window)
    assert font.edits == []
    assert window.diagnostic.text == f"Error: {state.text()}"
    assert seen[0] == ("a", "public.default")


def test_closed_when_setters_called_then_ignored(tg_mod):  # noqa: F811
    window = make(tg_mod)
    window.close()
    window.set_overlay(window.model.data)
    window.highlight(points=[(0, 0)])
    assert window.overlay is None and window.highlights["points"] == frozenset()


def test_hint_check_when_not_injected_then_default_native_resolver_used(tg_mod, monkeypatch):  # noqa: F811
    from fontlabapp.fontui import hinting

    seen = []
    monkeypatch.setattr(hinting, "hint_state_of", lambda pkg, name, layer: seen.append((pkg, name, layer)) or HintState(False, True))
    monkeypatch.setattr(hinting, "package_of", lambda font: "pkg")
    window = make(tg_mod)
    assert window.hint_state().tt_data
    assert seen[-1][:2] == ("pkg", "a")


def test_read_only_when_all_edit_inputs_then_font_and_model_unchanged(tg_mod):  # noqa: F811 - imported fixture
    font = editable_font()
    window = tg_mod.TGlyph(font, "a", read_only=True)
    window.canvas.width, window.canvas.height = 400, 400
    window.fit()
    before = window.model.data
    window.model.selection = {(0, 5)}
    for key in ("Key_O", "Key_Delete", "Key_Backspace", "Key_Left", "Key_Right", "Key_Up", "Key_Down", "Key_P"):
        window.key_press(key)
    for key in ("Key_X", "Key_V", "Key_C"):
        window.key_press(key, tg_mod.QtCore.Qt.ControlModifier)
        window.key_press(key, tg_mod.QtCore.Qt.MetaModifier)
    drag(window)
    window.set_tool("pen")
    window.press(10, 10, "LeftButton", 0)
    window.press(30, 30, "LeftButton", 0)
    assert window.model.data == before
    assert font.edits == []
    assert window.editor.pending is None
    window.key_press("Key_Plus")
    assert window.model.view.adjusted
    window.close()


def test_factory_when_read_only_requested_then_editor_refuses_writes(tg_mod):  # noqa: F811 - imported fixture
    from fontlabapp import fontui

    window = fontui.glyph_view(editable_font(), name="a", read_only=True)
    assert window.editor.read_only
    assert "Drag selected points" not in window.help.text
    window.close()


def test_factory_when_glyph_load_fails_then_partial_view_disconnects_and_stops_timer(tg_mod, monkeypatch):  # noqa: F811
    import pytest

    from fontlabapp import fontui

    made = []
    failure = ValueError("initial glyph load failed")

    def fail_load(owner, *args):
        made.append(owner)
        owner.follow_timer.start()
        raise failure

    monkeypatch.setattr(tg_mod.TGlyph, "load", fail_load)
    with pytest.raises(ValueError) as caught:
        fontui.glyph_view(editable_font(), name="a", read_only=True)
    assert caught.value is failure
    assert made[0]._close_complete and made[0].connections == []
    assert ("stop", ()) in made[0].follow_timer.calls
