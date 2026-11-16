# this_file: tests/test_fontui_tabular_audit.py
"""Exercise the real font chooser, glyph callbacks and exact width report."""

import importlib
import sys
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_fontui_glyph_metrics import composition_env as _composition_env, owned_font

composition_env = _composition_env
del _composition_env


@pytest.fixture
def audit_env(composition_env, monkeypatch):
    env = composition_env
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.fonts", raising=False)
    module = importlib.import_module("fontlabapp.fontui.tabular_audit")
    yield SimpleNamespace(**vars(env), module=module)
    for owner in tuple(module._HANDLES):
        owner.release()
    module._HANDLES.clear()
    sys.modules.pop("fontlabapp.fontui.fonts", None)


class World:
    def __init__(self, *fonts):
        self.fonts = list(fonts)
        self.calls = []

    def AllFonts(self):
        self.calls.append("AllFonts")
        return self.fonts

    def refresh(self):
        self.calls.append("refresh")
        return self.fonts


def select(controller, *names):
    browser = controller.browser.browser
    for item in browser.glyph_list.items:
        item.setSelected(item.text() in names)
    browser.glyph_list.itemSelectionChanged.emit()


def test_audit_when_real_callbacks_then_all_widths_row_order_and_duplicate_identity(audit_env):
    env = audit_env
    first, second = owned_font(), owned_font()
    first["V"].width = 600.5001
    second["V"].width = 600.5
    before = deepcopy((first, second))
    world = World(first, second)
    c = env.module.show(world, env.parent)
    assert c.world is world and world.calls == ["AllFonts"]
    assert c.browser.state.labels[0] == c.browser.state.labels[1]
    c.browser.font_list.setCurrentRow(0)
    select(c, "V")
    select(c, "V", "A")
    assert [(r.name, r.width, r.matches) for r in c.report.rows] == [
        ("A", 600.5, True), ("V", 600.5001, False)
    ]
    assert "600.5001" in c.comparison.text
    c.browser.font_list.setCurrentRow(1)
    assert c.report is None and not c.comparison.text
    select(c, "A", "V")
    assert c.report.same == 2
    assert (first, second) == before
    assert c.release() and c.world is None


def test_audit_when_refresh_return_changes_then_reacquire_and_clear(audit_env):
    env = audit_env
    first, second = owned_font(), owned_font()
    world = World(first)
    c = env.module.show(world, env.parent)
    c.browser.font_list.setCurrentRow(0)
    select(c, "A")
    world.fonts = [second]
    c.refresh_button.clicked.emit()
    assert world.calls[-1] == "refresh" and world.calls.count("refresh") == 1
    assert c.browser.state.fonts == (second,) and c.report is None
    assert c.status.text and not c.comparison.text
    assert c.release()


@pytest.mark.parametrize("route", ["empty", "filter", "removed", "missing_font", "foreign", "nan", "inf", "invalid", "refresh_error", "compare_error"])
def test_audit_when_data_unavailable_then_previous_report_cleared(audit_env, monkeypatch, route):
    env = audit_env
    font = owned_font()
    world = World(font)
    c = env.module.show(world, env.parent)
    c.browser.font_list.setCurrentRow(0)
    select(c, "A", "V")
    assert c.report is not None
    if route == "empty":
        for name in list(font.keys()):
            del font[name]
        c.browser.browser._changed()
        assert "no glyphs" in c.status.text
    elif route == "filter":
        c.browser.browser.filter_control.setText("absent")
    elif route == "removed":
        del font["A"]
        select(c, "A")
    elif route == "missing_font":
        world.fonts = []
        select(c, "A")
    elif route == "foreign":
        c.selected(owned_font(), ("A",))
    elif route in ("nan", "inf", "invalid"):
        font["A"].width = {"nan": float("nan"), "inf": float("inf"), "invalid": None}[route]
        select(c, "A")
    elif route == "refresh_error":
        def broken():
            assert c.report is None and not c.comparison.text
            raise ValueError("refresh failed")
        monkeypatch.setattr(world, "refresh", broken)
        c.refresh_button.clicked.emit()
    else:
        model = importlib.import_module("fontlabapp.metrics.tabular_width.model")
        def broken(*args):
            assert c.report is None and not c.comparison.text
            raise ValueError("comparison failed")
        monkeypatch.setattr(model, "compare", broken)
        select(c, "A")
    assert c.report is None and not c.comparison.text and c.status.text
    assert c.release()


