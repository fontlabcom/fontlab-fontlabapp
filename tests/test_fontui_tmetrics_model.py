# this_file: tests/test_fontui_tmetrics_model.py
# SPDX-License-Identifier: Apache-2.0
"""TMetrics model without Qt: shaping status, rows, geometry, selection, readouts, fingerprint."""

from types import SimpleNamespace

import pytest

import _cov_qt as fq
from fontlabapp.fontui import shaping
from fontlabapp.fontui import tmetrics_model as tm

pytest.importorskip("uharfbuzz")


@pytest.fixture(autouse=True)
def _fresh_cache():
    shaping.clear_cache()
    yield
    shaping.clear_cache()


def font(features: str = "") -> fq.FontModel:
    model = fq.FontModel(fq.ufo_font())
    model.features = SimpleNamespace(text=features)
    return model


def model(text: str = "AV", **settings) -> tm.TMetricsModel:
    result = tm.TMetricsModel(font())
    result.update(text=text, **settings)
    return result


def test_update_when_text_shaped_then_status_and_cells_follow():
    m = model("AV")
    assert m.status == tm.SHAPED_NOTE, "HarfBuzz shaping is named in the status"
    assert [c.name for c in m.cells] == ["A", "V"], "one cell per shaped glyph"
    first, second = m.cells
    assert (first.width, first.kern) == (600, -80), "own advance and kerning offset are split"
    assert second.x == 520, "the second glyph sits after the kerned advance"
    assert (first.lsb, first.rsb) == (0, 0), "sidebearings come from the outline bounds"


def test_update_when_kerning_off_then_no_kern_offset():
    m = model("AV", kerning=False)
    assert m.cells[0].kern == 0, "the toggle removes the kerning offset"
    assert m.cells[1].x == 600, "the next glyph starts at the full advance"


def test_update_when_text_blank_or_font_missing_then_status_says_so():
    assert model("  ").status == tm.NO_TEXT_NOTE, "blank text is not shaped"
    empty = tm.TMetricsModel(None)
    empty.update(text="AV")
    assert empty.status == tm.NO_FONT_NOTE, "no font gives a status, not an error"
    assert empty.cells == (), "no font gives no cells"


def test_update_when_shaping_raises_then_status_reports_it():
    m = tm.TMetricsModel(fq.FontModel(fq.ufo_font()))
    m.font.keys = lambda: (_ for _ in ()).throw(RuntimeError("broken font"))
    m.update(text="AV")
    assert m.status.startswith("Cannot shape:"), "a shaping failure becomes the status"
    assert m.cells == (), "a failed shape leaves no cells"


def test_update_when_uharfbuzz_missing_then_fallback_diagnostic(monkeypatch):
    monkeypatch.setattr(shaping, "_load_harfbuzz", lambda: None)
    m = model("AV")
    assert m.status.startswith(shaping.FALLBACK_NOTE), "the fallback diagnostic is shown"
    assert [c.name for c in m.cells] == ["A", "V"], "fallback still lays out glyphs"


def test_update_when_missing_character_then_cell_is_absent_and_status_notes_it():
    m = model("A?")
    missing = m.cells[1]
    assert not missing.present, "a glyph not in the font is marked absent"
    assert missing.lsb is None and missing.rsb is None, "absent glyphs have no sidebearings"
    assert "Missing glyph" in m.status, "the diagnostic joins the status"


def test_update_when_rtl_then_cells_in_visual_order_and_pair_uses_logical_previous():
    m = model("AV", direction="rtl")
    assert [c.name for c in m.cells] == ["V", "A"], "RTL cells are visual left to right"
    m.select(0)  # V is logically second
    pair = m.pair_readout()
    assert (pair.left, pair.right) == ("A", "V"), "the pair before V is A V in logical order"
    m.select(1)
    assert m.pair_readout() is None, "the logically first glyph has no pair before it"


def test_update_when_script_language_set_then_passed_to_shaper(monkeypatch):
    seen = {}
    real = shaping.shape

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(shaping, "shape", spy)
    model("AV", script=" latn ", language="")
    assert seen["script"] == "latn" and seen["language"] is None, "fields are stripped; blank is None"


def test_reshape_when_cells_shrink_then_selection_is_clamped_or_cleared():
    m = model("AVA")
    m.select(2)
    m.update(text="AV")
    assert m.selected == 1, "selection clamps to the last cell"
    m.update(text="")
    assert m.selected is None, "no cells clears the selection"


def test_set_wrap_width_when_narrow_then_rows_break_and_restart_at_zero():
    m = model("AVAV")
    assert m.rows == 1, "unbounded width keeps one row"
    assert m.set_wrap_width(1200) is True, "a new width re-places"
    assert m.set_wrap_width(1200) is False, "the same width is a no-op"
    assert [c.row for c in m.cells] == [0, 0, 1, 1], "rows break before the overflowing glyph"
    assert m.cells[2].x == 0, "each row starts at x 0"


