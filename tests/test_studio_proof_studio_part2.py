# this_file: tests/test_studio_proof_studio_part2.py
"""Proof Studio part 2 (Phase D A7, T9): registration, session and the new tabs on offscreen Qt.

Read-only: a font fake fails on any access, every public history callable
fails, settings are an in-memory fake that records writes, and the preview
fake records ``set_view``/``set_layer``/``set_text`` so no tab's size,
master or kerning leaks into another tab.
"""

import importlib
import sys
from types import SimpleNamespace as NS

import pytest
from _studio_qt import studio_qt  # noqa: F401 - fixture
from test_proof_studio_part2 import FACTS, ReadOnly, Settings

TABS = "fontlabapp.studios.proof_studio.tabs"
TITLES = ["Pattern strings", "Kerning proofs", "Random", "Real text", "Word finder", "Waterfall", "By master"]


@pytest.fixture(autouse=True)
def drop_studio_modules():
    yield
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)


@pytest.fixture(autouse=True)
def no_history(monkeypatch):
    from fontlabapp.core import history

    def refuse(*args, **kwargs):
        raise AssertionError("Proof Studio touched history")

    for name in [n for n in dir(history) if not n.startswith("_") and callable(getattr(history, n))]:
        monkeypatch.setattr(history, name, refuse)


class ReadOnlyFont:
    def __setattr__(self, name, value):
        raise AssertionError(f"Proof Studio wrote font.{name}")

    def __getattr__(self, name):
        raise AssertionError(f"Proof Studio read font.{name}")


class Preview:
    def __init__(self):
        self.calls = []

    def set_text(self, text):
        self.calls.append(("set_text", text))

    def set_view(self, size, kerning):
        self.calls.append(("set_view", size, kerning))

    def set_layer(self, layer):
        self.calls.append(("set_layer", layer))

    def last_view(self):
        return [c for c in self.calls if c[0] != "set_text"][-2:]


class Shell:
    def __init__(self):
        self.statuses = []

    def set_status(self, text):
        self.statuses.append(text)


def _gen(key):
    from fontlabapp.studios.proof_studio.generators import generators

    return {g.key: g for g in generators()}[key]


