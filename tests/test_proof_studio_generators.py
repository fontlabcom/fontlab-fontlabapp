# this_file: tests/test_proof_studio_generators.py
"""Proof Studio generators (Phase D A7, part 1): pure, Qt-free parity with the 12 Proof scripts.

Each absorbed Scriptmix script calls ``fly.ap.proof.context.run(mode)`` or
``fly.ap.kerning.proofs.run(mode)`` (``fly.ap`` is ``fontlabapp``). These tests
pin the exact control and surround strings, order, repeats, empty selection,
byte-for-byte kerning texts, and that "Open" reaches the same backend, which
opens the same number of new tabs in the same order without writing.
"""

import importlib
import json
import sys
from importlib.resources import files
from types import SimpleNamespace

import pytest

from fontlabapp.studios.proof_studio import generators as registry
from fontlabapp.studios.proof_studio.generators import Options, Proof, between, kerning_texts, surround
from fontlabapp.studios.proof_studio.generators._context import rows_text

LOWER = tuple("abcdefghijklmnopqrstuvwxyz")
UPPER = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
LINING = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
OLDSTYLE = tuple(f"{name}.osf" for name in LINING)
SURROUND = {"H": ("H",), "HHOHH": ("H", "H", "O", "H", "H"), "I": ("I",), "nnonn": ("n", "n", "o", "n", "n")}

#: Scriptmix Scripts/Proof/<title>.py -> (generator key, mode passed to run()).
SCRIPTS = {
    "Glyphs Between Lining Figures": ("between", "lining"),
    "Glyphs Between Lowercase": ("between", "lowercase"),
    "Glyphs Between Oldstyle Figures": ("between", "oldstyle"),
    "Glyphs Between Uppercase": ("between", "uppercase"),
    "Glyphs Surrounded by H": ("surround", "H"),
    "Glyphs Surrounded by HHOHH": ("surround", "HHOHH"),
    "Glyphs Surrounded by I": ("surround", "I"),
    "Glyphs Surrounded by Nnonn": ("surround", "nnonn"),
    "Hoefler Lowercase": ("kerning-texts", "hoefler-lowercase"),
    "Hoefler Uppercase": ("kerning-texts", "hoefler-uppercase"),
    "KernKing": ("kerning-texts", "kernking"),
    "KernSym": ("kerning-texts", "kernsym"),
}
CLASSES = {"lowercase": LOWER, "uppercase": UPPER, "lining": LINING, "oldstyle": OLDSTYLE}


def _line(names):
    return " ".join(f"/{name}" for name in names)


def _between(names, ctx):
    lines = []
    for name in names:
        lines += [_line([part for other in ctx for part in (name, other)] + [name]), ""]
    return "\n".join([*lines, ""])


def _surround(names, ctx):
    row = []
    for name in names:
        row += [*ctx, name]
    return _line(row + list(ctx))


def _bundled(mode):
    return tuple(json.loads(files("fontlabapp").joinpath("kerning", "kerning_proof_texts.json").read_text("utf-8"))[mode])


@pytest.fixture(autouse=True)
def drop_studio_modules():
    yield
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)  # keep later "no studio child loaded" contracts order-independent


# Registry ---------------------------------------------------------------------
def test_registry_when_listed_then_seven_tabs_eleven_generators_in_order():
    assert registry.tab_titles() == (
        "Pattern strings", "Kerning proofs", "Random", "Real text", "Word finder", "Waterfall", "By master")
    assert [g.key for g in registry.generators()] == [
        "between", "surround", "kerning-texts", "random", "real-text", "text-filter", "saved-sample",
        "word-finder", "waterfall", "text-by-master", "master-text"]
    assert [g.key for g in registry.for_tab("Pattern strings")] == ["between", "surround"]
    assert registry.for_tab("Missing") == ()


def test_registry_when_mapping_scripts_then_all_twelve_once_with_choices():
    part1 = ("between", "surround", "kerning-texts")
    mapped = {title: (g.key, key) for g in registry.generators() if g.key in part1 for key, title in g.scripts.items()}
    assert mapped == SCRIPTS, "every absorbed Proof script maps to exactly one generator choice"
    for generator in registry.generators():
        assert [key for _label, key in generator.choices] == list(generator.scripts), generator.key


def test_registry_when_new_module_added_then_listed_without_registry_change(tmp_path, monkeypatch):
    (tmp_path / "extra.py").write_text(
        "from fontlabapp.studios.proof_studio.generators import Generator, Proof\n"
        "GENERATOR = Generator('extra', 'Extra', 'Random', 30, 10, (('One', 'one'),), {'one': 'X'},"
        " lambda c, o: Proof(('x',)), lambda c: None)\n",
        encoding="utf-8",
    )
    (tmp_path / "_private.py").write_text("raise AssertionError('private modules are not generators')\n")
    live = importlib.import_module("fontlabapp.studios.proof_studio.generators")
    monkeypatch.setattr(live, "__path__", [*live.__path__, str(tmp_path)])
    try:
        assert live.tab_titles().count("Random") == 1
        extra = {g.key: g for g in live.for_tab("Random")}
        assert sorted(extra) == ["extra", "random"]
        assert extra["extra"].make("one", live.Options()).parts == ("x",)
    finally:
        sys.modules.pop("fontlabapp.studios.proof_studio.generators.extra", None)


def test_proof_preview_when_multiline_then_single_line_and_out_of_range_empty():
    proof = Proof(("\nab\ncd\n", "x"))
    assert proof.preview(0) == "ab cd"
    assert proof.preview(1) == "x"
    assert proof.preview(2) == proof.preview(-1) == ""


