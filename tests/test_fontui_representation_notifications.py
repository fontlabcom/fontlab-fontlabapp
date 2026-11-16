# this_file: tests/test_fontui_representation_notifications.py
"""Observe actual defcon invalidation and clean ownership with fake Qt."""

import importlib
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fontParts.fontshell import RFont
from test_fontui_glyph_metrics import choose, owned_font
from test_fontui_glyph_metrics import composition_env as _composition_env

composition_env = _composition_env


def live_font():
    font = RFont()
    font.info.unitsPerEm = 1000
    glyph = font.newGlyph("A")
    glyph.width = 600
    pen = glyph.getPen()
    pen.moveTo((0, 0))
    pen.lineTo((100, 0))
    pen.lineTo((100, 100))
    pen.closePath()
    return font


@pytest.fixture
def env(composition_env, monkeypatch):
    qt = composition_env.qt
    monkeypatch.setattr(qt.QtGui.QWidget, "setWindowTitle", lambda self, value: None, raising=False)
    module = importlib.import_module("fontlabapp.fontui.representation_notifications")
    yield composition_env, module
    for owner in tuple(module._HANDLES):
        owner.close()


def test_actual_notifications_when_outline_changes_then_cache_recomputed_and_observer_removed(env):
    qt, module = env
    font = live_font()
    owner = module.show(font, qt.parent)
    choose(owner.browser, ["A"])
    model = font["A"].naked()
    assert model.hasObserver(owner, "Glyph.Changed")
    assert owner.rows, owner.status.text
    assert float(owner.rows[0][1]) == 5000
    assert owner.rows[0][3] == "True"
    font["A"].scaleBy((2, 1))
    assert owner.notifications > 0
    assert float(owner.rows[0][1]) == 10000
    assert owner.rows[0][2:] == ("False", "True")
    assert "notification refresh completed" in owner.status.text
    owner.refresh_button.clicked.emit()
    assert owner.rows[0][2:] == ("True", "True")
    owner.close()
    owner.close()
    assert not model.hasObserver(owner, "Glyph.Changed")
    assert owner._close_complete and owner not in module._HANDLES
    owner.changed(None)
    owner.refresh()
    owner.selected(font, ("A",))


def test_unsupported_and_missing_selection_when_inspected_then_honest_status(env):
    qt, module = env
    font = owned_font()
    owner = module.show(font, qt.parent)
    choose(owner.browser, ["A"])
    assert len(owner.rows) == 2
    assert "unavailable" in owner.status.text
    owner.selected(None, ("A",))
    assert not owner.rows and "another font" in owner.status.text
    owner.selected(font, ())
    assert owner.status.text == "Select a glyph"
    owner.selected(font, ("missing",))
    assert not owner.rows
    owner.close()
    owner = module.show(None, qt.parent)
    assert owner.status.text == "No font supplied"


def test_refresh_when_glyph_replaced_or_read_fails_then_no_stale_rows(env, monkeypatch):
    qt, module = env
    font = live_font()
    owner = module.show(font, qt.parent)
    choose(owner.browser, ["A"])
    monkeypatch.setattr(owner.observed, "getRepresentation", lambda key: (_ for _ in ()).throw(ValueError("cache failure")))
    owner.refresh()
    assert not owner.rows and "cache failure" in owner.status.text
    owner._reading = True
    owner.refresh()
    owner._reading = False
    font.removeGlyph("A")
    font.newGlyph("A")
    owner.refresh()
    assert not owner.rows and "identity changed" in owner.status.text


def test_close_when_observer_removal_fails_then_owner_retained_for_retry(env, monkeypatch):
    qt, module = env
    owner = module.show(live_font(), qt.parent)
    choose(owner.browser, ["A"])
    model = owner.observed
    original = model.removeObserver
    monkeypatch.setattr(model, "removeObserver", lambda *args: (_ for _ in ()).throw(RuntimeError("unsubscribe")))
    with pytest.raises(RuntimeError, match="unsubscribe"):
        owner.close()
    assert owner in module._HANDLES and owner.observed is model
    monkeypatch.setattr(model, "removeObserver", original)
    owner.close()
    assert owner not in module._HANDLES


def test_show_when_widget_show_fails_then_resources_cleaned(env, monkeypatch):
    qt, module = env
    monkeypatch.setattr(qt.qt.QtGui.QWidget, "show", lambda self: (_ for _ in ()).throw(RuntimeError("show")))
    with pytest.raises(RuntimeError, match="show"):
        module.show(live_font(), qt.parent)
    assert not module._HANDLES


@pytest.mark.parametrize("dispatch", ["main", "script"])
def test_demo_when_invoked_then_captures_once_and_opens_actual_composition(env, monkeypatch, dispatch):
    _qt, module = env
    calls = []
    font = live_font()
    class World:
        def CurrentFont(self):
            calls.append(1)
            return font
    monkeypatch.setitem(sys.modules, "fontlab_fontport.world", SimpleNamespace(FontWorld=World))
    path = Path(__file__).resolve().parents[1] / "Scripts/Font Editors/Representation and Notification Explorer Demo.py"
    result = runpy.run_path(str(path), run_name="__main__" if dispatch == "script" else "demo")
    if dispatch == "main":
        result["main"]()
    assert calls == [1]
    owner = module._HANDLES[-1]
    choose(owner.browser, ["A"])
    assert owner.rows and owner.font is font


@pytest.mark.parametrize("failure", ["raise", "refuse"])
def test_registration_when_not_acknowledged_then_refresh_never_claims_observation(env, monkeypatch, failure):
    qt, module = env
    font = live_font()
    model = font["A"].naked()
    owner = module.show(font, qt.parent)
    def add(*args):
        if failure == "raise":
            raise RuntimeError("registration failed")
    monkeypatch.setattr(model, "addObserver", add)
    choose(owner.browser, ["A"])
    assert not owner._registered
    owner.refresh()
    assert not owner.rows
    assert "registration is not verified" in owner.status.text
    owner.close()


def test_parent_destruction_when_observing_then_disconnects_and_releases(env):
    qt, module = env
    font = live_font()
    owner = module.show(font, qt.parent)
    choose(owner.browser, ["A"])
    model = font["A"].naked()
    qt.parent.destroyed.emit()
    assert owner._close_complete and owner not in module._HANDLES
    assert not model.hasObserver(owner, "Glyph.Changed")


def test_constructor_when_browser_fails_then_root_is_cleaned(env, monkeypatch):
    qt, module = env
    native = importlib.import_module("fontlabapp.fontui.native")
    original = native.Browser.__init__
    def fail(self, *args):
        original(self, *args)
        raise ValueError("browser failed")
    monkeypatch.setattr(native.Browser, "__init__", fail)
    with pytest.raises(ValueError, match="browser failed"):
        module.show(live_font(), qt.parent)
    assert not module._HANDLES


def test_cold_import_when_host_missing_then_module_and_demo_remain_lazy():
    from test_fontui_master_width_comparison_demo import cold_import
    root = Path(__file__).resolve().parents[1]
    cold_import(root / "src/fontlabapp/fontui/representation_notifications.py",
                root / "Scripts/Font Editors/Representation and Notification Explorer Demo.py")