def test_break_rows_when_rtl_then_breaks_in_reading_order():
    run = tuple(shaping.PlacedGlyph(n, i, x, 0, 100) for i, (n, x) in enumerate([("c", 0), ("b", 100), ("a", 200)]))
    rows = tm.break_rows(run, [100, 100, 100], 250, "rtl")
    assert rows == [(1, 0), (0, 0), (0, 100)], "the rightmost glyphs fill the first row"


def test_break_rows_when_glyph_wider_than_row_then_own_row_and_bad_width_ignored():
    run = (shaping.PlacedGlyph("w", 0, 0, 0, 500), shaping.PlacedGlyph("x", 1, 500, 0, 100))
    assert tm.break_rows(run, [500, 100], 300, "ltr") == [(0, 0), (1, 0)], "the wide glyph stands alone"
    assert tm.break_rows(run, [500, 100], float("nan"), "ltr") == [(0, 0), (0, 500)], "NaN width means no wrap"


def test_geometry_when_ltr_and_rtl_then_rows_aligned_and_hits_found():
    m = model("AV")
    g = m.geometry(800)
    assert g.scale == pytest.approx(0.072), "72 px/em over 1000 upm"
    assert g.width == 800, "the canvas is at least the viewport width"
    assert g.origins[0] == (tm.MARGIN, tm.MARGIN + 800 * g.scale), "LTR starts at the margin on the baseline"
    assert m.cell_at(g, tm.MARGIN + 1, tm.MARGIN + 5) == 0, "a click on the first box hits it"
    assert m.cell_at(g, 5, 5) is None, "a click in the margin misses"
    m.update(direction="rtl")
    r = m.geometry(800)
    right = r.origins[-1][0] + m.cells[-1].width * r.scale
    assert right == pytest.approx(800 - tm.MARGIN), "RTL rows are right-aligned"


def test_geometry_when_empty_then_one_row_high_canvas():
    g = model("").geometry()
    assert g.origins == () and g.height > 0, "an empty model still has a drawable canvas"


def test_move_when_keys_then_visual_steps_and_logical_home_end():
    m = model("AVA")
    assert m.move("left") is True and m.selected == 2, "left from nothing selects the last cell"
    assert m.move("right") and m.selected == 2, "right stops at the edge"
    m.move("home")
    assert m.selected == 0, "home is the logical start (visual left in LTR)"
    m.move("end")
    assert m.selected == 2, "end is the logical end"
    assert m.move("up") is False, "unknown steps are not handled"
    m.update(direction="rtl")
    m.move("home")
    assert m.selected == 2, "RTL home is the visual right"
    m.select(None)
    m.move("right")
    assert m.selected == 0, "right from nothing selects the first cell"
    assert tm.TMetricsModel(font()).move("left") is False, "no cells, nothing to move"


def test_select_when_out_of_range_then_refused():
    m = model("AV")
    assert m.select(5) is False and m.selected is None, "out-of-range selection is refused"
    assert m.select(1) is True and m.select(1) is False, "re-selecting is not a change"


def test_readouts_when_selected_then_glyph_and_pair_texts():
    m = model("AV")
    assert m.glyph_readout() is None and m.pair_readout() is None, "nothing selected, nothing to read"
    m.select(1)
    assert m.glyph_readout().text() == "V  advance 600  LSB 0  RSB 0", "glyph readout format"
    pair = m.pair_readout()
    assert pair.kind == "group" and pair.value == -80, "group kerning is found"
    assert pair.text() == "Pair A V: -80 (group pair public.kern1.A public.kern2.V)", "pair readout format"
    m.select(0)
    assert m.pair_readout() is None, "the first glyph has no pair before it"


def test_kerning_pair_when_glyph_pair_exists_then_it_wins():
    f = font()
    f.kerning[("A", "V")] = -12.5
    pair = tm.kerning_pair(f, "A", "V")
    assert (pair.kind, pair.value, pair.key) == ("glyph", -12.5, ("A", "V")), "glyph pairs take precedence"
    assert pair.text().endswith("-12.5 (glyph pair A V)"), "fractions keep one decimal"
    none = tm.kerning_pair(f, "V", "A")
    assert none.kind == "none" and none.text() == "Pair V A: no kerning", "unkerned pairs say so"
    assert tm.kerning_pair(SimpleNamespace(), "A", "V").kind == "none", "a font without kerning reads none"


def test_glyph_readout_when_empty_glyph_then_dashes():
    ufo = fq.ufo_font()
    ufo.newGlyph("space").width = 250
    f = fq.FontModel(ufo)
    f.features = SimpleNamespace(text="")
    m = tm.TMetricsModel(f)
    m.update(text="/space")
    m.select(0)
    assert m.glyph_readout().text() == "space  advance 250  LSB –  RSB –", "empty glyphs have no sidebearings"