# Pattern strings ---------------------------------------------------------------
@pytest.mark.parametrize("mode", list(CLASSES))
def test_between_when_selection_repeats_then_exact_class_rows_in_order(mode):
    names = ("n", "A", "n")
    text = between.GENERATOR.make(mode, Options(names)).parts
    assert text == (_between(names, CLASSES[mode]),)
    assert text[0].split("\n")[0].startswith("/n /" + CLASSES[mode][0] + " /n")
    assert text[0].endswith("\n\n"), "every occurrence row is followed by an empty line, plus one final one"


@pytest.mark.parametrize("mode", list(CLASSES))
def test_between_when_selection_empty_then_one_empty_tab(mode):
    assert between.GENERATOR.make(mode, Options()).parts == ("",)


@pytest.mark.parametrize("mode", list(SURROUND))
def test_surround_when_selection_repeats_then_one_row_ending_in_context(mode):
    names = ("a", "b", "a")
    assert surround.GENERATOR.make(mode, Options(names)).parts == (_surround(names, SURROUND[mode]),)


@pytest.mark.parametrize("mode", list(SURROUND))
def test_surround_when_selection_empty_then_context_alone(mode):
    assert surround.GENERATOR.make(mode, Options()).parts == (_line(SURROUND[mode]),)


def test_surround_when_hhohh_then_literal_string():
    assert surround.GENERATOR.make("HHOHH", Options(("x",))).parts == ("/H /H /O /H /H /x /H /H /O /H /H",)


def test_pattern_when_mode_unknown_then_backend_error():
    with pytest.raises(ValueError, match="Unknown context proof mode: zz"):
        between.GENERATOR.make("zz", Options(("a",)))


def test_rows_text_when_rows_empty_then_empty_lines_kept():
    assert rows_text((("a", "b"), (), ("c",), ())) == "/a /b\n\n/c\n"


# Kerning proofs ----------------------------------------------------------------
@pytest.mark.parametrize("mode", ["hoefler-lowercase", "hoefler-uppercase", "kernking", "kernsym"])
def test_kerning_texts_when_made_then_bundled_texts_byte_for_byte(mode):
    proof = kerning_texts.GENERATOR.make(mode, Options(("ignored",)))
    assert proof.parts == _bundled(mode)
    assert len(proof.parts) == (2 if mode == "kernking" else 1)


def test_kerning_texts_when_kernking_then_lowercase_tab_first():
    first, second = kerning_texts.GENERATOR.make("kernking", Options()).parts
    assert first.startswith("\nlynx tuft frogs")
    assert any(char.isupper() for char in second), "the second tab is the mixed-case text"


def test_kerning_texts_when_mode_unknown_then_backend_error():
    with pytest.raises(ValueError, match="Unknown kerning proof: nope"):
        kerning_texts.GENERATOR.make("nope", Options())


# Open: same backend, same tabs, no writes ---------------------------------------
class ReadOnly:
    """A native object that fails the test on any attribute write."""

    def __init__(self, **values):
        object.__setattr__(self, "_values", values)

    def __getattr__(self, name):
        try:
            return self._values[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name, value):
        raise AssertionError(f"Proof Studio wrote {name}")


@pytest.fixture
def no_history(monkeypatch):
    """Any native history/notify call fails the test."""
    from fontlabapp.core import history

    def refuse(*args, **kwargs):
        raise AssertionError("Proof Studio touched history")

    for name in [n for n in dir(history) if not n.startswith("_") and callable(getattr(history, n))]:
        monkeypatch.setattr(history, name, refuse)


@pytest.mark.parametrize("mode", ["hoefler-lowercase", "hoefler-uppercase", "kernking", "kernsym"])
def test_kerning_open_when_run_then_same_tabs_in_order_on_captured_master(mode, monkeypatch, no_history):
    from fontlabapp.core import scripting
    from fontlabapp.proof.tabs import text

    package = ReadOnly(id=7, master="Bold")
    opened = []
    monkeypatch.setattr(scripting, "current_package", lambda: package)
    monkeypatch.setattr(text, "_open_tab", lambda t, **kw: opened.append((t, kw["expected_id"], kw["expected_master"])))
    kerning_texts.GENERATOR.open(mode)
    assert opened == [(t, 7, "Bold") for t in _bundled(mode)]


def test_kerning_open_when_no_font_then_original_error(monkeypatch):
    from fontlabapp.core import scripting

    monkeypatch.setattr(scripting, "current_package", lambda: None)
    with pytest.raises(ValueError, match="Open a font before creating a kerning proof."):
        kerning_texts.GENERATOR.open("kernsym")


@pytest.mark.parametrize(("key", "mode"), [v for v in SCRIPTS.values() if v[0] != "kerning-texts"])
def test_pattern_open_when_run_then_one_named_tab_from_live_selection(key, mode, monkeypatch, no_history):
    import fontlabapp.masters.layers.selection as layers
    from fontlabapp.proof.tabs import named

    generator = {g.key: g for g in registry.generators()}[key]
    rows = (SimpleNamespace(glyph_name="a"), SimpleNamespace(glyph_name="a"), SimpleNamespace(glyph_name="B"))
    selection = SimpleNamespace(context=(7, "Bold"), occurrences=rows)
    opened = []
    monkeypatch.setattr(layers, "capture", lambda deadline: selection)
    monkeypatch.setattr(named, "open_named_tab", lambda lines, **kw: opened.append((lines, kw["expected_id"], kw["master"])))
    generator.open(mode)
    assert len(opened) == 1, "each context proof opens exactly one new tab"
    lines, package_id, master = opened[0]
    assert (package_id, master) == (7, "Bold")
    assert rows_text(lines) == generator.make(mode, Options(("a", "a", "B"))).parts[0]