def test_audit_when_blank_component_then_all_advances_and_full_font_preserved(audit_env, monkeypatch):
    env = audit_env
    font = owned_font()
    blank = font.newGlyph("blank")
    blank.width = 600.5
    component = font.newGlyph("component")
    component.getPen().addComponent("A", (1, 0, 0, 1, 12, 0))
    component.width = 600.5001
    font.glyphOrder = ["blank", "component", "A", "V"]
    before = deepcopy(font)
    closes = []
    monkeypatch.setattr(type(font), "close", lambda self: closes.append(self))
    c = env.module.show(World(font), env.parent)
    c.browser.font_list.setCurrentRow(0)
    select(c, "A", "component", "blank")
    assert [(r.name, r.width) for r in c.report.rows] == [
        ("blank", 600.5), ("component", 600.5001), ("A", 600.5)
    ]
    assert c.report.same == 2 and c.report.different == 1
    assert c.release() and font == before and not closes


@pytest.mark.parametrize("level", ["font", "glyph", "preview"])
@pytest.mark.parametrize("failure", ["return", "raise", "disconnect"])
def test_audit_when_child_cleanup_refuses_then_exact_owner_retained_and_retry(audit_env, monkeypatch, level, failure):
    env = audit_env
    world = World(owned_font())
    c = env.module.show(world, env.parent)
    child = {"font": c.browser, "glyph": c.browser.browser, "preview": c.browser.browser.preview}[level]
    if failure == "disconnect":
        signal, slot = child.connections[-1]
        original = signal.disconnect
        monkeypatch.setattr(signal, "disconnect", lambda slot: False)
        restore = lambda: monkeypatch.setattr(signal, "disconnect", original)
    else:
        original = child.close
        def refuse():
            if failure == "raise":
                raise ValueError("child refusal")
            return False
        monkeypatch.setattr(child, "close", refuse)
        restore = lambda: monkeypatch.setattr(child, "close", original)
    assert not c.release() and c.world is world
    assert c in env.module._HANDLES and c._stranded[0] is child
    first_error = c._stranded[1]
    assert not c.release() and c._stranded[1] is first_error
    calls = list(world.calls)
    c.refresh()
    c.selected(world.fonts[0], ("A",))
    assert world.calls == calls
    restore()
    assert c.release() and c.release() and c not in env.module._HANDLES


@pytest.mark.parametrize("route", ["finished", "destroyed", "dispatch", "refresh", "scope", "outer"])
def test_audit_when_closing_then_deferred_or_retry_and_no_late_callback(audit_env, monkeypatch, route):
    env = audit_env
    world = World(owned_font())
    c = env.module.show(world, env.parent)
    c.browser.font_list.setCurrentRow(0)
    if route in ("finished", "destroyed"):
        getattr(c.owned.content, route).emit()
        if route == "finished":
            c.owned.content.finished.emit()
        assert len(env.queue) == 1
        env.queue.pop()()
    elif route in ("dispatch", "refresh"):
        def closing(*args):
            assert not c.release()
            assert c.world is world and c._closing
            return world.fonts if route == "refresh" else original(*args)
        if route == "refresh":
            monkeypatch.setattr(world, "refresh", closing)
            c.refresh()
        else:
            model = importlib.import_module("fontlabapp.metrics.tabular_width.model")
            original = model.compare
            monkeypatch.setattr(model, "compare", closing)
            select(c, "A")
        assert c.report is None and not c.comparison.text
        env.queue.pop()()
    elif route == "scope":
        signal, slot, _ = c.scope.records[0]
        original = signal.disconnect
        monkeypatch.setattr(signal, "disconnect", lambda slot: False)
        assert not c.release()
        monkeypatch.setattr(signal, "disconnect", original)
        assert c.release()
    else:
        widget = c.owned.widget
        original = widget.close
        monkeypatch.setattr(widget, "close", lambda: False)
        assert not c.release()
        monkeypatch.setattr(widget, "close", original)
        assert c.release()
    assert c._released and c.world is None
    calls = list(world.calls)
    c.refresh()
    c.selected(world.fonts[0], ("A",))
    assert world.calls == calls


def test_audit_when_constructor_fails_after_widgets_then_preserve_first_failure(audit_env, monkeypatch):
    env = audit_env
    original = env.module.TabularAudit.build
    error = ValueError("after widgets")
    def broken(self, content):
        original(self, content)
        raise error
    monkeypatch.setattr(env.module.TabularAudit, "build", broken)
    with pytest.raises(ValueError) as caught:
        env.module.show(World(owned_font()), env.parent)
    assert caught.value is error and not env.module._HANDLES


