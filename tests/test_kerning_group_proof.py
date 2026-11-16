# this_file: tests/test_kerning_group_proof.py
"""Independent oracle for Reza's ordered, independent kerning-group rows."""

from dataclasses import FrozenInstanceError

import pytest
from fontlabapp.kerning.group_proof.model import GlyphGroups, build


def test_both_groups_keep_font_order_identity_exclusion_and_repeated_names():
    rows = (
        GlyphGroups(5, "repeat", "L", "R"),
        GlyphGroups(2, "current", "L", "R"),
        GlyphGroups(7, "unencoded.alt", "L", None),
        GlyphGroups(9, "repeat", None, "R"),
    )
    result = build(rows, 2)
    assert result.left == ("repeat", "unencoded.alt")
    assert result.right == ("repeat", "repeat")
    assert result.rows == (
        ("", ("current",)),
        ("L: ", result.left),
        ("R: ", result.right),
        ("", ()),
    )
    assert result.has_peers
    with pytest.raises(FrozenInstanceError):
        result.current = "changed"


@pytest.mark.parametrize(
    "left,right,peers,expected",
    [
        (None, None, (), (("", ("current",)), ("", ()), ("", ()), ("", ()))),
        ("L", "R", (), (("", ("current",)), ("", ()))),
        ("", None, (), (("", ("current",)), ("", ()), ("", ()), ("", ()))),
        (
            "L",
            None,
            ("left",),
            (("", ("current",)), ("L: ", ("left",)), ("", ()), ("", ())),
        ),
        (
            None,
            "R",
            ("right",),
            (("", ("current",)), ("", ()), ("R: ", ("right",)), ("", ())),
        ),
    ],
)
def test_missing_empty_singleton_and_independent_group_rows(
    left, right, peers, expected
):
    rows = (GlyphGroups(1, "current", left, right),)
    if peers:
        rows += (GlyphGroups(2, peers[0], left, right),)
    result = build(rows, 1)
    assert result.rows == expected
    assert result.has_peers == bool(peers)


def test_missing_selected_glyph_and_empty_inventory_refuse():
    for rows in [(), (GlyphGroups(1, "a", None, None),)]:
        with pytest.raises(ValueError, match="selected glyph"):
            build(rows, 99)


def test_names_are_never_sorted_deduplicated_unicode_substituted_or_slash_parsed():
    rows = (
        GlyphGroups(1, "current", None, "R"),
        GlyphGroups(2, "/slash name", None, "R"),
        GlyphGroups(3, "z.unencoded", None, "R"),
        GlyphGroups(4, "a", None, "other"),
    )
    assert build(rows, 1).right == ("/slash name", "z.unencoded")


def test_singleton_left_group_does_not_add_a_blank_before_right_peers():
    result = build(
        (
            GlyphGroups(1, "current", "singleton", "R"),
            GlyphGroups(2, "peer", None, "R"),
        ),
        1,
    )
    assert result.rows == (("", ("current",)), ("R: ", ("peer",)), ("", ()))


def test_all_peers_are_retained_without_preview_truncation():
    rows = tuple(GlyphGroups(i, f"g{i}", "L", "R") for i in range(1000))
    result = build(rows, 500)
    expected = tuple(row.name for row in rows if row.ident != 500)
    assert result.left == result.right == expected
    assert len(result.left) == 999
