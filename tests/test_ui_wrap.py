# this_file: tests/test_ui_wrap.py
"""Sequence selection over Fontport's placed run (host-free, Qt mocked)."""

from types import SimpleNamespace

import pytest
from fontlabapp.fontui.wrap import wrap


@pytest.fixture
def sequence_class(monkeypatch):
    import importlib
    import sys
    from unittest.mock import Mock

    for name in (
        "fontlabapp.fontui.sequence",
        "fontlabapp.fontui.sequence_canvas",
        "fontlabapp.fontui.lifecycle",
        "fontlabapp.fontui.wrap",
    ):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setitem(
        sys.modules, "PythonQt", SimpleNamespace(QtGui=Mock(), QtCore=Mock())
    )
    yield importlib.import_module("fontlabapp.fontui.sequence").Sequence
    for name in ("fontlabapp.fontui.sequence", "fontlabapp.fontui.sequence_canvas"):
        sys.modules.pop(name, None)


@pytest.mark.parametrize("wrapped", [False, True])
def test_select_at_when_advance_negative_then_interval_normalised(
    sequence_class, wrapped
):
    seq = sequence_class.__new__(sequence_class)
    seq.closed, seq.origin_x, seq.scale, seq.line_height = False, 0.0, 1.0, 100.0
    glyphs = [SimpleNamespace(index=0, x=0.0, advance=-200.0, name="n", label="n")]
    seq.run = SimpleNamespace(glyphs=glyphs, direction="ltr")
    seq.positions = wrap(glyphs, 1000 if wrapped else None, "ltr")
    picked = []
    seq._select_occurrence = picked.append
    seq.select_at(-100.0, 50.0)
    assert picked == glyphs, "x inside [-200, 0] selects the negative-advance glyph"


class Glyphs(dict):
    """A font whose glyph wrappers are new objects on every lookup (as after
    Fontport invalidation) unless fixed."""

    def __init__(self, names, fixed=True, native=None):
        super().__init__({n: SimpleNamespace(name=n) for n in names})
        self.fixed = fixed
        if native is not None:
            self._backend = SimpleNamespace(font_id=native)

    def __getitem__(self, name):
        glyph = dict.__getitem__(self, name)
        return glyph if self.fixed else SimpleNamespace(name=glyph.name)


def selected_sequence(sequence_class, font, monkeypatch):
    import sys

    seq = sequence_class.__new__(sequence_class)
    seq.closed, seq.font, seq.on_select = False, font, None
    glyphs = (SimpleNamespace(index=0, x=0.0, advance=500.0, name="A", label="A"),)
    run = SimpleNamespace(glyphs=glyphs, direction="ltr")
    seq.run, seq.selected_index = run, 0
    seq._selected_font, seq._selected_glyph = font, font["A"]
    seq._kerning_capability = lambda: None
    seq._load_run = lambda: setattr(seq, "run", run)
    seq.canvas = SimpleNamespace(update=lambda: None)
    monkeypatch.setattr(
        sys.modules["fontlabapp.fontui.sequence"], "reveal", lambda *a: None
    )
    return seq


def test_refresh_keeps_selection_when_fontlab_font_rewraps_glyphs(
    sequence_class, monkeypatch
):
    font = Glyphs(["A"], fixed=False, native=7)  # FontLab-backed: no stable wrappers
    seq = selected_sequence(sequence_class, font, monkeypatch)
    seq.refresh()
    assert seq.selected_index == 0


def test_refresh_drops_selection_when_detached_glyph_replaced(
    sequence_class, monkeypatch
):
    font = Glyphs(["A"])
    seq = selected_sequence(sequence_class, font, monkeypatch)
    dict.__setitem__(font, "A", SimpleNamespace(name="A"))  # a different glyph named A
    seq.refresh()
    assert seq.selected_index is None
