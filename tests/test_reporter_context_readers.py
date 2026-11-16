# this_file: tests/test_reporter_context_readers.py
"""Offline tests for the G003 Task 3 readers: kerning groups, other glyphs,
the owner master rule and same-line neighbours.

Native objects are plain fakes; ``Spy`` fakes record every native access so
the tests prove no kerning writer, layer creator or history API is touched.
"""

import math
from types import SimpleNamespace as NS

import pytest

import fontlabapp.components.decompose as decompose
from fontlabapp.glyphs import others
from fontlabapp.kerning import groups
from fontlabapp.qt.painting import view
from paint_safety import Spy, assert_paint_safe, recorder


def items(get):
    return list(get())


def kerning_package(log, classes):
    """A package whose kerning(master).groups.items() returns ``classes``."""
    table = Spy(log, "groups", items=recorder(log, "groups", "items", classes.items()))
    kerning = Spy(log, "kerning", groups=table)
    return Spy(log, "package", kerning=recorder(log, "package", "kerning", kerning))


def test_groups_when_side_specific_and_both_then_specific_wins_in_native_order():
    log = []
    package = kerning_package(
        log,
        {
            "both_A": (["A", "B"], "KernBothSide"),
            "left_A": (["A"], "KernLeft"),
            "left_A2": (["A"], "KernLeft"),
            "other": (["C"], "KernRight"),
        },
    )
    left, right, members = groups.read(package, "Bold", "A")
    assert (left, right) == ("left_A", "both_A"), (
        "left: first side-specific class; right: falls back to the both-side class"
    )
    assert dict(members) == {"left_A": ("A",), "both_A": ("A", "B")}
    assert ("package", "call", "kerning", ("Bold",)) in log


def test_groups_when_glyph_in_no_class_then_none_and_unknown_modes_ignored():
    log = []
    package = kerning_package(
        log, {"odd": (["A"], "KernSomething"), "r": (["B"], "KernRight")}
    )
    assert groups.read(package, "Regular", "A") == (None, None, {})


def test_groups_read_touches_only_groups_items_and_writes_nothing():
    log = []
    package = kerning_package(log, {"l": (["A"], "KernLeft")})
    groups.read(package, "Regular", "A")
    assert {(e[0], e[2]) for e in log if e[0] == "kerning"} == {("kerning", "groups")}
    assert {(e[0], e[2]) for e in log if e[0] == "groups"} == {("groups", "items")}
    assert_paint_safe(log)


def test_owner_master_when_shown_layer_is_a_master_then_it_else_current():
    package = NS(master="Regular", masters=["Regular", "Bold"])
    assert decompose.owner_master(package, NS(name="Bold"), items) == "Bold"
    assert decompose.owner_master(package, NS(name="mask.Bold"), items) == "Regular"


def test_others_find_when_glyph_and_layer_exist_then_both_else_none():
    log = []
    layer = Spy(log, "otherLayer", isNull=False)
    glyph = Spy(
        log,
        "other",
        isNull=False,
        findLayer=recorder(log, "other", "findLayer", layer),
    )
    package = Spy(
        log,
        "package",
        findName=lambda name: (
            log.append(("package", "call", "findName", (name,)))
            or {"B": glyph, "N": NS(isNull=True)}.get(name)
        ),
    )
    assert others.find(package, "B", "Bold") == (glyph, layer)
    assert others.find(package, "Z", "Bold") is None, "missing glyph is absent"
    assert others.find(package, "N", "Bold") is None, "null glyph is absent"
    assert ("other", "call", "findLayer", ("Bold",)) in log
    assert_paint_safe(log)
    missing = NS(isNull=False, findLayer=lambda name: None)
    assert others.find(NS(findName=lambda name: missing), "B", "Bold") is None
    null = NS(isNull=False, findLayer=lambda name: NS(isNull=True))
    assert others.find(NS(findName=lambda name: null), "B", "Bold") is None


class Scale:
    """A QTransform-like scale with ``m11``."""

    def __init__(self, m11):
        self.value = m11

    def m11(self):
        return self.value


def slot(log, label, name, kern, m11=2.0):
    """A glyph info whose stored kerning is the pair (this, next)."""
    return Spy(
        log,
        label,
        glyph=NS(isNull=False, name=name),
        transform=Scale(m11),
        kerningOffset=recorder(log, label, "kerningOffset", kern),
    )


def block_of(log, prev, nxt):
    return Spy(
        log,
        "block",
        getPrevGlyphInLine=recorder(log, "block", "getPrevGlyphInLine", prev),
        getNextGlyphInLine=recorder(log, "block", "getNextGlyphInLine", nxt),
    )