def test_read_metrics_when_values_bad_then_defaults():
    metrics = tm.read_metrics(SimpleNamespace(info=SimpleNamespace(unitsPerEm=0, ascender="x", descender=float("inf"))))
    assert metrics.upm == 1000 and metrics.ascender is None and metrics.descender is None, "bad values are dropped"
    assert metrics.top == 800 and metrics.bottom == -200, "row extents fall back to the em"
    full = tm.read_metrics(SimpleNamespace(info=SimpleNamespace(unitsPerEm=2048, ascender=1600, descender=-400, xHeight=1000, capHeight=1400)))
    assert [k for k, _ in full.lines()] == ["baseline", "ascender", "cap height", "x-height", "descender"], "all guides"


def test_sidebearings_when_glyph_unreadable_then_none():
    class Broken:
        def __contains__(self, name):
            raise RuntimeError("gone")

    assert tm.sidebearings(Broken(), "A") == (None, None, None), "errors read as unknown"
    assert tm.sidebearings(font(), "Z") == (None, None, None), "missing glyph is unknown"


def test_fingerprint_when_font_changes_then_digest_changes():
    m = model("AV")
    before = m.fingerprint()
    assert before == m.fingerprint(), "the digest is stable"
    m.font.kerning[("A", "V")] = -10
    assert m.fingerprint() != before, "kerning edits change the digest"
    again = m.fingerprint()
    m.font["A"].width = 610
    assert m.fingerprint() != again, "metric edits change the digest"
    again = m.fingerprint()
    m.font.features.text = "feature kern {} kern;"
    assert m.fingerprint() != again, "feature edits change the digest"


def test_fingerprint_when_font_unreadable_then_never_raises():
    digest = tm.fingerprint(SimpleNamespace(), ["A"])
    assert len(digest) == 40, "an unreadable font still digests"


# --- marks: no false kern bar ---------------------------------------------------
MARK_FEATURES = (
    "markClass acutecomb <anchor 150 700> @TOP;\n"
    "feature mark { pos base A <anchor 300 700> mark @TOP; } mark;\n"
)


def mark_font(features: str = MARK_FEATURES, width: float = 300) -> fq.FontModel:
    model = font(features)
    glyph = model.ufo.newGlyph("acutecomb")
    glyph.width, glyph.unicodes = width, [0x0301]
    pen = glyph.getPen()
    pen.moveTo((100, 700))
    pen.lineTo((200, 800))
    pen.lineTo((150, 700))
    pen.closePath()
    return model


def test_place_when_gdef_mark_then_mark_cell_has_no_kern():
    m = tm.TMetricsModel(mark_font())
    m.update(text="ÁV")
    by_name = {c.name: c for c in m.cells}
    assert by_name["acutecomb"].mark is True, "GDEF class mark is recognised"
    assert by_name["acutecomb"].kern == 0, "a mark never gets a kern bar"
    assert by_name["acutecomb"].width == 300, "the mark keeps its own width"
    assert by_name["A"].mark is False and by_name["V"].mark is False, "GDEF base glyphs are not marks"


def test_place_when_gdef_classes_and_nonzero_advance_then_gdef_decides():
    run = (shaping.PlacedGlyph("A", 0, 0, 0, 600, mark=True), shaping.PlacedGlyph("V", 1, 400, 0, 600, mark=False))
    m = tm.TMetricsModel(font())
    m.result = shaping.GlyphRunResult(run, 1000, True)
    m._place()
    assert [(c.mark, c.kern) for c in m.cells] == [(True, 0.0), (False, 0.0)], "GDEF mark wins over the advance"


def test_place_when_no_gdef_and_zero_nominal_width_then_treated_as_mark():
    run = (
        shaping.PlacedGlyph("A", 0, 0, 0, 600),
        shaping.PlacedGlyph("acutecomb", 1, 600, 0, 40),
        shaping.PlacedGlyph("V", 2, 640, 0, 600),
    )
    m = tm.TMetricsModel(mark_font(features="", width=0))
    m.result = shaping.GlyphRunResult(run, 1240, True)
    m._place()
    base, mark, after = m.cells
    assert (mark.mark, mark.kern, mark.width) == (True, 0.0, 0), "own width 0 marks it; no kern bar"
    assert (base.mark, after.mark) == (False, False), "glyphs with own width are bases"


def test_place_when_no_gdef_and_kerned_to_zero_advance_then_not_mark_and_kern_kept():
    run = (shaping.PlacedGlyph("A", 0, 0, 0, 0), shaping.PlacedGlyph("V", 1, 0, 0, 600))
    m = tm.TMetricsModel(font())
    m.result = shaping.GlyphRunResult(run, 600, True)
    m._place()
    first, second = m.cells
    assert first.mark is False, "a base kerned to zero advance is not a mark"
    assert first.kern == -600.0, "the kern bar stays: the whole 600 advance was kerned away"
    assert (second.mark, second.kern) == (False, 0.0), "the last glyph is unchanged"


def test_place_when_no_gdef_and_nonzero_advance_then_not_mark():
    m = model("AV")
    assert [c.mark for c in m.cells] == [False, False], "no GDEF: positive advances are bases"
    assert m.cells[0].kern == -80, "the base kern bar is unchanged"
