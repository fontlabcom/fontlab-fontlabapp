# this_file: tests/test_fontui_node_editor.py
"""Shared-shell Node Editor controls, accepted actions and retryable teardown."""
import importlib
import sys
from types import SimpleNamespace as NS

import pytest
from _studio_qt import studio_qt  # noqa: F401


@pytest.fixture
def ui(studio_qt, monkeypatch):  # noqa: F811
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.node_editor.ui", raising=False)
    module = importlib.import_module("fontlabapp.fontui.node_editor.ui")
    gui = module.QtGui
    package = NS(id=7, master="Regular", masters=["Regular"])
    monkeypatch.setattr(module.scripting, "current_package", lambda *a: package)
    monkeypatch.setattr(module.fontui, "current_font", lambda: "font")
    views = []

    class View(module.Owned):
        def __init__(self, *a, **k):
            super().__init__(k["parent"])
            self.calls, self.options = [], k
            self.model = NS(data="data")
            views.append(self)

        def load(self, *a):
            self.calls.append(("load", a))

        def refresh(self):
            self.calls.append(("refresh",))

        def set_overlay(self, value):
            self.calls.append(("overlay", value))

    monkeypatch.setattr(module.fontui, "glyph_view", View)
    monkeypatch.setattr(module.overlays, "literal", lambda *a: "overlay")
    monkeypatch.setattr(module.overlays, "per_glyph", lambda *a: "overlay")

    class Panel(gui.QDialog):
        def __init__(self, parent):
            super().__init__(parent)
            self.package, self._bound_id = package, package.id
            self._snapshot_valid, self._connections = True, []
            self.close_button = gui.QPushButton("Close", self)
            self.apply_button = gui.QPushButton("Apply", self)
            self.reload_button = gui.QPushButton("Reload", self)
            self.timer = module.QtCore.QTimer(self)
            self.timer.start(10000)
            self.calls = []

        def tick(self):
            self.calls.append("tick")

        def apply(self):
            self.calls.append("copy")

        def reload(self):
            self.calls.append("reload")

        def summary(self, plan):
            return "1 contour"

    for name, cls in (("duplicate", "DuplicatePanel"), ("coordinates", "NodePanel")):
        monkeypatch.setitem(sys.modules, f"fontlabapp.fontui.node_editor.{name}", NS(**{cls: Panel}))
    made = NS(module=module, package=package, views=views, Panel=Panel)
    yield made
    for shell in tuple(module.OPEN_WINDOWS):
        shell.close()
    sys.modules.pop("fontlabapp.fontui.node_editor.ui", None)


def test_shell_has_five_embedded_tasks_read_only_preview_and_owned_close(ui):
    module = ui.module
    shell = module.show()
    assert [shell.tabs.tabText(i) for i in range(shell.tabs.count())] == [
        "Per-glyph Duplicator", "Current Layer", "All Foreground Layers", "Two Handles", "Coordinates", "About"]
    assert ui.views[0].options["read_only"] and not ui.views[0].options["controls"]
    panels = [p for p in shell.children if isinstance(p, module.PanelOwner)]
    assert len(panels) == 2
    assert all(not p.panel.isWindow() for p in panels)
    assert all(p.panel.apply_button.isHidden() for p in panels)
    shell.tabs.setCurrentIndex(4)
    shell._run_action("refresh")
    shell._run_action("apply")
    assert panels[1].panel.calls == ["tick", "copy"]
    shell.close()
    assert shell._close_complete and shell not in module.OPEN_WINDOWS
    assert all(not p.panel.timer.isActive() and p.panel.package is None for p in panels)


def test_write_actions_accept_preview_discard_and_refuse_refresh(ui, monkeypatch):
    shell = ui.module.show()
    tab = next(p for p in shell.children if isinstance(p, ui.module.WriteTab))
    before = NS(bound={1: (NS(name="a"), NS(name="Regular", id=1))})
    def accepted():
        tab.session.accepted = before
        return NS(inserted=1, skipped=(), no_selection_message="")
    monkeypatch.setattr(tab.session, "preview", accepted)
    monkeypatch.setattr(tab.session, "apply", lambda: {"inserted": 1})
    tab.preview()
    assert "1 inserted" in tab.details.text()
    with pytest.raises(ValueError, match="Discard"):
        tab.refresh()
    tab.apply()
    assert "Applied" in shell.status.text()
    tab.discard_button.click()
    assert not tab.session.dirty
    tab.refresh()
    assert ui.views[0].calls[-1] == ("refresh",)


def test_per_glyph_controls_preview_refresh_apply(ui, monkeypatch):
    shell = ui.module.show()
    tab = next(p for p in shell.children if isinstance(p, ui.module.DuplicateTab))
    tab.panel.read_font()
    assert tab.panel.current_master == "Regular"
    tab.refresh()
    assert "reload" in tab.panel.calls
    tab.session.accepted = "accepted"
    with pytest.raises(ValueError, match="Discard"):
        tab.refresh()
    monkeypatch.setattr(tab.session, "preview", lambda: NS(work=[(NS(name="a"), NS(name="Regular"), [])]))
    tab.preview()
    assert "Preview accepted" in shell.status.text()
    monkeypatch.setattr(ui.module.scripting, "current_package", lambda *a: None)
    with pytest.raises(ValueError, match="captured font"):
        tab.panel.read_font()


