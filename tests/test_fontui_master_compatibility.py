# this_file: tests/test_fontui_master_compatibility.py
"""Borrowed fake native topology, real report and browser callback checks."""

import importlib
from types import SimpleNamespace as NS

import pytest
from test_fontui_glyph_metrics import composition_env as _composition_env, owned_font, choose

composition_env = _composition_env
del _composition_env


class Font:
    def __init__(self):
        self.ufo = owned_font()
        self.package = NS(id=9, fgId=7, masters=["Light", "Bold"])
        glyph = NS(id=1, name="A", package=self.package, isNull=False, layers=[])
        for i, master in enumerate(self.package.masters):
            glyph.layers.append(NS(id=i, name=master, glyph=glyph, isNull=False,
                isValid=True, isMasterLayer=True, isMaskLayer=False,
                isService=False, shapes=[], anchors=[]))
        self.package.findName = lambda name: glyph if name == "A" else None
        self._backend = NS(font_id=7, _package=lambda: self.package)

    def _check(self):
        pass

    def __getattr__(self, name):
        return getattr(self.ufo, name)

    def __getitem__(self, name):
        return self.ufo[name]


@pytest.fixture
def module(composition_env):
    module = importlib.import_module("fontlabapp.fontui.master_compatibility")
    yield module
    for owner in tuple(module._HANDLES):
        owner.release()


def test_report_when_selected_then_existing_report_and_preview(module, composition_env):
    font = Font()
    owner = module.show(font, composition_env.parent)
    choose(owner.browser, ["A"])
    assert "A is compatible" in owner.comparison.text
    assert owner.browser.preview.name == "A"
    glyph = font.package.findName("A")
    glyph.layers[1].anchors = [NS(id=30, name="top")]
    owner.refresh()
    assert "anchors differ" in owner.comparison.text
    assert "Light has" in owner.comparison.text and "Bold has top" in owner.comparison.text
    choose(owner.browser, [])
    assert owner.rows == () and not owner.comparison.text
    assert owner.release() and owner.release()
    owner.selected(font, ("A",))
    assert not module._HANDLES


@pytest.mark.parametrize("fault", ["unsupported", "masters", "duplicate", "foreign", "missing", "layer", "stale", "backend", "empty", "badname"])
def test_capture_when_invalid_then_refuse_without_partial_report(module, fault):
    font = Font()
    glyph = font.package.findName("A")
    if fault == "unsupported":
        font = None
    elif fault == "masters":
        font.package.masters = []
    elif fault == "duplicate":
        font.package.masters = ["Light", "Light"]
    elif fault == "foreign":
        glyph.package = NS(id=22)
    elif fault == "missing":
        glyph.layers.pop()
    elif fault == "layer":
        glyph.layers[0].isNull = True
    elif fault == "stale":
        original = font._check
        def changing():
            original()
            font.package.id += 1
        font._check = changing
    elif fault == "backend":
        font._check = lambda: setattr(font, "_backend", object())
    elif fault == "badname":
        font.package.masters = [None]
    else:
        font.package.findName = lambda name: None
    with pytest.raises(ValueError):
        module.capture(font, "A")


def test_callback_when_bad_selection_then_clear_and_remain_open(module, composition_env):
    font = Font()
    owner = module.show(font, composition_env.parent)
    choose(owner.browser, ["A"])
    owner.selected(Font(), ("A",))
    assert "another font" in owner.status.text
    assert not owner.rows and not owner.comparison.text
    choose(owner.browser, ["V"])
    assert "missing" in owner.status.text
    assert owner.browser.preview.name is None
    assert owner.release()


def test_close_when_signal_and_refusal_then_defer_and_retry(module, composition_env, monkeypatch):
    owner = module.show(Font(), composition_env.parent)
    child = owner.browser
    original = child.close
    monkeypatch.setattr(child, "close", lambda: False)
    owner.owned.content.finished.emit()
    composition_env.queue.pop()()
    assert owner in module._HANDLES
    monkeypatch.setattr(child, "close", original)
    assert owner.release()


def test_show_when_build_fails_then_cleanup_and_original_error(module, composition_env, monkeypatch):
    original = module.CompatibilityBrowser.build
    def broken(self, content):
        original(self, content)
        raise ValueError("build failure")
    monkeypatch.setattr(module.CompatibilityBrowser, "build", broken)
    with pytest.raises(ValueError, match="build failure"):
        module.show(Font(), composition_env.parent)
    assert not module._HANDLES


def test_selection_when_reentered_then_old_report_cannot_overwrite(module, composition_env, monkeypatch):
    font = Font()
    owner = module.show(font, composition_env.parent)
    original = module.capture
    def reenter(font, name):
        result = original(font, name)
        choose(owner.browser, ["V"])
        return result
    monkeypatch.setattr(module, "capture", reenter)
    choose(owner.browser, ["A"])
    assert not owner.rows and not owner.comparison.text
    assert "missing" in owner.status.text
    assert owner.release()


def test_show_when_cleanup_interrupted_then_retain_original_failure(module, composition_env, monkeypatch):
    initial = ValueError("initial failure")
    def broken(self, content):
        raise initial
    def interrupted(self):
        raise KeyboardInterrupt("cleanup interrupted")
    original_release = module.CompatibilityBrowser.release
    monkeypatch.setattr(module.CompatibilityBrowser, "build", broken)
    monkeypatch.setattr(module.CompatibilityBrowser, "release", interrupted)
    with pytest.raises(ValueError) as caught:
        module.show(Font(), composition_env.parent)
    assert caught.value is initial
    owner = module._HANDLES[-1]
    assert isinstance(owner.problems[-1], KeyboardInterrupt)
    monkeypatch.setattr(module.CompatibilityBrowser, "release", original_release)
    assert owner.release()
