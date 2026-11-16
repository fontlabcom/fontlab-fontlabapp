# this_file: tests/test_vfjo_nodes.py
"""Tests for fontlabapp.vfjo.nodes: exact round-trip, flags, errors, transforms."""

import pytest

from fontlabapp.vfjo.nodes import Node, format_nodes, format_number, parse_nodes

OBSERVED = [
    "439 572 {n:'hr01'}",
    "326 994  348 983  375 983 s {n:'sv01'}",
    "312 1020",
    "678 661 s",
    "443 496  374 425 c",
    "722.507 1510 s g2 {n:'av01'}",
    "1111 852  897 1056 c",
    "51 190  267 -16  583 -16 s {n:'ab01'}",
]


@pytest.mark.parametrize("text", OBSERVED)
def test_parse_format_when_unmodified_then_byte_exact(text):
    assert Node.parse(text).format() == text, "round-trip must be exact"
    assert str(Node.parse(text)) == text


def test_parse_nodes_when_list_then_round_trips():
    assert format_nodes(parse_nodes(OBSERVED)) == OBSERVED


def test_parse_when_flags_then_set():
    n = Node.parse("722.507 1510 s g2 {n:'av01'}")
    assert n.smooth and n.g2 and not n.close and not n.offcurve
    assert Node.parse("1 2 o").offcurve
    assert Node.parse("1 2  3 4 c").close


def test_parse_when_unknown_flags_then_kept_in_order():
    n = Node.parse("1 2 s zz yy")
    assert n.flags == ("zz", "yy") and n.smooth
    assert n.format() == "1 2 s zz yy"


def test_format_when_flags_built_then_canonical_order():
    n = Node(points=((1, 2),), close=True, g2=True, offcurve=True, smooth=True, flags=("x",))
    assert n.format() == "1 2 s o g2 c x"


def test_name_when_present_then_extracted_else_none():
    assert Node.parse("439 572 {n:'hr01'}").name == "hr01"
    assert Node.parse('1 2 {n:"q"}').name == "q"
    assert Node.parse("1 2").name is None
    assert Node.parse("1 2 {x:1}").name is None


def test_on_and_offcurves_by_shape():
    cubic = Node.parse("326 994  348 983  375 983 s")
    assert cubic.on == (375, 983)
    assert cubic.offcurves == [(326, 994), (348, 983)]
    line = Node.parse("312 1020")
    assert line.on == (312, 1020) and line.offcurves == []
    closing = Node.parse("443 496  374 425 c")
    assert closing.on is None and closing.offcurves == [(443, 496), (374, 425)]
    tt = Node.parse("5 6 o")
    assert tt.on is None and tt.offcurves == [(5, 6)]


@pytest.mark.parametrize("bad", ["", "{n:'a'}", "1", "1 2 3", "a b", "1 x", "s 1 2"])
def test_parse_when_malformed_then_value_error_with_text(bad):
    with pytest.raises(ValueError, match="malformed node"):
        Node.parse(bad)


def test_moved_when_ints_then_ints_and_new_node():
    n = Node.parse("326 994  348 983  375 983 s {n:'sv01'}")
    m = n.moved(10, -4)
    assert m.format() == "336 990  358 979  385 979 s {n:'sv01'}"
    assert n.format().startswith("326 994"), "original unchanged"
    assert all(isinstance(v, int) for p in m.points for v in p)


def test_moved_when_float_then_rounded_three_decimals():
    assert Node.parse("1 2").moved(0.12345, 0.5).format() == "1.123 2.5"


def test_scaled_when_origin_and_uniform_then_applied():
    n = Node.parse("10 20  30 40 c")
    assert n.scaled(2).format() == "20 40  60 80 c"
    assert n.scaled(2, 0.5, origin=(10, 20)).format() == "10 20  50 30 c"


def test_scaled_when_result_integral_float_then_int_text():
    assert Node.parse("3 3").scaled(1.5).format() == "4.5 4.5"
    assert Node.parse("4 4").scaled(1.5).format() == "6 6"


def test_mapped_when_fn_then_point_count_kept():
    n = Node.parse("1 2  3 4  5 6")
    assert len(n.mapped(lambda x, y: (y, x)).points) == 3


@pytest.mark.parametrize(
    ("value", "text"),
    [(583, "583"), (-16, "-16"), (722.507, "722.507"), (1.0004, "1"), (2.5, "2.5"), (-0.0, "0")],
)
def test_format_number(value, text):
    assert format_number(value) == text
