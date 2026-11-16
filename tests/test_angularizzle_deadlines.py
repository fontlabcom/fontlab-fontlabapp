# this_file: tests/test_angularizzle_deadlines.py
"""Deadline checkpoints run inside source sampling loops, not after a prefix."""

import pytest

import fontlabapp.contours.angularizzle._sampling as api


@pytest.mark.parametrize(
    "run",
    [
        lambda: api._lookup(((0, 0), (0, 100), (100, 100), (100, 0)), 1),
        lambda: api._line(((0, 0), (100, 0)), 20, 1),
        lambda: api._curve(((0, 0), (10, 0), (20, 0), (30, 0)), [0, 10, 20, 30], 4, 1),
        lambda: api._strip(((0, 0), (10, 0), (20, 0), (30, 0)), 5, 1),
    ],
)
def test_expiry_inside_sampling_discards_every_partial_result(monkeypatch, run):
    ticks = iter((0.0, 2.0))
    monkeypatch.setattr(api, "monotonic", lambda: next(ticks, 2.0))
    with pytest.raises(TimeoutError, match="no partial"):
        run()
