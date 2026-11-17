# this_file: tests/test_fontui_appshell.py
"""AppShell on real offscreen Qt: layout, sizing, tabs, status line and the history path."""

from types import SimpleNamespace

import pytest
from _studio_qt import studio_qt  # noqa: F401 - fixture

import fontlabapp.core.edit_guards as guards
import fontlabapp.core.history.glyphs as history


def shell(studio_qt, *args, **kwargs):  # noqa: F811
    made = studio_qt.modules.appshell.AppShell(*args, **kwargs)
    studio_qt.owned.append(made)
    return made


def owned_tab(studio_qt, title="Tab"):  # noqa: F811
    Owned = studio_qt.modules.lifecycle.Owned
    built = []

    def build(app):
        panel = Owned(None)
        built.append(panel)
        return panel

    return SimpleNamespace(title=title, build=build), built


def test_shell_when_tglyph_preview_then_tabs_left_preview_right(studio_qt):  # noqa: F811
    Qt = studio_qt.QtCore.Qt
    app = shell(studio_qt, "Glyph Studio", preview="tglyph")
    assert app.splitter.orientation() == Qt.Horizontal
    assert app.splitter.indexOf(app.tabs) == 0
    assert app.splitter.indexOf(app.preview_box) == 1
    assert app.status.text() == "Ready."


def test_shell_when_tmetrics_preview_then_preview_on_top(studio_qt):  # noqa: F811
    app = shell(studio_qt, "Kerning Studio", preview="tmetrics")
    assert app.splitter.orientation() == studio_qt.QtCore.Qt.Vertical
    assert app.splitter.indexOf(app.preview_box) == 0
    assert app.splitter.indexOf(app.tabs) == 1


def test_shell_when_no_preview_then_pane_hidden_and_bad_kind_refused(studio_qt):  # noqa: F811
    app = shell(studio_qt, "Plain")
    assert app.preview_box.isHidden()
    with pytest.raises(ValueError, match="preview must be one of"):
        studio_qt.modules.appshell.AppShell("Bad", preview="canvas")


def test_shell_when_small_content_on_large_screen_then_compact_size_and_title(studio_qt, monkeypatch):  # noqa: F811
    module = studio_qt.modules.appshell
    area = studio_qt.QtCore.QRect(0, 0, 3840, 2160)
    monkeypatch.setattr(module, "available_geometry", lambda widget: area)
    app = module.show_app("Kerning Studio")
    studio_qt.owned.append(app)
    assert app.widget.windowTitle() == "Kerning Studio"
    hint = app.widget.sizeHint().expandedTo(app.widget.minimumSizeHint())
    assert app.widget.size() == hint
    assert app.widget.width() < area.width() / 2
    assert app.widget.height() < area.height() / 2


def test_available_geometry_when_qt5_desktop_then_used(studio_qt, monkeypatch):  # noqa: F811
    module = studio_qt.modules.appshell
    rect = object()
    desktop = SimpleNamespace(availableGeometry=lambda widget: rect)
    monkeypatch.setattr(module.QtGui, "QApplication", SimpleNamespace(desktop=lambda: desktop), raising=False)
    assert module.available_geometry(SimpleNamespace()) is rect


def test_available_geometry_when_screen_property_then_value_returned(studio_qt):  # noqa: F811
    rect = object()
    screen = SimpleNamespace(availableGeometry=rect)
    assert studio_qt.modules.appshell.available_geometry(SimpleNamespace(screen=lambda: screen)) is rect


def test_available_geometry_when_screen_method_then_called(studio_qt):  # noqa: F811
    rect = object()
    screen = SimpleNamespace(availableGeometry=lambda: rect)
    assert studio_qt.modules.appshell.available_geometry(SimpleNamespace(screen=lambda: screen)) is rect


