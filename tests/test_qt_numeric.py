# this_file: tests/test_qt_numeric.py
"""Exact generic integer Qt mechanics, preserving failure and mutation timing."""

import math

import fontlabapp.qt.numeric as api
import pytest


def test_original_constant_and_arithmetic_association():
    assert api.STEPS == 1_000_000
    for value in (-1e100, -1, -0.0, 1e-20, 1.25, 1e100):
        assert api.position(value, -2.75, 9.125, 371) == (value + 2.75) * 371 / 9.125
        assert api.value_at(-2.75, value, 9.125, 371) == -2.75 + value * 9.125 / 371


def test_setter_is_unblocked_and_rounds_before_native_entry():
    seen = []
    api.set_position(seen.append, 2.5)
    api.set_position(seen.append, 3.5)
    api.set_step_range(lambda *args: seen.append(args), 27)
    assert seen == [2, 4, (0, 27)]


@pytest.mark.parametrize(
    "position,error", [(math.nan, ValueError), (math.inf, OverflowError)]
)
def test_nonfinite_conversion_fails_before_native_setter(position, error):
    with pytest.raises(error):
        api.set_position(lambda x: pytest.fail("native mutation"), position)


def test_degenerate_inputs_and_setter_exceptions_are_not_normalized():
    with pytest.raises(ZeroDivisionError):
        api.position(1, 0, 0, 100)
    with pytest.raises(ZeroDivisionError):
        api.value_at(1, 0, 3, 0)
    seen = []

    def mutate_then_fail(value):
        seen.append(value)
        raise RuntimeError("after mutation")

    with pytest.raises(RuntimeError, match="after mutation"):
        api.set_position(mutate_then_fail, 5.5)
    assert seen == [6]
    with pytest.raises(RuntimeError):
        api.set_step_range(lambda *a: mutate_then_fail(a), 100)
    assert seen[-1] == (0, 100)
