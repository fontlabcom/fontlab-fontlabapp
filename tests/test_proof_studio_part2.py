# this_file: tests/test_proof_studio_part2.py
"""Proof Studio part 2 generators (Phase D A7, T9): pure, Qt-free parity.

Random (fixed seeds), Real text (corpus pins), Word finder, Waterfall, Text by
master, Master text comparison, Text filter and Saved sample. Native openers
and settings are fakes: ``ReadOnly`` packages fail on any write and the
settings fake records every write, so persistence is exactly the originals'.
"""

import hashlib
import json
import random
import sys
from importlib.resources import files
from types import SimpleNamespace as NS

import pytest

from fontlabapp.core import scripting
from fontlabapp.studios.proof_studio import generators as registry
from fontlabapp.studios.proof_studio.generators import Context, Facts, Options, Proof

ENGLISH_SHA = "d32bf1a4fedf7428744a84427368cd5054184deca88cc5314345cf934511cfc5"
SPANISH_SHA = "4a38830c689cc037b4935590df77fac435734e4272fa2d10796ef54514272110"
PART2 = {
    "Random Numbers": ("random", "numbers"),
    "Random Lowercase Nontext": ("random", "lowercase-nontext"),
    "Random Title Nontext": ("random", "title-nontext"),
    "Random Uppercase Nontext": ("random", "uppercase-nontext"),
    "Random Lowercase Words": ("random", "lowercase-words"),
    "Random Title Words": ("random", "title-words"),
    "Random Uppercase Words": ("random", "uppercase-words"),
    "Real English Text": ("real-text", "english"),
    "Real Spanish Text": ("real-text", "spanish"),
    "Text Filter": ("text-filter", "text-filter"),
    "Saved Proof Sample": ("saved-sample", "saved-sample"),
    "Waterfall": ("waterfall", "waterfall"),
    "Text By Master": ("text-by-master", "text-by-master"),
}
FACTS = Facts({ord(c): c for c in "Hamburgefonstiv"} | {0x20: "space", 0x30: "zero"},
              frozenset([*"Hamburgefonstiv", "space", "zero", "a.alt"]), ("Light", "Bold"), "Bold")


@pytest.fixture(autouse=True)
def drop_studio_modules():
    yield
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)


class ReadOnly:
    """A package fake: id, masters and glyph count readable; any write fails."""

    def __init__(self, **values):
        object.__setattr__(self, "_values", values)

    def __getattr__(self, name):
        try:
            return self._values[name]
        except KeyError:
            raise AssertionError(f"read package.{name}") from None

    def __setattr__(self, name, value):
        raise AssertionError(f"wrote package.{name}")


class Settings:
    """QSettings fake: records writes; ``status_code`` simulates a failed sync."""

    def __init__(self, values=None, status_code=0, writable=True):
        self.values, self.status_code, self.writable, self.writes = dict(values or {}), status_code, writable, []

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):  # noqa: N802 - Qt name
        self.writes.append(("set", key, value))
        self.values[key] = value

    def remove(self, key):
        self.writes.append(("remove", key))
        self.values.pop(key, None)

    def sync(self):
        pass

    def status(self):
        return self.status_code

    def isWritable(self):  # noqa: N802 - Qt name
        return self.writable


def _gen(key):
    return {g.key: g for g in registry.generators()}[key]


def _opened(monkeypatch, module, package=None):
    """Patch the module's current package and the text-tab opener; return the opened calls."""
    calls = []
    backends = scripting.proof_studio_backends()
    fake = NS(**vars(backends))
    fake.text_tab = NS(open_text_tab=lambda text, *, expected_id: calls.append((text, expected_id)))
    monkeypatch.setattr(module, "current_package", lambda: package)
    monkeypatch.setattr(module, "proof_studio_backends", lambda: fake)
    return calls


# Registry ----------------------------------------------------------------------
def test_registry_when_part2_then_every_absorbed_script_maps_once():
    registry.generators()
    part2 = {g.key for g in registry.generators()} - {"between", "surround", "kerning-texts"}
    mapped = {}
    for g in registry.generators():
        if g.key in part2:
            for key, title in g.scripts.items():
                mapped.setdefault(title, []).append((g.key, key))
    assert mapped.pop("Word Finder") == [("word-finder", c) for c in ("lowercase", "Capitalised", "UPPERCASE")]
    assert mapped.pop("Master Text Comparison") == [("master-text", "characters"), ("master-text", "names")]
    assert {title: pairs[0] for title, pairs in mapped.items()} == PART2
    assert all(len(pairs) == 1 for pairs in mapped.values())


