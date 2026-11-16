# this_file: tests/test_case_coverage.py
import pytest
from fontlabapp.glyphs.case_coverage.model import GlyphFact, Options, analyze


def fact(name, text=None, export=True, category="Letter", codes=()):
    return GlyphFact(
        name, tuple(codes or (() if text is None else (ord(text),))), export, category
    )


def test_original_defaults_and_clear_pair():
    assert Options() == Options(False, True, True, False)
    result = analyze([fact("A", "A"), fact("a", "a")], {"A": "A", "a": "a"})
    assert result["all_clear"] and result["proof"] == []
    assert [r["status"] for r in result["rows"]] == ["matched", "matched"]


def test_missing_and_export_mismatch_keep_order_repeated_occurrences():
    result = analyze(
        [fact("A", "A"), fact("a", "a", False), fact("B", "B")],
        {"a": "a", "A": "A", "b": "b"},
    )
    assert result["proof"] == ["A", "a", "B"]
    assert [r["status"] for r in result["rows"]] == [
        "export_mismatch",
        "matched",
        "missing",
    ]


def test_canonical_then_encoded_alias_and_ambiguity_are_explicit():
    glyphs = [fact("A", "A"), fact("alternate", "a", False), fact("other", "a")]
    result = analyze(glyphs, {"a": "a", "A": "A"})
    row = result["rows"][0]
    assert row["counterpart"] == "alternate"
    assert row["candidates"] == ["alternate", "other"]
    assert row["ambiguous"] and row["status"] == "export_mismatch"
    glyphs.append(fact("a", "x"))
    assert analyze(glyphs, {"a": "a"})["rows"][0]["counterpart"] == "a"


def test_multichar_compatibility_and_missing_expansion_never_pass_silently():
    result = analyze(
        [fact("Idotaccent", "İ"), fact("germandbls", "ß"), fact("jcaron", "ǰ")],
        {"i̇": "i_dotaccentcomb", "SS": "SS", "J̌": "J_caroncomb"},
    )
    assert [r["mapped_text"] for r in result["rows"]] == ["i̇", "SS", "J̌"]
    assert [r["preferred"] for r in result["rows"]] == [
        "i",
        "Germandbls",
        "J_caroncomb",
    ]
    assert result["proof"] == ["Idotaccent", "germandbls", "jcaron"]
    assert (
        analyze(
            [fact("germandbls", "ß"), fact("Germandbls", "ẞ")],
            {"SS": "SS", "ß": "germandbls"},
        )["rows"][0]["status"]
        == "matched"
    )


def test_alternative_encodings_and_math_ligature_unknown_rows():
    rows = [
        fact("multi", codes=(65, 66)),
        fact("math", "µ", category="Math"),
        fact("f_i", "ﬁ", category="Ligature"),
        fact("mystery"),
    ]
    result = analyze(rows, {"a": "a", "b": "b"}, Options(excludeMathSymbols=True))
    assert result["proof"] == ["multi", "multi"]
    assert [r["status"] for r in result["rows"]] == [
        "missing",
        "missing",
        "excluded_math",
        "excluded_ligature",
        "unknown_mapping",
    ]
    assert not result["all_clear"]


def test_nonexporting_source_still_checked_empty_unknown_and_uncased():
    result = analyze(
        [fact("A", "A", False), fact("one", "1"), fact("mystery")], {"a": "a"}
    )
    assert result["proof"] == ["A"]
    assert [r["status"] for r in result["rows"]] == [
        "missing",
        "uncased",
        "unknown_mapping",
    ]
    assert analyze([], {})["all_clear"]


def test_deadline_cancel_and_invalid_facts_fail_before_partial_report():
    with pytest.raises(TimeoutError):
        analyze([fact("A", "A")], {}, deadline=0, clock=lambda: 0)
    with pytest.raises(InterruptedError):
        analyze([], {}, cancelled=lambda: True)
    for args in [
        ("", (), True, "Letter"),
        ("A", (0xD800,), True, "Letter"),
        ("A", (65,), 1, "Letter"),
    ]:
        with pytest.raises(ValueError):
            GlyphFact(*args)
    with pytest.raises(ValueError, match="Duplicate"):
        analyze([fact("A"), fact("A")], {})


def test_compatibility_expansions_match_encoded_alternate_names_and_export_policy():
    glyphs = [
        fact("Idotaccent", "İ"),
        fact("dotlessAlias", "i", False),
        fact("germandbls", "ß"),
        fact("capitalAlias", "ẞ"),
    ]
    result = analyze(
        glyphs, {"i̇": "i_dotaccentcomb", "SS": "SS", "I": "I", "ß": "germandbls"}
    )
    assert result["rows"][0]["counterpart"] == "dotlessAlias"
    assert result["rows"][0]["status"] == "export_mismatch"
    assert result["rows"][2]["counterpart"] == "capitalAlias"
    assert result["rows"][2]["status"] == "matched"


@pytest.mark.parametrize(
    "codes,status", [((), "unknown_mapping"), ((0x10FFFF,), "uncased")]
)
def test_unknown_metadata_when_unencoded_or_uncased_then_never_all_clear(codes, status):
    result = analyze([GlyphFact("unassigned", codes, True, None)], {})
    assert result["rows"][0]["status"] == status, (
        "Keep the complete unknown diagnostic row"
    )
    assert result["unresolved"] is True, "Unknown metadata must remain unresolved"
    assert result["all_clear"] is False, (
        "Unknown rows cannot display no-issues feedback"
    )
    assert result["proof"] == [], (
        "Unknown uncased facts do not invent case proof glyphs"
    )
    if codes:
        assert result["rows"][0]["metadata_unknown"] is True


@pytest.mark.parametrize("exclude_math", [False, True])
@pytest.mark.parametrize(
    "glyph",
    [
        GlyphFact("period", (46,), True, "Punctuation"),
        GlyphFact("product", (0x220F,), True, "Math"),
        GlyphFact("fi", (0xFB01,), True, "Ligature"),
    ],
)
def test_known_uncased_or_excluded_metadata_when_complete_then_remains_clear(
    glyph, exclude_math
):
    result = analyze([glyph], {}, Options(excludeMathSymbols=exclude_math))
    assert result["all_clear"] and not result["unresolved"], (
        "Known uncased/excluded metadata stays clear"
    )
    assert result["proof"] == [] and len(result["rows"]) == 1, (
        "Preserve diagnostic rows without proof"
    )
