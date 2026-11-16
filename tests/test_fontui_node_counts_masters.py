# this_file: tests/test_fontui_node_counts_masters.py
"""Owned native boundary fixtures and real browser callbacks for point counts."""

import importlib
from types import SimpleNamespace as NS

import pytest
from test_fontui_glyph_metrics import composition_env as _composition_env, owned_font, choose

composition_env = _composition_env
del _composition_env


@pytest.fixture
def env(composition_env):
    env = composition_env
    env.module = importlib.import_module("fontlabapp.fontui.node_counts_masters")
    yield env
    for owner in tuple(env.module._HANDLES):
        owner.release()


def model():
    ufo = owned_font()
    package = NS(id=9, fgId=7, isNull=False, masters=["Light", "Bold"])
    glyph = NS(id=1, name="A", isNull=False, package=package)
    layers = {}
    for i, name in enumerate(package.masters):
        nodes = [NS(id=n, isNull=False, isOff=lambda: False, isCurve=lambda: False,
                    isOn=lambda: True) for n in range(i + 2)]
        contour = NS(id=10, closed=True, nodes=lambda nodes=nodes: nodes)
        layers[name] = NS(id=i + 1, name=name, glyph=glyph, isNull=False,
                          isValid=True, isMasterLayer=True, isMaskLayer=False,
                          isService=False, autoLayer=False,
                          shapes=[NS(id=11, isComponent=False, isComposite=False,
                                     contours=[contour])])
    glyph.findLayer = layers.get
    package.findName = lambda name: glyph if name in ufo else None

    class Font:
        _backend = NS(font_id=7, _package=lambda: package)
        info = ufo.info
        glyphOrder = ufo.glyphOrder
        def _check(self):
            pass
        def keys(self):
            return ufo.keys()
        def __getitem__(self, name):
            return ufo[name]
        def __contains__(self, name):
            return name in ufo

    return Font(), package, glyph, layers


def test_real_browser_and_master_chooser_report(env):
    font, package, glyph, layers = model()
    owner = env.module.show(font, env.parent)
    choose(owner.browser, ["A"])
    assert owner.table.items == [("Light", "2", "0", "2", "1", "+0"),
                                 ("Bold", "3", "0", "3", "1", "+1")]
    assert "Bold: +1 points" in owner.comparison.calls[-1][1][0]
    assert "Total: 3 Points" in owner.comparison.calls[-1][1][0]
    owner.choose_master(1)
    assert owner.table.items[0][-1] == "-1"
    assert "Light: -1 points" in owner.comparison.calls[-1][1][0]
    assert owner.browser.preview.name == "A"
    assert owner.release() and owner.release()
    owner.choose_master(0)
    owner.selected(font, ("A",))


@pytest.mark.parametrize("route", ["missing", "reference_missing", "role", "foreign", "none", "changed", "invalid_index"])
def test_refusals_clear_previous_values(env, route):
    font, package, glyph, layers = model()
    owner = env.module.show(font, env.parent)
    choose(owner.browser, ["A"])
    if route == "missing":
        del layers["Bold"]
    elif route == "reference_missing":
        del layers["Light"]
    elif route == "role":
        layers["Bold"].autoLayer = True
    elif route == "changed":
        package.masters.append("Other")
    elif route == "invalid_index":
        owner.choose_master(-1)
    if route == "none":
        choose(owner.browser, [])
    else:
        owner.selected(object() if route == "foreign" else font, ("A",))
    if route == "missing":
        assert owner.table.items[1] == ("Bold", "Missing layer", "—", "—", "—", "—")
        assert "Bold: Missing layer" in owner.comparison.calls[-1][1][0]
    else:
        assert not owner.rows and not owner.comparison.text
    assert owner.release()


@pytest.mark.parametrize("route", ["no_font", "duplicate", "empty", "stale", "missing_glyph", "race"])
def test_native_boundaries(env, route):
    font, package, glyph, layers = model()
    if route == "no_font":
        font = None
    elif route == "duplicate":
        package.masters = ["Light", "Light"]
    elif route == "empty":
        package.masters = []
    elif route == "stale":
        package.fgId = 8
    owner = env.module.show(font, env.parent)
    if route in ("no_font", "duplicate", "empty", "stale"):
        assert "required" in owner.status.text
    elif route == "missing_glyph":
        owner.selected(font, ("absent",))
        assert "unavailable" in owner.status.text
    else:
        calls = []
        def find(name):
            calls.append(name)
            glyph.id += 1
            return glyph
        package.findName = find
        owner.selected(font, ("A",))
        assert "changed during" in owner.status.text
    assert owner.release()


def test_close_during_read_and_reentry(env, monkeypatch):
    font, *_ = model()
    owner = env.module.show(font, env.parent)
    original = env.module.counts
    def closing(*args):
        owner.selected(font, ("A",))
        assert not owner.release()
        env.queue.pop()()
        assert len(env.queue) == 1
        return original(*args)
    monkeypatch.setattr(env.module, "counts", closing)
    owner.selected(font, ("A",))
    assert not owner.rows
    env.queue.pop()()
    assert owner._released


def test_constructor_failure_keeps_first_error_and_releases(env, monkeypatch):
    original = env.module.NodeCounts.build
    def failed(self, content):
        original(self, content)
        raise ValueError("build failure")
    monkeypatch.setattr(env.module.NodeCounts, "build", failed)
    with pytest.raises(ValueError, match="build failure"):
        env.module.show(model()[0], env.parent)
    assert not env.module._HANDLES


def test_reentry_discards_interrupted_report(env, monkeypatch):
    font, *_ = model()
    owner = env.module.show(font, env.parent)
    original = env.module.counts
    def reenter(*args):
        owner.selected(font, ())
        return original(*args)
    monkeypatch.setattr(env.module, "counts", reenter)
    owner.selected(font, ("A",))
    assert not owner.rows and not owner.comparison.text
    assert owner.release()


@pytest.mark.parametrize("closing", [False, True])
def test_old_failure_cannot_replace_new_state(env, monkeypatch, closing):
    font, *_ = model()
    owner = env.module.show(font, env.parent)
    def obsolete(*args):
        if closing:
            assert not owner.release()
        else:
            owner.selected(font, ())
        owner.status.setText("newer state")
        raise ValueError("obsolete failure")
    monkeypatch.setattr(env.module, "counts", obsolete)
    owner.selected(font, ("A",))
    assert owner.status.text == "newer state"
    assert not owner.rows and not owner.comparison.text
    assert owner.release()


def test_setup_error_survives_cleanup_base_exception(env, monkeypatch):
    initial = ValueError("setup failed")
    original = env.module.NodeCounts.release
    def broken_build(self, content):
        raise initial
    def broken_release(self):
        raise KeyboardInterrupt("cleanup interrupted")
    monkeypatch.setattr(env.module.NodeCounts, "build", broken_build)
    monkeypatch.setattr(env.module.NodeCounts, "release", broken_release)
    with pytest.raises(ValueError) as caught:
        env.module.show(model()[0], env.parent)
    assert caught.value is initial
    owner = env.module._HANDLES[-1]
    assert isinstance(owner.problems[-1], KeyboardInterrupt)
    monkeypatch.setattr(env.module.NodeCounts, "release", original)
    assert owner.release()