def test_registry_when_tabs_then_filter_and_saved_sample_join_real_text():
    assert [g.key for g in registry.for_tab("Real text")] == ["real-text", "text-filter", "saved-sample"]
    assert [g.key for g in registry.for_tab("By master")] == ["text-by-master", "master-text"]
    assert not _gen("word-finder").opens and not _gen("waterfall").opens
    assert _gen("random").opens and _gen("random").seeded and not _gen("word-finder").seeded


def test_proof_when_views_given_then_per_part_and_defaults():
    proof = Proof(("a\nb", "c"), previews=("P0", "P1"), sizes=(10.0,), layers=("Bold",), kerning=False)
    assert proof.preview(1) == "P1" and proof.preview(5) == ""
    assert proof.view(0) == (10.0, "Bold", False) and proof.view(1) == (72.0, None, False)
    assert Proof(("a\nb",)).preview(0) == "a b" and Proof(("x",)).view(0) == (72.0, None, True)
    context = Context("k", {}, proof=proof, part=1)
    assert context.text() == "c" and Context("k", {}).text() == ""


# Random --------------------------------------------------------------------------
@pytest.mark.parametrize("mode", ["numbers", "lowercase-nontext", "title-nontext", "uppercase-nontext",
                          "lowercase-words", "title-words", "uppercase-words"])
def test_random_when_seeded_then_backend_draw_with_that_rng(mode):
    backend = scripting.proof_studio_backends().random
    proof = _gen("random").make(mode, Options(seed=242))
    assert proof.parts == (backend.generate(mode, rng=random.Random(242)),)
    assert _gen("random").make(mode, Options(seed=242)) == proof, "same seed, same proof"


def test_random_when_unseeded_then_module_rng_as_scripts(monkeypatch):
    random.seed(7)
    first = _gen("random").make("numbers", Options()).parts[0]
    random.seed(7)
    assert scripting.proof_studio_backends().random.generate("numbers") == first
    assert set(first) <= set("0123456789 ")


def test_random_when_opened_then_one_tab_or_no_font_refusal(monkeypatch):
    from fontlabapp.studios.proof_studio.generators import random_proofs as module

    calls = _opened(monkeypatch, module, ReadOnly(id=9))
    proof = _gen("random").make("title-words", Options(seed=1))
    module.open_current("title-words", Context("title-words", {}, proof=proof))
    module.open_tab("numbers")
    assert calls[0] == (proof.parts[0], 9) and calls[1][1] == 9 and len(calls) == 2
    _opened(monkeypatch, module, None)
    for call in (lambda: module.open_tab("numbers"), lambda: module.open_current("numbers", Context("numbers", {}))):
        with pytest.raises(ValueError, match="^Open a font before generating a random proof.$"):
            call()


# Real text -----------------------------------------------------------------------
def test_real_text_when_corpus_loaded_then_byte_identical_to_scriptmix():
    from fontlabapp.studios.proof_studio.generators import real_text

    data = json.loads(files("fontlabapp").joinpath("proof", "real_text_passages.json").read_text("utf-8"))
    assert sorted(data) == ["english", "spanish"]
    for language, sha in (("english", ENGLISH_SHA), ("spanish", SPANISH_SHA)):
        found = real_text.passages(language)
        assert len(found) == 24
        assert hashlib.sha256(json.dumps(list(found), ensure_ascii=False).encode()).hexdigest() == sha


def test_real_text_when_seeded_then_five_distinct_passages_and_final_space():
    from fontlabapp.studios.proof_studio.generators import real_text

    proof = _gen("real-text").make("spanish", Options(seed=3))
    expected = " ".join(random.Random(3).sample(real_text.passages("spanish"), 5)) + " "
    assert proof.parts == (expected,) and expected.endswith(" ")
    assert proof.parts[0].startswith(tuple(real_text.passages("spanish")))