def test_available_geometry_when_screen_none_then_desktop_used(studio_qt, monkeypatch):  # noqa: F811
    module = studio_qt.modules.appshell
    rect = object()
    desktop = SimpleNamespace(availableGeometry=lambda widget: rect)
    monkeypatch.setattr(module.QtGui, "QApplication", SimpleNamespace(desktop=lambda: desktop), raising=False)
    assert module.available_geometry(SimpleNamespace(screen=lambda: None)) is rect


def test_shell_when_tabs_built_then_titled_and_closed_with_shell(studio_qt):  # noqa: F811
    spec, built = owned_tab(studio_qt, "Pairs")
    plain = SimpleNamespace(title="Plain", build=lambda app: studio_qt.modules.appshell.QtGui.QWidget())
    app = shell(studio_qt, "Kerning Studio", preview="tglyph", tabs=[spec, plain])
    assert [app.tabs.tabText(i) for i in range(app.tabs.count())] == ["Pairs", "Plain", "About"]
    preview = app.set_preview(studio_qt.modules.lifecycle.Owned(None))
    assert app.preview is preview
    app.close()
    assert built[0].closed and preview.closed and app.children == []


def test_current_layer_when_font_open_then_default_master(studio_qt):  # noqa: F811
    package = SimpleNamespace(defaultMaster="Bold")
    app = shell(studio_qt, "S", package=lambda: package)
    assert app.package() is package
    assert app.current_layer() == "Bold"


def test_current_layer_when_no_font_then_status_says_so(studio_qt, monkeypatch):  # noqa: F811
    from fontlabapp.core import scripting

    monkeypatch.setattr(scripting, "current_package", lambda: None)
    app = shell(studio_qt, "S")
    assert app.current_layer() is None
    assert app.status.text() == "Open a font first."


def test_history_when_canvas_refuses_then_status_line_and_no_write(studio_qt, monkeypatch):  # noqa: F811
    def refuse(glyphs, *, creates, native):
        raise ValueError(guards.CANVAS_TEXT)

    monkeypatch.setattr(guards, "require_history_scope", refuse)
    monkeypatch.setattr(history, "commit", lambda *a, **k: pytest.fail("commit after refusal"))
    app = shell(studio_qt, "S", package=lambda: None)
    assert app.history("S: width A", ["g"], lambda: pytest.fail("mutated"), layers=["l"]) is None
    assert app.status.text() == guards.CANVAS_TEXT


def test_history_when_partial_write_then_status_line(studio_qt, monkeypatch):  # noqa: F811
    monkeypatch.setattr(guards, "require_history_scope", lambda glyphs, **k: None)
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: None)

    def partial(*a, **k):
        raise history.PartialWriteError.__new__(history.PartialWriteError)

    monkeypatch.setattr(history, "commit", partial)
    app = shell(studio_qt, "S", package=lambda: None)
    assert app.history("S: width A", ["g"], lambda: None, layers=["l"]) is None
    assert app.status.text().startswith("Partly applied")


def test_history_when_allowed_then_one_named_commit_on_explicit_layers(studio_qt, monkeypatch):  # noqa: F811
    seen = {}
    monkeypatch.setattr(guards, "require_history_scope", lambda glyphs, **k: seen.update(scope=(glyphs, k)))
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: ("facts", package))

    def commit(title, layers, glyphs, mutate, **kwargs):
        seen.update(title=title, layers=layers, glyphs=glyphs, kwargs=kwargs)
        mutate()
        return SimpleNamespace(pending_note="Pending.")

    monkeypatch.setattr(history, "commit", commit)
    app = shell(studio_qt, "Kerning Studio", package=lambda: "pkg")
    done = []
    result = app.history("Kerning Studio: width A", ["g"], lambda: done.append(1), layers=["Bold"])
    assert result.pending_note == "Pending."
    assert done == [1]
    assert seen["scope"] == (["g"], {"creates": False, "native": None})
    assert (seen["title"], seen["layers"], seen["glyphs"]) == ("Kerning Studio: width A", ["Bold"], ["g"])
    assert seen["kwargs"]["operation"] == "geometry" and seen["kwargs"]["facts"] == ("facts", "pkg")
    assert app.status.text() == "Kerning Studio: width A. Pending."
    assert seen["kwargs"]["allow_bases"] is False  # default: bases of auto glyphs stay refused
    app.history("Spacing Studio: add sidebearings n", ["g"], lambda: None, layers=["Regular"], allow_bases=True)
    assert seen["kwargs"]["allow_bases"] is True
    assert seen["kwargs"]["window"] is None  # default: no Font-window guards
    app.history("Layer Manager: copy layers from font A", ["g"], lambda: None, layers=["Regular"], window=5)
    assert seen["kwargs"]["window"] == 5
    assert seen["kwargs"]["retain"] == ()  # default: nothing retained, two-argument notification
    app.history("Component Studio: decompose A", ["g"], lambda: None, layers=["Regular"], retain=["shape"])
    assert seen["kwargs"]["retain"] == ["shape"]


