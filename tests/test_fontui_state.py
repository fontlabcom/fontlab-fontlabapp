# this_file: tests/test_fontui_state.py
import pickle
import sys

import pytest

ufoLib2 = pytest.importorskip("ufoLib2")
from fontlabapp.fontui.model import (
    BrowserState,
    FontListState,
    outline,
    partition_paths,
    viewport,
)


def fixture_font():
    font = ufoLib2.Font()
    font.info.unitsPerEm = 1000
    font.info.ascender = 800
    font.info.descender = -200
    for name in (".notdef", "A", "Aacute", "space", "zero"):
        font.newGlyph(name).width = 600
    pen = font["A"].getPen()
    pen.moveTo((20, -100))
    pen.lineTo((220, -100))
    pen.lineTo((20, 700))
    pen.closePath()
    font["Aacute"].getPen().addComponent("A", (2, 0, 0, 0.5, 50, 100))
    return font


def test_filter_selection_and_refresh():
    font = fixture_font()
    state = BrowserState(font)
    original = state.names
    state.select(["A"])
    state.mode = "grid"
    state.cell_size = 120
    assert state.selected == ("A",)
    state.filter("aa")
    assert state.names == ("Aacute",)
    state.filter("missing")
    assert state.names == () and state.selected == ()
    state.filter("")
    assert state.names == original
    state.select(["A"])
    del font["A"]
    state.refresh()
    assert state.selected == ()


def test_outline_components_empty_and_model_unchanged():
    font = fixture_font()
    before = pickle.dumps(font)
    base = outline(font, "A")
    component = outline(font, "Aacute")
    assert base.bounds == (20, -100, 220, 700)
    assert component.bounds == (90, 50, 490, 450)
    assert outline(font, "space").bounds is None
    assert outline(font, "space").width == 600
    assert pickle.dumps(font) == before
    assert "PythonQt" not in sys.modules


def test_missing_and_cyclic_components_report():
    font = fixture_font()
    font["zero"].getPen().addComponent("missing", (1, 0, 0, 1, 0, 0))
    with pytest.raises(ValueError, match="missing"):
        outline(font, "zero")
    font["zero"].clearComponents()
    font["zero"].getPen().addComponent("zero", (1, 0, 0, 1, 0, 0))
    with pytest.raises(ValueError, match="Cyclic"):
        outline(font, "zero")


def test_viewport_uniform_scale_and_negative_y():
    scale, x, y = viewport((20, -100, 220, 700), 600, -200, 800, 400, 300)
    assert scale > 0
    assert y - (-100) * scale > y
    assert x + 220 * scale < 400
    assert y - 700 * scale > 0


def test_quadratic_cubic_and_open_paths():
    font = fixture_font()
    pen = font["zero"].getPen()
    pen.moveTo((0, 0))
    pen.qCurveTo((100, 200), (200, 0))
    pen.curveTo((250, 50), (300, 50), (350, 0))
    pen.endPath()
    result = outline(font, "zero")
    assert [op for op, args in result.recording] == [
        "moveTo",
        "qCurveTo",
        "curveTo",
        "endPath",
    ]


@pytest.mark.parametrize("backend", ["defcon", "fontparts"])
def test_real_upstream_models(backend):
    if backend == "defcon":
        from defcon import Font
    else:
        from fontParts.fontshell import RFont as Font
    font = Font()
    glyph = font.newGlyph("A")
    glyph.width = 500
    pen = glyph.getPen()
    pen.moveTo((0, 0))
    pen.lineTo((100, 300))
    pen.lineTo((200, 0))
    pen.closePath()
    assert BrowserState(font).names == ("A",)
    assert outline(font, "A").bounds == (0, 0, 200, 300)


def test_font_list_preserves_identity_across_sort_refresh_and_removal():
    first, second = fixture_font(), fixture_font()
    first.info.familyName, first.info.styleName = "Zebra", "Regular"
    second.info.familyName, second.info.styleName = "Àlpha", "Italic"
    first.lib["unrelated"] = {"keep": True}
    before = pickle.dumps((first, second))
    state = FontListState([first, second])
    state.select(0)
    assert state.selected is first, "Font selection must retain object identity"
    state.sort()
    assert state.selected is first, "Sorting must keep the selected font"
    assert state.labels == tuple(sorted(state.labels, key=str.casefold)), (
        "Font name sorting must be deterministic"
    )
    first.info.familyName = "Changed"
    state.refresh([first, second])
    assert "Changed" in state.labels[state.index], "Refresh must update labels"
    state.refresh([second])
    assert state.selected is None, "Removing the active font must clear selection"
    state.refresh([])
    assert state.labels == () and state.index is None, "Empty font lists must be safe"
    first.info.familyName = "Zebra"
    assert pickle.dumps((first, second)) == before, "Browsing must not edit fonts"


def test_font_list_uses_identity_for_distinct_equal_models():
    class EqualFont:
        info = type("Info", (), {"familyName": None, "styleName": None})()
        path = None
        dirty = False

        def __eq__(self, other):
            return True

    first, second = EqualFont(), EqualFont()
    state = FontListState([first, second])
    state.select(1)
    state.refresh([second, first])
    assert state.selected is second and state.index == 0, (
        "Equality must not retarget a font"
    )
    assert state.labels == ("Untitled — Untitled", "Untitled — Untitled")
    with pytest.raises(IndexError):
        state.select(3)


def test_font_label_reports_names_filename_and_dirty_state():
    class Font:
        info = type("Info", (), {"familyName": "Zażółć", "styleName": "Italic"})()
        path = "/owned-fixture/Unicode Font.ufo"
        dirty = True

    font = Font()
    assert FontListState.label(font) == "Zażółć Italic — Unicode Font.ufo *"
    font.dirty = False
    assert FontListState.label(font) == "Zażółć Italic — Unicode Font.ufo"


def test_closed_font_clears_views_with_a_diagnostic():
    class ClosedFont:
        def keys(self):
            raise RuntimeError("Font is closed")

        @property
        def info(self):
            raise RuntimeError("Font is closed")

    font = ClosedFont()
    state = BrowserState(font)
    assert state.names == () and state.error == "Font is closed", (
        "Closed fonts need an empty, explained browser"
    )
    fonts = FontListState([font])
    assert fonts.labels == ("Unavailable font: Font is closed",)
    fonts.select(0)
    assert fonts.selected is None, "A closed font must not become the active model"
    fonts.sort()
    assert fonts.selected is None, "Sorting closed fonts must remain safe"


def test_open_contours_are_separate_from_filled_paths():
    closed = (("moveTo", ((0, 0),)), ("lineTo", ((10, 10),)), ("closePath", ()))
    opened = (("moveTo", ((20, 20),)), ("lineTo", ((30, 30),)), ("endPath", ()))
    assert partition_paths(closed + opened) == (closed, opened), (
        "Open contours must never receive a closing fill"
    )
    assert partition_paths(()) == ((), ()), "Empty glyphs must have no invented paths"

