# this_file: tests/test_studio_proof_studio.py
"""Proof Studio (Phase D A7, part 1): session, tabs and window on offscreen Qt.

The studio is read-only: these tests drive every control with a font fake that
fails on any attribute write and a history fake that fails on any call, and
check that previews reach ``TMetrics.set_text``, Copy puts the exact text on
the clipboard, and Open calls the absorbed script's backend once per choice.
"""

import importlib
import json
import sys
from importlib.resources import files
from types import SimpleNamespace

import pytest
from _studio_qt import studio_qt  # noqa: F401 - fixture

TABS = "fontlabapp.studios.proof_studio.tabs"


@pytest.fixture(autouse=True)
def drop_studio_modules():
    yield
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)  # keep later "no studio child loaded" contracts order-independent


@pytest.fixture(autouse=True)
def no_history(monkeypatch):
    """Any native history call fails the test (the studio sets no history)."""
    from fontlabapp.core import history

    def refuse(*args, **kwargs):
        raise AssertionError("Proof Studio touched history")

    for name in [n for n in dir(history) if not n.startswith("_") and callable(getattr(history, n))]:
        monkeypatch.setattr(history, name, refuse)


class ReadOnlyFont:
    """A font that fails the test on any attribute write or edit call."""

    def __setattr__(self, name, value):
        raise AssertionError(f"Proof Studio wrote font.{name}")

    def __getattr__(self, name):
        raise AssertionError(f"Proof Studio read font.{name}; generators use the selection only")


class Preview:
    def __init__(self):
        self.calls = []

    def set_text(self, text):
        self.calls.append(("set_text", text))


class Shell:
    def __init__(self):
        self.statuses = []

    def set_status(self, text):
        self.statuses.append(text)


def _bundled(mode):
    return tuple(json.loads(files("fontlabapp").joinpath("kerning", "kerning_proof_texts.json").read_text("utf-8"))[mode])


def _generator(key):
    from fontlabapp.studios.proof_studio.generators import generators

    return {g.key: g for g in generators()}[key]


def _studio(selection=("a", "b")):
    from fontlabapp.studios.proof_studio.session import Studio

    shell = Shell()
    studio = Studio(shell, font=ReadOnlyFont, selection=lambda: selection)
    studio.preview = Preview()
    return studio, shell


# Session ------------------------------------------------------------------------
def test_session_when_generating_pattern_then_selection_used_and_status():
    studio, shell = _studio(("a", "a"))
    proof = studio.generate(_generator("surround"), "H")
    assert proof.parts == ("/H /a /H /a /H",)
    assert shell.statuses == ["Glyphs Surrounded by H: 1 tab(s) from 2 selected glyph(s)."]
    assert studio.show(proof) == "/H /a /H /a /H"
    assert studio.preview.calls == [("set_text", "/H /a /H /a /H")]


def test_session_when_generating_kerning_then_selection_not_read():
    from fontlabapp.studios.proof_studio.session import Studio

    shell = Shell()

    def selection():
        raise AssertionError("kerning texts do not read the selection")

    studio = Studio(shell, font=ReadOnlyFont, selection=selection)
    proof = studio.generate(_generator("kerning-texts"), "kernking")
    assert proof.parts == _bundled("kernking")
    assert shell.statuses == ["KernKing: 2 tab(s) from bundled text."]
    assert studio.show(proof, 1) == proof.preview(1)  # no preview attached: still returns text


def test_session_when_selection_fails_then_status_and_none():
    from fontlabapp.studios.proof_studio.session import Studio

    shell = Shell()

    def selection():
        raise TimeoutError("Selected-layer capture exceeded its deadline; no partial result.")

    studio = Studio(shell, selection=selection)
    assert studio.generate(_generator("between"), "lowercase") is None
    assert shell.statuses == ["Glyphs between: Selected-layer capture exceeded its deadline; no partial result."]
    assert studio.show(None) == ""


def test_session_when_copying_then_exact_part_text_or_status():
    studio, shell = _studio()
    proof = studio.generate(_generator("kerning-texts"), "kernking")
    copied = []
    assert studio.copy(proof, 1, copied.append) == _bundled("kernking")[1]
    assert copied == [_bundled("kernking")[1]]
    assert shell.statuses[-1] == f"Copied part 2 of 2 ({len(copied[0])} characters)."
    assert studio.copy(None, 0, copied.append) is None
    assert studio.copy(proof, 5, copied.append) is None
    assert shell.statuses[-1] == "Nothing to copy; preview a proof first." and len(copied) == 1


