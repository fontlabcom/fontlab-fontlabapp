# this_file: tests/test_fontui_tmetrics_embed.py
"""Embedded TMetrics: controls=False, explicit layer, label prefix, set_text, highlights, hint guard."""

from types import SimpleNamespace

from _tmetrics_fakes import EditableFont
from test_cov_ui_tmetrics import tm_mod  # noqa: F401 - fixture

from fontlabapp.fontui.hinting import HintState


class LayeredFont(EditableFont):
    def getLayer(self, name):
        source = self.ufo["V"]
        return {"V": SimpleNamespace(width=source.width, bounds=tuple(source.getBounds()))}


def embedded(module, font=None, **kwargs):
    window = module.TMetrics(font or EditableFont(), None, None, "AV", **kwargs)
    window.scroll.viewport().width = 800
    window.refresh()
    window.model.select(1)
    window._show_selection()
    return window


def test_controls_false_when_embedded_then_controls_hidden_canvas_kept(tm_mod):  # noqa: F811
    window = embedded(tm_mod, controls=False)
    assert window.control_widgets and all(not w.shown for w in window.control_widgets)
    assert window.scroll.shown and window.diagnostic.shown


def test_controls_default_when_standalone_then_controls_visible(tm_mod):  # noqa: F811
    window = embedded(tm_mod)
    assert all(w.shown for w in window.control_widgets)


def test_label_prefix_and_layer_when_writing_then_used_in_edit(tm_mod):  # noqa: F811
    window = embedded(tm_mod, LayeredFont(), layer="Bold", label_prefix="Spacing Studio")
    assert window.commit("width", "650")
    assert window.font.edits == [("V", "Bold", "Spacing Studio: width V")]


def test_kerning_when_layer_not_current_master_then_refused_in_status(tm_mod):  # noqa: F811
    window = embedded(tm_mod, layer="Bold", label_prefix="Kerning Studio")
    assert window.commit("kerning", "-50") is False
    assert "Kerning is written to the default master (public.default) only; Bold cannot be targeted." in window.diagnostic.text
    assert "current master" not in window.diagnostic.text


def test_kerning_when_label_prefix_then_undo_name_names_app_and_pair(tm_mod):  # noqa: F811
    window = embedded(tm_mod, label_prefix="Kerning Studio")
    seen = []
    pairs = window.font.kerning
    original = pairs.apply
    pairs.apply = lambda values, *, undo_name: (seen.append(undo_name), original(values, undo_name=undo_name))
    assert window.commit("kerning", "-50")
    assert seen == ["Kerning Studio: kerning A V"]


def test_nudge_when_layer_set_then_reads_layer_rsb(tm_mod):  # noqa: F811
    window = embedded(tm_mod, LayeredFont(), layer="Bold")
    assert window.nudge("rsb", 5)
    assert window.font.edits[0][1] == "Bold"


def test_set_text_when_called_then_same_path_as_constructor(tm_mod):  # noqa: F811
    window = embedded(tm_mod)
    window.set_text("VA")
    assert window.text_control.text == "VA"
    assert [cell.name for cell in window.model.cells] == ["V", "A"]
    fresh = tm_mod.TMetrics(EditableFont(), None, None, "VA")
    assert [c.name for c in fresh.model.cells] == [c.name for c in window.model.cells]


def test_highlight_pair_and_cell_when_found_then_selected(tm_mod):  # noqa: F811
    window = embedded(tm_mod)
    assert window.highlight_pair("A", "V") and window.model.selected == 1
    assert window.highlight_cell(0) and window.model.selected == 0
    assert not window.highlight_pair("V", "A")
    assert not window.highlight_cell(9)


def test_hint_guard_when_layer_hinted_then_sidebearings_off_width_works(tm_mod):  # noqa: F811
    state = HintState(True, False, False)
    seen = []

    def check(name, layer):
        seen.append((name, layer))
        return state

    window = embedded(tm_mod, hint_check=check)
    assert not window.metric_controls["rsb"].enabled and not window.metric_controls["lsb"].enabled
    assert window.metric_controls["width"].enabled
    assert window.diagnostic.text == state.text()
    assert window.commit("rsb", "10") is False and window.diagnostic.text == f"Error: {state.text()}"
    assert window.font.edits == []
    assert window.commit("width", "650")
    assert seen[0] == ("V", None)


