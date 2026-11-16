# this_file: tests/test_fontui_tmetrics_outline_once.py
"""TMetrics builds each (source, glyph) outline once per refresh; reads outside a scope build afresh."""

from collections import Counter

from _tmetrics_fakes import EditableFont
from test_cov_ui_tmetrics import tm_mod  # noqa: F401 - fixture


def spy_builds(monkeypatch, module):
    builds = Counter()
    real = module.outline

    def counting(font, name):
        builds[name] += 1
        return real(font, name)

    monkeypatch.setattr(module, "outline", counting)
    return builds


def test_refresh_when_glyph_repeats_then_each_outline_built_once(tm_mod, monkeypatch):  # noqa: F811
    window = tm_mod.TMetrics(EditableFont(), None, None, "AAB")
    window.scroll.viewport().width = 800
    builds = spy_builds(monkeypatch, tm_mod.model_module)
    window.refresh()
    assert builds["A"] == 1, builds
    # The fake font has no glyph B, so only A is built; every built glyph must be built exactly once.
    assert all(count == 1 for count in builds.values()), builds


def test_outline_of_when_outside_scope_then_each_read_builds_afresh(tm_mod, monkeypatch):  # noqa: F811
    window = tm_mod.TMetrics(EditableFont(), None, None, "A")
    builds = spy_builds(monkeypatch, tm_mod.model_module)
    window.model.outline_of(window.font, "A")
    window.model.outline_of(window.font, "A")
    assert builds["A"] == 2
    with window.model.outline_scope():
        window.model.outline_of(window.font, "A")
        window.model.outline_of(window.font, "A")
    assert builds["A"] == 3