# Registration guard ------------------------------------------------------------------
def test_register_when_new_module_appears_then_only_missing_titles_added(tmp_path, monkeypatch):
    from fontlabapp import studios
    import fontlabapp.studios.proof_studio as ps_mod
    from fontlabapp.studios.proof_studio import generators as registry

    monkeypatch.setattr(studios, "_REGISTRY", {})
    assert ps_mod.register_tabs() == tuple(TITLES)
    (tmp_path / "extra_tab.py").write_text(
        "from fontlabapp.studios.proof_studio.generators import Generator, Proof\n"
        "GENERATOR = Generator('extra', 'Extra', 'Extra tab', 99, 10, (('One', 'one'),), {'one': 'X'},"
        " lambda c, o: Proof(('x',)), lambda c: None)\n"
        "TWIN = Generator('twin', 'Twin', 'Random', 40, 99, (('One', 'one'),), {'one': 'Y'},"
        " lambda c, o: Proof(('y',)), lambda c: None)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(registry, "__path__", [*registry.__path__, str(tmp_path)])
    try:
        assert ps_mod.register_tabs()[-1] == "Extra tab"
        assert ps_mod.register_tabs()[-1] == "Extra tab"  # idempotent
        assert [s.title for s in studios.tabs(ps_mod.APP)] == [*TITLES, "Extra tab"], "no duplicates, appended"
    finally:
        sys.modules.pop("fontlabapp.studios.proof_studio.generators.extra_tab", None)


# Session -------------------------------------------------------------------------------
def test_font_facts_when_package_then_maps_masters_and_active(monkeypatch):
    from fontlabapp.studios.proof_studio import session

    monkeypatch.setattr(session, "current_package", lambda: ReadOnly(masters=("Light", "Bold"), master="Bold"))
    monkeypatch.setattr(session, "proof_api", lambda: NS(font_maps=lambda: ({65: "A"}, {"A", "A.alt"})))
    assert session.font_facts() == session.Facts({65: "A"}, frozenset({"A", "A.alt"}), ("Light", "Bold"), "Bold")
    monkeypatch.setattr(session, "current_package", lambda: None)
    assert session.font_facts() is None


def test_show_when_waterfall_then_kerning_tab_gets_defaults_back():
    from fontlabapp.studios.proof_studio.session import Studio

    shell, preview = Shell(), Preview()
    studio = Studio(shell, font=ReadOnlyFont, selection=lambda: (), facts=lambda: FACTS)
    studio.preview = preview
    waterfall = studio.generate(_gen("waterfall"), "waterfall", values={"sizes": "10 24", "master": "Light"})
    studio.show(waterfall, 1)
    assert preview.last_view() == [("set_view", 24.0, False), ("set_layer", "Light")]
    kerning = studio.generate(_gen("kerning-texts"), "kernking")
    studio.show(kerning, 0)
    assert preview.last_view() == [("set_view", 72.0, True), ("set_layer", None)], "no size/master/kerning leak"
    studio.show(None)
    assert preview.calls[-3:] == [("set_view", 72.0, True), ("set_layer", None), ("set_text", "")]


def test_generate_when_seeded_or_note_then_status_names_source():
    from fontlabapp.studios.proof_studio.session import Studio

    shell = Shell()
    studio = Studio(shell, font=ReadOnlyFont, selection=lambda: (), facts=lambda: FACTS)
    studio.generate(_gen("random"), "numbers", seed=5)
    studio.generate(_gen("random"), "numbers")
    studio.generate(_gen("text-by-master"), "text-by-master", values={"text": "Ham"})
    studio.generate(_gen("text-filter"), "text-filter", values={"input": "x", "characters": "z-a"})
    assert shell.statuses[0] == "Random Numbers: 1 tab(s) from seed 5."
    assert shell.statuses[1] == "Random Numbers: 1 tab(s) from an unseeded draw."
    assert shell.statuses[2] == "Text By Master: 2 masters · 3 glyphs · advance widths, no kerning."
    assert shell.statuses[3].startswith("Text filter: bad character range"), "re.error is a status, not a crash"


def test_open_and_actions_when_failing_or_inert_then_status(monkeypatch):
    from fontlabapp.studios.proof_studio.generators import Action, Context, Outcome, Proof
    from fontlabapp.studios.proof_studio.session import Studio

    shell = Shell()
    studio = Studio(shell, font=ReadOnlyFont, selection=lambda: ())
    assert studio.open(_gen("word-finder"), "lowercase") is False
    assert shell.statuses[-1] == "Word Finder has no FontLab Glyph tab; use Copy."
    gen = _gen("text-filter")
    assert studio.open(gen, "text-filter", Context("text-filter", {})) is False
    assert studio.open(gen, "text-filter") is False and shell.statuses[-1] == "Nothing to open; preview a proof first."
    object.__setattr__(gen, "open_current", lambda c, ctx: "Opened it.")
    assert studio.open(gen, "text-filter", Context("text-filter", {}, proof=Proof(("x",)))) is True
    assert shell.statuses[-1] == "Opened it."
    boom = Action("Boom", lambda ctx: (_ for _ in ()).throw(OSError("disk")))
    assert studio.run(gen, boom, Context("c", {})) is None and shell.statuses[-1] == "Text filter: Boom failed: disk"
    assert studio.run(gen, Action("Quiet", lambda ctx: Outcome()), Context("c", {})) == Outcome()
    assert studio.load(_gen("random"), None) is None and studio.save(_gen("random"), None, {}, Proof(())) is False
    assert studio.load(gen, Settings(values={"input": 3})) is None
    assert shell.statuses[-1].startswith("Text filter: saved settings were not loaded: Saved Text Filter fields")
    assert studio.save(gen, Settings(writable=False), {"input": "", "characters": ""}, Proof(("",))) is False
    assert shell.statuses[-1] == "Text filter: text is not saved: Text Filter settings are read-only."


# Window and new tabs on offscreen Qt ---------------------------------------------------
@pytest.fixture
def ps(studio_qt, monkeypatch):  # noqa: F811
    monkeypatch.delitem(sys.modules, TABS, raising=False)
    studios = importlib.import_module("fontlabapp.studios.proof_studio")
    from PySide6.QtWidgets import QWidget

    class QtPreview(QWidget, Preview):
        def __init__(self):
            QWidget.__init__(self)
            Preview.__init__(self)

    preview, stores, copied = QtPreview(), {}, []

    def settings(organization, application):
        return stores.setdefault((organization, application), Settings())

    stores[("FontLab", "ScriptTextFilter")] = Settings({"input": "Saved input", "characters": "a-z "})
    stores[("FontLabPythonExamples", "SavedProofSample")] = Settings({"proof/sample": "Stored sample"})
    shell = studios.show(package=lambda: None, font=ReadOnlyFont, selection=lambda: ("n", "o"),
                         preview=lambda shell, studio: preview, facts=lambda: FACTS, settings=settings)
    studio_qt.owned.append(shell)
    yield NS(shell=shell, preview=preview, stores=stores, copied=copied, tabs=sys.modules[TABS], qt=studio_qt)
    sys.modules.pop(TABS, None)


def _tab(ps, title):
    tab = ps.tabs.GeneratorTab(ps.shell.proof_studio, title, clipboard=ps.copied.append)
    ps.qt.owned.append(NS(close=tab.widget.deleteLater))
    return tab


def _pick(tab, key):
    tab.picker.setCurrentIndex([g.key for g in tab.generators].index(key))


def test_window_when_opened_then_seven_tabs_in_registry_order(ps):
    assert [ps.shell.tabs.tabText(i) for i in range(ps.shell.tabs.count())] == TITLES + ["About"]


def test_random_tab_when_seeded_then_deterministic_and_invalid_seed_status(ps):
    tab = _tab(ps, "Random")
    assert tab.seed.isVisibleTo(tab.widget) and tab.choice_caption.text() == "Kind"
    assert [tab.choice.itemText(i) for i in range(tab.choice.count())][:2] == ["Numbers", "Lowercase nontext"]
    tab.seed.setText("42")
    first = tab.text.toPlainText()
    tab.seed.setText("")
    tab.seed.setText("42")
    assert tab.text.toPlainText() == first and first.strip()
    tab.seed.setText("4.2")
    assert tab.proof is None and ps.shell.status.text() == "Seed must be a whole number (or empty for an unseeded draw)."
    assert tab.open() is False


def test_real_text_tab_when_switching_generators_then_pages_fields_and_open(ps, monkeypatch):
    tab = _tab(ps, "Real text")
    assert [tab.picker.itemText(i) for i in range(tab.picker.count())] == ["Real text", "Text filter", "Saved sample"]
    assert tab.choice_caption.text() == "Language" and tab.open_button.isEnabled()
    _pick(tab, "text-filter")
    assert tab.values() == {"input": "Saved input", "characters": "a-z "}
    assert tab.text.toPlainText() == "aved input" and not tab.choice.isVisibleTo(tab.widget)
    store = ps.stores[("FontLab", "ScriptTextFilter")]
    tab.inputs["text-filter"]["input"].setPlainText("Hello World")
    assert store.values["input"] == "Hello World" and store.values["output"] == "ello orld", "saved on every edit"
    tab.inputs["text-filter"]["characters"].setPlainText("z-a")  # malformed class: no proof
    assert store.values["characters"] == "z-a" and store.values["output"] == "ello orld", "still saved"
    tab.inputs["text-filter"]["characters"].setPlainText("a-z ")
    tab.run(_gen("text-filter"), _gen("text-filter").actions[0])
    assert "output" not in store.values and store.values["input"] == "Hello World"
    assert tab.values()["characters"] == _gen("text-filter").fields[1].default
    opened = []
    object.__setattr__(tab.generator(), "open_current", lambda c, ctx: opened.append(ctx.text()))
    assert tab.open() is True and opened == [tab.text.toPlainText()]


def test_saved_sample_tab_when_saved_reset_and_checked_then_explicit_writes(ps, monkeypatch):
    tab = _tab(ps, "Real text")
    _pick(tab, "saved-sample")
    store = ps.stores[("FontLabPythonExamples", "SavedProofSample")]
    assert tab.values() == {"sample": "Stored sample"} and tab.text.toPlainText() == "Stored sample"
    tab.inputs["saved-sample"]["sample"].setText("Edited")
    assert store.writes == [], "never autosaved"
    gen = tab.generator()
    save, reset, check = gen.actions
    assert tab.run(gen, save).status == "Sample saved for the next launch."
    assert store.values["proof/sample"] == "Edited"
    from fontlabapp.studios.proof_studio.generators import saved_sample

    monkeypatch.setattr(saved_sample, "current_package", lambda: ReadOnly(glyphsCount=0))
    monkeypatch.setattr(saved_sample, "proof_studio_backends",
                        lambda: NS(catalog=NS(capture=lambda *, deadline: NS(rows=(("E", "U+0045", ""),)))))
    tab.run(gen, check)
    assert tab.report.isVisibleTo(tab.widget) and '"covered": [\n    "U+0045"' in tab.report.toPlainText()
    tab.run(gen, reset)
    assert "proof/sample" not in store.values and tab.values() == {"sample": "Hamburgefontsiv"}
    assert not tab.report.isVisibleTo(tab.widget)
    assert not tab.open_button.isEnabled() and tab.open() is False


def test_word_finder_tab_when_fields_change_then_words_and_copy(ps):
    tab = _tab(ps, "Word finder")
    assert tab.choice_caption.text() == "Case" and not tab.open_button.isEnabled()
    tab.inputs["word-finder"]["must"].setText("am")  # FACTS has a capital H only
    words = tab.text.toPlainText().split()
    assert words and all("a" in w and "m" in w and "h" not in w for w in words)
    tab.inputs["word-finder"]["max_len"].setValue(4)
    assert all(len(w) <= 4 for w in tab.text.toPlainText().split())
    assert tab.copy() == tab.text.toPlainText() and ps.copied[-1] == tab.text.toPlainText()


def test_waterfall_tab_when_size_picked_then_preview_size_master_no_kerning(ps):
    tab = _tab(ps, "Waterfall")
    master = tab.inputs["waterfall"]["master"]
    assert [master.itemText(i) for i in range(master.count())] == ["Light", "Bold"] and master.currentText() == "Bold"
    assert tab.part_caption.text() == "Size" and tab.part.count() == 9 and tab.part.itemText(0) == "10 px"
    tab.part.setCurrentIndex(8)
    assert ps.preview.last_view() == [("set_view", 96.0, False), ("set_layer", "Bold")]
    master.setCurrentIndex(0)
    tab.part.setCurrentIndex(2)
    assert ps.preview.last_view() == [("set_view", 14.0, False), ("set_layer", "Light")]
    kerning = _tab(ps, "Kerning proofs")
    kerning.regenerate()
    assert ps.preview.last_view() == [("set_view", 72.0, True), ("set_layer", None)]


def test_by_master_tab_when_master_comparison_then_presets_and_open(ps, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    tab = _tab(ps, "By master")
    assert tab.part_caption.text() == "Master" and [tab.part.itemText(i) for i in range(2)] == ["Light", "Bold"]
    tab.inputs["text-by-master"]["size"].setValue(100)
    assert ps.preview.last_view() == [("set_view", 100.0, False), ("set_layer", "Light")]
    _pick(tab, "master-text")
    assert tab.choice_caption.text() == "Input" and tab.choice.count() == 2
    preset = tab.inputs["master-text"]["preset"]
    assert preset.count() == 5 and preset.itemText(0) == "(no preset)"
    assert tab.proof is None, "no custom text and no preset: the original refusal goes to the status"
    assert ps.shell.status.text().startswith("Master text comparison: Enter custom text or select a preset")
    tab.inputs["master-text"]["custom"].setPlainText("Ham,Bag")
    assert tab.part.count() == 2 and ps.preview.last_view()[1] == ("set_layer", "Light")
    store = ps.stores[("FontLabScriptmix", "MasterTextComparison")]
    assert store.writes == [], "saved only after a successful Open"
    seen = []
    object.__setattr__(tab.generator(), "open_current", lambda c, ctx: seen.append((c, ctx.values["custom"])) or "Done.")
    assert tab.open() is True and seen == [("characters", "Ham,Bag")] and ps.shell.status.text() == "Done."


# Stacked views (the originals' WaterfallView and MasterRows) ---------------------------
PACKAGE = dict(upm=1000, ascender_value=800, descender_value=-200, masters=("Light", "Bold"))


def _glyph_run(package, names, master):
    """Fake ``proof_api().glyph_run``: Light 400 units, Bold 500, missing upm × 0.5 (no outline)."""
    return [(None, package.upm * 0.5) if name is None else ((master, name), 400.0 if master == "Light" else 500.0)
            for name in names]


def test_paint_canvas_when_waterfall_then_original_content_and_status(monkeypatch):
    from fontlabapp.studios.proof_studio import session

    monkeypatch.setattr(session, "proof_api", lambda: NS(glyph_run=_glyph_run))
    view = NS(width_units=0)
    view.set_content = lambda glyphs, sizes, upm, ascender: (
        setattr(view, "content", (glyphs, sizes, upm, ascender)),
        setattr(view, "width_units", sum(a for _, a in glyphs)))
    status = session.paint_canvas(view, ReadOnly(**PACKAGE), (("H", None, "a"), (4.0, 96.0), "Light"))
    assert view.content == ([(("Light", "H"), 400.0), (None, 500.0), (("Light", "a"), 400.0)], [4.0, 96.0], 1000, 800)
    assert status == "Line width 1300 units · 2 sizes · 1 missing (red boxes)", "the original Waterfall status line"
    assert session.paint_canvas(view, ReadOnly(**PACKAGE), (("H",), (12.0,), "Bold")) == "Line width 500 units · 1 sizes"


def test_paint_canvas_when_master_rows_then_one_row_per_master_and_width_range(monkeypatch):
    from fontlabapp.studios.proof_studio import session

    monkeypatch.setattr(session, "proof_api", lambda: NS(glyph_run=_glyph_run))
    view = NS(set_content=lambda *args: setattr(view, "content", args))
    status = session.paint_canvas(view, ReadOnly(**PACKAGE), (("H", "a", None), 60.0))
    rows, size, upm, frame = view.content
    assert [(m, w) for m, _run, w in rows] == [("Light", 1300.0), ("Bold", 1500.0)] and rows[1][1][2] == (None, 500.0)
    assert (size, upm, frame) == (60.0, 1000, (-200, 800))
    assert status == "2 rows · widths 1300–1500 units · 1 missing", "the original Text By Master status line"
    empty = ReadOnly(**{**PACKAGE, "masters": ()})
    assert session.paint_canvas(view, empty, (("H",), 48.0)) == "0 rows"


def test_studio_paint_when_no_font_no_canvas_or_failure_then_status(monkeypatch):
    from fontlabapp.studios.proof_studio import session
    from fontlabapp.studios.proof_studio.generators import Proof

    shell = Shell()
    studio = session.Studio(shell, font=ReadOnlyFont, facts=lambda: FACTS, package=lambda: None)
    gen = _gen("waterfall")
    proof = gen.make("waterfall", session.Options(values={"sizes": "12"}, facts=FACTS))
    assert studio.paint(gen, "waterfall", None, proof) is None and studio.paint(gen, "waterfall", NS(), Proof(("x",))) is None
    assert studio.paint(gen, "waterfall", NS(), proof) is None and shell.statuses[-1] == "Waterfall: Open a font first."
    studio.package = lambda: ReadOnly(**PACKAGE)
    monkeypatch.setattr(session, "proof_api", lambda: NS(glyph_run=lambda *a: (_ for _ in ()).throw(TimeoutError("slow"))))
    assert studio.paint(gen, "waterfall", NS(), proof) is None and shell.statuses[-1] == "Waterfall: slow"
    monkeypatch.setattr(session, "proof_api", lambda: NS(glyph_run=_glyph_run))
    view = NS(set_content=lambda *a: None, width_units=500)
    text = studio.paint(gen, "waterfall", view, proof)
    assert text == shell.statuses[-1] == f"Waterfall: {proof.note} Line width 500 units · 1 sizes · 3 missing (red boxes)"


@pytest.fixture
def stacked(ps, monkeypatch):
    """Fake view types (the real painters read PythonQt property bindings) and a read-only live package."""
    from PySide6.QtWidgets import QWidget
    from fontlabapp.studios.proof_studio import session

    made = []

    class Fake(QWidget):
        def __init__(self):
            QWidget.__init__(self)
            self.content, self.width_units = None, 0
            made.append(self)

        def set_content(self, first, *rest):
            self.content = (first, *rest)
            if rest and isinstance(rest[0], list):  # WaterfallView(glyphs, sizes, upm, ascender)
                self.width_units = sum(advance for _, advance in first)

    monkeypatch.setattr(ps.tabs, "proof_view_types", lambda: NS(WaterfallView=Fake, MasterRows=Fake))
    monkeypatch.setattr(session, "proof_api", lambda: NS(glyph_run=_glyph_run))
    ps.shell.proof_studio.package = lambda: ReadOnly(**PACKAGE)
    return made


def test_waterfall_tab_when_built_then_stacked_cascade_red_boxes_and_status(ps, stacked):
    tab = _tab(ps, "Waterfall")
    view = tab.canvases["waterfall"]
    glyphs, sizes, upm, ascender = view.content
    assert sizes == [10, 12, 14, 18, 24, 32, 48, 64, 96] and (upm, ascender) == (1000, 800), "every size in one view"
    assert all(path[0] == "Bold" for path, _ in glyphs if path), "the active master"
    tab.inputs["waterfall"]["text"].setText("Hz")
    glyphs = view.content[0]
    assert glyphs == [(("Bold", "H"), 500.0), (None, 500.0)], "z has no glyph: a red-box slot"
    status = ps.shell.status.text()
    assert status.endswith("Line width 1000 units · 9 sizes · 1 missing (red boxes)") and status.startswith("Waterfall: Master Bold")
    assert view.accessibleName() == "Waterfall proof" and view.isVisibleTo(tab.widget)


def test_by_master_tab_when_built_then_master_rows_with_width_range(ps, stacked, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    tab = _tab(ps, "By master")
    assert set(tab.canvases) == {"text-by-master"}, "Master text comparison keeps its text preview"
    view = tab.canvases["text-by-master"]
    tab.inputs["text-by-master"]["size"].setValue(100)
    rows, size, upm, frame = view.content
    assert [(m, w) for m, _r, w in rows] == [("Light", 6000.0), ("Bold", 7500.0)] and size == 100.0
    assert frame == (-200, 800) and ps.shell.status.text().endswith("2 rows · widths 6000–7500 units")


def test_canvas_when_view_type_fails_then_tab_kept_with_status(ps, monkeypatch):
    seen = []
    monkeypatch.setattr(ps.shell, "set_status", seen.append)
    monkeypatch.setattr(ps.tabs, "proof_view_types", lambda: (_ for _ in ()).throw(ImportError("no views")))
    tab = _tab(ps, "Waterfall")
    assert tab.canvases == {"waterfall": None} and tab.proof is not None
    assert "Waterfall: stacked view unavailable: no views" in seen, "the tab stays usable; the reason is shown"


def test_tab_when_closed_then_context_cancelled(ps, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    tab = _tab(ps, "By master")
    _pick(tab, "master-text")
    assert tab.context().cancelled() is False
    tab.close()
    assert tab.context().cancelled() is True, "closing the window cancels a running comparison Open"
