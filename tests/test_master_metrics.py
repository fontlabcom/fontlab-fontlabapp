# this_file: tests/test_master_metrics.py
"""write_master_metrics: field refusals, tolerance and one route-A commit (offline)."""

import math
from importlib import import_module

import pytest
from master_doubles import FakePackage, native

master_metrics = import_module("fontlabapp.metrics.master_writer")
font_history = import_module("fontlabapp.core.history.masters")
edit_guards = import_module("fontlabapp.core.edit_guards")


@pytest.fixture(autouse=True)
def guards(monkeypatch):
    monkeypatch.setattr(edit_guards, "require_selection_window", lambda package_id: None)


def test_write_master_metrics_when_two_masters_then_one_notify_and_read_back():
    p = FakePackage()
    values = {"Bold": {"xHeight": 515, "ascender": 780.0}, "Regular": {"lineGap": 20, "capsHeight": 701.5}}
    result = master_metrics.write_master_metrics(p, values, native=native(p, queue=(3,)))
    assert result.values == {
        "Regular": {"capsHeight": 701.5, "lineGap": 20.0},
        "Bold": {"ascender": 780.0, "xHeight": 515.0},
    }, f"read-back per master in field order: {result.values}"
    assert p.data["Bold"]["xHeight_value"] == 515.0 and p.data["Regular"]["lineGap_value"] == 20.0, "stored values"
    notifies = [e for e in p.log if e[0] == "notify"]
    assert notifies == [("notify", master_metrics.TITLE, (p, p.container), False)], f"one notify: {notifies}"
    assert result.pending_updates == (3,), "queued ids must be disclosed"
    writes = [e for e in p.log if isinstance(e, str) and e.startswith("set-")]
    assert writes == ["set-capsHeight_value", "set-lineGap_value", "set-ascender_value", "set-xHeight_value"], writes


@pytest.mark.parametrize(
    "values,match",
    [
        ({}, "No master"),
        ({"Bold": {}}, "no metric"),
        ({"Bold": {"lineGapX": 700}}, "Unknown metric field 'lineGapX'"),
        ({"Bold": {"capHeight": 700, "capsHeight": 701}}, "'capHeight' and 'capsHeight'"),
        ({"Bold": {"hhea_line_gap": 0}}, "Unknown metric field"),
        ({"Bold": {"ascender": math.nan}}, "finite"),
        ({"Bold": {"ascender": math.inf}}, "finite"),
        ({"Bold": {"ascender": True}}, "finite"),
        ({"Bold": {"ascender": "700"}}, "finite"),
        ({1: {"ascender": 700}}, "no metric"),
    ],
)
def test_write_master_metrics_when_request_bad_then_refuses_before_history(values, match):
    p = FakePackage()
    with pytest.raises(ValueError, match=match):
        master_metrics.write_master_metrics(p, values, native=native(p))
    assert p.log == [], f"refusal must come before any native call: {p.log}"


def test_write_master_metrics_when_unknown_master_then_refuses_before_history():
    p = FakePackage()
    with pytest.raises(ValueError, match="Unknown"):
        master_metrics.write_master_metrics(p, {"Black": {"ascender": 1}}, native=native(p))
    assert p.log == [], f"refusal must come before any native call: {p.log}"


@pytest.mark.parametrize("stored,accepted", [(780.0 + 1e-10, True), (780.0 + 1e-6, False), (780, True)])
def test_write_master_metrics_when_stored_value_differs_then_tolerance_decides(stored, accepted):
    p = FakePackage()
    original = p.data["Bold"]["ascender_value"]
    p.fail[("store-once", "ascender_value")] = stored
    if accepted:
        result = master_metrics.write_master_metrics(p, {"Bold": {"ascender": 780.0}}, native=native(p))
        assert result.values["Bold"]["ascender"] == stored, "the read-back value is returned as stored"
        return
    with pytest.raises(font_history.RolledBackError, match="planned 780"):
        master_metrics.write_master_metrics(p, {"Bold": {"ascender": 780.0}}, native=native(p))
    assert p.data["Bold"]["ascender_value"] == original, "a value outside the tolerance must be restored"
    assert not [e for e in p.log if e[0] == "notify"], "no notify after the rollback"


def test_write_master_metrics_when_value_rounded_then_restored_and_refused():
    p = FakePackage()
    original = p.data["Bold"]["descender_value"]
    calls = []

    def rounding(name, value):
        calls.append(value)
        object.__getattribute__(p, "data")[p.master][name] = round(value) if len(calls) == 1 else value

    p.__class__ = type(
        "Rounding",
        (FakePackage,),
        {"__setattr__": lambda self, name, value: rounding(name, value) if name.endswith("_value") else object.__setattr__(self, name, value)},
    )
    with pytest.raises(font_history.RolledBackError, match=r"descender -200 \(planned -200.4\)"):
        master_metrics.write_master_metrics(p, {"Bold": {"descender": -200.4}}, native=native(p))
    assert p.data["Bold"]["descender_value"] == original, "the rounded value must be restored"


def test_parse_when_fields_unordered_then_field_order():
    assert list(master_metrics.parse({"Bold": {"lineGap": 1, "ascender": 2}})["Bold"]) == [
        "ascender",
        "lineGap",
    ], "fields must follow FIELDS order"


def test_write_master_metrics_when_cap_height_alias_then_caps_height_written():
    p = FakePackage()
    result = master_metrics.write_master_metrics(p, {"Bold": {"capHeight": 702}}, native=native(p))
    assert result.values == {"Bold": {"capsHeight": 702.0}}, f"the alias reports capsHeight: {result.values}"
    assert p.data["Bold"]["capsHeight_value"] == 702.0, "capHeight must write capsHeight_value"