def test_fontui_factories_when_called_then_build_shell_table_and_hint_state(studio_qt):  # noqa: F811
    from fontlabapp import fontui

    app = fontui.app_shell("Glyph Studio", "tglyph")
    studio_qt.owned.append(app)
    table = fontui.glyph_table(["Glyph", "Width"])
    studio_qt.owned.append(table)
    assert app.splitter.count() == 2 and table.view is not None
    layer = SimpleNamespace(hasHints=False, hasTTData=True, hasTTH=False)
    assert fontui.layer_is_hinted(layer).tt_data
    with pytest.raises(ValueError):
        fontui.app_shell("Bad", "canvas")
    assert {"app_shell", "glyph_table", "layer_is_hinted"} <= set(fontui.__all__)


def test_hint_check_when_layer_hinted_then_reads_shell_package(studio_qt):  # noqa: F811
    hinted = SimpleNamespace(isNull=False, hasHints=True, hasTTData=False, hasTTH=False)
    glyph = SimpleNamespace(isNull=False, findLayer=lambda name: hinted if name == "Bold" else None)
    package = SimpleNamespace(defaultMaster="Bold", findName=lambda name: glyph)
    app = shell(studio_qt, "S", package=lambda: package)
    assert app.hint_check("A").ps_hints and app.hint_check("A", "Bold").ps_hints
    assert app.hint_check("A", "Light") is None


@pytest.mark.parametrize(
    "error",
    [TimeoutError("Glyph window scan exceeded its deadline."), RuntimeError("native refused"), KeyError("Z"), TypeError("bad")],
)
def test_history_when_other_write_errors_then_status_line_and_none(studio_qt, monkeypatch, error):  # noqa: F811
    def scope(glyphs, **k):
        raise error

    monkeypatch.setattr(guards, "require_history_scope", scope)
    app = shell(studio_qt, "S", package=lambda: None)
    assert app.history("S: width A", ["g"], lambda: None, layers=["l"]) is None
    assert app.status.text() == f"Error: {error}"


def test_shell_when_about_then_source_and_credits_visible(studio_qt):  # noqa: F811 - imported fixture
    app = shell(studio_qt, "S")
    assert app.tabs.tabText(app.tabs.count() - 1) == "About"
    assert "FontLab" in app.about.text()
    assert "Apache" in app.about.text()
    assert app.apply_button.isHidden()


