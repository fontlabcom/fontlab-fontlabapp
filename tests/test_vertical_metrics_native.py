# this_file: tests/test_vertical_metrics_native.py
"""Owned fontpr JSON controls test complete registry/master fencing and parsing."""

from copy import deepcopy

import pytest

import fontlabapp.metrics.vertical.native as api


def master(name="Regular", ascender=800):
    return {
        "fontMaster": {
            "name": name,
            "ascender": ascender,
            "descender": -200,
            "otherData": {
                "hhea_ascender": "800",
                "hhea_descender": -200,
                "hhea_line_gap": "0",
            },
        }
    }


@pytest.fixture
def host(monkeypatch):
    fonts = [
        {
            "id": 101,
            "file_name": "/owned/First.vfc",
            "full_name": "First",
            "family_name": "First",
            "masters_count": 2,
        },
        {
            "id": 202,
            "file_name": "",
            "full_name": "Second",
            "family_name": "Second",
            "masters_count": 1,
        },
    ]
    data = {
        101: {"masters": [master(), master("Bold", 900)]},
        202: {"masters": [master("Medium")]},
    }
    calls = []

    def call(name, **kwargs):
        calls.append((name, kwargs))
        return deepcopy(
            {"fonts": fonts} if name == "list_fonts" else data[kwargs["font_id"]]
        )

    monkeypatch.setattr(api, "_call", call)
    return fonts, data, calls, call


def test_every_font_and_master_uses_raw_json_without_current_master_switch(host):
    report = api.capture()
    assert [(row.font_id, row.document, row.master) for row in report.rows] == [
        (101, "First.vfc", "Regular"),
        (101, "First.vfc", "Bold"),
        (202, "Second", "Medium"),
    ]
    assert report.rows[0].values == (800, -200, 0, 800, -200, 0, 0, 0)
    assert {name for name, _ in host[2]} == {"list_fonts", "get_font_info"}
    assert [args["font_id"] for name, args in host[2] if name == "get_font_info"] == [
        101,
        202,
        101,
        202,
    ]


def test_missing_hhea_is_unset_and_zero_remains_explicit(host):
    data = host[1]
    data[101]["masters"][0]["fontMaster"]["otherData"] = {}
    data[101]["masters"][1]["fontMaster"]["otherData"]["hhea_ascender"] = "0"
    report = api.capture()
    assert report.rows[0].values[3:6] == (None, None, None)
    assert report.rows[1].values[3] == 0
    assert "❌ hheaAscender" in api.render(report)


@pytest.mark.parametrize(
    "problem",
    [
        "no_fonts",
        "duplicate_id",
        "zero_masters",
        "missing_ascender",
        "missing_master_name",
        "wrong_wrapper",
        "count_mismatch",
        "bad_number",
        "nonfinite",
        "bad_other",
        "bad_fonts",
    ],
)
def test_unreadable_registry_or_master_never_returns_a_valid_prefix(host, problem):
    fonts, data, _, _ = host
    if problem == "no_fonts":
        fonts.clear()
    if problem == "duplicate_id":
        fonts[1]["id"] = 101
    if problem == "zero_masters":
        fonts[1]["masters_count"] = 0
    if problem == "missing_ascender":
        del data[202]["masters"][0]["fontMaster"]["ascender"]
    if problem == "missing_master_name":
        del data[202]["masters"][0]["fontMaster"]["name"]
    if problem == "wrong_wrapper":
        data[202]["masters"] = [{}]
    if problem == "count_mismatch":
        data[202]["masters"] = []
    if problem == "bad_number":
        data[202]["masters"][0]["fontMaster"]["otherData"]["hhea_ascender"] = "bad"
    if problem == "nonfinite":
        data[202]["masters"][0]["fontMaster"]["ascender"] = float("nan")
    if problem == "bad_other":
        data[202]["masters"][0]["fontMaster"]["otherData"] = []
    if problem == "bad_fonts":
        fonts[1]["file_name"] = None
    with pytest.raises((ValueError, TypeError, KeyError)):
        api.capture()


