# this_file: tests/test_fontui_shaping.py
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the Qt-free text shaping backend."""

import sys

import pytest

defcon = pytest.importorskip("defcon")
pytest.importorskip("uharfbuzz")
pytest.importorskip("fontTools")

from fontlabapp.fontui import shaping  # noqa: E402

LIGA = "feature liga { sub f i by f_i; } liga;"


def make_font(features="", kerning=None, groups=None):
    font = defcon.Font()
    font.info.unitsPerEm = 1000
    font.newGlyph(".notdef").width = 500
    for name, char, width in [
        ("A", "A", 600), ("V", "V", 600), ("B", "B", 700), ("f", "f", 300), ("i", "i", 250),
        ("f_i", None, 520), ("space", " ", 200), ("alef", "א", 400), ("bet", "ב", 450),
        ("Aacute", "Á", 600),
    ]:
        glyph = font.newGlyph(name)
        glyph.width = width
        if char:
            glyph.unicode = ord(char)
    font.features.text = features
    for pair, value in (kerning or {}).items():
        font.kerning[pair] = value
    for name, members in (groups or {}).items():
        font.groups[name] = members
    return font


@pytest.fixture(autouse=True)
def fresh_cache():
    shaping.clear_cache()


def names(result):
    return [g.name for g in result.glyphs]


def test_shape_when_plain_text_then_advances_follow_widths():
    result = shape_text("AB")
    assert result.shaped is True
    assert names(result) == ["A", "B"]
    assert [g.x for g in result.glyphs] == [0, 600]
    assert result.advance == 1300
    assert result.diagnostics == ()


def shape_text(text, font=None, **kw):
    return shaping.shape(font or make_font(), text, **kw)


def test_shape_when_liga_feature_then_ligature_substituted():
    font = make_font(LIGA)
    assert names(shaping.shape(font, "fi")) == ["f_i"]
    assert names(shaping.shape(font, "fi", features="-liga")) == ["f", "i"]


def test_shape_when_kern_groups_then_group_pair_applied():
    font = make_font(
        kerning={("public.kern1.A", "public.kern2.V"): -80, ("A", "B"): -30},
        groups={"public.kern1.A": ["A", "Aacute"], "public.kern2.V": ["V"]},
    )
    assert shaping.shape(font, "AV").advance == 1200 - 80
    assert shaping.shape(font, "ÁV").advance == 1200 - 80
    assert shaping.shape(font, "AB").advance == 1300 - 30


def test_shape_when_kern_disabled_then_no_adjustment():
    font = make_font(kerning={("A", "V"): -80})
    assert shaping.shape(font, "AV").advance == 1120
    assert shaping.shape(font, "AV", features="-kern").advance == 1200
    assert shaping.shape(font, "AV", kerning=False).advance == 1200


def test_shape_when_user_kern_feature_then_generated_kern_skipped():
    font = make_font("feature kern { pos A V -10; } kern;", kerning={("A", "V"): -80})
    assert shaping.shape(font, "AV").advance == 1190


def test_shape_when_rtl_then_glyphs_in_visual_order():
    result = shape_text("אב", direction="rtl")
    assert names(result) == ["bet", "alef"]
    assert result.advance == 850
    assert [g.cluster for g in result.glyphs] == [1, 0]


def test_shape_when_glyph_missing_then_notdef_and_diagnostic():
    result = shape_text("AZ")
    assert names(result) == ["A", ".notdef"]
    assert result.diagnostics == ("Missing glyph for 'Z'",)


def test_shape_when_feature_code_invalid_then_recompiled_without_features():
    font = make_font("feature liga { sub nosuch by f_i; } liga;", kerning={("A", "V"): -80})
    result = shaping.shape(font, "AV")
    assert result.shaped is True
    assert result.advance == 1120
    assert result.diagnostics[0].startswith("features not compiled: ")


def test_shape_when_glyph_names_then_resolved_directly():
    font = make_font(LIGA)
    result = shaping.shape(font, "/f /i")
    assert names(result) == ["f_i"]
    assert names(shaping.shape(font, "/A /bogus")) == ["A"]
    assert "unknown glyph name /bogus" in shaping.shape(font, "/A /bogus").diagnostics
    assert names(shaping.shape_names(font, ["B", "A"])) == ["B", "A"]


def test_shape_when_only_unknown_glyph_names_then_empty_run_with_diagnostics():
    font = make_font()
    result = shaping.shape(font, "/bogus /nope")
    assert result.glyphs == () and result.advance == 0
    assert "unknown glyph name /bogus" in result.diagnostics
    assert "unknown glyph name /nope" in result.diagnostics


def test_shape_when_bad_arguments_then_raises():
    with pytest.raises(TypeError):
        shaping.shape(make_font(), b"A")
    with pytest.raises(ValueError):
        shaping.shape(make_font(), "A", direction="ttb")


def test_parse_features_when_mixed_tokens_then_mapping():
    assert shaping.parse_features("liga, -kern +ss01 cv01=2") == (
        {"liga": True, "kern": False, "ss01": True, "cv01": 2}, [],
    )


def test_parse_features_when_value_not_numeric_then_diagnostic_not_error():
    assert shaping.parse_features("cv01=x,-") == ({}, ["ignored feature 'cv01=x'", "ignored feature '-'"])
    result = shape_text("A", features="cv01=x")
    assert "ignored feature 'cv01=x'" in result.diagnostics


def test_shape_when_glyph_vs_class_exception_then_exception_beats_class_pair():
    font = make_font(
        kerning={("public.kern1.A", "public.kern2.V"): -80, ("A", "public.kern2.B"): -5},
        groups={"public.kern1.A": ["A", "Aacute"], "public.kern2.V": ["V"], "public.kern2.B": ["B"]},
    )
    assert shaping.shape(font, "AV").advance == 1120
    assert shaping.shape(font, "AB").advance == 1300 - 5
    assert shaping.shape(font, "\u00c1B").advance == 1300


def test_shape_when_class_vs_glyph_exception_then_exception_beats_class_pair():
    font = make_font(
        kerning={("public.kern1.A", "public.kern2.V"): -80, ("public.kern1.A", "V"): -10},
        groups={"public.kern1.A": ["A"], "public.kern2.V": ["V", "B"]},
    )
    assert shaping.shape(font, "AV").advance == 1190
    assert shaping.shape(font, "AB").advance == 1300 - 80


def test_shape_when_glyph_name_not_identifier_then_returns_with_diagnostic():
    font = make_font(kerning={("1x", "A"): -50})
    font.newGlyph("1x").width = 300
    result = shaping.shape(font, "/1x /A")
    assert names(result) == ["1x", "A"]
    assert result.advance == 900
    assert result.diagnostics == ("kerning skipped for unspellable glyph names: 1x",)


def test_shape_when_kern_generation_fails_then_returns_with_diagnostic(monkeypatch):
    font = make_font(LIGA, kerning={("A", "V"): -80})
    monkeypatch.setattr(shaping, "_kern_fea", lambda snap: "feature kern { garbage } kern;")
    result = shaping.shape(font, "fi")
    assert names(result) == ["f_i"]
    assert result.diagnostics[0].startswith("kerning not compiled: ")
    broken = make_font("feature x { bogus } x;", kerning={("A", "V"): -80})
    result = shaping.shape(broken, "AV")
    assert result.shaped is True
    assert any(d.startswith("features not compiled: ") for d in result.diagnostics)
    assert any(d.startswith("kerning not compiled: ") for d in result.diagnostics)


def test_shape_when_kern_only_in_comment_then_generated_kerning_applies():
    font = make_font("# feature kern is not here\n", kerning={("A", "V"): -80})
    assert shaping.shape(font, "AV").advance == 1120


def test_shape_when_font_defines_kern_then_skip_diagnostic():
    font = make_font("feature kern { pos A V -10; } kern;", kerning={("A", "V"): -80})
    assert "generated kerning skipped: the feature code defines kern" in shaping.shape(font, "AV").diagnostics


def test_shape_when_fonttools_missing_then_fallback(monkeypatch):
    pytest.importorskip("fontlab_fontport")
    monkeypatch.setitem(sys.modules, "fontTools.fontBuilder", None)
    assert shaping.shape(make_font(), "A").shaped is False


def test_compile_cache_when_font_unchanged_then_hit_and_changed_then_miss(monkeypatch):
    calls = []
    real = shaping._compile
    monkeypatch.setattr(shaping, "_compile", lambda snap: calls.append(1) or real(snap))
    font = make_font()
    shaping.shape(font, "A")
    shaping.shape(font, "AB", features="-kern")
    assert len(calls) == 1
    font["A"].width = 650
    assert shaping.shape(font, "A").advance == 650
    assert len(calls) == 2


def test_compile_cache_when_over_capacity_then_oldest_evicted(monkeypatch):
    monkeypatch.setattr(shaping, "CACHE_SIZE", 2)
    font = make_font()
    for width in (601, 602, 603):
        font["A"].width = width
        shaping.shape(font, "A")
    assert len(shaping._CACHE) == 2


def test_shape_when_uharfbuzz_missing_then_fontport_fallback(monkeypatch):
    pytest.importorskip("fontlab_fontport")
    monkeypatch.setitem(sys.modules, "uharfbuzz", None)
    font = make_font(kerning={("A", "V"): -80})
    result = shaping.shape(font, "AVZ")
    assert result.shaped is False
    assert result.diagnostics[0] == "unshaped: uharfbuzz not available"
    assert "Missing glyph for 'Z'" in result.diagnostics
    assert names(result) == ["A", "V", None]
    assert result.glyphs[1].x == 520
    assert names(shaping.shape(font, "/B /A")) == ["B", "A"]
    assert shaping.shape(font, "AV", kerning=False).advance == 1200


def test_shape_when_fontport_missing_in_fallback_then_names_extra(monkeypatch):
    monkeypatch.setattr(shaping, "_load_harfbuzz", lambda: None)
    monkeypatch.setitem(sys.modules, "fontlab_fontport", None)
    monkeypatch.setitem(sys.modules, "fontlab_fontport.glyphrun", None)
    with pytest.raises(ImportError, match="fontlab-fontport"):
        shaping.shape(make_font(), "A")


def test_shape_when_font_has_no_features_then_shapes_without_raising():
    class Bare:
        def __init__(self, base):
            self._base = base
            self.info = base.info
            self.kerning = base.kerning
            self.groups = base.groups

        def keys(self):
            return self._base.keys()

        def __getitem__(self, name):
            return self._base[name]

        def __contains__(self, name):
            return name in self._base

        def __iter__(self):
            return iter(self._base)

        def __len__(self):
            return len(self._base)

    result = shaping.shape(Bare(make_font()), "AB")
    assert names(result) == ["A", "B"], "a font without .features still shapes"


def test_mark_classes_when_uharfbuzz_lacks_gdef_api_then_none():
    from types import SimpleNamespace

    assert shaping._mark_classes(SimpleNamespace(), SimpleNamespace()) is None, "an old face API means no GDEF verdict"
    face = SimpleNamespace(has_layout_glyph_classes=False)
    assert shaping._mark_classes(SimpleNamespace(), face) is None, "a face without glyph classes gives no verdict"


def test_mark_classes_when_face_lacks_glyph_class_lookup_then_none():
    from types import SimpleNamespace

    hb = SimpleNamespace(OTLayoutGlyphClass=SimpleNamespace(MARK=3))
    face = SimpleNamespace(has_layout_glyph_classes=True)
    assert shaping._mark_classes(hb, face) is None, "a missing get_layout_glyph_class gives no verdict"
    face.get_layout_glyph_class = lambda gid: 3 if gid == 1 else 1
    is_mark = shaping._mark_classes(hb, face)
    assert (is_mark(1), is_mark(0)) == (True, False), "the resolved lookup classifies glyph ids"