def test_close_retries_failed_disconnect_and_keeps_owner(ui):
    shell = ui.module.show()
    tab = next(p for p in shell.children if isinstance(p, ui.module.CoordinatesTab))
    state = [False]
    signal = NS(disconnect=lambda slot: state[0])
    tab.panel._connections.append((signal, "slot"))
    with pytest.raises(RuntimeError, match="disconnect"):
        shell.close()
    assert shell in ui.module.OPEN_WINDOWS and tab in shell.children
    state[0] = True
    shell.close()
    assert shell._close_complete and not tab.panel._connections


def test_no_font_and_failed_build_leave_no_successful_shell(ui, monkeypatch):
    monkeypatch.setattr(ui.module.scripting, "current_package", lambda *a: None)
    with pytest.raises(ValueError, match="Open a font"):
        ui.module.show()
    monkeypatch.setattr(ui.module.scripting, "current_package", lambda *a: ui.package)
    monkeypatch.setattr(ui.module.fontui, "glyph_view", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("preview fault")))
    with pytest.raises(RuntimeError, match="preview fault"):
        ui.module.show()
    assert not ui.module.OPEN_WINDOWS


def test_preview_render_failure_discards_acceptance_and_empty_source_refuses(ui, monkeypatch):
    shell = ui.module.show()
    for tab in [p for p in shell.children if isinstance(p, (ui.module.WriteTab, ui.module.DuplicateTab))]:
        def accept(tab=tab):
            if isinstance(tab, ui.module.WriteTab):
                tab.session.accepted = NS(bound={1: (NS(name="a"), NS(name="Regular", id=1))})
                return NS(inserted=1, skipped=(), no_selection_message="")
            tab.session.accepted = "stamp"
            return NS(work=[(NS(name="a"), NS(name="Regular"), [])])
        monkeypatch.setattr(tab.session, "preview", accept)
        monkeypatch.setattr(tab.preview_view, "load", lambda *a: (_ for _ in ()).throw(RuntimeError("draw fault")))
        with pytest.raises(RuntimeError, match="draw fault"):
            tab.preview()
        assert not tab.session.dirty
    tab = next(p for p in shell.children if isinstance(p, ui.module.WriteTab))
    def empty():
        tab.session.accepted = NS(bound={})
        return NS(inserted=0)
    monkeypatch.setattr(tab.session, "preview", empty)
    with pytest.raises(ValueError, match="Select a glyph"):
        tab.preview()


def test_coordinates_follow_only_active_tab_and_contain_errors(ui, monkeypatch):
    shell = ui.module.show()
    tab = next(p for p in shell.children if isinstance(p, ui.module.CoordinatesTab))
    tab.panel.signature = ("a", "Regular", ())
    tab.follow()
    assert not ui.views[0].calls
    shell.tabs.setCurrentIndex(4)
    tab.follow()
    assert ui.views[0].calls[-1] == ("load", ("a", "Regular"))
    tab.panel._snapshot_valid = False
    tab.follow()
    tab.panel._snapshot_valid = True
    errors = []
    tab.panel.show_error = errors.append
    monkeypatch.setattr(tab.preview_view, "load", lambda *a: (_ for _ in ()).throw(RuntimeError("draw fault")))
    tab.follow()
    assert len(errors) == 1 and "draw fault" in shell.status.text()


def test_public_lazy_factories_open_same_window(ui, monkeypatch):
    from fontlabapp.fontui import node_editor as editor
    from fontlabapp.studios import node_editor

    expected = object()
    monkeypatch.setattr(ui.module, "show", lambda parent=None: expected)
    assert editor.show() is expected
    assert node_editor.show() is expected
    # The Scriptmix launcher that calls this factory is covered in Scriptmix.


def test_coordinate_timer_stop_failure_retains_owner_for_retry(ui):
    shell = ui.module.show()
    tab = next(p for p in shell.children if isinstance(p, ui.module.CoordinatesTab))
    tab.panel.timer.stop()
    active = [True]
    tab.panel.timer = NS(stop=lambda: None, isActive=lambda: active[0])
    with pytest.raises(RuntimeError, match="timer did not stop"):
        shell.close()
    assert shell in ui.module.OPEN_WINDOWS
    active[0] = False
    shell.close()
    assert shell._close_complete


def test_write_failure_retains_owned_recovery_exception(ui, monkeypatch):
    shell = ui.module.show()
    tab = next(p for p in shell.children if isinstance(p, ui.module.WriteTab))
    error = RuntimeError("partial history")
    error.pending_nodes = (object(),)
    def fail():
        raise error
    monkeypatch.setattr(tab.session, "apply", fail)
    with pytest.raises(RuntimeError, match="partial history"):
        tab.apply()
    assert tab.last_error is error and tab.last_error.pending_nodes
