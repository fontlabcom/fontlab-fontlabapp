# this_file: tests/test_layer_navigation_data.py
from dataclasses import FrozenInstanceError

import pytest
from fontlabapp.masters.layers.navigation.data import plan, require_current

ROWS = (("a", "A"), ("b", "B"), ("c", "C"))


@pytest.mark.parametrize("direction,target", [(1, "b"), (-1, "c")])
def test_order_wrap_inverse(direction, target):
    change = plan("a", ROWS, direction, ("opaque",))
    assert change.after_layer == target
    assert plan(target, ROWS, -direction, ()).after_layer == "a"
    with pytest.raises(FrozenInstanceError):
        change.after_layer = "x"


def test_repeat_and_single():
    current = "a"
    for _ in range(3):
        current = plan(current, ROWS, 1, ()).after_layer
    assert current == "a"
    assert plan("a", ROWS[:1], 1, ()).after_layer == "a"


@pytest.mark.parametrize("direction", [0, 2, True, None])
def test_bad_direction(direction):
    with pytest.raises(ValueError):
        plan("a", ROWS, direction, ())


@pytest.mark.parametrize(
    "rows",
    [
        [],
        (),
        (("a",),),
        (("", "A"),),
        (("a", "A"), ("a", "B")),
        (("a", "A"), ("b", "A")),
    ],
)
def test_bad_layers(rows):
    with pytest.raises(ValueError):
        plan("a", rows, 1, ())


def test_stale_complete_opaque_token():
    change = plan("a", ROWS, 1, ("font", "tab", "A /x\n😀A", (1, 2)))
    require_current(change, change.source_token)
    with pytest.raises(ValueError):
        require_current(change, ("changed",))
    with pytest.raises(ValueError):
        plan("missing", ROWS, 1, ())
    with pytest.raises(ValueError):
        plan("a", ROWS, 1, [])