def test_real_text_when_bad_corpus_then_original_refusals(monkeypatch):
    from fontlabapp.studios.proof_studio.generators import real_text

    monkeypatch.setattr(real_text, "passages", lambda language: ())
    with pytest.raises(ValueError, match="^No proof passages are available.$"):
        real_text.proof_text("english")
    for bad in ("\0", " ", " ", " "):
        monkeypatch.setattr(real_text, "passages", lambda language, bad=bad: ("a", "b", "c", "d", "e" + bad))
        with pytest.raises(ValueError, match="^Unsupported proof character; text cannot pass intact.$"):
            real_text.proof_text("english")


def test_real_text_when_opened_then_int_id_or_no_font(monkeypatch):
    from fontlabapp.studios.proof_studio.generators import real_text

    calls = _opened(monkeypatch, real_text, ReadOnly(id="12"))
    real_text.open_tab("english")
    real_text.open_current("english", Context("english", {}, proof=Proof(("shown ",))))
    assert calls[0][1] == 12 and calls[0][0].endswith(" ") and calls[1] == ("shown ", 12)
    _opened(monkeypatch, real_text, None)
    for call in (lambda: real_text.open_tab("english"), lambda: real_text.open_current("x", Context("x", {}))):
        with pytest.raises(ValueError, match="^Open a font before creating a prose proof.$"):
            call()


# Word finder ---------------------------------------------------------------------
def test_word_finder_when_font_letters_then_original_filters_and_text():
    api = scripting.proof_api()
    available = {chr(c) for c in FACTS.cmap}
    values = {"must": " ab ", "only": "", "min_len": 3, "max_len": 12}
    proof = _gen("word-finder").make("lowercase", Options(values=values, facts=FACTS))
    words = api.find_words(api.WORDS, available, "lowercase", "ab", "", 3, 12)
    assert proof.parts == (" ".join(words),)
    assert proof.note.startswith(f"{len(api.WORDS)} English and Latin words; showing those the font can set with its "
                                 f"{len(available)} characters.")
    assert proof.note.endswith(f"{len(words)} word{'s' if len(words) != 1 else ''}")
    upper = _gen("word-finder").make("UPPERCASE", Options(values=values, facts=FACTS))
    assert upper.parts == ("",) and upper.note.endswith("0 words")


def test_word_finder_when_no_font_then_original_notice_and_defaults():
    proof = _gen("word-finder").make("lowercase", Options())
    assert proof.parts == ("",) and proof.note == "Open a font with encoded glyphs first. 0 words"
    fields = {f.key: f for f in _gen("word-finder").fields}
    assert (fields["min_len"].default, fields["max_len"].default, fields["min_len"].minimum, fields["max_len"].maximum) \
        == (3, 12, 1, 20)
    assert fields["must"].placeholder == "e.g. kz"
    assert fields["only"].placeholder == "e.g. hamburgefonstiv (empty = any)"
    assert [label for label, _ in _gen("word-finder").choices] == ["lowercase", "Capitalised", "UPPERCASE"]


# Waterfall and Text by master -------------------------------------------------------
def test_waterfall_when_defaults_then_one_part_per_size_on_active_master():
    proof = _gen("waterfall").make("waterfall", Options(values={"text": "Ham /a.alt x", "sizes": "4, 12 x 500 24",
                                                                 "master": ""}, facts=FACTS))
    assert proof.sizes == (4.0, 12.0, 24.0) and proof.labels == ("4 px", "12 px", "24 px")
    assert proof.layers == ("Bold",) * 3 and proof.kerning is False
    assert proof.parts == ("Ham /a.alt x",) * 3
    assert proof.preview(0) == "/H /a /m /space /a.alt", "one space after /name is syntax; x is missing"
    assert proof.canvas == (("H", "a", "m", "space", "a.alt", None), (4.0, 12.0, 24.0), "Bold"), "WaterfallView keeps 4 px"
    assert _gen("waterfall").canvas == "WaterfallView"
    assert proof.note == ("Master Bold · 6 glyphs · advance widths, no kerning. Use /name for unencoded glyphs. "
                          "TMetrics shows 1 size(s) below 8 px at 8 px.")
    named = _gen("waterfall").make("waterfall", Options(values={"master": "Light"}, facts=FACTS))
    assert named.layers[0] == "Light" and len(named.parts) == 9
    assert _gen("waterfall").make("waterfall", Options()).note == "Open a font first."
    fields = {f.key: f.default for f in _gen("waterfall").fields}
    assert fields == {"text": "Hamburgefonstiv 0123", "sizes": "10 12 14 18 24 32 48 64 96", "master": ""}