def test_neighbours_when_both_sides_then_prev_pair_on_prev_and_next_pair_on_this():
    log = []
    prev, this, nxt = (
        slot(log, "prev", "T", -80.0),
        slot(log, "this", "o", 30.0),
        slot(log, "next", "n", 999.0),
    )
    errors = []
    before, after = view.neighbours(block_of(log, prev, nxt), 7, this, errors.append)
    assert errors == []
    assert before == ("T", -40.0), "(prev, this) is stored on prev, in block units"
    assert after == ("n", 15.0), "(this, next) is stored on this"
    calls = [e for e in log if e[1] == "call"]
    assert ("block", "call", "getPrevGlyphInLine", (7,)) in calls
    assert ("block", "call", "getNextGlyphInLine", (7,)) in calls
    assert {e[3] for e in calls if e[2] == "kerningOffset"} == {(True,)}
    assert not [e for e in calls if e[0] == "next" and e[2] == "kerningOffset"]
    assert not [e for e in log if e[2] == "findLayer"]
    assert_paint_safe(log)


def test_neighbours_when_line_ends_or_glyph_null_then_that_side_is_none():
    log = []
    this = slot(log, "this", "o", 0.0)
    errors = []
    assert view.neighbours(block_of(log, None, None), 0, this, errors.append) == (
        None,
        None,
    )
    gone = NS(glyph=NS(isNull=True))
    assert view.neighbours(
        block_of(log, gone, NS(glyph=None)), 3, this, errors.append
    ) == (None, None)
    assert errors == [], "absence is not an error"


@pytest.mark.parametrize("m11", [0.0, math.inf, math.nan])
def test_neighbours_when_this_scale_unusable_then_only_next_side_is_none(m11):
    log = []
    prev = slot(log, "prev", "T", -80.0)
    this = slot(log, "this", "o", 10.0, m11=m11)
    nxt = slot(log, "next", "n", 0.0)
    errors = []
    sides = view.neighbours(block_of(log, prev, nxt), 1, this, errors.append)
    assert sides == (("T", -40.0), None), "the prev side survives"
    assert len(errors) == 1 and isinstance(errors[0], ValueError)
    assert "kerning" in str(errors[0])


@pytest.mark.parametrize("kern", [math.inf, -math.inf, math.nan])
def test_neighbours_when_kerning_not_finite_then_that_side_is_none(kern):
    log = []
    prev = slot(log, "prev", "T", kern)
    this = slot(log, "this", "o", 30.0)
    nxt = slot(log, "next", "n", 0.0)
    errors = []
    sides = view.neighbours(block_of(log, prev, nxt), 1, this, errors.append)
    assert sides == (None, ("n", 15.0)), "the next side survives"
    assert len(errors) == 1 and isinstance(errors[0], ValueError)


def test_neighbours_when_line_lookup_raises_then_only_that_side_is_none():
    log = []
    this = slot(log, "this", "o", 30.0)
    nxt = slot(log, "next", "n", 0.0)
    block = block_of(log, None, nxt)

    def broken(index):
        raise RuntimeError("stale")

    object.__getattribute__(block, "_attrs")["getPrevGlyphInLine"] = broken
    errors = []
    assert view.neighbours(block, 1, this, errors.append) == (None, ("n", 15.0))
    assert [str(e) for e in errors] == ["stale"]


class Pt:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class Full:
    """A QTransform-like fake with the six getters ``affine`` reads."""

    def __init__(self, scale=1.0, dx=0.0, dy=0.0):
        self.s, self._dx, self._dy = scale, dx, dy

    def m11(self):
        return self.s

    def m12(self):
        return 0.0

    def m21(self):
        return 0.0

    def m22(self):
        return self.s

    def dx(self):
        return self._dx

    def dy(self):
        return self._dy


def test_glyph_point_inverts_glyph_then_block_transforms():
    # canvas = block(glyph(p)) = (2x + 10 + 1, 2y + 2)
    assert view.glyph_point(Full(2, 10, 0), Full(1, 1, 2), Pt(31, 10)) == (10.0, 4.0)


def test_glyph_point_when_not_invertible_or_not_finite_then_value_error():
    with pytest.raises(ValueError, match="invertible"):
        view.glyph_point(Full(0), Full(1), Pt(0, 0))
    with pytest.raises(ValueError):
        view.glyph_point(Full(1), Full(1), Pt(math.nan, 0))
