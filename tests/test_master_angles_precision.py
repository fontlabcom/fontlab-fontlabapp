# this_file: tests/test_master_angles_precision.py
# SPDX-License-Identifier: Apache-2.0
"""Refuse native masters-history hinting loss before any angle or history write."""

import pytest
from test_master_angles import owned  # noqa: F401

import fontlabapp.masters.angles.model as api


@pytest.mark.parametrize(
    "value,safe",
    [
        (0.039625, True),
        (0.039625 + 1e-14, True),
        (0.3636, False),
        (0.363636, False),
        (0.5, True),
        (1.0, True),
        (-0.25, True),
        (0.0, True),
        (1e-12, True),
        (1e-8, False),
        (2e-8, True),
        (0.12345, True),
        (0.032767, True),
        (0.032768, True),
        (0.99999999, False),
        (32767.0, True),
        (32768.0, True),
        (16777217.0, False),
        (float("nan"), False),
        (float("inf"), False),
        (1e100, False),
    ],
)
def test_known_native_compact_and_binary32_boundaries(value, safe):
    assert api.history_preserves_blue_scale(value) is safe


def test_unsafe_later_master_refuses_whole_batch_before_history(owned):  # noqa: F811
    p, _ = owned
    p.hints["Black"] = 0.363636
    with pytest.raises(ValueError, match="blueScale"):
        api.apply(api.capture(p), {"Thin": -12})
    assert p.master == "Regular" and p.events == []
    assert set(p.values.values()) == {-10}


def test_noop_does_not_reject_or_rewrite_unsafe_hinting(owned):  # noqa: F811
    p, _ = owned
    p.hints["Black"] = 0.363636
    assert api.apply(api.capture(p), {"Thin": -10}) == []
    assert p.hints["Black"] == 0.363636 and p.events == []


def test_hinting_read_failure_restores_master_without_history(owned):  # noqa: F811
    p, _ = owned
    del p.hints["Black"]
    with pytest.raises(KeyError, match="Black"):
        api.apply(api.capture(p), {"Thin": -12})
    assert p.master == "Regular" and p.events == []


def test_default_omission_must_not_restore_different_global_hinting(owned):  # noqa: F811
    p, _ = owned
    p.info.postscriptBlueScale = 0.363636
    assert not api.history_preserves_blue_scale(0.039625, 0.363636)
    with pytest.raises(ValueError, match="blueScale"):
        api.apply(api.capture(p), {"Thin": -12})
    assert p.events == [] and p.master == "Regular"