def test_text_by_master_when_two_masters_then_rows_in_order_without_kerning():
    proof = _gen("text-by-master").make("text-by-master", Options(values={"text": "Hamz", "size": 60}, facts=FACTS))
    assert proof.labels == ("Light", "Bold") and proof.layers == ("Light", "Bold")
    assert proof.sizes == (60.0, 60.0) and proof.kerning is False and proof.parts == ("Hamz", "Hamz")
    assert proof.note == "2 masters · 4 glyphs · advance widths, no kerning."
    assert proof.canvas == (("H", "a", "m", None), 60.0) and _gen("text-by-master").canvas == "MasterRows"
    assert _gen("text-by-master").make("text-by-master", Options()).note == "Open a font first."
    size = {f.key: f for f in _gen("text-by-master").fields}["size"]
    assert (size.default, size.minimum, size.maximum) == (48, 12, 160)


# Text filter -----------------------------------------------------------------------
def test_text_filter_when_filtering_then_original_regex_and_defaults():
    backends = scripting.proof_studio_backends()
    gen = _gen("text-filter")
    fields = {f.key: f.default for f in gen.fields}
    assert fields == {"input": "", "characters": backends.text_filter.DEFAULT_CHARACTERS}
    assert gen.settings == ("FontLab", "ScriptTextFilter")
    proof = gen.make("text-filter", Options(values={"input": "Héllo, wörld 42!", "characters": "a-z ,"}))
    assert proof.parts == ("llo, wrld ",) and proof.note == "Kept 10 characters."
    import re

    with pytest.raises(re.error):
        gen.make("text-filter", Options(values={"input": "x", "characters": "z-a"}))


def test_text_filter_when_loaded_saved_reset_then_original_keys_only():
    gen = _gen("text-filter")
    from fontlabapp.studios.proof_studio.generators import text_filter

    settings = Settings({"input": "kept", "output": "old", "characters": "a-z"})
    loaded = gen.load(settings)
    assert loaded.values == {"input": "kept", "characters": "a-z"} and settings.writes == []
    assert loaded.status == "Input and output are saved for the next session."
    gen.save(settings, {"input": "in", "characters": "a-z"}, Proof(("n",)))
    assert settings.writes == [("set", "input", "in"), ("set", "output", "n"), ("set", "characters", "a-z")]
    settings.writes.clear()
    outcome = text_filter.reset(Context("text-filter", {}, settings))
    assert settings.writes == [("remove", "output"), ("remove", "characters")] and settings.values == {"input": "in"}
    assert outcome.values == {"characters": scripting.proof_studio_backends().text_filter.DEFAULT_CHARACTERS}
    with pytest.raises(OSError, match="read-only"):
        gen.save(Settings(writable=False), {"input": "", "characters": ""}, Proof(()))


def test_text_filter_when_opened_then_output_tab_or_no_font(monkeypatch):
    from fontlabapp.studios.proof_studio.generators import text_filter

    calls = _opened(monkeypatch, text_filter, ReadOnly(id=5))
    text_filter.open_current("text-filter", Context("text-filter", {}, proof=Proof(("out",))))
    assert calls == [("out", 5)]
    _opened(monkeypatch, text_filter, None)
    with pytest.raises(ValueError, match="Reopen this tool with a font"):
        text_filter.open_current("text-filter", Context("text-filter", {}, proof=Proof(("out",))))


# Saved sample ----------------------------------------------------------------------
def test_saved_sample_when_loaded_then_original_key_default_and_unusable_notice():
    from fontlabapp.studios.proof_studio.generators import saved_sample as ss

    gen = _gen("saved-sample")
    assert gen.settings == ("FontLabPythonExamples", "SavedProofSample") and ss.KEY == "proof/sample"
    assert ss.DEFAULT == "Hamburgefontsiv" and {f.key: f.default for f in gen.fields} == {"sample": "Hamburgefontsiv"}
    assert gen.load(Settings()).values == {"sample": "Hamburgefontsiv"}
    assert gen.load(Settings({"proof/sample": "Stored"})).values == {"sample": "Stored"}
    bad = gen.load(Settings({"proof/sample": "a b"}))
    assert bad.values == {"sample": "Hamburgefontsiv"} and bad.status == ss.UNUSABLE
    with pytest.raises(RuntimeError, match="Cannot read"):
        gen.load(Settings(status_code=1))
    assert gen.save is None, "explicit Save only; never autosaved"


