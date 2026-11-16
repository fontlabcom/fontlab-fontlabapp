# this_file: tests/test_text_holder.py
"""Original literal search/replacement with explicit Qt UTF16 boundaries."""

import pytest
from fontlabapp.proof.text_holder.model import (
    find_first,
    index_at,
    plan_replacement,
    utf16_units,
)


def test_find_always_uses_first_case_sensitive_literal_and_qt_units():
    text = "😀x é e\u0301 中 😀x"
    assert find_first(text, "x") == (2, 3)
    assert find_first(text, "😀x") == (0, 3)
    assert find_first(text, "é") == (4, 5)
    assert find_first(text, "E") is None and find_first(text, "") is None


def test_all_codepoint_boundaries_roundtrip_unicode_without_normalization():
    text = "a😀\n👩\u200d💻e\u0301אב中\x00"
    for i in range(len(text) + 1):
        assert index_at(text, utf16_units(text[:i])) == i
    with pytest.raises(ValueError, match="boundary"):
        index_at(text, 2)


@pytest.mark.parametrize("position", [-1, 100, True, 1.5])
def test_invalid_qt_selection_never_becomes_a_python_slice(position):
    with pytest.raises((ValueError, TypeError)):
        index_at("😀a", position)


def test_replacement_selection_or_whole_matches_independent_original_intent():
    text = "😀abc abc\nאבabc"
    plan = plan_replacement(text, "abc", "X😀", 2, 5)
    assert (plan.start, plan.end, plan.text) == (2, 5, "X😀")
    full = plan_replacement(text, "abc", "", 2, 2)
    assert (full.start, full.end, full.text) == (0, utf16_units(text), "😀 \nאב")
    assert plan_replacement(text, "", "x", 0, 0) is None
    assert plan_replacement(text, "missing", "x", 0, 0) is None
    assert plan_replacement(text, "abc", "abc", 0, 0) is None
    assert plan_replacement(text, "abc", "x", 0, 2) is None
    with pytest.raises(ValueError):
        plan_replacement(text, "a", "b", 4, 2)
    with pytest.raises(ValueError):
        plan_replacement(text, "a", "b", 1, 2)


def test_literal_cocoa_origin_converts_full_logical_screen_and_decorated_height():
    from fontlabapp.proof.text_holder.model import client_sizes, window_origin

    assert window_origin(0, 0, 1080, 424) == (0, 156)
    assert window_origin(40, -200, 1200, 550) == (40, -50)
    assert window_origin(0, 0, 700, 550) == (0, -350), (
        "The source allows negative top placement; never clamp"
    )
    assert client_sizes((8, 30), None) == ((492, 370), (1192, 770), (500, 400))
    assert client_sizes((8, 30), (800, 600)) == ((492, 370), (1192, 770), (792, 570))
    with pytest.raises(ValueError):
        client_sizes((-1, 20), None)
    with pytest.raises(ValueError):
        window_origin(0, 0, 0, 400)
