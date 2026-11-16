# this_file: tests/test_instance_style_names.py
"""Detached source contracts; no Glyphs/reference body or native code executes."""

import pytest

from fontlabapp.fonts.style_names import (
    Link,
    prepare_names,
    propose_ps_name,
    shorten_style,
    split_style_words,
    style_link,
)


@pytest.mark.parametrize(
    "style,expected",
    [
        ("", "Rg"),
        ("Regular", "Rg"),
        ("SemiCondensed ExtraBold Italic", "SmCnXBdIt"),
        ("UltraCompressed Hairline Oblique", "UltCmHairObl"),
        ("Thin Book Heavy Medium", "ThBkHvMd"),
        ("Light Black Demi Super", "LtBlkDmSup"),
        ("Compact Narrow Extended Expanded Wide", "CpNrExExpWd"),
        ("Display Text Caption Poster Variable Slanted", "DsTxCaPoVFSl"),
        ("regular", "regular"),
        ("123 Bold", "123Bd"),
        ("!!!", "!!!"),
        ("Müller", "Mller"),
        ("Bold-Italic", "BdIt"),
        ("VF", "VF"),
    ],
)
def test_original_case_sensitive_abbreviations_and_tokenization(style, expected):
    assert shorten_style(style) == expected, (
        f"Source abbreviation changed for {style!r}"
    )


def test_proposal_accepts_already_resolved_family_and_removes_only_ascii_spaces():
    assert split_style_words("SemiCondensed Bold 12") == (
        "Semi",
        "Condensed",
        "Bold",
        "12",
    )
    assert propose_ps_name("Acme", "Condensed Bold") == "Acme-CnBd"
    assert propose_ps_name("Acme Family", "") == "AcmeFamily-Rg"
    assert propose_ps_name("Acme\tFamily", "Italic") == "Acme\tFamily-It"


def test_original_warning_order_duplicates_whitespace_and_length_are_preserved():
    edits = prepare_names((" Acme-Bd ", "Acme-Bd", "", "", "A-" + "x" * 28, None))
    assert edits.names == ("Acme-Bd", "Acme-Bd", "", "", "A-" + "x" * 28, "None")
    assert edits.problems == (
        "duplicate: Acme-Bd",
        "'' is not a valid PS name",
        "'' is not a valid PS name",
        "duplicate: ",
        "A-" + "x" * 28 + " is 30 chars (>29)",
        "'None' is not a valid PS name",
    )
    assert prepare_names(()).names == () and prepare_names(()).problems == ()
    assert prepare_names(("Acme-Rg", "A-" + "x" * 27)).problems == ()


@pytest.mark.parametrize(
    "style,available,expected",
    [
        ("Bold", {"Regular"}, Link("Regular", True, False)),
        ("Italic", {"Regular"}, Link("Regular", False, True)),
        ("Bold Italic", {"Regular", "Bold"}, Link("Regular", True, True)),
        ("Bold Italic", {"Bold"}, Link("Bold", False, True)),
        ("Condensed Bold Oblique", {"Condensed"}, Link("Condensed", True, True)),
        (
            "Condensed Bold Italic",
            {"Condensed Bold"},
            Link("Condensed Bold", False, True),
        ),
        ("ExtraBold", {"Regular"}, None),
        ("SemiBold", {"Regular"}, None),
        ("SemiBold Italic", {"SemiBold"}, Link("SemiBold", False, True)),
        ("Regular", {"Regular"}, None),
        ("", {"Regular"}, None),
        ("bold italic", {"Regular"}, None),
        ("Bold", set(), None),
        ("Italic", {"Italic"}, None),
        ("Condensed Bold", {"Regular"}, None),
    ],
)
def test_original_whole_word_link_rules_and_bold_only_fallback(
    style, available, expected
):
    assert style_link(style, available) == expected
