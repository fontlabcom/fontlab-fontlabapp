# this_file: tests/test_master_text.py
"""Source workflow fidelity on detached, owned glyph facts."""

import pytest
from pathlib import Path
from fontlabapp.masters.text.model import analyze, font_maps, select_text
from fontlabapp.masters.text.settings import (
    FALLBACKS,
    load_presets,
    read_presets,
    load,
    save,
)
from test_case_coverage_settings import Memory


def test_exact_delimiters_all_words_masters_repeats_and_whitespace():
    cmap = {ord(c): c for c in "ab "}
    result = analyze(" ab ,a?b,,?", cmap, set(cmap.values()), ("R", "B"), 1)
    assert result.preview == " ab   ab  \nab ab \n", (
        "Keep each copy's final literal space and every final newline"
    )
    assert result.words == ((" ", "a", "b", " "), ("a", "b")), (
        "Do not strip source whitespace"
    )
    assert result.rows[-1] == (), "Final group newline survives native rows"
    assert result.rows[0][-1] == (None, ""), "Final copy has its space"
    assert [(d.word, d.offset, d.text) for d in result.dropped] == [
        (1, 1, "?"),
        (3, 0, "?"),
    ]
    stacked = analyze("ab,a", cmap, set(cmap.values()), ("R", "B"), 0)
    assert stacked.preview == "ab\nab\n\na\na\n\n"
    assert stacked.rows == (
        (("a", "R"), ("b", "R")),
        (("a", "B"), ("b", "B")),
        (),
        (("a", "R"),),
        (("a", "B"),),
        (),
        (),
    )


def test_named_tokens_alternative_encodings_and_complete_diagnostics():
    cmap, names, aliases = font_maps(
        (("a", (97, 65)), ("alternate", (97,)), ("unencoded", ()))
    )
    assert cmap == {97: "a", 65: "a"} and aliases == ((97, "a", "alternate"),)
    result = analyze(
        "aA,/unencoded /unencoded,/missing", cmap, names, ("R",), 1, mode="names"
    )
    assert result.words == (("a", "a"), ("unencoded", "unencoded"))
    assert result.dropped[-1].text == "/missing" and result.dropped[-1].kind == "token"
    assert result.preview == "aA \n/unencoded/unencoded \n"
    literal = analyze("/a", {47: "slash", 97: "a"}, {"slash", "a"}, ("R",), 1)
    assert literal.words == (("slash", "a"),), (
        "Character mode never reinterprets raw slash syntax"
    )


@pytest.mark.parametrize("text", ["", ",", "???"])
def test_empty_sanitation_refuses_explicitly(text):
    with pytest.raises(ValueError, match="usable") as caught:
        analyze(text, {}, set(), ("R",), 1)
    assert len(caught.value.comparison.dropped) == text.count("?"), (
        "Retain every omitted character even for empty results"
    )


@pytest.mark.parametrize(
    "masters,layout", [((), 1), (("",), 1), (("R", "R"), 1), (("R",), 2)]
)
def test_invalid_layout_or_master_domain_refuses(masters, layout):
    with pytest.raises(ValueError):
        analyze("a", {97: "a"}, {"a"}, masters, layout)


def test_input_precedence_and_no_selection():
    assert select_text("a", ("b", "c"), 1) == "a"
    assert select_text("a", ("b", "c"), 1, immediate=0) == "b"
    assert select_text("", ("b", "c"), 1) == "c"
    for index in (-1, 3):
        with pytest.raises(ValueError, match="preset"):
            select_text("", ("b",), index)


def test_presets_original_fallbacks_optional_local_utf8_and_manual(tmp_path):
    assert (
        len(FALLBACKS) == 4
        and FALLBACKS[3]
        == "00000,00100,00200,00300,00400,00500,00600,00700,00800,00900"
    )
    assert (
        FALLBACKS[0].startswith("arrowroot,barley,chervil")
        and "marjioram" in FALLBACKS[0]
    )
    assert FALLBACKS[1] == ",".join(
        s[:1].upper() + s[1:] for s in FALLBACKS[0].split(",")
    )
    assert FALLBACKS[2] == FALLBACKS[0].upper()
    result = load_presets(tmp_path)
    assert result.lines == FALLBACKS and "fallback" in result.notice
    path = tmp_path / "MasterBlaster-presets.txt"
    path.write_bytes("\ufeff a,b \r\nżółć,漢字\r\n\r\n".encode())
    assert read_presets(path) == (" a,b ", "żółć,漢字")
    assert load_presets(tmp_path).lines == (" a,b ", "żółć,漢字")
    path.write_bytes(b"\xff")
    assert load_presets(tmp_path).lines == FALLBACKS
    with pytest.raises(UnicodeError):
        read_presets(path)
    path.write_text("")
    with pytest.raises(ValueError):
        read_presets(path)


def test_settings_defaults_roundtrip_owned_keys_and_errors():
    settings = Memory()
    assert load(settings) == ("", 1, None), (
        "Blank custom and Side-by-side are source defaults"
    )
    save(settings, " 汉 a ", 0)
    save(settings, geometry=b"owned")
    assert load(settings) == (" 汉 a ", 0, b"owned")
    assert set(settings.data) == {"inputCustom", "layout", "geometry"}
    settings.data["layout"] = 2
    with pytest.raises(ValueError):
        load(settings)
    settings.data["layout"] = 1
    settings.writable = False
    with pytest.raises(OSError):
        save(settings, "a", 1)
    settings.error = 1
    with pytest.raises(OSError):
        load(settings)


