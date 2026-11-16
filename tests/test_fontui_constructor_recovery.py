# this_file: tests/test_fontui_constructor_recovery.py
"""Constructor failures preserve every incomplete owner and borrowed font."""
import importlib
import sys
from copy import deepcopy

import pytest
from test_fontui_glyph_metrics import composition_env as _composition_env, owned_font

composition_env = _composition_env
del _composition_env


@pytest.mark.parametrize("factory_name", ["glyph_browser", "font_browser"])
@pytest.mark.parametrize("unacknowledged_return", [None, False, 0])
def test_public_factory_postinit_error_retains_ancestor_with_unfinished_child(
    composition_env, monkeypatch, factory_name, unacknowledged_return
):
    env = composition_env
    ui = importlib.import_module("fontlabapp.fontui")
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.fonts", raising=False)
    cls = (env.native.Browser if factory_name == "glyph_browser" else
           importlib.import_module("fontlabapp.fontui.fonts").FontBrowser)
    original_init = cls.__init__
    parents, children, normal_closes, font_closes, close_calls = [], [], [], [], []
    font = owned_font()
    before = deepcopy(font)
    monkeypatch.setattr(type(font), "close", lambda self: font_closes.append(self))
    original_error = ValueError("normal ancestor initialization completed, then failed")

    def fail_after_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        parents.append(self)
        child = self.preview if factory_name == "glyph_browser" else self.browser
        children.append(child)
        normal_closes.append(child.close)
        def refuse_without_ack():
            close_calls.append("refused without completion")
            return unacknowledged_return
        monkeypatch.setattr(child, "close", refuse_without_ack)
        raise original_error

    monkeypatch.setattr(cls, "__init__", fail_after_init)
    consumer_owner = None
    with pytest.raises(BaseException) as caught:
        consumer_owner = getattr(ui, factory_name)(
            font if factory_name == "glyph_browser" else [font], parent=env.parent
        )
    parent, child = parents[0], children[0]
    public_error = caught.value
    initial = {
        "factory": factory_name,
        "consumer_assignment_happened": consumer_owner is not None,
        "error_type": type(public_error).__name__,
        "error_is_original": public_error is original_error,
        "error_owner_is_parent": getattr(public_error, "owner", None) is parent,
        "error_has_owner": hasattr(public_error, "owner"),
        "parent_closed": parent.closed,
        "parent_complete": parent._close_complete,
        "parent_child_ack": parent._child_closed,
        "parent_connections": len(parent.connections),
        "child_closed": child.closed,
        "child_complete": child._close_complete,
        "child_connections": len(child.connections),
        "child_close_calls": len(close_calls),
    }
    monkeypatch.setattr(child, "close", normal_closes[0])
    retained = getattr(public_error, "owner", None)
    if retained is not None:
        retained.close()
    # Even the probe's private parent reference cannot repair a falsely completed parent.
    parent.close()
    initial.update(
        retry_parent_complete=parent._close_complete,
        retry_child_complete=child._close_complete,
        retry_child_connections=len(child.connections),
        retry_child_close_calls=len(close_calls),
        source_preserved=font == before,
        borrowed_font_close_calls=len(font_closes),
    )
    try:
        assert consumer_owner is None and font == before and not font_closes
        assert initial["error_owner_is_parent"] and not initial["parent_complete"], initial
        assert parent._close_complete and child._close_complete, initial
    finally:
        child.close()
        sys.modules.pop("fontlabapp.fontui.fonts", None)


def contains(error, target):
    return error is target or (
        isinstance(error, BaseExceptionGroup)
        and any(contains(child, target) for child in error.exceptions)
    )