def test_shell_when_actions_then_staged_refresh_and_unaccepted_apply_refused(studio_qt):  # noqa: F811 - imported fixture
    spec, built = owned_tab(studio_qt)
    app = shell(studio_qt, "S", tabs=[spec])
    seen = []
    state = {"dirty": True, "ready": False}
    app.set_actions(built[0], refresh=lambda: seen.append("refresh"),
                    preview=lambda: seen.append("preview"), apply=lambda: seen.append("apply"),
                    dirty=lambda: state["dirty"], ready=lambda: state["ready"])
    app.refresh_button.click()
    assert seen == [] and "staged" in app.status.text()
    app.preview_button.click()
    app.apply_button.click()
    assert seen == ["preview"] and not app.apply_button.isEnabled()
    app._run_action("apply")
    assert seen == ["preview"] and "accepted" in app.status.text()
    state.update(dirty=False, ready=True)
    app.refresh_button.click()
    app.apply_button.click()
    assert seen == ["preview", "refresh", "apply"]
    app.tabs.setCurrentIndex(app.tabs.count() - 1)
    assert app.apply_button.isHidden()
    assert not app.refresh_button.isEnabled()
    app.tabs.setCurrentIndex(0)
    assert not app.apply_button.isHidden()
    assert state == {"dirty": False, "ready": True}


def test_shell_when_child_close_unacknowledged_then_retained_for_retry(studio_qt, monkeypatch):  # noqa: F811 - imported fixture
    app = shell(studio_qt, "S")
    child = studio_qt.modules.lifecycle.Owned(None)
    app.embed(child)
    close = child.close
    monkeypatch.setattr(child, "close", lambda: None)
    with pytest.raises(RuntimeError, match="incomplete"):
        app.close()
    assert app.children == [child] and not app._close_complete
    monkeypatch.setattr(child, "close", close)
    app.close()
    assert app._close_complete and child._close_complete


@pytest.mark.parametrize("area", [(0, 0, 300, 240), (-1600, 50, 1200, 900)])
def test_shell_when_saved_geometry_outside_display_then_clamped(studio_qt, monkeypatch, area):  # noqa: F811 - imported fixture
    app = shell(studio_qt, "S", preview="tglyph")
    rect = studio_qt.QtCore.QRect(*area)
    monkeypatch.setattr(studio_qt.modules.appshell, "available_geometry", lambda widget: rect)
    app.show()
    assert app.widget.width() <= rect.width() and app.widget.height() <= rect.height()
    app.widget.resize(4000, 3000)
    app.widget.move(9000, 9000)
    app.show()
    geometry = app.widget.geometry()
    assert rect.contains(geometry)
    assert rect.contains(app.widget.frameGeometry())


def test_shell_when_splitter_initialized_then_preview_gets_equal_half(studio_qt):  # noqa: F811 - imported fixture
    for kind, index in (("tglyph", 1), ("tmetrics", 0)):
        app = shell(studio_qt, "S", preview=kind)
        app.show()
        sizes = app.splitter.sizes()
        assert sizes[index] / sum(sizes) == pytest.approx(0.5, abs=0.01)


def test_shell_when_close_button_fails_then_button_retries(studio_qt, monkeypatch):  # noqa: F811 - imported fixture
    app = shell(studio_qt, "S")
    child = studio_qt.modules.lifecycle.Owned(None)
    app.embed(child)
    close = child.close
    monkeypatch.setattr(child, "close", lambda: None)
    app.close_button.click()
    assert "Retry Close" in app.status.text()
    monkeypatch.setattr(child, "close", close)
    app.close_button.click()
    assert app._close_complete


def test_shell_when_task_help_supplied_then_about_replaced(studio_qt):  # noqa: F811 - imported fixture
    app = shell(studio_qt, "S")
    app.set_about("Task help. Source: example.org. Credits: Author, MIT.")
    assert "Author, MIT" in app.about.text()


def test_shell_when_action_raises_then_status_and_window_retained(studio_qt):  # noqa: F811 - imported fixture
    spec, built = owned_tab(studio_qt)
    app = shell(studio_qt, "S", tabs=[spec])
    def fail():
        raise ValueError("stale target")
    app.set_actions(built[0], preview=fail)
    app.preview_button.click()
    assert app.status.text() == "Error: stale target"
    app._run_action("missing")
    app.close()
    app._run_action("preview")