def test_session_when_opening_then_backend_called_and_errors_reported(monkeypatch):
    studio, shell = _studio()
    generator = _generator("kerning-texts")
    calls = []
    object.__setattr__(generator, "open", lambda mode: calls.append(mode))
    assert studio.open(generator, "kernsym") is True
    assert calls == ["kernsym"] and shell.statuses[-1] == "KernSym: opened in new FontLab Glyph tab(s)."

    def fail(mode):
        raise ValueError("Open a font before creating a kerning proof.")

    object.__setattr__(generator, "open", fail)
    assert studio.open(generator, "kernsym") is False
    assert shell.statuses[-1] == "KernSym did not open: Open a font before creating a kerning proof."


def test_selected_names_when_captured_then_ordered_names_with_repeats(monkeypatch):
    import fontlabapp.masters.layers.selection as layers
    from fontlabapp.studios.proof_studio import session

    rows = tuple(SimpleNamespace(glyph_name=n) for n in ("b", "a", "b"))
    seen = []
    monkeypatch.setattr(layers, "capture", lambda deadline: seen.append(deadline) or SimpleNamespace(occurrences=rows))
    assert session.selected_names() == ("b", "a", "b")
    assert len(seen) == 1


# Window and tabs on offscreen Qt --------------------------------------------------
@pytest.fixture
def ps(studio_qt, monkeypatch):  # noqa: F811
    monkeypatch.delitem(sys.modules, TABS, raising=False)
    studios = importlib.import_module("fontlabapp.studios.proof_studio")
    from PySide6.QtWidgets import QWidget

    class QtPreview(QWidget, Preview):
        def __init__(self):
            QWidget.__init__(self)
            Preview.__init__(self)

    preview = QtPreview()
    copied = []
    shell = studios.show(package=lambda: None, font=ReadOnlyFont, selection=lambda: ("n", "o"),
                         preview=lambda shell, studio: preview)
    studio_qt.owned.append(shell)
    tabs_module = sys.modules[TABS]
    views = [shell.tabs.widget(i) for i in range(shell.tabs.count())]
    yield SimpleNamespace(shell=shell, preview=preview, copied=copied, tabs=tabs_module, views=views, qt=studio_qt)
    sys.modules.pop(TABS, None)


def _tab(ps, title):
    tab = ps.tabs.GeneratorTab(ps.shell.proof_studio, title, clipboard=ps.copied.append)
    ps.qt.owned.append(SimpleNamespace(close=tab.widget.deleteLater))
    return tab


def test_show_when_opened_then_registry_tabs_and_first_preview(ps):
    assert [ps.shell.tabs.tabText(i) for i in range(ps.shell.tabs.count())] == ["Pattern strings", "Kerning proofs", "Random", "Real text", "Word finder", "Waterfall", "By master", "About"]
    assert ps.shell.preview is ps.preview
    texts = [text for _name, text in ps.preview.calls]
    assert texts[0].startswith("/n /zero /n /one"), "Pattern strings opens on Glyphs between, Lining figures"


def test_pattern_tab_when_choices_change_then_preview_follows(ps):
    tab = _tab(ps, "Pattern strings")
    assert [tab.picker.itemText(i) for i in range(tab.picker.count())] == ["Glyphs between", "Glyphs surrounded by"]
    assert [tab.choice.itemText(i) for i in range(tab.choice.count())] == [
        "Lining figures", "Lowercase", "Oldstyle figures", "Uppercase"]
    assert tab.choice_key() == "lining"
    assert tab.text.toPlainText().startswith("/n /zero /n /one")
    tab.picker.setCurrentIndex(1)
    assert [tab.choice.itemText(i) for i in range(tab.choice.count())] == ["H", "HHOHH", "I", "nnonn"]
    tab.choice.setCurrentIndex(1)
    assert tab.text.toPlainText() == "/H /H /O /H /H /n /H /H /O /H /H /o /H /H /O /H /H"
    assert ps.preview.calls[-1] == ("set_text", tab.text.toPlainText())
    assert not tab.part.isEnabled() and tab.part.count() == 1


