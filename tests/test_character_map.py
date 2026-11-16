# this_file: tests/test_character_map.py
"""Complete original map equations and immutable source coverage."""

import unicodedata

import pytest
from fontlabapp.glyphs.character_map.model import (
    Glyph,
    Snapshot,
    codepoint_at,
    coverage,
    proof,
    selectable,
)


def test_all_bmp_cells_preserve_both_original_profiles():
    for part, cell in ((2, 36), (3, 24)):
        for code in range(65536):
            assert (
                codepoint_at(part, (code % 16) * cell, (code // 16) * cell, cell)
                == code
            )
            expected = unicodedata.category(chr(code)) not in {"Cn", "Cs"}
            assert selectable(part, code, True) == expected
    assert not selectable(2, 65, False) and selectable(3, 65, False)


@pytest.mark.parametrize("point", [(-1, 0), (0, -1), (576, 0), (0, 147456)])
def test_grid_refuses_outside_cells(point):
    assert codepoint_at(2, *point, 36) is None


def test_complete_cmap_and_proof_keep_order_duplicates_unencoded_and_nonbmp():
    facts = Snapshot(
        (1, 2, "Regular"),
        (Glyph(3, "A", (65, 0x1F600)), Glyph(4, "A.alt", (65,)), Glyph(5, "space", ())),
    )
    assert coverage(facts) == {65: ("A", "A.alt"), 0x1F600: ("A",)}
    assert proof(facts, "A😀BA") == (
        (0, 65, ("A", "A.alt")),
        (1, 0x1F600, ("A",)),
        (2, 66, ()),
        (3, 65, ("A", "A.alt")),
    )
