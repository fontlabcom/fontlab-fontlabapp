# this_file: tests/test_duplicate_unicodes.py
"""Source-derived ordered duplicate/keeper and exact removal contracts."""

import pytest
from fontlabapp.glyphs.unicode.duplicates.model import Glyph, Snapshot, groups, plan


def glyph(name, codes, identity=1):
    return Glyph(identity, identity + 100, name, tuple(codes), (), ())


def test_primary_keeper_and_numeric_groups_keep_font_order():
    rows = (
        glyph("secondary", [66, 65], 1),
        glyph("primary", [65, 66], 2),
        glyph("other", [65], 3),
    )
    found = groups(rows)
    assert [(g.code, g.keeper, g.names) for g in found] == [
        (65, "primary", ("secondary", "primary", "other")),
        (66, "secondary", ("secondary", "primary")),
    ]


def test_secondary_only_prefers_first_font_owner_and_empty_is_empty():
    assert groups(()) == ()
    assert groups((glyph("one", []),)) == ()
    assert (
        groups((glyph("first", [90, 65], 1), glyph("next", [91, 65], 2)))[0].keeper
        == "first"
    )


def test_repeated_associations_remain_literal_source_members():
    found = groups((glyph("A", [65, 65]),))
    assert found[0].names == ("A", "A") and found[0].keeper == "A"


def test_exact_plan_keeps_unrelated_order_and_ticked_keeper_is_allowed():
    rows = (glyph("A", [65, 66, 67], 1), glyph("B", [66, 65], 2))
    facts = Snapshot((1,), rows, ())
    assert [
        (g.name, codes) for g, codes in plan(facts, [("B", 65), ("A", 66), ("B", 65)])
    ] == [("B", (66,)), ("A", (65, 67))]
    assert plan(facts, []) == ()
    assert plan(facts, [("A", 65), ("B", 65)])[0][1] == (66, 67)


def test_remaining_duplicate_assignments_cannot_be_silently_normalized():
    facts = Snapshot((1,), (glyph("A", [65, 66, 66], 1), glyph("B", [65], 2)), ())
    with pytest.raises(ValueError, match="collapse"):
        plan(facts, [("A", 65)])
    assert plan(Snapshot((1,), (glyph("A", [65, 65], 1),), ()), [("A", 65)])[0][1] == ()


@pytest.mark.parametrize(
    "rows",
    [
        (glyph("A", [0x110000]),),
        (glyph("A", [True]),),
        (glyph("A", [65]), glyph("A", [66], 2)),
        (glyph("A", [65]), glyph("B", [66])),
    ],
)
def test_ambiguous_or_invalid_glyph_records_are_refused(rows):
    with pytest.raises(ValueError):
        groups(rows)


def test_unknown_nonduplicate_removal_is_refused():
    facts = Snapshot((1,), (glyph("A", [65]),), ())
    with pytest.raises(ValueError, match="preview"):
        plan(facts, [("A", 65)])


from itertools import product


@pytest.mark.parametrize(
    "assignments",
    product(
        ((), (65,), (66,), (65, 66), (66, 65), (65, 65), (0,), (0x1F600,)), repeat=3
    ),
)
def test_complete_original_group_oracle_512_ordered_fonts(assignments):
    rows = tuple(
        glyph(chr(65 + i), codes, i + 1) for i, codes in enumerate(assignments)
    )
    codes = sorted({code for row in assignments for code in row})
    expected = []
    for code in codes:
        positions = [
            i for i, row in enumerate(assignments) for item in row if item == code
        ]
        if len(positions) > 1:
            keeper = min(positions, key=lambda i: (assignments[i][0] != code, i))
            expected.append(
                (code, chr(65 + keeper), tuple(chr(65 + i) for i in positions))
            )
    assert [(g.code, g.keeper, g.names) for g in groups(rows)] == expected
