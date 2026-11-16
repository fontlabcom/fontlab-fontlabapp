# this_file: tests/test_case_coverage_targets.py
from types import SimpleNamespace as NS
import pytest
from fontlabapp.glyphs.case_coverage.targets import Target, TargetChoiceRequired, choose
from fontlabapp.glyphs.case_coverage.capture import FontReport


def test_active_then_unique_then_explicit_target_and_fresh_modes():
    font = FontReport(1, 10, "Font", "Regular", dict(proof=["A", "A"]))
    a = Target(1, 10, 100, "Font — view 10 / block 100")
    b = Target(1, 11, 101, "Font — view 11 / block 101")
    assert choose((font,), (a, b), 100, True, {}) == {1: a}
    assert choose((font,), (a,), None, True, {}) == {1: a}
    assert choose((font,), (), None, True, {}) == {1: None}
    assert choose((font,), (a, b), None, False, {}) == {1: None}
    assert choose((font,), (a, b), None, True, {1: (11, 101)}) == {1: b}
    with pytest.raises(TargetChoiceRequired) as caught:
        choose((font,), (a, b), None, True, {})
    assert caught.value.targets == {1: (a, b)}
    with pytest.raises(ValueError, match="changed"):
        choose((font,), (a, b), None, True, {1: (11, 999)})
    clear = FontReport(2, 20, "Clear", "Bold", dict(proof=[]))
    assert choose((clear,), (a,), None, True, {}) == {}
