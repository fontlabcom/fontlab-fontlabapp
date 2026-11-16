# this_file: tests/test_show_all_layers.py
"""Independent full original selection/order/newline policy."""

import pytest
from fontlabapp.masters.layers.show_all.model import Group, expand


@pytest.mark.parametrize(
    "groups,expected",
    [
        ((), ()),
        ((Group(None, ("Regular",)),), ()),
        ((Group("A", ("Regular",), True),), ()),
        ((Group("A", ()),), (None,)),
        (
            (
                Group("A", ("Bold", "Alt", "Regular")),
                Group("A", ("Bold",)),
                Group(None, ()),
            ),
            (("A", "Bold"), ("A", "Alt"), ("A", "Regular"), None, ("A", "Bold"), None),
        ),
    ],
)
def test_entire_original_order_duplicates_control_parentless_and_trailing_newlines(
    groups, expected
):
    assert expand(groups) == expected
