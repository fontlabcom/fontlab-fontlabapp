# this_file: tests/test_common_glyphs.py
"""Original CommonGlyphs reports preserve exact names and first-font strings."""

import pytest
from fontlabapp.glyphs.common.model import Font, Glyph, Production, analyze, checkpoint


def font(identity, family, *glyphs):
    return Font(identity, identity + 100, family, tuple(Glyph(*row) for row in glyphs))


def metadata(name, *, checkpoint):
    checkpoint()
    return (
        Production("uni0410", "database")
        if name == "afii10017"
        else Production(None, "unknown")
    )


def test_multifont_uses_first_font_preserves_names_alternatives_and_trailing_spaces():
    first = font(
        1,
        "First family",
        ("z", ()),
        ("afii10017", (0x410, 65)),
        ("fi", (0xFB01,)),
        ("f_i", ()),
    )
    second = font(
        2,
        "Other family",
        ("f_i", (102,)),
        ("afii10017", (66,)),
        ("fi", (99,)),
        ("z", ()),
        ("extra", ()),
    )
    result = analyze((first, second), metadata)
    assert result["glyph_names"] == ["afii10017", "f_i", "fi", "z"], (
        "Sort only the multi-font intersection"
    )
    assert result["slash_text"] == "/afii10017/f_i/fi/z", (
        "Retain reusable slash-name proof text"
    )
    assert (
        result["families"] == ["First family", "Other family"] and result["count"] == 4
    )
    assert (
        result["characters"] == "А ﬁ " and result["nice_names"] == "afii10017 f_i fi z "
    ), "Keep first-font primary strings and exact final spaces"
    assert (
        result["production_names"] == "uni0410 [unknown:f_i] [unknown:fi] [unknown:z] "
    )
    assert result["unicode_by_font"][0]["glyphs"]["afii10017"] == ["U+0410", "U+0041"]
    assert result["unicode_by_font"][1]["glyphs"]["afii10017"] == ["U+0042"]
    assert "Nice names: \nafii10017 f_i fi z \n" in result["source_text"]
    assert (
        result["charcoal"]["default"] is False and not result["charcoal"]["available"]
    )
    reordered = analyze((second, first), metadata)
    assert reordered["families"] == ["Other family", "First family"]
    assert (
        reordered["characters"] == "B f c "
        and reordered["glyph_names"] == result["glyph_names"]
    ), (
        "Changing the first carrier changes its strings/family order without changing shared names"
    )


def test_one_font_keeps_source_glyph_order_no_current_font_is_required():
    result = analyze(
        (font(9, "Single", ("z", (122,)), ("a", (97,)), ("unencoded", ())),), metadata
    )
    assert (
        result["glyph_names"] == ["z", "a", "unencoded"]
        and result["characters"] == "z a "
    )
    assert analyze((font(1, "Empty"),), metadata)["count"] == 0
    assert (
        analyze((font(1, "One", ("a", ())), font(2, "Two", ("b", ()))), metadata)[
            "count"
        ]
        == 0
    )
    with pytest.raises(ValueError, match="Insufficient"):
        analyze((), metadata)


@pytest.mark.parametrize(
    "row",
    [("", ()), ("a", (True,)), ("a", (-1,)), ("a", (0xD800,)), ("a", (0x110000,))],
)
def test_invalid_boundary_facts_fail_before_report(row):
    with pytest.raises(ValueError):
        analyze((font(1, "Family", row),), metadata)


def test_duplicates_invalid_production_cancellation_and_deadline_refuse_complete_report():
    for fonts in (
        (font(1, "Family", ("a", ()), ("a", ())),),
        (font(1, "A"), font(1, "B")),
    ):
        with pytest.raises(ValueError):
            analyze(fonts, metadata)
    with pytest.raises(ValueError):
        Production("fallback", "unknown")
    with pytest.raises(ValueError):
        Production(None, "database")
    with pytest.raises(TimeoutError):
        checkpoint(0, clock=lambda: 0)
    with pytest.raises(InterruptedError):
        checkpoint(10, clock=lambda: 0, cancelled=lambda: True)


def test_metadata_and_encoding_loops_propagate_checkpoint_and_incomplete_mapping():
    calls = []

    def check():
        calls.append(1)
        if len(calls) == 8:
            raise InterruptedError("stop during facts")

    with pytest.raises(InterruptedError):
        analyze((font(1, "Family", ("a", (65, 66, 67))),), metadata, check=check)

    def failed(name, *, checkpoint):
        raise RuntimeError("metadata unavailable")

    with pytest.raises(RuntimeError, match="metadata unavailable"):
        analyze((font(1, "Family", ("a", ())),), failed)


def test_exact_complete_source_sections_empty_families_and_known_same_name_conversion():
    result = analyze(
        (font(1, "Family", ("a", (97,))),),
        lambda name, **kw: Production(name, "database"),
    )
    assert (
        result["source_text"]
        == "Analysed fonts: Family\nNumber of common glyphs: 1\n\na \n\n\nNice names: \na \n\n\nProduction names: \na \n\n\n"
    ), "Keep print-statement line breaks and every final space verbatim"
    with pytest.raises(ValueError, match="explicit Production"):
        analyze((font(1, "Family", ("a", ())),), lambda *a, **kw: "a")
    for args in (("a", "invented"), ("", "database"), (1, "derived")):
        with pytest.raises(ValueError):
            Production(*args)
    for value in (
        Font(True, 2, "Family", ()),
        Font(1, 2, "Family", (Glyph(None, ()),)),
    ):
        with pytest.raises(ValueError):
            analyze((value,), metadata)


def test_render_serialization_checks_each_chunk_and_rejects_invalid_json():
    from fontlabapp.glyphs.common.model import render

    snapshot = analyze((font(1, "Family", ("a", (97,))),), metadata)
    calls = []

    def cancel():
        calls.append(1)
        if len(calls) >= 20:
            raise InterruptedError("cancelled during encoding")

    with pytest.raises(InterruptedError, match="during encoding"):
        render(snapshot, check=cancel)
    with pytest.raises(ValueError):
        render({"source_text": "", "invalid": float("nan")})
