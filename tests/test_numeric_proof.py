# this_file: tests/test_numeric_proof.py
"""Advance/scale/proof-cost calculations preserve all occurrences and exact units."""

from types import SimpleNamespace as NS
import math
import pytest
from fontlabapp.proof.numeric.model import Facts, calculate


def facts():
    return Facts(
        1000,
        (("A", "Regular", 500.5), ("A", "Bold", 600), ("B", "Regular", -20)),
        (("A", 0), ("B", None)),
    )


def test_every_occurrence_and_distinct_glyph_quote():
    result = calculate(facts(), 2, (1, 100, 99, 0.5, 50, 99.99))
    assert result["advances_units"] == (
        ("A", "Regular", 501.5, 250.5),
        ("A", "Bold", 601, 300.25),
        ("B", "Regular", -19, -9.75),
    )
    assert result["proof_widths_pt"][0] == pytest.approx(501.5 * 12 / 1000)
    assert result["integer_quote_usd"] == 198 and result["decimal_quote_usd"] == 199.98
    assert len(result["advances_units"]) == 3


def test_special_zero_semantics_only_part3():
    a = calculate(facts(), 2, (0, 0, 25, 0, 0, 12.34))
    b = calculate(facts(), 3, (0, 0, 99, 0, 0, 99.99))
    assert a["proof_widths_pt"] == (0, 0, 0)
    assert all(row[2] == row[3] for row in b["advances_units"])
    assert sum(abs(w) for w in b["proof_widths_pt"]) == pytest.approx(500)
    assert (
        calculate(Facts(1000, (("space", "R", 0),), ()), 3, (0, 0, 0, 0, 0, 0))[
            "effective_zoom_percent"
        ]
        == 100
    )


@pytest.mark.parametrize("upm", [0, -1, math.nan, math.inf, True])
def test_invalid_upm_is_not_a_font_fact(upm):
    with pytest.raises((ValueError, TypeError)):
        Facts(upm, (), ())


@pytest.mark.parametrize(
    "rows,revisions",
    [
        ((("A", "R", math.nan),), ()),
        ((("", "R", 1),), ()),
        ((), (("A", True),)),
        ((), (("A", 1), ("A", 2))),
    ],
)
def test_invalid_captured_rows_are_refused(rows, revisions):
    with pytest.raises((ValueError, TypeError)):
        Facts(1000, rows, revisions)


@pytest.mark.parametrize(
    "part,values",
    [
        (1, (0, 100, 99, 0, 100, 99)),
        (3, (0, 100, 99, 21, 100, 99)),
        (3, (0, 100, 99, 0, -1, 99)),
        (2, (0, 100, 99, 1001, 100, 99)),
        (2, (0, 100, 99, 0, 100, math.inf)),
        (2, (0,)),
        (2, (0.1, 100, 99, 0, 100, 99)),
    ],
)
def test_invalid_settings_are_refused_before_arithmetic(part, values):
    with pytest.raises((ValueError, TypeError)):
        calculate(facts(), part, values)