def test_shell_when_tabs_added_after_construction_then_first_task_selected(studio_qt):  # noqa: F811 - imported fixture
    app = shell(studio_qt, "S")
    spec, built = owned_tab(studio_qt)
    app.add_tab(spec)
    assert app.tabs.currentWidget() is built[0].widget
    app.tabs.setCurrentIndex(1)
    app.add_tab(owned_tab(studio_qt, "Second")[0])
    assert app.tabs.currentWidget() is app.about


class _PropertyCountTabs:
    """PythonQt exposes QTabWidget.count as an int property, not a method."""

    def __init__(self, tabs):
        self._tabs = tabs

    @property
    def count(self):
        return self._tabs.count()

    def __getattr__(self, name):
        return getattr(self._tabs, name)


def test_shell_when_tab_count_is_int_property_then_first_task_selected(studio_qt):  # noqa: F811 - imported fixture
    app = shell(studio_qt, "S")
    app.tabs = _PropertyCountTabs(app.tabs)
    assert isinstance(app.tabs.count, int)
    spec, built = owned_tab(studio_qt)
    app.add_tab(spec)
    assert app.tabs.currentWidget() is built[0].widget


def test_shell_when_child_reenters_close_then_retained_and_retry_completes(studio_qt, monkeypatch):  # noqa: F811 - imported fixture
    app = shell(studio_qt, "S")
    child = studio_qt.modules.lifecycle.Owned(None)
    app.embed(child)
    close = child.close
    monkeypatch.setattr(child, "close", app.close)
    with pytest.raises(RuntimeError, match="already in progress"):
        app.close()
    assert app.children == [child] and not app._close_complete
    monkeypatch.setattr(child, "close", close)
    app.close()
    assert app._close_complete


@pytest.mark.parametrize("before_close", [False, True])
def test_shell_when_disconnect_refused_then_close_button_can_retry(studio_qt, before_close):  # noqa: F811
    app = shell(studio_qt, "S")
    state = {"refuse": True}
    def disconnect(slot):
        if state["refuse"]:
            raise RuntimeError("disconnect refused")
    signal = SimpleNamespace(connect=lambda slot: None, disconnect=disconnect)
    app.connect(signal, lambda: None)
    if before_close:
        app.connections.insert(1, app.connections.pop())
    app.close_button.click()
    assert not app._close_complete and "Retry Close" in app.status.text()
    state["refuse"] = False
    app.close_button.click()
    assert app._close_complete


def test_shell_when_legacy_close_adapter_then_return_acknowledges_cleanup(studio_qt):  # noqa: F811
    app = shell(studio_qt, "S")
    calls = []
    class Adapter(studio_qt.modules.lifecycle.Owned):
        def __init__(self):
            pass
        def close(self):
            calls.append("closed")
    app.children.append(Adapter())
    app.close()
    assert calls == ["closed"] and app._close_complete


def test_factory_when_tab_build_fails_then_partial_shell_releases_owned_resources(studio_qt):  # noqa: F811
    from fontlabapp import fontui

    made = []
    failure = ValueError("task construction failed")

    def build(app):
        made.append(app)
        child = studio_qt.modules.lifecycle.Owned(None)
        app.embed(child)
        made.append(child)
        raise failure

    with pytest.raises(ValueError) as caught:
        fontui.app_shell("Broken task", tabs=[SimpleNamespace(title="Task", build=build)])
    assert caught.value is failure
    assert all(owner._close_complete and not owner.connections for owner in made)
    assert made[0].children == []


def test_shell_when_apply_leaves_task_status_then_shell_shows_it(studio_qt):  # noqa: F811 - imported fixture
    spec, built = owned_tab(studio_qt)
    app = shell(studio_qt, "S", tabs=[spec])
    app.set_actions(
        built[0],
        apply=lambda: None,
        ready=lambda: True,
        status=lambda: "Close the Glyph windows first.",
    )
    app.set_status("Ready.")
    app._run_action("apply")
    assert app.status.text() == "Close the Glyph windows first.", (
        "A refusal reported in the task panel must replace the shell's Ready."
    )


