# this_file: tests/test_layer_compatibility.py
"""Source-based adjacent layer checks with independently specified messages."""

import pytest
from fontlabapp.masters.layers.compatibility.model import (
    GlyphLayers,
    Layer,
    differences,
    render,
)


def layer(name, paths=(), anchors=(), components=()):
    return Layer(name, paths, frozenset(anchors), frozenset(components))


def test_render_when_equal_or_one_layer_then_original_text_and_repeats():
    g = GlyphLayers(
        "a", (layer("Regular", (("line", "curve", "offcurve", "qcurve"),)),)
    )
    assert render((g, g)) == "a is compatible\n\n\na is compatible\n\n\n"
    assert differences(GlyphLayers("space", (layer("A"), layer("B")))) == ()


def test_differences_when_paths_nodes_types_and_names_then_complete_order():
    g = GlyphLayers(
        "b",
        (
            layer("Narrow", (("line",),), ["top"], ["base"]),
            layer("Wide", (("curve",), ()), ["bottom"], ["part"]),
            layer("Black", (("offcurve",), ()), ["bottom"], ["part"]),
            layer("Heavy", (("offcurve", "qcurve"), ()), ["bottom"], ["part"]),
        ),
    )
    d = differences(g)
    assert [(v.kind, v.previous_layer, v.layer, v.previous, v.current) for v in d] == [
        ("path counts", "Narrow", "Wide", 1, 2),
        ("anchors", "Narrow", "Wide", "top", "bottom"),
        ("components", "Narrow", "Wide", "base", "part"),
        ("path 1, node 1 node types", "Wide", "Black", "curve", "offcurve"),
        ("path 1, node count", "Black", "Heavy", 1, 2),
    ]
    text = render((g,))
    assert text.startswith(
        "b is not compatible\npath counts differ:\n  Narrow has 1\n  Wide has 2\n"
    )
    assert text.endswith(
        "path 1, node count differ:\n  Black has 1\n  Heavy has 2\n\n\n"
    )


def test_report_when_name_sets_equal_then_order_multiplicity_and_unrelated_geometry_ignored():
    a = layer("A", (("line",),), ["top", "bottom", "top"], ["b", "a", "b"])
    b = layer("B", (("line",),), ["bottom", "top"], ["a", "b"])
    assert differences(GlyphLayers("x", (a, b))) == ()


def test_report_when_only_name_sets_differ_then_later_path_checks_still_run():
    a = layer("A", (("line",),), ["top"], ["b"])
    b = layer("B", (("line",),), ["z", "a"], ["y", "c"])
    c = layer("C", (("curve",),), ["z", "a"], ["y", "c"])
    d = differences(GlyphLayers("second", (a, b, c)))
    assert [v.kind for v in d] == ["anchors", "components", "path 1, node 1 node types"]
    assert (d[0].previous, d[0].current) == ("top", "a, z")
    assert (d[1].previous, d[1].current) == ("b", "c, y")
    assert "B has line" in render((GlyphLayers("second", (a, b, c)),))


def test_report_when_many_paths_then_checks_every_equal_count_pair():
    g = GlyphLayers(
        "x",
        (
            layer("A", (("line", "line"), ())),
            layer("B", (("curve", "qcurve"), ("line",))),
        ),
    )
    assert [v.kind for v in differences(g)] == [
        "path 1, node 1 node types",
        "path 1, node 2 node types",
        "path 2, node count",
    ]


def test_report_when_no_layers_then_no_valid_prefix():
    with pytest.raises(ValueError, match="layer"):
        render((GlyphLayers("valid", (layer("A"),)), GlyphLayers("bad", ())))
    assert render(()) == ""