@pytest.mark.parametrize("index", [0, 1, 2])
@pytest.mark.parametrize("refuse", [False, True])
def test_existing_composition_nested_preview_failure_keeps_recoverable_owner(
    composition_env, monkeypatch, index, refuse
):
    env = composition_env
    module = env.modules[index]
    font = owned_font()
    before = deepcopy(font)
    close_calls, children, controllers, dialogs = [], [], [], []
    monkeypatch.setattr(type(font), "close", lambda self: close_calls.append(self))
    cls = [module.MetricsInspector if index == 0 else None,
           module.AnchorComponentInspector if index == 1 else None,
           module.UnicodeOrderExplorer if index == 2 else None][index]
    original_controller = cls.__init__
    def capture_controller(self, *args, **kwargs):
        original_controller(self, *args, **kwargs)
        controllers.append(self)
    monkeypatch.setattr(cls, "__init__", capture_controller)
    widgets = importlib.import_module("fontlabapp.qt.widgets")
    original_dialog = widgets.OwnedWidget.__init__
    def capture_dialog(self, *args, **kwargs):
        original_dialog(self, *args, **kwargs)
        dialogs.append(self)
    monkeypatch.setattr(widgets.OwnedWidget, "__init__", capture_dialog)
    original_preview = env.native.Preview.__init__
    first = ValueError("preview allocated then construction failed")
    original_closes = []
    def broken(self, *args, **kwargs):
        original_preview(self, *args, **kwargs)
        children.append(self)
        original_closes.append(self.close)
        if refuse:
            monkeypatch.setattr(self, "close", lambda: False)
        raise first
    monkeypatch.setattr(env.native.Preview, "__init__", broken)
    with pytest.raises(BaseException) as caught:
        module.show(font, env.parent)
    child, controller, outer = children[0], controllers[0], dialogs[0]
    initial = {
        "composition": module.__name__, "refuse": refuse,
        "primary_preserved": contains(caught.value, first),
        "error_has_owner": hasattr(caught.value, "owner"),
        "error_owner_is_nested": getattr(caught.value, "owner", None) is child,
        "controller_retained": controller in module._HANDLES,
        "controller_released": controller._released,
        "outer_closed": outer.closed,
        "controller_owns_outer": controller.owned is outer,
        "child_complete": child._close_complete,
        "child_connections": len(child.connections),
    }
    if refuse:
        child.widget.args[0].destroyed.emit()
        child.widget.destroyed.emit()
        while env.queue:
            env.queue.pop(0)()
        initial["after_destroy_connections"] = len(child.connections)
        initial["after_destroy_complete"] = child._close_complete
        monkeypatch.setattr(child, "close", original_closes[0])
    retried = controller.release()
    initial.update(retry_result=retried, retry_child_complete=child._close_complete,
                   retry_outer_closed=outer.closed, source_preserved=font == before,
                   borrowed_close_calls=len(close_calls))
    try:
        assert contains(caught.value, first)
        assert font == before and not close_calls
        assert retried and child._close_complete and outer.closed, initial
    finally:
        monkeypatch.setattr(child, "close", original_closes[0])
        child.close()


@pytest.mark.parametrize("index", [0, 1, 2])
def test_existing_composition_browser_failure_separates_outer_and_nested_close_protocols(
    composition_env, monkeypatch, index
):
    env = composition_env
    module = env.modules[index]
    font, children, controllers, dialogs, close_calls = owned_font(), [], [], [], []
    before = deepcopy(font)
    monkeypatch.setattr(type(font), "close", lambda self: close_calls.append(self))
    cls = [module.MetricsInspector if index == 0 else None,
           module.AnchorComponentInspector if index == 1 else None,
           module.UnicodeOrderExplorer if index == 2 else None][index]
    original_controller = cls.__init__
    def capture_controller(self, *args, **kwargs):
        original_controller(self, *args, **kwargs)
        controllers.append(self)
    monkeypatch.setattr(cls, "__init__", capture_controller)
    widgets = importlib.import_module("fontlabapp.qt.widgets")
    original_dialog = widgets.OwnedWidget.__init__
    def capture_dialog(self, *args, **kwargs):
        original_dialog(self, *args, **kwargs)
        dialogs.append(self)
    monkeypatch.setattr(widgets.OwnedWidget, "__init__", capture_dialog)
    original_browser = env.native.Browser.__init__
    first = ValueError("browser allocated then construction failed")
    original_closes = []
    def broken(self, *args, **kwargs):
        original_browser(self, *args, **kwargs)
        children.append(self)
        original_closes.append(self.close)
        monkeypatch.setattr(self, "close", lambda: False)
        raise first
    monkeypatch.setattr(env.native.Browser, "__init__", broken)
    with pytest.raises(BaseExceptionGroup) as caught:
        module.show(font, env.parent)
    child, controller, outer = children[0], controllers[0], dialogs[0]
    initial = {
        "composition": module.__name__, "failure": "Browser.close returns False",
        "primary_preserved": contains(caught.value, first),
        "error_owner_is_browser": caught.value.owner is child,
        "controller_owns_nested_as_outer": controller.owned is child,
        "controller_retained": controller in module._HANDLES,
        "outer_closed": outer.closed, "child_complete": child._close_complete,
        "child_connections": len(child.connections),
    }
    monkeypatch.setattr(child, "close", original_closes[0])
    retried = controller.release()
    initial.update(retry_result=retried, retry_child_complete=child._close_complete,
                   retry_preview_complete=child.preview._close_complete,
                   retry_retained=controller in module._HANDLES,
                   source_preserved=font == before, borrowed_close_calls=len(close_calls))
    assert contains(caught.value, first) and font == before and not close_calls
    assert retried and controller._released and child._close_complete and outer.closed, initial


