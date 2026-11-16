# this_file: tests/test_kerning_selection.py
"""Independent selected-exception and text plans using owned native doubles."""

from types import SimpleNamespace as NS

import fontlabapp.kerning.batch as batch
import fontlabapp.kerning.selection as api
import pytest
from test_kerning_batch import font_double


def test_exception_precedence_redundancy_and_class_sides(monkeypatch):
    font, kerns, _, _ = font_double(monkeypatch)
    kerns["Light"].groups["Both"] = (["T"], "KernBothSide")
    left, right = api.class_maps(font, "Light")
    assert left == {"A": "@L_A", "T": "@Both"} and right == {"V": "@R_V", "T": "@Both"}
    values = {
        ("A", "V"): 0,
        ("A", "@R_V"): 0,
        ("@L_A", "V"): -40,
        ("@L_A", "@R_V"): -80,
    }
    assert api.exceptions(values, left, right) == [
        (("@L_A", "V"), -40, ("@L_A", "@R_V"), -80),
        (("A", "@R_V"), 0, ("@L_A", "@R_V"), -80),
        (("A", "V"), 0, ("A", "@R_V"), 0),
    ], "Glyph-right-class precedes left-class-glyph and the two-class fallback"
    kerns["Light"].values = values
    assert api.find(font, ["Light"])[-1] == ("Light", ("A", "V"), 0, ("A", "@R_V"), 0)


def test_words_keep_original_token_and_unknown_character_semantics():
    glyphs = {name: NS(name=name) for name in ("A", "V", "Aacute")}
    font = NS(findName=glyphs.get, findUnicode=lambda n: glyphs.get(chr(n)))
    words = api.parse_words("AVAVA A?V /Aacute/V /unknown/A /AacuteV //V", font)
    assert words == [
        ["A", "V", "A", "V", "A"],
        ["A", "V"],
        ["Aacute", "V"],
        ["A"],
        [],
        ["V"],
    ]
    assert api.adjacent_pairs(words) == [("A", "V"), ("V", "A"), ("Aacute", "V")]
    assert api.parse_words("", font) == [] and api.adjacent_pairs([[], ["A"]]) == []


def test_explicit_zero_precedes_effective_and_failed_read_is_not_zero():
    kern = NS(get=lambda pair: -80)
    assert api.current_value(kern, {("A", "V"): 0}, ("A", "V")) == (0, True)
    assert api.current_value(kern, {}, ("A", "V")) == (-80, False)
    kern.get = lambda pair: None
    assert api.current_value(kern, {}, ("A", "V")) == (0, False)
    kern.get = lambda pair: (_ for _ in ()).throw(RuntimeError("read failed"))
    with pytest.raises(RuntimeError, match="read failed"):
        api.current_value(kern, {}, ("A", "V"))


def test_text_add_set_explicit_zero_and_ticked_only_across_masters(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    for kern in kerns.values():
        kern.get = lambda pair: -80
    values = api.text_values(font, font.masters, [("A", "V"), ("V", "A")])
    assert values[("A", "V"), "Light"] == (-10, True)
    assert values[("V", "A"), "Bold"] == (-80, False)
    plan = api.text_plan(font.masters, [("V", "A")], values, "add", -10)
    assert plan == {"Light": {("V", "A"): -90}, "Bold": {("V", "A"): -90}}
    batch.write_kerning(font, plan, "Text")
    assert kerns["Light"].values == {("A", "V"): -10, ("T", "V"): 0, ("V", "A"): -90}
    assert len(history) == 2
    assert api.text_plan(["Light"], [("A", "V")], values, "set", 0) == {
        "Light": {("A", "V"): 0}
    }
    assert api.text_plan(font.masters, [], values, "add", -10) == {}
    with pytest.raises(ValueError, match="mode"):
        api.text_plan(font.masters, [], values, "invalid", -10)


def test_late_invalid_text_plan_and_missing_preview_refuse(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    values = {(("A", "V"), "Light"): (-10, True), (("A", "V"), "Bold"): (2000, True)}
    plan = api.text_plan(font.masters, [("A", "V")], values, "add", 1)
    with pytest.raises(ValueError, match="save/reopen range"):
        batch.write_kerning(font, plan, "Text")
    assert not history and kerns["Light"].values[("A", "V")] == -10
    with pytest.raises(ValueError, match="preview"):
        api.text_plan(["Missing"], [("A", "V")], values, "set", 0)


def test_manual_exception_selection_deletes_only_ticked_override(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Light"].values[("@L_A", "V")] = -69
    kerns["Light"].values[("A", "V")] = -40
    rows = api.find(font, ["Light"])
    assert rows == [("Light", ("A", "V"), -40, ("@L_A", "V"), -69)]
    batch.write_kerning(font, api.exception_plan(rows), "Remove")
    assert kerns["Light"].values == {("@L_A", "V"): -69, ("T", "V"): 0}
    assert len(history) == 2 and kerns["Bold"].values[("A", "V")] == -30
    assert api.exception_plan([]) == {}


def test_empty_text_and_exception_plans_do_not_create_history(monkeypatch):
    font, _, history, _ = font_double(monkeypatch)
    font.checkInitHistoryState = lambda _: pytest.fail(
        "Empty selection initialized history"
    )
    assert not batch.write_kerning(font, api.exception_plan([]), "Remove")
    assert not batch.write_kerning(
        font, api.text_plan(font.masters, [], {}, "set", 0), "Text"
    )
    assert history == []


def test_text_batch_late_native_failure_reports_partial_outcome(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    values = {(("A", "V"), "Light"): (-10, True), (("A", "V"), "Bold"): (-30, True)}
    kerns["Bold"].fail = True
    with pytest.raises(RuntimeError, match="partially changed.*Undo.*Refresh"):
        batch.write_kerning(
            font, api.text_plan(font.masters, [("A", "V")], values, "add", -10), "Text"
        )
    assert (
        kerns["Light"].values[("A", "V")] == -20
        and kerns["Bold"].values[("A", "V")] == -30
    )
    assert len(history) == 2 and history[0] != history[1]
