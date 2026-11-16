# this_file: tests/test_glyph_identity.py
"""Glyph identity reads from recording fakes: values, mark colours, no writes."""

import pytest

from fontlabapp.glyphs.identity import GREY, Identity, mark_rgb, read
from paint_safety import Spy, assert_paint_safe

def native(log, *, tags=(), skip=None, unicodes=(0x41,), mark=1):
    """Return a spying package and glyph named ``A``."""
    lib = {} if skip is None else {"public.skipExportGlyphs": skip}
    record = Spy(log, "record", unicodes=list(unicodes))
    fg = Spy(log, "fgPackage", items={"A": record})
    package = Spy(log, "package", fgPackage=fg, packageLib=lib)
    glyph = Spy(log, "glyph", name="A", mark=mark, tags=list(tags))
    return package, glyph


def assert_read_only(log):
    assert_paint_safe(log)
    fg = [e for e in log if e[0] == "fgPackage"]
    assert fg == [("fgPackage", "item", "A")], f"fgPackage only item lookup: {fg}"


def test_mark_rgb_when_mark_is_zero_then_none():
    assert mark_rgb(0) is None


def test_mark_rgb_when_mark_above_1000_then_grey():
    assert mark_rgb(1001) == GREY == (128, 128, 128)
    assert mark_rgb(5000) == GREY


def test_mark_rgb_when_hue_mark_then_hsl_lightness_065_saturation_1():
    assert mark_rgb(1) == (255, 77, 77), "mark 1 is hue 0 (red)"
    assert mark_rgb(121) == (77, 255, 77), "mark 121 is hue 120 (green)"
    assert mark_rgb(241) == (77, 77, 255), "mark 241 is hue 240 (blue)"


def test_mark_rgb_when_out_of_hue_range_then_hue_wraps():
    assert mark_rgb(1000) == mark_rgb(1000 - 360 * 2), "999 degrees wraps to 279"
    assert mark_rgb(-5) == mark_rgb(355), "-6 degrees wraps to 354"


def test_read_when_plain_glyph_then_copies_identity_read_only():
    log = []
    package, glyph = native(log, unicodes=(0x41, 0x391), mark=121)
    assert read(package, glyph) == Identity(
        "A", (0x41, 0x391), 121, (77, 255, 77), True
    )
    assert_read_only(log)


def test_read_when_noexport_tag_then_not_exported():
    log = []
    package, glyph = native(log, tags=("noexport",), mark=0)
    identity = read(package, glyph)
    assert identity.exported is False
    assert identity.mark_rgb is None
    assert_read_only(log)


def test_read_when_name_in_skip_export_list_then_not_exported():
    log = []
    package, glyph = native(log, skip=["B", "A"], unicodes=())
    identity = read(package, glyph)
    assert (identity.exported, identity.unicodes) == (False, ())
    assert_read_only(log)


@pytest.mark.parametrize("skip", ["A", [1], {"A": True}])
def test_read_when_skip_list_is_malformed_then_value_error(skip):
    package, glyph = native([], skip=skip)
    with pytest.raises(ValueError, match="skipExportGlyphs"):
        read(package, glyph)


def test_read_when_native_attribute_missing_then_attribute_error():
    log = []
    package, _ = native(log)
    glyph = Spy(log, "glyph", name="A", mark=1)
    with pytest.raises(AttributeError, match="tags"):
        read(package, glyph)
