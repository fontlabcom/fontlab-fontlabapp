# this_file: tests/test_node_duplicator.py
"""Independent literal original topology/order cases; original bodies never run."""

import pytest
from fontlabapp.contours.nodes.duplicator.model import Node, Path, Layer, Source, plan


def node(key, kind="line", x=None):
    return Node(key, float(key if x is None else x), 0.125, kind, 8, "n" + str(key), ())


def layer(key, glyph, rows):
    return Layer(
        key, glyph, tuple(Path(i, tuple(row), True) for i, row in enumerate(rows))
    )


def test_current_layer_uses_reverse_selection_identity_and_ignores_handles():
    first = layer(1, 10, [[node(1), node(2, "off"), node(3, "curve")]])
    other = layer(2, 10, [[node(4)]])
    result = plan(
        Source((first, other), (1,), ((0, 1), (0, 2), (0, 3)), True), "current"
    )
    assert [n.name for n in result.layers[0].paths[0].nodes] == [
        "n1",
        "n1",
        "n2",
        "n3",
        "n3",
    ]
    assert [n.kind for n in result.layers[0].paths[0].nodes] == [
        "line",
        "line",
        "off",
        "curve",
        "line",
    ]
    assert result.layers[1] == other and result.inserted == 2
    assert result.selection == ((0, 1), (0, 2), (0, 3))


def test_all_layers_replays_numeric_indices_even_for_handles_and_duplicate_parent_occurrences():
    first = layer(1, 10, [[node(1), node(2), node(3)]])
    auxiliary = layer(2, 10, [[node(4, "off"), node(5), node(6)]])
    empty = layer(3, 10, [[]])
    unrelated = layer(4, 20, [[node(7)]])
    result = plan(
        Source((first, auxiliary, empty, unrelated), (1, 2), ((0, 1), (0, 3)), True),
        "all",
    )
    assert [n.name for n in result.layers[0].paths[0].nodes] == [
        "n1",
        "n1",
        "n1",
        "n2",
        "n2",
        "n3",
        "n3",
    ]
    assert [n.name for n in result.layers[1].paths[0].nodes] == [
        "n4",
        "n4",
        "n4",
        "n5",
        "n5",
        "n6",
        "n6",
    ]
    assert result.layers[1].paths[0].nodes[1].kind == "line"
    assert result.layers[2] == empty and result.layers[3] == unrelated
    assert result.inserted == 8 and len(result.skipped) == 4


def test_handles_only_first_layer_forward_selection_snapshot_coincident_cubic_triplets():
    a = layer(1, 10, [[node(1, "qcurve"), node(2, "off"), node(3)]])
    b = layer(2, 10, [[node(4)]])
    result = plan(Source((a, b), (1, 2), ((0, 1), (0, 2), (0, 3)), True), "handles")
    row = result.layers[0].paths[0].nodes
    assert [n.kind for n in row] == [
        "qcurve",
        "off",
        "off",
        "curve",
        "off",
        "line",
        "off",
        "off",
        "curve",
    ]
    assert [(n.x, n.y) for n in row[1:4]] == [(1.0, 0.125)] * 3
    assert [(n.x, n.y) for n in row[6:9]] == [(3.0, 0.125)] * 3
    assert row[3].name == "n1" and row[8].name == "n3"
    assert result.layers[1] == b and result.inserted == 6


@pytest.mark.parametrize(
    "mode,any_selection,expected",
    [
        ("current", False, True),
        ("current", True, False),
        ("all", False, True),
        ("all", True, True),
        ("handles", False, False),
        ("handles", True, False),
    ],
)
def test_empty_and_handle_only_original_messages_differ(mode, any_selection, expected):
    a = layer(1, 10, [[node(1, "off")]])
    result = plan(
        Source((a,), (1,), ((0, 1),) if any_selection else (), any_selection), mode
    )
    assert (
        bool(result.no_selection_message) == expected
        and result.inserted == 0
        and result.layers == (a,)
    )


def test_all_layers_skips_each_short_path_or_node_without_aborting_other_layers():
    a = layer(1, 10, [[node(1)], [node(2)]])
    b = layer(2, 10, [[]])
    c = layer(3, 10, [[node(3)], [node(4)]])
    result = plan(Source((a, b, c), (1,), ((1, 2), (0, 1)), True), "all")
    assert result.inserted == 4 and len(result.skipped) == 2
    assert result.layers[1] == b
    assert [n.name for n in result.layers[2].paths[1].nodes] == ["n4", "n4"]


def test_copies_preserve_coordinates_connection_name_metadata_and_do_not_mutate_source():
    n = Node(1, 0.125, 0.375, "curve", 0x1008, "named", (("thickness", 13.5),))
    original = layer(1, 10, [[n]])
    result = plan(Source((original,), (1,), ((0, 1),), True), "current")
    copy = result.layers[0].paths[0].nodes[1]
    assert (copy.x, copy.y, copy.flags, copy.name, copy.properties) == (
        n.x,
        n.y,
        n.flags,
        n.name,
        n.properties,
    )
    assert copy.kind == "line" and copy.key != n.key and original.paths[0].nodes == (n,)