def test_saved_sample_when_saved_or_reset_then_only_owned_key(monkeypatch):
    from fontlabapp.studios.proof_studio.generators import saved_sample as ss

    settings = Settings({"other": 1})
    assert ss.save_sample(Context("s", {"sample": "Ogonek"}, settings)).status == "Sample saved for the next launch."
    reset = ss.reset_sample(Context("s", {}, settings))
    assert settings.writes == [("set", "proof/sample", "Ogonek"), ("remove", "proof/sample")]
    assert reset.values == {"sample": "Hamburgefontsiv"} and reset.status == "Saved sample reset." and reset.report == ""
    assert settings.values == {"other": 1}
    with pytest.raises(RuntimeError, match="^Settings write failed. The sample may not persist; retry Save.$"):
        ss.persist(Settings(status_code=1), "x")
    for bad in ("\0", " ", " ", " ", "\ud800"):
        with pytest.raises(ValueError, match="^Use text without NUL, NBSP, line separators or lone surrogates.$"):
            ss.make("s", Options(values={"sample": "a" + bad}))
    assert ss.make("s", Options(values={"sample": "Zażółć"})).parts == ("Zażółć",)


def test_saved_sample_when_checked_then_original_json_and_budget(monkeypatch):
    from fontlabapp.studios.proof_studio.generators import saved_sample as ss

    rows = (("A", "U+0041", ""), ("Aacute", "U+00C1 U+0041", ""), ("x", "", ""))
    seen = []
    backends = NS(catalog=NS(capture=lambda *, deadline: seen.append(deadline) or NS(rows=rows)))
    monkeypatch.setattr(ss, "proof_studio_backends", lambda: backends)
    monkeypatch.setattr(ss, "current_package", lambda: ReadOnly(glyphsCount=lambda: 6000))
    outcome = ss.check_coverage(Context("s", {"sample": "ÁAB"}), clock=lambda: 100.0)
    assert seen == [100.0 + 120.0], "min(120, 10 + 0.02 * 6000)"
    assert json.loads(outcome.report) == {"sample": "ÁAB", "glyph_count": 3, "missing": ["U+0042"],
                                          "covered": ["U+0041", "U+00C1"]}
    assert outcome.report == ss.coverage_report("ÁAB", rows) and "\\u00c1" in outcome.report
    assert outcome.status == "Scanned 6,000 glyphs (budget 120 s). Coverage at the last check."
    monkeypatch.setattr(ss, "current_package", lambda: ReadOnly(glyphsCount=100))
    assert "budget 12 s" in ss.check_coverage(Context("s", {"sample": "A"}), clock=lambda: 0.0).status
    monkeypatch.setattr(ss, "current_package", lambda: None)
    with pytest.raises(ValueError, match="^Open a font before scanning.$"):
        ss.check_coverage(Context("s", {"sample": "A"}))


# Master text comparison ------------------------------------------------------------
def test_master_text_when_custom_or_preset_then_analyze_rows_per_master():
    mt = scripting.proof_studio_backends().master_text
    gen = _gen("master-text")
    proof = gen.make("characters", Options(values={"custom": "Ham,zz", "layout": 1}, facts=FACTS))
    expected = mt.model.analyze("Ham,zz", dict(FACTS.cmap), set(FACTS.names), FACTS.masters, 1)
    assert proof.parts == (expected.preview, expected.preview) and proof.layers == ("Light", "Bold")
    assert proof.preview(0) == "/H /a /m" and proof.kerning is True
    assert proof.note == "1 words × 2 masters; 2 unavailable occurrences and 1 empty words omitted."
    preset = gen.make("characters", Options(values={"custom": "", "preset": 1}, facts=FACTS))
    assert preset.parts[0] == mt.model.analyze(mt.settings.FALLBACKS[0], dict(FACTS.cmap), set(FACTS.names),
                                               FACTS.masters, 1).preview
    with pytest.raises(ValueError, match="Enter custom text or select a preset"):
        gen.make("characters", Options(values={"custom": "", "preset": 0}, facts=FACTS))
    assert gen.make("characters", Options()).note == "Open a font first."
    fields = {f.key: f for f in gen.fields}
    assert fields["layout"].items == ("Stacked", "Side-by-side") and fields["layout"].default == 1
    assert fields["preset"].items[1:] == mt.settings.FALLBACKS and gen.settings == (
        "FontLabScriptmix", "MasterTextComparison")


