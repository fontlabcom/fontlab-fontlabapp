# this_file: tests/test_smallcap_consistency.py
"""Full detached smallcap report, including the legacy kerning workflow."""

import sys
import subprocess

import pytest

from fontlabapp.glyphs.smallcaps.model import GlyphFact, analyze, legacy_cap_name


def glyph(name, text=None, case="unknown", export=True, left=(), right=()):
    return GlyphFact(name, export, case, text, left, right)


def test_modern_allowed_counterparts_when_present_then_not_missing():
    facts = [
        glyph("a", "a", "lower"),
        glyph("A", "A", "upper"),
        glyph("a.smcp", "a", "smallcap"),
        glyph("A.c2sc", "A", "smallcap"),
    ]
    report = analyze(facts)
    assert report["counts"] == {"smallcap": 2, "lower": 1, "upper": 1}, (
        'Expected report["counts"] == {"smallcap": 2, "lower": 1, "upper": 1}'
    )
    assert report["missing_lowercase_smallcaps"] == [], (
        'Expected report["missing_lowercase_smallcaps"] == []'
    )
    assert report["missing_uppercase_smallcaps"] == [], (
        'Expected report["missing_uppercase_smallcaps"] == []'
    )
    assert report["orphan_smallcaps"] == [], 'Expected report["orphan_smallcaps"] == []'


def test_export_and_order_when_mixed_then_excludes_nonexporting_counterparts():
    report = analyze(
        [
            glyph("b", "b", "lower"),
            glyph("a", "a", "lower"),
            glyph("b.sc", "b", "smallcap", False),
        ]
    )
    assert report["missing_lowercase_smallcaps"] == ["b", "a"], (
        'Expected report["missing_lowercase_smallcaps"] == ["b", "a"]'
    )
    assert report["excluded_nonexporting"] == ["b.sc"], (
        'Expected report["excluded_nonexporting"] == ["b.sc"]'
    )


def test_legacy_lowercase_when_smcp_only_then_modern_passes_and_legacy_warns():
    report = analyze(
        [
            glyph("b", "b", "lower"),
            glyph("a", "a", "lower"),
            glyph("b.smcp", "b", "smallcap"),
            glyph("a.smcp", "a", "smallcap"),
            glyph("b.sc", "b", "smallcap", False),
            glyph("c", "c", "lower"),
            glyph("c.sc", "c", "smallcap"),
            glyph("d", "d", "lower", False),
        ]
    )
    assert report["missing_lowercase_smallcaps"] == [], (
        "Modern lowercase coverage accepts .smcp"
    )
    assert report["legacy_lowercase_without_smallcaps"] == ["b", "a"], (
        "Legacy .sc-only warnings retain exporting lowercase font order"
    )


def test_orphans_when_suffix_order_ligature_alternate_unicode_then_preserved():
    report = analyze(
        [
            glyph("custom.alt", "SS", "upper"),
            glyph("f_i.alt", "fi", "lower"),
            glyph("germandbls.sc.alt.c2sc", "ß", "smallcap"),
            glyph("f_i.smcp.alt", "fi", "smallcap"),
            glyph("mystery.sc.alt", None, "smallcap"),
        ]
    )
    assert report["orphan_smallcaps"] == ["mystery.sc.alt"], (
        'Expected report["orphan_smallcaps"] == ["mystery.sc.alt"]'
    )
    assert report["unknown_mapping"] == ["mystery.sc.alt"], (
        'Expected report["unknown_mapping"] == ["mystery.sc.alt"]'
    )


def test_legacy_when_groups_absent_mismatched_or_ambiguous_then_report_each_side():
    report = analyze(
        [
            glyph("A", "A", "upper", left=("A",), right=()),
            glyph("a", "a", "lower"),
            glyph("a.sc", "a", "smallcap", left=("a.sc",), right=("v.sc",)),
            glyph("b.sc", "b", "smallcap"),
            glyph("C", "C", "upper", left=("C", "C.alt")),
            glyph("c.sc", "c", "smallcap", left=("c.sc",)),
        ]
    )
    assert report["missing_smallcap_capitals"] == ["b.sc"], (
        'Expected report["missing_smallcap_capitals"] == ["b.sc"]'
    )
    assert report["missing_smallcap_lowercase"] == ["b.sc", "c.sc"], (
        'Expected report["missing_smallcap_lowercase"] == ["b.sc", "c.sc"]'
    )
    assert report["legacy_capitals_without_smallcaps"] == [], (
        'Expected report["legacy_capitals_without_smallcaps"] == []'
    )
    assert report["kerning_mismatches"] == [
        {
            "glyph": "a.sc",
            "capital": "A",
            "side": "right",
            "smallcap": ["v.sc"],
            "capital_groups": [],
        }
    ], (
        'Expected report["kerning_mismatches"] == [{"glyph": "a.sc", "capital": "A", "side": "right", "smallcap": ["v.sc"], "capital_groups": []}]'
    )
    assert report["unknown_groups"] == [
        {"glyph": "c.sc", "capital": "C", "side": "left"}
    ], (
        'Expected report["unknown_groups"] == [{"glyph": "c.sc", "capital": "C", "side": "left"}]'
    )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("aeacute.sc.alt", "AEacute.alt"),
        ("oe.sc", "OE"),
        ("f_i.sc.alt", "F_I.alt"),
        ("--", "--"),
        ("", ""),
    ],
)
def test_legacy_cap_name_when_meaningful_names_then_preserve_suffixes(name, expected):
    assert legacy_cap_name(name) == expected, (
        "Expected legacy_cap_name(name) == expected"
    )


def test_unknown_case_and_empty_when_analyzed_then_disclosed_without_native_imports():
    report = analyze([glyph("opaque")])
    assert report["unclassified"] == ["opaque"], (
        'Expected report["unclassified"] == ["opaque"]'
    )
    assert analyze([])["counts"] == {"smallcap": 0, "lower": 0, "upper": 0}, (
        'Expected analyze([])["counts"] == {"smallcap": 0, "lower": 0, "upper": 0}'
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import fontlabapp.glyphs.smallcaps.model; assert 'fontlab' not in sys.modules",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_deadline_when_expired_then_no_partial_report():
    with pytest.raises(TimeoutError, match="complete"):
        analyze([glyph("a")], deadline=0, clock=lambda: 1)


def test_boundary_when_invalid_then_fail_loud():
    with pytest.raises(ValueError):
        analyze([glyph("a"), glyph("a")])
    with pytest.raises(ValueError):
        GlyphFact("", True, "unknown")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"export": None},
        {"case": "other"},
        {"text": ""},
        {"left": ["A"]},
        {"right": ("",)},
    ],
)
def test_boundary_when_metadata_invalid_then_refuses(kwargs):
    values = {"name": "a", "export": True, "case": "lower", **kwargs}
    with pytest.raises(ValueError):
        GlyphFact(**values)


def test_groups_when_unavailable_then_disclose_unknown_instead_of_missing():
    report = analyze(
        [glyph("A", "A", "upper", left=None), glyph("a.sc", "a", "smallcap")]
    )
    assert report["unknown_groups"] == [
        {"glyph": "a.sc", "capital": "A", "side": "left"}
    ], "Unavailable groups are not empty groups"
    assert report["kerning_mismatches"] == [], "Known absent right groups match"


def test_large_font_when_deadline_expires_midscan_then_never_return_partial():
    ticks = iter(range(10000))
    with pytest.raises(TimeoutError, match="complete"):
        analyze(
            (glyph(f"g{i}") for i in range(10000)),
            deadline=100,
            clock=lambda: next(ticks),
        )