def test_every_engine_and_file_loop_is_cooperatively_bounded(tmp_path):
    def stop():
        raise TimeoutError("owned deadline")

    for call in (
        lambda: analyze("a", {97: "a"}, {"a"}, ("R",), 1, check=stop),
        lambda: font_maps((("a", (97,)),), check=stop),
        lambda: read_presets(tmp_path / "none", check=stop),
        lambda: load(Memory(), check=stop),
        lambda: save(Memory(), "a", 1, check=stop),
    ):
        with pytest.raises(TimeoutError):
            call()


def test_mapped_control_nonbmp_and_whitespace_are_exact_named_slots():
    text = " \0\t\n\u00a0\u2028\u2029😀 "
    cmap = {ord(c): f"g{ord(c)}" for c in text}
    result = analyze(text, cmap, set(cmap.values()), ("R", "B", "X"), 1)
    assert result.preview == (text + " ") * 3 + "\n"
    assert result.words[0] == tuple(cmap[ord(c)] for c in text)
    assert len(result.rows[0]) == (len(text) + 1) * 3


def test_cancellation_at_every_engine_loop_boundary_never_returns_partial():
    calls = []
    facts = (("a", (97, 65)), ("b", (98,)), ("space", (32,)))
    font_maps(facts, check=lambda: calls.append(1))
    for stop_at in range(1, len(calls) + 1):
        count = []

        def check():
            count.append(1)
            if len(count) == stop_at:
                raise InterruptedError("owned cancellation")

        with pytest.raises(InterruptedError):
            font_maps(facts, check=check)
    calls.clear()
    analyze(
        "a?/a /a, b,b",
        {97: "a", 98: "b", 32: "space"},
        {"a", "b", "space"},
        ("R", "B"),
        1,
        mode="names",
        check=lambda: calls.append(1),
    )
    for stop_at in range(1, len(calls) + 1):
        count = []

        def check():
            count.append(1)
            if len(count) == stop_at:
                raise InterruptedError("owned cancellation")

        with pytest.raises(InterruptedError):
            analyze(
                "a?/a /a, b,b",
                {97: "a", 98: "b", 32: "space"},
                {"a", "b", "space"},
                ("R", "B"),
                1,
                mode="names",
                check=check,
            )


@pytest.mark.parametrize(
    "facts",
    [
        (("", (97,)),),
        (("a", (97,)), ("a", (98,))),
        (("a", (-1,)),),
        (("a", (0xD800,)),),
        (("a", (0x110000,)),),
    ],
)
def test_maps_refuse_ambiguous_or_invalid_font_data(facts):
    with pytest.raises(ValueError):
        font_maps(facts)


@pytest.mark.parametrize("failure", [InterruptedError, TimeoutError])
def test_optional_preset_lookup_does_not_turn_one_shot_cancellation_into_fallback(
    tmp_path, failure
):
    checks = []

    def cancel_once():
        checks.append(1)
        if len(checks) == 1:
            raise failure("stop acquisition")

    with pytest.raises(failure, match="stop acquisition"):
        load_presets(tmp_path, check=cancel_once)


def test_complete_large_utf8_file_all_chunk_line_and_cleanup_boundaries(tmp_path):
    path = tmp_path / "MasterBlaster-presets.txt"
    payload = ("漢字" * 3000 + ",a\r\n") * 3
    path.write_bytes(("\ufeff" + payload).encode("utf-8"))
    calls = []
    expected = tuple(("漢字" * 3000 + ",a") for _ in range(3))
    assert read_presets(path, check=lambda: calls.append(1)) == expected
    for stop_at in range(1, len(calls) + 1):
        count = []

        def cancelled():
            count.append(1)
            if len(count) == stop_at:
                raise InterruptedError("file cancelled")

        with pytest.raises(InterruptedError):
            read_presets(path, check=cancelled)
    # Every failed read released its handle; replacement remains possible.
    path.write_text("a,b")
    assert read_presets(path) == ("a,b",)


def test_presets_directory_when_no_explicit_then_user_folder_scripts(monkeypatch, tmp_path):
    import types
    from fontlabapp.masters.text import settings as mts

    prefs = types.SimpleNamespace(dataPathDefault=str(tmp_path))
    fake = types.SimpleNamespace(flPreferences=lambda: prefs)
    monkeypatch.setattr(mts, "_native", lambda name: fake)
    assert mts.presets_directory() == tmp_path / "Scripts"
    assert mts.presets_directory(tmp_path / "x") == tmp_path / "x"
    prefs.dataPathDefault = lambda: str(tmp_path / "callable")
    assert mts.presets_directory() == tmp_path / "callable" / "Scripts"


def test_presets_directory_when_no_host_then_working_directory(monkeypatch):
    from fontlabapp.masters.text import settings as mts

    def missing(name):
        raise RuntimeError("requires the native API")

    monkeypatch.setattr(mts, "_native", missing)
    assert mts.presets_directory() == Path.cwd()


def test_load_presets_when_read_or_missing_then_notice_names_path(tmp_path):
    missing = load_presets(tmp_path)
    assert str(tmp_path / "MasterBlaster-presets.txt") in missing.notice
    (tmp_path / "MasterBlaster-presets.txt").write_text("a,b\n", encoding="utf-8")
    found = load_presets(tmp_path)
    assert found.lines == ("a,b",)
    assert str(tmp_path / "MasterBlaster-presets.txt") in found.notice
