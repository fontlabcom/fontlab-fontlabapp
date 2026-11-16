# this_file: tests/test_fontpr_tuple_arrays.py
"""fontpr.call returns tuples for JSON arrays on FontLab 9.0.9808 (A2 report 18, D18-3/D18-4).

Every reader of a fontpr result must accept a list or a tuple, never a str.
"""

from types import SimpleNamespace as NS

import pytest

import fontlabapp.components.creation as creation
import fontlabapp.contours.near_miss.native as near_miss
import fontlabapp.contours.raise_ascender._capture as capture
import fontlabapp.core.outline as outline
import fontlabapp.metrics.vertical.native as vertical

MASTER = {
    "fontMaster": {
        "name": "Regular",
        "ascender": 800,
        "capsHeight": 700,
        "xHeight": 500,
        "descender": -200,
        "fontStemsH": ({"value": 80},),
        "fontStemsV": ({"value": 90},),
        "otherData": {"hhea_ascender": "800", "hhea_descender": -200, "hhea_line_gap": "0"},
    }
}


def test_outline_master_measures_when_arrays_are_tuples_then_read():
    metrics, stems_h, stems_v = outline.master_measures({"masters": (MASTER,)}, "Regular")
    assert (metrics, stems_h, stems_v) == ((800.0, 700.0, 500.0, -200.0), (80.0,), (90.0,))


def test_near_miss_master_when_arrays_are_tuples_then_read():
    name, metrics, stems_h, stems_v = near_miss._master({"masters": (MASTER,)}, "Regular:1")
    assert (name, metrics[0], stems_h, stems_v) == ("Regular", 800, (80,), (90,))


def test_raise_ascender_masters_when_entries_are_tuple_then_read(monkeypatch):
    fontpr = NS(call=lambda name, **kw: {"masters": (MASTER,)})
    monkeypatch.setattr(capture, "_native", lambda module: fontpr)
    monkeypatch.setattr(capture.scripting, "font_id", lambda package: 7)
    assert capture.masters(NS(masters=["Regular"]), float("inf")) == (("Regular", 500),)


def test_raise_ascender_masters_when_entries_are_str_then_refused(monkeypatch):
    fontpr = NS(call=lambda name, **kw: {"masters": "Regular"})
    monkeypatch.setattr(capture, "_native", lambda module: fontpr)
    monkeypatch.setattr(capture.scripting, "font_id", lambda package: 7)
    with pytest.raises(ValueError, match="Unreadable or ambiguous"):
        capture.masters(NS(masters=["Regular"]), float("inf"))


def test_vertical_metrics_when_arrays_are_tuples_then_read(monkeypatch):
    font = {"id": 1, "file_name": "", "full_name": "F", "family_name": "F", "masters_count": 1}

    def call(name, **kwargs):
        return {"fonts": (font,)} if name == "list_fonts" else {"masters": (MASTER,)}

    monkeypatch.setattr(vertical, "_call", call)
    report = vertical.capture()
    assert [row.master for row in report.rows] == ["Regular"]


def test_component_elements_when_elements_are_tuple_then_listed():
    data = {"layers": ({"name": "L", "elements": ({"a": 1}, {"b": 2})},)}
    assert creation._elements(data, NS(name="L")) == [{"a": 1}, {"b": 2}]


def test_component_elements_when_elements_are_str_then_none():
    assert creation._elements({"layers": [{"name": "L", "elements": "ab"}]}, NS(name="L")) is None


@pytest.mark.parametrize("locked", [True, False])
def test_qualifies_when_native_content_lock_set_then_ignored(locked, monkeypatch):
    """Native contentLocked reads True for all 504 components in plum; the VFJ locked key decides."""
    shape = NS(excluded=False, contentLocked=locked, opacity=1.0, isComponent=True)
    monkeypatch.setattr(creation.component_writer, "plain_move", lambda s: True)
    monkeypatch.setattr(creation, "_vfj_element", lambda element, s: True)
    assert creation._qualifies(shape, {}) is True
