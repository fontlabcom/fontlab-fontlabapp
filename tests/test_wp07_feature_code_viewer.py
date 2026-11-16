# this_file: tests/test_wp07_feature_code_viewer.py
# SPDX-License-Identifier: Apache-2.0
"""Behaviour checks for the Feature Code Inspector dialog with fake Qt and fonts."""

from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS

import pytest

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "src/fontlabapp/features/identity_tools/feature_authoring/feature_code_viewer.py"
DUP = ROOT / "src/fontlabapp/glyphs/identity_tools/glyph_identity/duplicate_unicodes.py"
BLOCKS = {"prefix": "languagesystem DFLT dflt;", "features": [("liga", "sub f i by fi;"), ("kern", "pos A V -50;")]}


class Signal:
    def connect(self, slot):
        self.slot = slot


class Combo:
    def __init__(self):
        self.items, self.currentIndex, self.blocked = [], 0, []
        self.currentIndexChanged = Signal()

    def addItem(self, text):
        self.items.append(text)

    def addItems(self, texts):
        self.items.extend(texts)

    def clear(self):
        self.items = []

    def setCurrentIndex(self, i):
        self.currentIndex = i

    def blockSignals(self, flag):
        self.blocked.append(flag)


class Line:
    def __init__(self):
        self.text = ""
        self.textChanged = Signal()

    def setPlaceholderText(self, text):
        self.placeholder = text


class Cursor:
    def __init__(self):
        self.moved = None

    def movePosition(self, where):
        self.moved = where


class Edit:
    def __init__(self):
        self.plain = self.html = None
        self.finds, self.found = [], [False, True]
        self.cursor = Cursor()

    def setReadOnly(self, v):
        pass

    def setAcceptRichText(self, v):
        pass

    def setPlainText(self, t):
        self.plain = t

    def setHtml(self, t):
        self.html = t

    def find(self, text):
        self.finds.append(text)
        return self.found.pop(0) if self.found else True

    def textCursor(self):
        return self.cursor

    def setTextCursor(self, c):
        self.set_cursor = c


class Base:
    def __init__(self, parent=None, title="", subtitle="", key=""):
        self.package = "pkg"
        self.apply_button = NS(texts=[], enabled=[], setText=lambda t: self.apply_button.texts.append(t),
                               setEnabled=lambda v: self.apply_button.enabled.append(v))
        self.status = NS(setText=lambda t: setattr(self, "status_text", t))
        self.palette = NS(color=lambda role: NS(name=lambda: "#" + str(role)))
        self.root = NS(addWidget=lambda *a: None)
        self.fonts = 0
        self.previews = 0

    def prepare(self):
        return self.root

    def _connect(self, signal, slot):
        signal.connect(slot)

    def ensure_font(self):
        self.fonts += 1

    def ensure_preview(self):
        self.previews += 1