def test_master_text_when_loaded_then_saved_controls_and_presets(tmp_path):
    from fontlabapp.studios.proof_studio.generators import master_text

    mt = scripting.proof_studio_backends().master_text
    outcome = master_text.load(Settings({"inputCustom": "Hi", "layout": "0"}), directory=tmp_path)
    assert outcome.values["custom"] == "Hi" and outcome.values["layout"] == 0
    assert outcome.values["presets"] == mt.settings.FALLBACKS and outcome.items["preset"][0] == master_text.NONE
    assert outcome.status.startswith("Four original fallback lists")
    (tmp_path / "MasterBlaster-presets.txt").write_text("﻿one,two\nthree\n", encoding="utf-8")
    local = master_text.load(Settings({"layout": 7}), directory=tmp_path)
    assert local.values["presets"] == ("one,two", "three") and local.values["layout"] == 1
    assert local.status.startswith("Saved custom text/layout is invalid")
    loaded = master_text.load_file(Context("characters", {"preset_file": str(tmp_path / "MasterBlaster-presets.txt")}))
    assert loaded.values["presets"] == ("one,two", "three") and loaded.status.startswith("2 presets loaded")
    with pytest.raises(ValueError, match="absolute"):
        master_text.load_file(Context("characters", {"preset_file": "relative.txt"}))


def test_master_text_when_opened_then_clear_capture_open_then_save(monkeypatch):
    from fontlabapp.studios.proof_studio.generators import master_text

    real = scripting.proof_studio_backends().master_text
    events = []
    opening = NS(masters=("Light", "Bold"), maps=lambda check: (dict(FACTS.cmap), set(FACTS.names), ()))
    fake = NS(
        model=real.model,
        settings=NS(save=lambda settings, custom, layout, *, preserve_custom, check:
                    events.append(("save", custom, layout, preserve_custom)), FALLBACKS=real.settings.FALLBACKS),
        owners=NS(require_clear=lambda: events.append("clear")),
        capture=NS(read=lambda deadline, *, check: events.append("capture") or opening),
        proof=NS(open_proof=lambda o, result, *, deadline, cancelled: events.append(("open", o is opening, result.preview, cancelled()))),
    )
    monkeypatch.setattr(master_text, "_mt", lambda: fake)
    context = Context("characters", {"custom": "Ham", "layout": 0, "preset": 1, "presets": ("ab",)}, "S")
    status = master_text.open_current("characters", context)
    preview = real.model.analyze("Ham", dict(FACTS.cmap), set(FACTS.names), ("Light", "Bold"), 0).preview
    assert events == ["clear", "capture", ("open", True, preview, False), ("save", "Ham", 0, False)]
    assert status.startswith("Opened comparison; omitted 0 unavailable occurrences")
    events.clear()
    outcome = master_text.open_preset(context)
    ab = real.model.analyze("ab", dict(FACTS.cmap), set(FACTS.names), ("Light", "Bold"), 0).preview
    assert events[2] == ("open", True, ab, False) and events[3] == ("save", "Ham", 0, False), "preset saves the readable custom field"
    assert outcome.status.startswith("Opened comparison")
    events.clear()
    closed = Context("characters", context.values, "S", cancelled=lambda: True)
    with pytest.raises(InterruptedError, match="cancelled"):
        master_text.open_current("characters", closed)
    assert events == ["clear", "capture"], "a closed window cancels at the next check: no open, no save"
    events.clear()
    fake.owners.require_clear = lambda: (_ for _ in ()).throw(RuntimeError("cleanup is incomplete"))
    with pytest.raises(RuntimeError, match="cleanup"):
        master_text.open_current("characters", context)
    assert events == [], "nothing captured, opened or saved when owners are pending"
