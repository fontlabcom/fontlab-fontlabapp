# this_file: tests/test_fontui_wrap.py
"""B04 wrapping: line assignment over a placed run (host-free).

The Sequence widget tests moved with the widget to Fontport (issue 122,
T10/T13b). Only the pure ``wrap`` helper stays in App.
"""

from types import SimpleNamespace

import pytest

from fontlabapp.fontui.wrap import wrap


def run(advances, direction="ltr", kern=None):
    """Place like Fontport's glyph run: LTR grows right, RTL grows left."""
    kern = kern or {}
    cursor, glyphs = 0.0, []
    for index, width in enumerate(advances):
        adjust = kern.get(index, 0)
        cursor += adjust if direction == "ltr" else -adjust - width
        glyphs.append(SimpleNamespace(index=index, x=cursor, advance=width))
        cursor += width if direction == "ltr" else 0
    return glyphs


def test_wrap_when_off_then_keeps_one_line_and_positions():
    glyphs = run([600, 600, 600])
    assert wrap(glyphs, None, "ltr") == [(0, 0), (600, 0), (1200, 0)]


def test_wrap_when_ltr_overflows_then_lines_restart_at_zero():
    glyphs = run([600, 600, 600, 600, 600])
    assert wrap(glyphs, 1300, "ltr") == [(0, 0), (600, 0), (0, 1), (600, 1), (0, 2)]


def test_wrap_when_kerned_then_line_keeps_kerned_offsets():
    glyphs = run([600, 600, 600], kern={1: -80})
    assert wrap(glyphs, 1200, "ltr") == [(0, 0), (520, 0), (0, 1)]


def test_wrap_when_rtl_then_each_line_is_right_aligned_at_zero():
    glyphs = run([600, 600, 600], direction="rtl")
    assert wrap(glyphs, 1300, "rtl") == [(-600, 0), (-1200, 0), (-600, 1)]


def test_wrap_when_glyph_wider_than_width_then_it_gets_its_own_line():
    glyphs = run([2000, 300])
    assert wrap(glyphs, 1000, "ltr") == [(0, 0), (0, 1)]


@pytest.mark.parametrize("width", [0, -5, float("nan")])
def test_wrap_when_width_not_positive_finite_then_no_wrap(width):
    glyphs = run([600, 600])
    assert wrap(glyphs, width, "ltr") == [(0, 0), (600, 0)]


def test_wrap_when_empty_then_empty():
    assert wrap([], 500, "ltr") == []