@pytest.fixture
def module(monkeypatch):
    shown = []
    qt = NS(
        QtCore=NS(),
        QtGui=NS(QComboBox=Combo, QLineEdit=Line, QTextEdit=Edit,
                 QPalette=NS(Highlight=1, HighlightedText=2), QTextCursor=NS(Start=7)),
    )
    glyphs = [NS(name="b"), NS(name="a")]
    fl = NS(CurrentFont=lambda: NS(glyphs=glyphs))
    app = ModuleType("fontlabapp")
    app._native = lambda name: qt if name == "PythonQt" else fl
    scripting = ModuleType("fontlabapp.core.scripting")
    scripting.features_dialog_type = lambda: Base
    scripting.show_script_dialog = lambda cls, key: shown.append((cls, key)) or "shown"
    fb = ModuleType("fontlabapp.fontui.feature_blocks")
    fb.read_feature_blocks = lambda package: dict(BLOCKS)
    for name, mod in (("fontlabapp", app), ("fontlabapp.core", ModuleType("fontlabapp.core")),
                      ("fontlabapp.core.scripting", scripting), ("fontlabapp.fontui", ModuleType("fontlabapp.fontui")),
                      ("fontlabapp.fontui.feature_blocks", fb)):
        monkeypatch.setitem(sys.modules, name, mod)
    spec = importlib.util.spec_from_file_location("wp07_fcv", SOURCE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.shown = shown
    return mod


def make(module):
    dialog = module.Dialog()
    dialog.setup()
    return dialog


def test_setup_when_package_then_lists_prefix_and_features(module) -> None:
    d = make(module)
    assert d.feature.items == ["Prefix / languagesystems", "liga", "kern"]
    assert d.apply_button.texts == [module.ACTION]


def test_setup_when_no_package_then_only_prefix(module) -> None:
    d = module.Dialog()
    d.package = None
    d.setup()
    assert d.feature.items == ["Prefix / languagesystems"]


def test_refresh_when_feature_changed_then_shows_source_and_enables_on_search(module) -> None:
    d = make(module)
    d.search.text = "fi"
    d.feature.currentIndex = 1
    d.feature.currentIndexChanged.slot()
    assert d.code.plain == "sub f i by fi;"
    assert d.apply_button.enabled[-1] is True
    assert d.fonts >= 1


def test_highlight_when_needle_then_counts_matches_case_insensitively_and_escapes(module) -> None:
    d = make(module)
    d.feature.currentIndex = 1
    d.code.plain = None
    d.refresh()
    d.search.text = "FI"
    d.search.textChanged.slot()
    assert d.match_count == 1
    assert d.status_text == "2 features · 1 search matches"
    assert d.code.html.startswith('<pre style="white-space:pre-wrap">')
    assert "<span" in d.code.html


def test_reload_when_font_changed_then_rereads_names_and_keeps_tag(module) -> None:
    d = make(module)
    d.feature.currentIndex = 2
    BLOCKS_BACKUP = module.read_feature_blocks
    module.read_feature_blocks = lambda p: {"prefix": "", "features": [("kern", "x"), ("liga", "y")]}
    d.reload()
    assert d.names == ["a", "b"]
    assert d.feature.items == ["Prefix / languagesystems", "kern", "liga"]
    assert d.feature.currentIndex == 1
    assert d.feature.blocked == [True, False]
    module.read_feature_blocks = BLOCKS_BACKUP


def test_reload_when_tag_gone_then_index_zero(module) -> None:
    d = make(module)
    d.feature.currentIndex = 1
    module.read_feature_blocks = lambda p: {"prefix": "", "features": [("zzz", "x")]}
    d.reload()
    assert d.feature.currentIndex == 0


def test_proof_text_when_tokens_known_then_unique_slash_names(module) -> None:
    d = make(module)
    d.names = ["f", "i", "fi"]
    d.feature.currentIndex = 1
    d.code.plain = None
    assert d.proof_text() == "/f/i/fi"


def test_apply_when_no_search_then_nothing_found(module) -> None:
    d = make(module)
    d.apply()
    assert d.code.finds == []
    assert d.previews == 1


def test_apply_when_not_found_then_wraps_to_start(module) -> None:
    d = make(module)
    d.search.text = "fi"
    d.feature.currentIndex = 1
    d.refresh()
    d.apply()
    assert d.code.finds == ["fi", "fi"]
    assert d.code.cursor.moved == 7
    assert d.last_result == {"matches": d.match_count}


def test_run_and_main_delegate(module) -> None:
    assert module.run(("a", "b")) == ["a", "b"]
    assert module.main() == "shown"
    assert module.shown == [(module.Dialog, module.KEY)]


def test_duplicate_unicodes_when_run_as_main_then_shows(monkeypatch) -> None:
    calls = []
    model = ModuleType("fontlabapp.glyphs.unicode.duplicates.model")
    model.show = lambda: calls.append(1)
    monkeypatch.setitem(sys.modules, model.__name__, model)
    runpy.run_path(str(DUP), run_name="__main__")
    assert calls == [1]