@pytest.mark.parametrize("index", [0, 1, 2, 3])
@pytest.mark.parametrize("child_kind", ["Preview", "Browser"])
@pytest.mark.parametrize("interrupt", [False, True])
def test_composition_constructor_error_retains_nested_and_outer_until_both_ack(
    composition_env, monkeypatch, index, child_kind, interrupt
):
    from test_fontui_tabular_audit import World

    env = composition_env
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.fonts", raising=False)
    audit = importlib.import_module("fontlabapp.fontui.tabular_audit")
    module = [*env.modules, audit][index]
    cls = [env.modules[0].MetricsInspector, env.modules[1].AnchorComponentInspector,
           env.modules[2].UnicodeOrderExplorer, audit.TabularAudit][index]
    font = owned_font()
    before = deepcopy(font)
    borrowed_closes, controllers, children, dialogs = [], [], [], []
    monkeypatch.setattr(type(font), "close", lambda self: borrowed_closes.append(self))
    original_controller = cls.__init__
    def capture(self, *args, **kwargs):
        original_controller(self, *args, **kwargs)
        controllers.append(self)
    monkeypatch.setattr(cls, "__init__", capture)
    widgets = importlib.import_module("fontlabapp.qt.widgets")
    original_outer_init = widgets.OwnedWidget.__init__
    def capture_outer(self, *args, **kwargs):
        original_outer_init(self, *args, **kwargs)
        dialogs.append(self)
    monkeypatch.setattr(widgets.OwnedWidget, "__init__", capture_outer)
    original_outer_close = widgets.OwnedWidget.close
    monkeypatch.setattr(widgets.OwnedWidget, "close", lambda self: False)
    child_class = getattr(env.native, child_kind)
    original_init = child_class.__init__
    first = KeyboardInterrupt("original construction interrupt") if interrupt else ValueError("original construction failure")
    child_closes = []
    def fail_after_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        children.append(self)
        child_closes.append(self.close)
        monkeypatch.setattr(self, "close", lambda: False)
        raise first
    monkeypatch.setattr(child_class, "__init__", fail_after_init)
    with pytest.raises(BaseExceptionGroup) as caught:
        module.show(World(font) if index == 3 else font, env.parent)
    child, controller, outer = children[0], controllers[0], dialogs[0]
    try:
        assert contains(caught.value, first)
        assert controller in module._HANDLES and controller.owned is outer
        assert child in controller._failed_owners
        assert not child._close_complete and not outer.closed
        monkeypatch.setattr(child, "close", child_closes[0])
        assert not controller.release()  # outer still refuses after child completion
        assert child._close_complete and not child.connections
        assert controller in module._HANDLES and controller.owned is outer
        monkeypatch.setattr(widgets.OwnedWidget, "close", original_outer_close)
        assert controller.release() and outer.closed
        assert controller not in module._HANDLES and controller._failed_owners == []
        assert controller.release()
        while env.queue:
            env.queue.pop(0)()
        assert font == before and borrowed_closes == []
    finally:
        monkeypatch.setattr(child, "close", child_closes[0])
        monkeypatch.setattr(widgets.OwnedWidget, "close", original_outer_close)
        controller.release()
        audit._HANDLES.clear()
        sys.modules.pop("fontlabapp.fontui.fonts", None)


@pytest.mark.parametrize("destroy_parent", [False, True])
def test_audit_font_browser_postinit_failure_keeps_entire_nested_tree(
    composition_env, monkeypatch, destroy_parent
):
    from test_fontui_tabular_audit import World

    env = composition_env
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.fonts", raising=False)
    module = importlib.import_module("fontlabapp.fontui.tabular_audit")
    fonts = importlib.import_module("fontlabapp.fontui.fonts")
    original_init = fonts.FontBrowser.__init__
    children, original_closes = [], []
    font = owned_font()
    before = deepcopy(font)
    first = ValueError("font chooser fully initialized before failure")
    def broken(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        children.append(self)
        original_closes.append(self.close)
        monkeypatch.setattr(self, "close", lambda: False)
        raise first
    monkeypatch.setattr(fonts.FontBrowser, "__init__", broken)
    with pytest.raises(BaseExceptionGroup) as caught:
        module.show(World(font), env.parent)
    owner = module._HANDLES[-1]
    child = children[0]
    try:
        assert contains(caught.value, first)
        assert owner.browser is None and child in owner._failed_owners
        assert not child._close_complete
        assert child.browser._close_complete and child.browser.preview._close_complete
        if destroy_parent:
            child.widget.args[0].destroyed.emit()
            child.widget.destroyed.emit()
            while env.queue:
                env.queue.pop(0)()
        monkeypatch.setattr(child, "close", original_closes[0])
        assert owner.release() and child._close_complete
        assert not child.connections and not child.browser.connections
        assert font == before and owner not in module._HANDLES
    finally:
        monkeypatch.setattr(child, "close", original_closes[0])
        owner.release()
        module._HANDLES.clear()
        sys.modules.pop("fontlabapp.fontui.fonts", None)
