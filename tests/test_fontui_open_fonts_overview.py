# this_file: tests/test_fontui_open_fonts_overview.py
"""Real font-browser callbacks over explicit fake native package metrics."""

import importlib
import sys
from types import SimpleNamespace

import pytest
from test_fontui_glyph_metrics import composition_env as _composition_env, owned_font

composition_env = _composition_env
del _composition_env


class Font:
    def __init__(self, identifier=1):
        self.source = owned_font()
        self.package = SimpleNamespace(
            id=identifier + 10, fgId=identifier, master="Regular",
            masters=["Regular", "Bold"], axes=[],
            location=lambda master: {},
        )
        self._backend = SimpleNamespace(font_id=identifier, _package=lambda: self.package)

    def _check(self):
        pass

    def __getattr__(self, name):
        return getattr(self.source, name)

    def __getitem__(self, name):
        return self.source[name]

    def __contains__(self, name):
        return name in self.source


class World:
    def __init__(self, *fonts):
        self.fonts = list(fonts)

    def AllFonts(self):
        return self.fonts


@pytest.fixture
def overview_env(composition_env, monkeypatch):
    env = composition_env
    import fontlabapp
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.fonts", raising=False)
    module = importlib.import_module("fontlabapp.fontui.open_fonts_overview")
    values = SimpleNamespace(ascender=750, capsHeight=700, xHeight=500, descender=-250)
    native = fontlabapp._native
    host = SimpleNamespace(FontMetrics=lambda package, master: values)
    monkeypatch.setattr(fontlabapp, "_native", lambda name: host if name == "fontlab" else native(name))
    yield SimpleNamespace(**vars(env), module=module, values=values, host=host)
    for owner in tuple(module._HANDLES):
        owner.release()
    module._HANDLES.clear()
    sys.modules.pop("fontlabapp.fontui.fonts", None)


def test_overview_when_font_changes_then_current_master_report_and_no_master_switch(overview_env):
    env = overview_env
    first, second = Font(), Font(2)
    second.package.master = "Bold"
    owner = env.module.show(World(first, second), env.parent)
    assert owner.report is None and "Choose" in owner.status.text
    owner.browser.font_list.setCurrentRow(0)
    assert owner.report == ("Regular", "–", (("Ascender", 750.0), ("Cap height", 700.0), ("x-height", 500.0), ("Descender", -250.0)))
    assert "Current master: Regular" in owner.comparison.text
    owner.browser.font_list.setCurrentRow(1)
    assert owner.report[0] == "Bold"
    assert first.package.master == "Regular" and second.package.master == "Bold"
    owner.refresh_button.clicked.emit()
    assert owner.report[0] == "Bold"
    owner._closing = True
    owner.selected(first, ())
    owner.refresh()
    assert owner.release() and owner.release()


@pytest.mark.parametrize("failure", ["foreign", "closed", "identity", "master", "nonfinite", "read", "changed", "refresh"])
def test_overview_when_source_invalid_then_clear_old_report(overview_env, failure):
    env = overview_env
    font = Font()
    world = World(font)
    owner = env.module.show(world, env.parent)
    owner.browser.font_list.setCurrentRow(0)
    assert owner.report
    if failure == "foreign":
        owner.selected(Font(), ())
    elif failure == "refresh":
        world.AllFonts = lambda: (_ for _ in ()).throw(ValueError("refresh failed"))
        owner.refresh()
    else:
        if failure == "closed":
            world.fonts = []
        elif failure == "identity":
            font.package.fgId = 99
        elif failure == "master":
            font.package.master = "Missing"
        elif failure == "nonfinite":
            env.values.ascender = float("nan")
        elif failure == "read":
            font._check = lambda: (_ for _ in ()).throw(ValueError("closed"))
        else:
            def changed(package, master):
                package.master = "Bold"
                return env.values
            env.host.FontMetrics = changed
        owner.selected(font, ())
    assert owner.report is None and not owner.comparison.text and owner.status.text
    assert owner.release()


def test_overview_when_close_during_read_then_no_late_report(overview_env):
    env = overview_env
    font = Font()
    owner = env.module.show(World(font), env.parent)
    def closing(package, master):
        owner._closing = True
        return env.values
    env.host.FontMetrics = closing
    owner.browser.font_list.setCurrentRow(0)
    assert owner.report is None
    assert owner.release()


def test_overview_when_construction_fails_then_owner_released(overview_env, monkeypatch):
    env = overview_env
    widgets = importlib.import_module("fontlabapp.qt.widgets")
    monkeypatch.setattr(widgets, "create_dialog", lambda *args: (_ for _ in ()).throw(ValueError("build")))
    with pytest.raises(ValueError, match="build"):
        env.module.show(World(Font()), env.parent)
    assert not env.module._HANDLES


def test_overview_when_selection_reenters_then_old_font_cannot_replace_report(overview_env):
    env = overview_env
    first, second = Font(), Font(2)
    second.package.master = "Bold"
    owner = env.module.show(World(first, second), env.parent)
    def reenter(package, master):
        if package is first.package:
            owner.browser.font_list.setCurrentRow(1)
        return env.values
    env.host.FontMetrics = reenter
    owner.browser.font_list.setCurrentRow(0)
    assert owner.browser.state.selected is second
    assert owner.report[0] == "Bold"
    assert owner.release()


def test_overview_when_created_then_font_browser_following_is_opted_out(overview_env, monkeypatch):
    env = overview_env
    fonts = importlib.import_module("fontlabapp.fontui.fonts")
    calls = []
    monkeypatch.setattr(fonts, "follow_changes", lambda *args: calls.append(args))
    owner = env.module.show(World(Font()), env.parent)
    assert calls == []
    from fontlabapp.fontui import font_browser
    ordinary = font_browser([], env.parent)
    assert len(calls) == 1
    ordinary.close()
    assert owner.release()


def test_overview_when_obsolete_read_fails_then_new_font_report_is_retained(overview_env):
    env = overview_env
    first, second = Font(), Font(2)
    second.package.master = "Bold"
    owner = env.module.show(World(first, second), env.parent)
    def reenter(package, master):
        if package is first.package:
            owner.browser.font_list.setCurrentRow(1)
            raise ValueError("obsolete read failed")
        return env.values
    env.host.FontMetrics = reenter
    owner.browser.font_list.setCurrentRow(0)
    assert owner.report[0] == "Bold"
    assert "obsolete" not in owner.status.text
    assert owner.release()


@pytest.mark.parametrize("cleanup_error", [False, True])
def test_overview_when_failed_cleanup_then_primary_error_and_owner_retained(overview_env, monkeypatch, cleanup_error):
    env = overview_env
    widgets = importlib.import_module("fontlabapp.qt.widgets")
    monkeypatch.setattr(widgets, "create_dialog", lambda *args: (_ for _ in ()).throw(ValueError("primary")))
    original = env.module.OpenFontsOverview.release
    def cleanup(self):
        if cleanup_error:
            raise RuntimeError("cleanup")
        return False
    monkeypatch.setattr(env.module.OpenFontsOverview, "release", cleanup)
    with pytest.raises(ValueError, match="primary") as caught:
        env.module.show(World(Font()), env.parent)
    assert "owner retained" in caught.value.__notes__[0]
    assert len(env.module._HANDLES) == 1
    monkeypatch.setattr(env.module.OpenFontsOverview, "release", original)
    assert env.module._HANDLES[0].release()
