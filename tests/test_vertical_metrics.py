# this_file: tests/test_vertical_metrics.py
"""Preserve the eight-metric all-font/master report, including zero versus unset."""

import pytest

from fontlabapp.metrics.vertical.model import KEYS, MasterMetrics, MetricsReport, render


def test_report_keeps_all_eight_keys_time_status_and_complete_mismatch_rows():
    a = MasterMetrics(1, "First.vfc", "Regular", (800, -200, 0, None, 0, 0, 200, 800))
    b = MasterMetrics(2, "Second.vfc", "Bold", (801, -200, 0, 0, 0, 0, 200, 800))
    report = MetricsReport((a, b), "12:34:56")
    text = render(report)
    assert text.startswith("Vertical metrics reporter @ 12:34:56\n")
    assert (
        "\t❌ typoAscender\n\t\t800 @ First.vfc/Regular\n\t\t801 @ Second.vfc/Bold\n"
        in text
    )
    assert (
        "\t❌ hheaAscender\n\t\tNone @ First.vfc/Regular\n\t\t0 @ Second.vfc/Bold\n"
        in text
    )
    assert "\t✅ typoDescender\n" in text
    assert text.endswith("Vertical metrics reported.\n")
    assert [
        line[3:] for line in text.splitlines() if line.startswith(("\t✅ ", "\t❌ "))
    ] == list(KEYS)
    assert report.fonts == 2 and len(report.rows) == 2


def test_equal_fractional_negative_huge_and_unset_values_are_not_rounded():
    row = MasterMetrics(
        9, "é.vfc", "", (2**60 + 1, -200.125, 0, None, None, None, 0, 0)
    )
    text = render(MetricsReport((row, row), "now"))
    assert text.count("✅") == 8 and "❌" not in text
    changed = MasterMetrics(
        9, "é.vfc", "Other", (2**60, -200.125, 0, None, None, None, 0, 0)
    )
    assert "❌ typoAscender" in render(MetricsReport((row, changed), "now"))


@pytest.mark.parametrize(
    "values",
    [
        (),
        (0,) * 7,
        (0,) * 7 + (float("nan"),),
        (0,) * 7 + (float("inf"),),
        (0,) * 7 + (True,),
    ],
)
def test_incomplete_or_invalid_metric_values_refuse(values):
    with pytest.raises(ValueError):
        MasterMetrics(1, "Doc", "Regular", values)


def test_no_fonts_is_a_diagnosis_not_eight_false_successes():
    with pytest.raises(ValueError, match="Open"):
        MetricsReport((), "now")
