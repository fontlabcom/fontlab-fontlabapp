# this_file: tests/test_feature_code.py
"""Independent host-free tests of the calculations shared by feature scripts."""

import pytest
from fontlabapp.features.code import feature_text, safe_name, suffix_pairs


def test_pairs_accept_iterables_deduplicate_and_sort_by_alternate_name():
    names = iter(
        ["a", "a.sc", "a-cy", "a-cy.sc", "a.sc", "orphan.sc", "bad name", "bad name.sc"]
    )
    assert suffix_pairs(names, ".sc") == [("a-cy", "a-cy.sc"), ("a", "a.sc")]
    assert suffix_pairs(["a", "a.sc"], "") == []
    assert suffix_pairs([], "sc") == []


@pytest.mark.parametrize(
    "name,expected",
    [
        (".notdef", True),
        ("a.alt-1", True),
        ("", False),
        ("9name", False),
        ("a;", False),
        ("a b", False),
        ("ą", False),
    ],
)
def test_safe_name_is_conservative_ascii(name, expected):
    assert safe_name(name) is expected


def test_feature_text_preserves_pair_order_and_accepts_generator():
    assert (
        feature_text("ss01", iter([("a-cy", "a-cy.sc"), ("a", "a.sc")]))
        == "feature ss01 {\n    sub a-cy by a-cy.sc;\n    sub a by a.sc;\n} ss01;"
    )
    assert feature_text("smcp", []) == "feature smcp {\n\n} smcp;"


@pytest.mark.parametrize(
    "tag,pairs",
    [
        ("bad", []),
        ("ąalt", []),
        ("smcp", [("a", "a.sc"), ("a", "a.alt")]),
        ("smcp", [("a;", "a.sc")]),
    ],
)
def test_feature_text_rejects_invalid_tags_names_and_duplicate_sources(tag, pairs):
    with pytest.raises(ValueError):
        feature_text(tag, pairs)
