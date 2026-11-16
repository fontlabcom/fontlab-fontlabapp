# this_file: tests/test_smallcap_capture.py
"""Native-shaped read-only capture with explicit name-table and group APIs."""

from types import SimpleNamespace as NS

import pytest

import fontlabapp.glyphs.smallcaps.capture as capture


def host(monkeypatch, *, groups=(), names=("A", "a", "a.sc"), skip=()):
    package = NS(
        id=12,
        fgId=77,
        isNull=False,
        master="Regular",
        packageLib={"public.skipExportGlyphs": list(skip)},
    )
    font = NS(
        info=NS(familyName="Owned"),
        glyphs=[
            NS(name=name, unicodes=[ord(name)] if len(name) == 1 else [])
            for name in names
        ],
    )
    table = NS(
        unc=lambda name: {"A": 65, "a": 97, "f": 102, "i": 105}.get(name, 0xFFFFFFFF)
    )
    calls = []

    def call(name, **kwargs):
        calls.append((name, kwargs))
        return {"classes": list(groups), "master": "Regular"}

    modules = {
        "fontlab": NS(CurrentFont=lambda: font),
        "fontgate": NS(fgNametable=lambda: table),
        "fontpr": NS(call=call),
    }
    monkeypatch.setattr(capture, "_native", modules.__getitem__)
    monkeypatch.setattr(capture.scripting, "current_package", lambda *a: package)
    return package, font, calls


def test_capture_when_native_metadata_then_detached_export_groups_and_report(
    monkeypatch,
):
    groups = [
        {"name": "a.sc", "left": True, "right": False, "glyph_names": ["a.sc"]},
        {"name": "A", "left": True, "right": True, "glyph_names": ["A"]},
    ]
    package, font, calls = host(monkeypatch, groups=groups, skip=("a",))
    report = capture.current_report()
    assert report["counts"] == {"smallcap": 1, "lower": 0, "upper": 1}, (
        'Expected report["counts"] == {"smallcap": 1, "lower": 0, "upper": 1}'
    )
    assert report["excluded_nonexporting"] == ["a"], (
        'Expected report["excluded_nonexporting"] == ["a"]'
    )
    assert report["kerning_mismatches"][0]["side"] == "left", (
        'Expected report["kerning_mismatches"][0]["side"] == "left"'
    )
    assert "skipExportGlyphs" in report["export_scope"], (
        'Expected "skipExportGlyphs" in report["export_scope"]'
    )
    assert calls == [
        ("list_kerning_classes", {"font_id": 77, "master_name": "Regular"})
    ], (
        'Expected calls == [("list_kerning_classes", {"font_id": 77, "master_name": "Regular"})]'
    )
    assert package.packageLib == {"public.skipExportGlyphs": ["a"]}, (
        'Expected package.packageLib == {"public.skipExportGlyphs": ["a"]}'
    )
    assert [g.name for g in font.glyphs] == ["A", "a", "a.sc"], (
        'Expected [g.name for g in font.glyphs] == ["A", "a", "a.sc"]'
    )


def test_capture_when_ligatures_suffixes_unknown_then_mapping_is_disclosed(monkeypatch):
    host(monkeypatch, names=("f_i.alt", "f_i.sc.alt", "mystery", ".notdef", "one"))
    report = capture.current_report()
    assert report["counts"] == {"smallcap": 1, "lower": 1, "upper": 0}, (
        'Expected report["counts"] == {"smallcap": 1, "lower": 1, "upper": 0}'
    )
    assert report["unclassified"] == ["mystery", ".notdef", "one"], (
        'Expected report["unclassified"] == ["mystery", ".notdef", "one"]'
    )
    assert report["orphan_smallcaps"] == [], 'Expected report["orphan_smallcaps"] == []'


def test_capture_when_no_font_then_no_panel_snapshot(monkeypatch):
    monkeypatch.setattr(capture.scripting, "current_package", lambda *a: None)
    with pytest.raises(ValueError, match="Open a font"):
        capture.current_report()


def test_capture_when_font_changes_then_no_stale_snapshot(monkeypatch):
    package, _, _ = host(monkeypatch)
    count = iter([package, None])
    monkeypatch.setattr(capture.scripting, "current_package", lambda *a: next(count))
    with pytest.raises(ValueError, match="changed"):
        capture.current_report()


def test_capture_when_deadline_expires_then_refuses_partial(monkeypatch):
    host(monkeypatch)
    tick = iter([0, 0, 4])
    with pytest.raises(TimeoutError, match="complete"):
        capture.current_report(clock=lambda: next(tick))


def test_capture_when_ambiguous_groups_then_never_silently_choose_first(monkeypatch):
    groups = [
        {"name": name, "left": True, "right": True, "glyph_names": ["a.sc"]}
        for name in ("a.sc", "a.alt.sc")
    ]
    host(monkeypatch, groups=groups)
    assert len(capture.current_report()["unknown_groups"]) == 2, (
        'Expected len(capture.current_report()["unknown_groups"]) == 2'
    )


def test_capture_when_missing_current_font_or_bad_export_policy_then_refuses(
    monkeypatch,
):
    package, font, _ = host(monkeypatch)
    package.packageLib["public.skipExportGlyphs"] = "a"
    with pytest.raises(ValueError, match="skipExportGlyphs"):
        capture.current_report()
    package.packageLib.clear()
    monkeypatch.setattr(capture, "_native", lambda name: NS(CurrentFont=lambda: None))
    with pytest.raises(ValueError, match="FontGate"):
        capture.current_report()


def test_capture_when_master_changes_then_rejects_snapshot(monkeypatch):
    package, _, calls = host(monkeypatch)
    def current(*args):
        if calls:
            package.master = "Bold"
        return package
    monkeypatch.setattr(capture.scripting, "current_package", current)
    with pytest.raises(ValueError, match="changed"):
        capture.current_report()


@pytest.mark.parametrize("code", [-1, 0xFFFFFFFF, 0xD800, 0x110000])
def test_character_when_unknown_or_invalid_then_no_character(code):
    assert capture._character(code) is None, "Invalid Unicode values must remain unknown"


def test_capture_when_uncased_unicode_then_not_classified_as_a_letter(monkeypatch):
    host(monkeypatch, names=("1",))
    assert capture.current_report()["counts"] == {"smallcap": 0, "lower": 0, "upper": 0}, "Digits have no letter case"