def test_set_layer_when_unhinted_then_sidebearings_back_on(tm_mod):  # noqa: F811
    states = {"Hinted": HintState(True, False, False), "Clean": HintState(False, False, False)}
    window = embedded(tm_mod, layer="Hinted", hint_check=lambda name, layer: states[layer])
    assert not window.metric_controls["rsb"].enabled
    window.set_layer("Clean")
    assert window.layer == "Clean" and window.metric_controls["rsb"].enabled


def test_closed_when_setters_called_then_ignored(tm_mod):  # noqa: F811
    window = embedded(tm_mod)
    window.close()
    window.set_text("VA")
    window.set_layer("Bold")
    assert window.layer is None
    assert not window.highlight_cell(0)


def test_layer_when_non_default_then_readout_and_preview_read_that_layer(tm_mod):  # noqa: F811
    from _tmetrics_fakes import TwoLayerFont

    window = embedded(tm_mod, TwoLayerFont(), layer="Bold")
    window.model.select(0)
    glyph = window.model.glyph_readout()
    assert (glyph.name, glyph.advance, glyph.lsb, glyph.rsb) == ("A", 700, 50, 50)
    assert window.outlines["A"].bounds == (50, 0, 650, 700)
    cells = window.model.cells
    assert cells[1].x == cells[0].x + cells[0].width + cells[0].kern, "layer widths re-space the run"


def test_layer_when_written_then_readout_shows_new_value(tm_mod):  # noqa: F811
    from _tmetrics_fakes import TwoLayerFont

    font = TwoLayerFont()
    window = embedded(tm_mod, font, layer="Bold")
    window.model.select(0)
    window._show_selection()
    assert window._write_metric("width", 720)
    window.refresh()
    window.model.select(0)
    assert window.model.glyph_readout().advance == 720
    assert font.ufo["A"].width == 600, "the default layer is untouched"
    assert font.edits[-1][1] == "Bold"


def test_set_layer_when_switched_then_readout_follows(tm_mod):  # noqa: F811
    from _tmetrics_fakes import TwoLayerFont

    window = embedded(tm_mod, TwoLayerFont())
    window.model.select(0)
    assert window.model.glyph_readout().advance == 600
    window.set_layer("Bold")
    window.model.select(0)
    assert window.model.layer == "Bold" and window.model.glyph_readout().advance == 700
    before = window.model.fingerprint()
    window.font.ufo.layers["Bold"]["A"].width = 710
    assert window.model.fingerprint() != before, "follow sees edits on the target layer"
    window.set_layer("Missing")
    assert window.model.source is window.font


def test_hint_check_when_not_injected_then_default_native_resolver_used(tm_mod, monkeypatch):  # noqa: F811
    from fontlabapp.fontui import hinting

    seen = []
    monkeypatch.setattr(hinting, "hint_state_of", lambda pkg, name, layer: seen.append((pkg, name, layer)) or HintState(True))
    monkeypatch.setattr(hinting, "package_of", lambda font: "pkg")
    window = embedded(tm_mod, layer="public.default")
    assert window.hint_state().ps_hints
    assert seen[-1] == ("pkg", "V", "public.default")
    assert window.hint_state("A") and seen[-1][1] == "A"


def test_read_only_when_commit_or_nudge_then_refused_without_edits(tm_mod):  # noqa: F811
    window = embedded(tm_mod, LayeredFont(), layer="Bold", read_only=True)
    assert window.commit("width", "650") is False
    assert window.commit("kerning", "-50") is False
    assert window.nudge("rsb", 5) is False
    assert window.nudge("kerning", 5) is False
    assert window.font.edits == [] and tm_mod.READ_ONLY_MESSAGE in window.diagnostic.text


def test_set_view_when_sized_then_clamped_kerning_set_and_none_kept(tm_mod):  # noqa: F811
    window = embedded(tm_mod)
    assert window.set_view(4, False) == 8.0
    assert not window.kerning_control.checked
    assert window.set_view(600) == 512.0 and not window.kerning_control.checked
    assert window.set_view(None, True) == 512.0 and window.kerning_control.checked
    assert window.set_view(48.4) == 48.0
    window.close()
    assert window.set_view(96) == 48.0
