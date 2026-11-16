# this_file: tests/test_kerning_symmetry.py
"""Independent finite arithmetic and sequential original workflow oracle."""

from fractions import Fraction
from random import Random

import fontlabapp.kerning.symmetry.model as model
import pytest
from fontlabapp.kerning.batch import KerningSnapshot

NAMES = tuple("g" + str(i) for i in range(28))
GROUPS = {"left": ((), "KernLeft"), "right": ((), "KernRight")}


def nearest_five(value):
    quotient = Fraction(value) / 5
    low = quotient.numerator // quotient.denominator
    tail = quotient - low
    return 5 * (low + (tail > Fraction(1, 2) or (tail == Fraction(1, 2) and low % 2)))


def expected_value(a, b):
    if a is None or b is None:
        return b if a is None else a
    chosen = min(a, b) if abs(abs(a) - abs(b)) <= 10 else Fraction(a + b, 2)
    return nearest_five(chosen)


def original_oracle(names, groups, pairs):
    def key(name, side):
        options = [
            (0 if mode == side else 1, i, group)
            for i, (group, (members, mode)) in enumerate(groups.items())
            if name in members and mode in (side, "KernBothSide")
        ]
        return "@" + min(options)[2] if options else name

    final = dict(pairs)
    changes = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            forward = key(a, "KernLeft"), key(b, "KernRight")
            reverse = key(b, "KernLeft"), key(a, "KernRight")
            before = final.get(forward), final.get(reverse)
            if before[0] == before[1]:
                continue
            value = expected_value(*before)
            changes.append(((a, b), forward, reverse, before, value))
            for pair in (forward, reverse):
                if value == 0:
                    final.pop(pair, None)
                else:
                    final[pair] = value
    return final, changes


def snapshot(pairs, groups=None, masters=("Light",)):
    return KerningSnapshot(
        7,
        masters,
        {m: dict(pairs) for m in masters},
        {m: dict(groups or GROUPS) for m in masters},
    )


def test_complete_source_constants_and_pair_denominator():
    assert model.TOKENS == (
        "/a.sc",
        "/v.sc",
        "/w.sc",
        "/y.sc",
        "/t.sc",
        "/x.sc",
        "/o.sc",
        "A",
        "V",
        "W",
        "Y",
        "U",
        "X",
        "8",
        "0",
        "T",
        "O",
        "o",
        "v",
        "w",
        "x",
        ":",
        "!",
        "*",
        "|",
        "`",
        ".",
        "-",
    )
    result = model.plan(snapshot({}), NAMES)
    assert result.masters[0].comparisons == 378
    assert not result.edits["Light"] and not result.masters[0].mismatches


def test_arithmetic_exhaustive_signed_absence_ties_against_fraction_oracle():
    for a in (None, *range(-80, 81)):
        for b in (None, *range(-80, 81)):
            assert model.symmetric_value(a, b) == expected_value(a, b), (a, b)
    assert model.symmetric_value(None, 2.5) == 2.5, (
        "Present one-sided values are never rounded"
    )
    assert model.symmetric_value(2.5, 2.5) == 0
    assert model.symmetric_value(-7.5, -7.5) == -10


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), True, "2"])
def test_invalid_numeric_domain_refused(bad):
    with pytest.raises(ValueError, match="finite"):
        model.symmetric_value(bad, 5)


def test_zero_set_deletes_both_keys_but_equal_zeros_remain():
    source = {
        (NAMES[0], NAMES[1]): 0,
        (NAMES[2], NAMES[3]): 0,
        (NAMES[3], NAMES[2]): 0,
        (NAMES[4], NAMES[5]): 1,
        (NAMES[5], NAMES[4]): 2,
    }
    result = model.plan(snapshot(source), NAMES)
    assert result.edits["Light"] == {
        (NAMES[0], NAMES[1]): None,
        (NAMES[4], NAMES[5]): None,
        (NAMES[5], NAMES[4]): None,
    }
    assert [x.value for x in result.masters[0].mismatches] == [0, 0]
    assert [x.warning for x in result.masters[0].mismatches] == [True, False]


def test_side_specific_priority_first_native_order_and_ambiguity():
    groups = {
        "both": ((NAMES[0], NAMES[1]), "KernBothSide"),
        "zFirst": ((NAMES[0],), "KernLeft"),
        "aSecond": ((NAMES[0],), "KernLeft"),
        "right": ((NAMES[1],), "KernRight"),
    }
    pairs = {("@zFirst", "@right"): -20}
    result = model.plan(snapshot(pairs, groups), NAMES)
    row = result.masters[0].mismatches[0]
    assert row.forward == ("@zFirst", "@right") and row.reverse == ("@both", "@both")
    assert result.masters[0].ambiguities == (
        (NAMES[0], "KernLeft", ("zFirst", "aSecond")),
    )


def test_sequential_aliases_match_independent_oracle_every_diagnostic_and_net_delta():
    random = Random(9182)
    groups = {
        "both": (NAMES[:8], "KernBothSide"),
        "left": (NAMES[8:13], "KernLeft"),
        "right": (NAMES[13:18], "KernRight"),
        "second": (NAMES[9:15], "KernLeft"),
    }
    candidates = ("@both", "@left", "@right", "@second", *NAMES)
    for _ in range(40):
        pairs = {
            (random.choice(candidates), random.choice(candidates)): random.randrange(
                -100, 101
            )
            for _ in range(120)
        }
        expected, events = original_oracle(NAMES, groups, pairs)
        result = model.plan(snapshot(pairs, groups), NAMES)
        actual = dict(pairs)
        for pair, value in result.edits["Light"].items():
            if value is None:
                actual.pop(pair, None)
            else:
                actual[pair] = value
        assert actual == expected
        assert [
            (r.glyphs, r.forward, r.reverse, r.before, r.value)
            for r in result.masters[0].mismatches
        ] == events
        assert pairs == result.before.pairs["Light"], (
            "Planning must not mutate captured maps"
        )


def test_skip_is_case_sensitive_substring_and_not_final_master_only():
    facts = snapshot(
        {(NAMES[0], NAMES[1]): -17},
        masters=("Light", "Ctr", "WideCtrHeavy", "ctr", "Bold"),
    )
    facts.pairs["Bold"] = {}
    result = model.plan(facts, NAMES)
    assert result.skipped == ("Ctr", "WideCtrHeavy")
    assert [m.name for m in result.masters] == ["Light", "ctr", "Bold"]
    assert result.edits["Light"] and not result.edits["Bold"]


def test_duplicate_unicode_targets_are_not_deduplicated():
    names = (NAMES[0], NAMES[0], *NAMES[2:])
    result = model.plan(snapshot({}), names)
    assert result.masters[0].comparisons == 378


@pytest.mark.parametrize(
    "groups", [{}, {"one": (("g0",), "KernLeft")}, {"one": (("g0",), "KernBothSide")}]
)
def test_original_missing_required_class_categories_is_explicit_refusal(groups):
    facts = snapshot({})
    facts.groups["Light"] = groups
    with pytest.raises(ValueError, match="KernLeft|KernRight"):
        model.plan(facts, NAMES)


def test_full_target_domain_and_cooperative_cancel():
    with pytest.raises(ValueError, match="28"):
        model.plan(snapshot({}), NAMES[:2])

    def stop():
        raise TimeoutError("deadline")

    with pytest.raises(TimeoutError):
        model.plan(snapshot({}), NAMES, check=stop)
