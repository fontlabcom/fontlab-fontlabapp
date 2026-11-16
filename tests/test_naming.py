# this_file: tests/test_naming.py
"""English menu labels become stable snake_case Python names."""

import keyword

import pytest

from fontlabapp.core.menu_names import assign_names, clean_label, object_slug, snake


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Add Component...", "Add Component"),
        ("&Rename Glyph…", "Rename Glyph"),
        ("Anchors && Pins", "Anchors & Pins"),
        ("O&pen", "Open"),
        ("Save\tCtrl+S", "Save"),
        ("  Gl&yph  ", "Glyph"),
    ],
)
def test_clean_label_when_menu_markup_then_human_label(raw, expected):
    assert clean_label(raw) == expected, raw


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Add Component...", "add_component"),
        ("Anchors && Pins", "anchors_and_pins"),
        ("Export Font As Glyphs 3 (.glyphs)", "export_font_as_glyphs_3_glyphs"),
        ("Copy Element's", "copy_elements"),
        ("Zoom 100%", "zoom_100"),
        ("1:1", "n1_1"),
        ("Import", "import_"),
        ("Café Crème", "cafe_creme"),
        ("TT Hinting", "tt_hinting"),
        ("", ""),
        ("...", ""),
    ],
)
def test_snake_when_label_then_python_identifier(raw, expected):
    name = snake(raw)
    assert name == expected, raw
    if name:
        assert name.isidentifier() and not keyword.iskeyword(name)


@pytest.mark.parametrize(
    ("object_name", "expected"),
    [
        ("actionFogFlatten_Glyph", "fog_flatten_glyph"),
        ("actionAdd_Component", "add_component"),
        ("menuRecentFonts", "recent_fonts"),
        ("actionTTHPanel", "tth_panel"),
        ("actionFontLab_VI_Web", "font_lab_vi_web"),
        ("", ""),
    ],
)
def test_object_slug_when_qt_object_name_then_snake(object_name, expected):
    assert object_slug(object_name) == expected


def test_assign_names_when_unique_then_plain_snake():
    entries = [("&Next Glyph", "actionBrowse_Next", True), ("&Previous Glyph", "actionBrowse_Previous", True)]
    assert assign_names(entries) == ["next_glyph", "previous_glyph"]


def test_assign_names_when_collision_then_visible_keeps_plain_and_hidden_uses_object_name():
    entries = [
        ("Flatten Glyph", "actionFogFlatten_Glyph", False),
        ("&Flatten Glyph", "actionFlatten_Glyph", True),
    ]
    assert assign_names(entries) == ["fog_flatten_glyph", "flatten_glyph"]


def test_assign_names_when_collision_without_object_name_then_numbered_suffix():
    entries = [("Default", "", True), ("Default", "", True), ("Default", "", True)]
    assert assign_names(entries) == ["default", "default_2", "default_3"]


def test_assign_names_when_object_slug_taken_then_numbered_suffix():
    entries = [("Remove Anchors", "actionRemove_Anchors", True), ("Remove Anchors", "actionRemove_Anchors", False)]
    assert assign_names(entries) == ["remove_anchors", "remove_anchors_2"]


def test_assign_names_when_empty_label_then_object_slug_then_item():
    assert assign_names([("", "actionFoo_Bar", True), ("", "", True)]) == ["foo_bar", "item"]


def test_assign_names_when_reserved_then_trailing_underscore():
    assert assign_names([("Path", "", True), ("Title", "", True)], reserved={"path", "title"}) == ["path_", "title_"]


def test_assign_names_when_same_input_then_deterministic():
    entries = [("A", "x", False), ("A", "y", True), ("A", "", True), ("B", "", True)]
    assert assign_names(entries) == assign_names(list(entries))


def test_assign_names_when_visibility_flips_then_names_follow_object_names():
    a = [("Flatten Glyph", "actionFogFlatten_Glyph", True), ("&Flatten Glyph", "actionFlatten_Glyph", False)]
    b = [(label, obj, not visible) for label, obj, visible in a]
    assert assign_names(a) == assign_names(b) == ["fog_flatten_glyph", "flatten_glyph"]


def test_assign_names_when_no_slug_matches_then_smallest_object_name_wins_regardless_of_order():
    entries = [("+10", "actionFlag_Plus10", True), ("-10", "actionFlag_Minus10", True)]
    assert assign_names(entries) == ["flag_plus10", "n10"]
    assert assign_names(entries[::-1]) == ["n10", "flag_plus10"]
