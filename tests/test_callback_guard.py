# this_file: tests/test_callback_guard.py
"""Exercise owned callback suppression independently of Qt or FontLab."""

from types import SimpleNamespace

import pytest
from fontlabapp.core.signals.callbacks import quiet_callbacks


@pytest.mark.parametrize("initial", [False, True])
@pytest.mark.parametrize("raises", [False, True])
def test_quiet_callbacks_when_nested_then_outer_state_survives(initial, raises):
    owner = SimpleNamespace(_quiet=initial)
    error = RuntimeError("inner failure")
    with quiet_callbacks(owner):
        assert owner._quiet is True, "outer scope must suppress owned callbacks"
        try:
            with quiet_callbacks(owner):
                assert owner._quiet is True, "inner scope must remain suppressed"
                if raises:
                    raise error
        except RuntimeError as caught:
            assert caught is error, "the original error must propagate unchanged"
        assert owner._quiet is True, (
            "leaving the inner scope must not release the outer"
        )
    assert owner._quiet is initial, "restore the exact prior suppression state"


@pytest.mark.parametrize("initial", [False, True])
@pytest.mark.parametrize(
    "error", [RuntimeError("failure"), KeyboardInterrupt(), SystemExit(7)]
)
def test_quiet_callbacks_when_body_fails_then_restore_and_propagate(initial, error):
    owner = SimpleNamespace(_quiet=initial)
    with pytest.raises(type(error)) as caught, quiet_callbacks(owner):
        raise error
    assert caught.value is error, "do not replace the body exception"
    assert owner._quiet is initial, (
        "restore state for all exits, including cancellation"
    )


def test_quiet_callbacks_when_two_owners_then_each_state_is_independent():
    first, second = SimpleNamespace(_quiet=False), SimpleNamespace(_quiet=False)
    with quiet_callbacks(first):
        assert not second._quiet, "only suppress the supplied owner"
        with quiet_callbacks(second):
            assert first._quiet and second._quiet
        assert first._quiet and not second._quiet
    assert not first._quiet and not second._quiet


def test_quiet_callbacks_when_reused_then_each_entry_gets_current_state():
    owner = SimpleNamespace(_quiet=False)
    for previous in (False, True, False):
        owner._quiet = previous
        with quiet_callbacks(owner):
            assert owner._quiet
        assert owner._quiet is previous


def test_quiet_callbacks_when_missing_flag_then_refuse_before_body():
    with pytest.raises(AttributeError), quiet_callbacks(object()):
        pytest.fail("missing owner state must refuse before entering")
