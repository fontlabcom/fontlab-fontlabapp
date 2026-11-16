# this_file: tests/test_kerning_scripting.py
"""Verify host-free explicit presence, native fallback and complete proof fitting."""

from types import SimpleNamespace as NS

import pytest
from fontlabapp.core import scripting


def test_explicit_pairs_preserve_zero_and_reject_unknown_native_modes():
    left = NS(id="L_A", mode="groupMode")
    right = NS(id="V", mode="glyphMode")
    package = NS(
        kerning=lambda master: NS(items=lambda: [(NS(left=left, right=right), 0)])
    )
    assert scripting.kerning_pairs(package, "Bold") == {("@L_A", "V"): 0}
    right.mode = "unsupported"
    with pytest.raises(ValueError, match="Unknown kerning side"):
        scripting.kerning_pairs(package, "Bold")


@pytest.mark.parametrize("value,expected", [(None, 0), (0, 0), (-12.5, -12.5)])
def test_effective_reads_keep_native_fallback_value(value, expected):
    calls = []
    kern = NS(get=lambda pair: (calls.append(pair), value)[1])
    assert scripting.kerning_pair_value(kern, "A", "V") == expected
    assert calls == [("A", "V")], (
        "Use native effective resolution, rather than another calculator"
    )


def test_native_effective_errors_propagate_instead_of_inventing_zero():
    def fail(pair):
        raise RuntimeError("native failure")

    with pytest.raises(RuntimeError, match="native failure"):
        scripting.kerning_pair_value(NS(get=fail), "A", "V")


def test_complete_proof_positions_preserve_kerning_and_fit_ink():
    rows = [("A", 0, 600, 0), ("V", 520, 600, -80)]
    bounds = {"A": (-200, -400, 800, 1500), "V": (-100, -200, 850, 800)}
    scale, positions = scripting.kerning_proof_geometry(
        rows, bounds, 1000, 300, 0.1, 800, -200, False
    )
    assert scale == 0.1
    assert positions[1][1] - positions[0][1] == 52, (
        "Pen displacement must include -80 kerning"
    )
    for name, x, y, _ in positions:
        a, b, c, d = bounds[name]
        assert x + a * scale >= 0 and x + c * scale <= 1000
        assert y - d * scale >= 0 and y - b * scale <= 300


@pytest.mark.parametrize(
    "width,height,scale", [(0, 20, 0.1), (20, 0, 0.1), (20, 20, 0)]
)
def test_invalid_proof_size_is_refused(width, height, scale):
    with pytest.raises(ValueError, match="positive"):
        scripting.kerning_proof_geometry(
            [("A", 0, 600, 0)],
            {"A": (0, 0, 600, 700)},
            width,
            height,
            scale,
            800,
            -200,
            False,
        )