def test_shell_when_apply_task_status_empty_then_status_unchanged(studio_qt):  # noqa: F811 - imported fixture
    spec, built = owned_tab(studio_qt)
    app = shell(studio_qt, "S", tabs=[spec])
    app.set_actions(built[0], apply=lambda: None, ready=lambda: True, status=lambda: "")
    app.set_status("Ready.")
    app._run_action("apply")
    assert app.status.text() == "Ready."


@pytest.mark.parametrize("kind", [None, "tglyph", "tmetrics"])
def test_shell_when_controls_have_minima_then_fit_initial_window(studio_qt, monkeypatch, kind):
    module = studio_qt.modules.appshell
    area = studio_qt.QtCore.QRect(0, 0, 3840, 2160)
    monkeypatch.setattr(module, "available_geometry", lambda widget: area)
    app = shell(studio_qt, "Controls", preview=kind)
    panel = module.QtGui.QWidget()
    layout = module.QtGui.QVBoxLayout(panel)
    button = module.QtGui.QPushButton("A long accessible control label")
    button.setMinimumSize(420, 180)
    layout.addWidget(button)
    app.add_tab(SimpleNamespace(title="Controls", build=lambda app: panel))
    if kind is not None:
        app.set_preview(module.QtGui.QWidget())
    app.show()
    studio_qt.app.processEvents()
    assert button.width() >= 420 and button.height() >= 180
    assert app.widget.rect().contains(app.splitter.geometry())
    if kind is not None:
        sizes = app.splitter.sizes()
        assert sizes[0] == pytest.approx(sizes[1], abs=1)
        assert app.preview_layout.contentsMargins().left() == 0
        assert app.preview_layout.contentsMargins().top() == 0
        assert not isinstance(app.preview_box, module.QtGui.QFrame)


def test_shell_when_shown_again_then_user_window_and_splitter_sizes_retained(studio_qt, monkeypatch):
    module = studio_qt.modules.appshell
    monkeypatch.setattr(module, "available_geometry", lambda widget: studio_qt.QtCore.QRect(0, 0, 3840, 2160))
    app = shell(studio_qt, "Resize", preview="tglyph")
    app.show()
    app.widget.resize(900, 600)
    app.splitter.setSizes([600, 300])
    before = app.widget.size(), app.splitter.sizes()
    app.show()
    assert (app.widget.size(), app.splitter.sizes()) == before
def test_shell_when_plan_readiness_changes_then_apply_enabled_follows_actions(studio_qt):  # noqa: F811
    spec, built = owned_tab(studio_qt)
    app = shell(studio_qt, "S", tabs=[spec])
    state = {"ready": False, "writes": 0}

    def preview():
        state["ready"] = True

    def apply():
        state["writes"] += 1
        state["ready"] = False

    app.set_actions(built[0], preview=preview, apply=apply,
                    ready=lambda: state["ready"])
    assert not app.apply_button.isEnabled()
    app.apply_button.click()
    assert state["writes"] == 0
    app.preview_button.click()
    assert app.apply_button.isEnabled()
    app.apply_button.click()
    assert state["writes"] == 1 and not app.apply_button.isEnabled()
    state["ready"] = True
    app.set_status("New accepted preview")
    assert app.apply_button.isEnabled()
    state["ready"] = False
    app.set_status("Draft changed")
    assert not app.apply_button.isEnabled()


def test_shell_when_ready_check_raises_then_apply_disabled_and_error_contained(studio_qt):  # noqa: F811
    spec, built = owned_tab(studio_qt)
    app = shell(studio_qt, "S", tabs=[spec])

    def ready():
        raise ValueError("Original font closed")

    app.set_actions(built[0], apply=lambda: pytest.fail("Applied invalid target"), ready=ready)
    assert not app.apply_button.isEnabled()
    assert "Original font closed" in app.status.text()
    app.apply_button.click()