def test_audit_when_real_world_backend_changes_then_reacquire_without_closing_fonts(audit_env):
    from fontlab_fontport.world import FontWorld
    from fontlab_fontport.memory import UFOBackend

    class Backend(UFOBackend):
        def __init__(self, font):
            super().__init__(font)
            self.close_calls = 0

        def close(self):
            self.close_calls += 1
            super().close()

    class Application:
        def __init__(self):
            self.backends = {1: Backend(owned_font()), 2: Backend(owned_font())}

        def font_ids(self):
            return tuple(self.backends)

        def backend(self, identifier, *, owned):
            assert not owned
            return self.backends[identifier]

    env = audit_env
    host = Application()
    borrowed = tuple(host.backends.values())
    before = tuple(deepcopy(b.font) for b in borrowed)
    world = FontWorld(host)
    c = env.module.show(world, env.parent)
    c.browser.font_list.setCurrentRow(0)
    select(c, "A", "V")
    assert c.report.rows[0].width == 600.5
    departed = c.browser.state.selected
    del host.backends[1]
    c.refresh_button.clicked.emit()
    assert c.report is None and len(c.browser.state.fonts) == 1
    with pytest.raises(RuntimeError):
        departed.keys()
    c.browser.font_list.setCurrentRow(0)
    select(c, "A")
    assert c.report.same == 1
    assert c.release()
    assert tuple(b.font for b in borrowed) == before
    assert all(b.close_calls == 0 for b in borrowed)


def test_audit_when_construction_and_close_fail_then_first_error_and_recovery_retained(audit_env, monkeypatch):
    env = audit_env
    original = env.module.TabularAudit.build
    initial = ValueError("first setup error")
    retained = []
    def broken(self, content):
        original(self, content)
        retained.append(self)
        child = self.browser.browser.preview
        original_close = child.close
        monkeypatch.setattr(child, "close", lambda: False)
        retained.append(original_close)
        raise initial
    monkeypatch.setattr(env.module.TabularAudit, "build", broken)
    with pytest.raises(ValueError) as caught:
        env.module.show(World(owned_font()), env.parent)
    c = retained[0]
    assert caught.value is initial and c.problems[0] is initial
    assert c in env.module._HANDLES and c._stranded[0] is c.browser.browser.preview
    monkeypatch.setattr(c.browser.browser.preview, "close", retained[1])
    assert c.release()


def test_audit_when_initial_world_read_fails_then_allocated_dialog_released(audit_env, monkeypatch):
    env = audit_env
    world = World()
    def broken():
        raise ValueError("initial world read")
    monkeypatch.setattr(world, "AllFonts", broken)
    with pytest.raises(ValueError, match="initial world read"):
        env.module.show(world, env.parent)
    assert not env.module._HANDLES


def test_audit_when_stale_font_refresh_then_reason_and_report_clear(audit_env, monkeypatch):
    env = audit_env
    font = owned_font()
    c = env.module.show(World(font), env.parent)
    c.browser.font_list.setCurrentRow(0)
    select(c, "A")
    def stale(self):
        raise RuntimeError("stale document")
    monkeypatch.setattr(type(font), "keys", stale)
    c.browser.browser._changed()
    assert c.report is None and not c.comparison.text
    assert "stale document" in c.status.text
    assert c.release()


def test_audit_when_retry_reaches_next_failed_owner_then_keep_current_and_first_errors(audit_env, monkeypatch):
    env = audit_env
    c = env.module.show(World(owned_font()), env.parent)
    preview, glyphs = c.browser.browser.preview, c.browser.browser
    first, second = ValueError("preview failed"), ValueError("browser failed")
    original = preview.close
    def first_failure():
        raise first
    def second_failure():
        raise second
    monkeypatch.setattr(preview, "close", first_failure)
    assert not c.release() and c._stranded == (preview, first)
    monkeypatch.setattr(preview, "close", original)
    original_glyphs = glyphs.close
    monkeypatch.setattr(glyphs, "close", second_failure)
    assert not c.release()
    assert c._stranded == (glyphs, second) and c.problems[0] is first
    monkeypatch.setattr(glyphs, "close", original_glyphs)
    assert c.release()