@pytest.mark.parametrize("drift", ["metrics", "master_order", "registry", "font_label"])
def test_source_changes_between_reads_refuse_the_entire_report(
    host, monkeypatch, drift
):
    fonts, data, _, call = host
    count = []

    def changed(name, **kwargs):
        if name == "list_fonts":
            count.append(1)
            if len(count) == 2:
                if drift == "metrics":
                    data[202]["masters"][0]["fontMaster"]["ascender"] += 1
                if drift == "master_order":
                    data[101]["masters"].reverse()
                if drift == "registry":
                    fonts.reverse()
                if drift == "font_label":
                    fonts[1]["full_name"] = "Changed"
        return call(name, **kwargs)

    monkeypatch.setattr(api, "_call", changed)
    with pytest.raises(ValueError, match="changed"):
        api.capture()


def test_native_call_failure_and_deadline_do_not_publish_partial_rows(
    host, monkeypatch
):
    def fail(name, **kwargs):
        raise RuntimeError("owned read failure")

    monkeypatch.setattr(api, "_call", fail)
    with pytest.raises(RuntimeError, match="owned read failure"):
        api.capture()
    monkeypatch.setattr(api, "monotonic", lambda: 0)
    with pytest.raises(TimeoutError):
        api._registry(-1)


def test_native_tool_bridge_preserves_keyword_id(monkeypatch):
    from types import SimpleNamespace

    calls = []
    monkeypatch.setattr(
        api,
        "_native",
        lambda name: SimpleNamespace(
            call=lambda *a, **k: calls.append((name, a, k)) or {"owned": True}
        ),
    )
    assert api._call("get_font_info", font_id=9) == {"owned": True}
    assert calls == [("fontpr", ("get_font_info",), {"font_id": 9})]


@pytest.mark.parametrize(
    "value,expected",
    [("1.125", 1.125), ("-200", -200), (2**65 + 1, 2**65 + 1), (0.125, 0.125)],
)
def test_native_numeric_text_preserves_fraction_and_large_integer(value, expected):
    assert api._number(value) == expected


@pytest.mark.parametrize("value", [None, True, [], float("inf"), "nan"])
def test_invalid_native_values_cannot_become_zero(value):
    with pytest.raises((ValueError, TypeError)):
        api._number(value)


@pytest.mark.parametrize(
    "case", ["family", "untitled", "empty_master", "duplicate_label"]
)
def test_display_labels_do_not_merge_native_identities(host, case):
    fonts, data, _, _ = host
    if case == "family":
        fonts[1]["full_name"] = ""
    if case == "untitled":
        fonts[1]["full_name"] = fonts[1]["family_name"] = ""
    if case == "empty_master":
        data[202]["masters"][0]["fontMaster"]["name"] = ""
    if case == "duplicate_label":
        fonts[1]["file_name"] = "/owned/First.vfc"
    report = api.capture()
    assert report.fonts == 2 and len(report.rows) == 3
    assert (
        report.rows[-1].document
        == {
            "family": "Second",
            "untitled": "Untitled 202",
            "empty_master": "Second",
            "duplicate_label": "First.vfc",
        }[case]
    )
    if case == "empty_master":
        assert report.rows[-1].master == ""


def test_final_registry_fence_catches_close_after_second_complete_read(
    host, monkeypatch
):
    fonts, _, _, call = host
    scans = []

    def changed(name, **kwargs):
        if name == "list_fonts":
            scans.append(1)
            if len(scans) == 3:
                fonts.pop()
        return call(name, **kwargs)

    monkeypatch.setattr(api, "_call", changed)
    with pytest.raises(ValueError, match="changed"):
        api.capture()


def test_clock_overrun_after_native_call_discards_complete_result(host, monkeypatch):
    _, _, _, call = host
    clock = [0.0]

    def late(name, **kwargs):
        result = call(name, **kwargs)
        if name == "get_font_info":
            clock[0] = 3.0
        return result

    monkeypatch.setattr(api, "_call", late)
    monkeypatch.setattr(api, "monotonic", lambda: clock[0])
    with pytest.raises(TimeoutError, match="no partial"):
        api.capture()