def test_kerning_tab_when_kernking_then_two_parts_copy_and_open(ps, monkeypatch):
    tab = _tab(ps, "Kerning proofs")
    tab.choice.setCurrentIndex(2)
    assert tab.choice_key() == "kernking"
    assert tab.part.isEnabled() and [tab.part.itemText(i) for i in range(2)] == ["Tab 1 of 2", "Tab 2 of 2"]
    assert tab.text.toPlainText() == _bundled("kernking")[0].replace("\r\n", "\n")
    tab.part.setCurrentIndex(1)
    assert ps.preview.calls[-1] == ("set_text", tab.proof.preview(1))
    assert tab.copy() == _bundled("kernking")[1] and ps.copied == [_bundled("kernking")[1]]
    opened = []
    generator = tab.generator()
    object.__setattr__(generator, "open", opened.append)
    assert tab.open() is True and opened == ["kernking"]


def test_tab_when_no_generators_then_empty_and_inert(ps):
    tab = _tab(ps, "Nothing here")
    assert tab.generator() is None and tab.choice_key() is None and tab.proof is None
    assert tab.open() is False and tab.copy() is None and tab.show_part() == ""


def test_default_clipboard_when_copied_then_qt_clipboard_holds_text(ps):
    ps.tabs._clipboard("/a /b")
    assert ps.qt.app.clipboard().text() == "/a /b"


def test_show_when_default_preview_then_metrics_preview_called(monkeypatch):
    from fontlabapp import fontui
    import fontlabapp.studios.proof_studio.app as studios

    calls = []
    monkeypatch.setattr(fontui, "metrics_preview", lambda *a, **k: calls.append((a, k)) or "preview")
    shell = SimpleNamespace(widget="w", hint_check="check")
    assert studios._metrics_preview(shell, SimpleNamespace(font=lambda: "font")) == "preview"
    assert calls == [(("font", "w"), {"controls": False, "hint_check": "check", "read_only": True})]
    assert studios._metrics_preview(shell, SimpleNamespace(font=lambda: None)) is None


def test_show_when_build_fails_then_shell_closed(monkeypatch):
    from fontlabapp import fontui
    import fontlabapp.studios.proof_studio as studios

    import fontlabapp.studios.proof_studio.app  # noqa: F401 - bind fontui before patching
    closed = []
    fake = SimpleNamespace(close=lambda: closed.append(True), hint_check=None, widget=None)
    monkeypatch.setattr(fontui, "app_shell", lambda *a, **k: fake)

    def boom(shell, studio):
        raise RuntimeError("no preview")

    with pytest.raises(RuntimeError, match="no preview"):
        studios.show(package=lambda: None, font=lambda: None, preview=boom)
    assert closed == [True]


def test_show_when_no_font_then_no_preview_set(monkeypatch):
    from fontlabapp import fontui
    import fontlabapp.studios.proof_studio as studios

    import fontlabapp.studios.proof_studio.app  # noqa: F401 - bind fontui before patching
    added, previews = [], []
    fake = SimpleNamespace(close=lambda: None, hint_check=None, widget=None, show=lambda: None,
                           add_tab=added.append, set_preview=previews.append)
    monkeypatch.setattr(fontui, "app_shell", lambda *a, **k: fake)
    assert studios.show(package=lambda: None, font=lambda: None) is fake
    assert previews == [] and [spec.title for spec in added] == list(studios.TAB_TITLES)


def test_registry_when_imported_then_lazy_tabs_and_studio_shared():
    from fontlabapp import studios
    import fontlabapp.studios.proof_studio as ps_mod

    assert ps_mod.TAB_TITLES == tuple(["Pattern strings", "Kerning proofs", "Random", "Real text", "Word finder", "Waterfall", "By master"])
    assert ps_mod.register_tabs() == ps_mod.TAB_TITLES
    assert ps_mod.register_tabs() == ps_mod.TAB_TITLES  # idempotent: no duplicate tabs
    with pytest.raises(AttributeError, match="no attribute 'missing'"):
        ps_mod.missing  # noqa: B018
    assert [spec.title for spec in studios.tabs(ps_mod.APP)] == list(ps_mod.TAB_TITLES)
    shell = SimpleNamespace()
    assert ps_mod.studio_for(shell) is ps_mod.studio_for(shell)
