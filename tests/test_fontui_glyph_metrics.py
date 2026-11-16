# this_file: tests/test_fontui_glyph_metrics.py
"""Real metrics values and linked owned compositions, without native Qt."""

from _demo_support import stub_natives

import importlib
import sys
from copy import deepcopy
from types import SimpleNamespace

import pytest
import _cov_qt as fq


class ListItem:
    def __init__(self, text):
        self.value, self.selected = text, False

    def text(self):
        return self.value

    def setSelected(self, value):
        self.selected = value

    def isSelected(self):
        return self.selected

    def setIcon(self, icon):
        pass


class List(fq.FakeWidget):
    def __init__(self, *args):
        super().__init__(*args)
        self.itemDoubleClicked = fq.Signal()

    def addItem(self, item):
        self.items.append(item)

    def item(self, index):
        return self.items[index]

    def setIconSize(self, value):
        pass

    def setGridSize(self, value):
        pass


class Tree(fq.FakeWidget):
    def setHeaderLabels(self, labels):
        self.headers = tuple(labels)

    def addTopLevelItem(self, item):
        self.items.append(item)


class Dialog(fq.FakeWidget):
    def __init__(self, *args):
        super().__init__(*args)
        self.finished = fq.Signal()

    def setWindowTitle(self, title):
        self.title = title

    def setModal(self, value):
        self.modal = value

    def close(self):
        return True


@pytest.fixture
def composition_env(monkeypatch):
    handle = fq.install(monkeypatch)
    qt, queue = handle.qt, []
    qt.QtGui.QListWidget, qt.QtGui.QListWidgetItem = List, ListItem
    qt.QtGui.QTreeWidget, qt.QtGui.QTreeWidgetItem = Tree, lambda values: tuple(values)
    qt.QtGui.QDialog = Dialog
    monkeypatch.setattr(
        qt.QtCore.QTimer,
        "singleShot",
        staticmethod(lambda delay, call: queue.append(call)),
        raising=False,
    )
    for name in ["fontlabapp.fontui.preview", "fontlabapp.qt.widgets"]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    native = handle.load("fontlabapp.fontui.native")
    monkeypatch.setattr(native.Browser, "thumbnail", lambda self, name: None)
    modules = [
        importlib.import_module("fontlabapp.fontui." + name)
        for name in ["glyph_metrics", "anchor_components", "unicode_order"]
    ]
    yield SimpleNamespace(
        qt=qt, queue=queue, modules=modules, native=native, parent=fq.FakeWidget()
    )
    for module in modules:
        module._HANDLES.clear()
    fq.release()
    sys.modules.pop("fontlabapp.fontui.preview", None)


def owned_font():
    font = fq.ufo_font()
    font.glyphOrder = ["A", "V"]
    font["A"].width = 600.5
    return font


def choose(browser, names):
    for item in browser.glyph_list.items:
        item.setSelected(item.text() in names)
    browser.selection_changed()


def test_metrics_when_fractional_and_empty_then_real_advance_bounds_and_unset_bearings():
    module = importlib.import_module("fontlabapp.fontui.glyph_metrics")
    font = owned_font()
    value = module.metrics(font, "A")
    assert value.advance == 600.5 and value.bounds == (0, 0, 600, 700)
    assert value.left == 0 and value.right == 0.5
    font["A"].clearContours()
    value = module.metrics(font, "A")
    assert value.advance == 600.5 and value.bounds is None
    assert value.left is None and value.right is None
    for invalid in [None, float("nan"), float("inf")]:
        font["A"].width = invalid
        with pytest.raises((ValueError, TypeError)):
            module.metrics(font, "A")


def test_metrics_controller_when_selected_then_real_comparison_and_host_diagnostic(
    composition_env,
):
    env = composition_env
    font = owned_font()
    before = deepcopy(font)
    controller = env.modules[0].show(font, env.parent)
    choose(controller.browser, ["A", "V"])
    assert controller.rows[0] == ("Advance", 600.5)
    assert controller.table.items[-2:] == [("A", "600.5", "Same"), ("V", "600.0", "Different")]
    assert controller.comparison.text == "1 same width · 1 different"
    assert "1 glyphs are on different width" in controller.comparison.calls[-1][1][0]
    assert controller.browser.preview.name == "A"

    def broken(*args):
        raise ValueError("actual consumer")

    controller.browser.on_selection = broken
    controller.browser._changed()
    assert (
        "Selection callback failed: actual consumer"
        in controller.browser.preview.diagnostic.text
    )
    controller.browser.on_selection = controller.selected
    controller.browser._changed()
    assert "callback failed" not in controller.browser.preview.diagnostic.text
    assert font == before
    assert controller.release() is True


@pytest.mark.parametrize("index", [0, 1, 2])
def test_controller_when_release_partial_base_disconnect_then_owner_retained(
    composition_env, monkeypatch, index
):
    env = composition_env
    controller = env.modules[index].show(owned_font(), env.parent)
    child = controller.browser
    signal, slot = child.connections[-1]

    def fail(*args):
        raise RuntimeError("partial disconnect")

    monkeypatch.setattr(signal, "disconnect", fail)
    assert controller.release() is False
    assert child.closed and child.connections
    assert controller in env.modules[index]._HANDLES and controller.font is not None
    assert controller.release() is False
    assert controller in env.modules[index]._HANDLES


@pytest.mark.parametrize("index", [0, 1, 2])
@pytest.mark.parametrize(
    "route",
    ["none", "queued", "parent", "scope", "outer_false", "outer_error", "foreign"],
)
def test_controllers_when_owned_terminal_or_refused_then_exact_retention(
    composition_env, monkeypatch, index, route
):
    env = composition_env
    module = env.modules[index]
    font = None if route == "none" else owned_font()
    c = module.show(font, env.parent)
    if route == "none":
        assert "No font" in c.status.text
    elif route == "queued":
        content = c.owned.content
        content.finished.emit()
        content.finished.emit()
        assert len(env.queue) == 1 and c.font is font
        env.queue.pop()()
        assert c._released and c.release()
        return
    elif route == "parent":
        content = c.owned.content
        content.destroyed.emit()
        assert len(env.queue) == 1
        env.queue.pop()()
        assert c._released
        return
    elif route == "scope":
        signal, slot, _ = c.scope.records[0]
        original = signal.disconnect
        monkeypatch.setattr(signal, "disconnect", lambda slot: False)
        assert not c.release() and c in module._HANDLES
        monkeypatch.setattr(signal, "disconnect", original)
    elif route in ["outer_false", "outer_error"]:
        widget = c.owned.widget
        original = widget.close

        def refuse():
            if route == "outer_error":
                raise ValueError("outer close")
            return False

        monkeypatch.setattr(widget, "close", refuse)
        assert not c.release() and c.font is font and c in module._HANDLES
        monkeypatch.setattr(widget, "close", original)
    elif route == "foreign":
        c.selected(object(), ("A",))
        assert "another font" in c.status.text
        choose(c.browser, ["A"])
    assert c.release() and c._released and c.font is None and c not in module._HANDLES
    assert c.release()


@pytest.mark.parametrize("index", [0, 1, 2])
def test_construction_when_setup_and_cleanup_fail_then_exact_recovery_owner(
    composition_env, monkeypatch, index
):
    env = composition_env
    module = env.modules[index]
    font = owned_font()
    cls = [
        module.MetricsInspector if hasattr(module, "MetricsInspector") else None,
        module.AnchorComponentInspector
        if hasattr(module, "AnchorComponentInspector")
        else None,
        module.UnicodeOrderExplorer
        if hasattr(module, "UnicodeOrderExplorer")
        else None,
    ]
    kind = next(c for c in cls if c is not None)
    original = kind.build

    def broken(self, content):
        original(self, content)
        raise ValueError("setup broke")

    monkeypatch.setattr(kind, "build", broken)
    monkeypatch.setattr(Dialog, "close", lambda self: False)
    with pytest.raises(BaseExceptionGroup) as error:
        module.show(font, env.parent)
    c = module._HANDLES[-1]
    assert c.owned is error.value.owner and c.font is font
    assert "setup broke" in str(error.value.exceptions[0])
    monkeypatch.setattr(Dialog, "close", lambda self: True)
    assert c.release()


@pytest.mark.parametrize("structure", ["package", "zip"])
@pytest.mark.parametrize("index", [0, 1, 2])
def test_composition_when_real_checked_font_then_complete_saved_reopen_unchanged(
    composition_env, tmp_path, structure, index
):
    from fontlab_fontport.live import RFont
    from fontlab_fontport.memory import UFOBackend
    from ufoLib2 import Font

    env = composition_env
    source = owned_font()
    source.lib["owned"] = {"nested": [1, "preserve"]}
    source.data["owned.bin"] = b"\0\xff"
    source.groups["owned.keep"] = ["A"]
    source["A"].note = "preserve"
    initial = tmp_path / "input.ufo"
    source.save(initial)
    backend = UFOBackend(Font.open(initial, lazy=False))
    before = deepcopy(backend.font)
    c = env.modules[index].show(RFont(backend), env.parent)
    choose(c.browser, ["A"])
    c.refresh()
    assert backend.font == before and not backend.closed
    assert c.release() and not backend.closed
    out = tmp_path / ("output.ufo" if structure == "package" else "output.ufoz")
    control = tmp_path / ("control.ufo" if structure == "package" else "control.ufoz")
    backend.font.save(out, structure=structure)
    before.save(control, structure=structure)
    with (
        Font.open(out, lazy=False) as actual,
        Font.open(control, lazy=False) as expected,
    ):
        assert actual == expected and actual.data["owned.bin"] == b"\0\xff"


def test_metrics_when_affine_component_and_negative_width_then_geometric_values():
    from ufoLib2.objects import Component

    module = importlib.import_module("fontlabapp.fontui.glyph_metrics")
    font = owned_font()
    font["A"].clearContours()
    font["A"].components = [Component("V", (2, 0, 0, 1, 10, 20))]
    font["A"].width = -3.25
    value = module.metrics(font, "A")
    assert (
        value.bounds == (10, 20, 1210, 720)
        and value.left == 10
        and value.right == -1213.25
    )
    with pytest.raises(ValueError, match="No font"):
        module.metrics(None, "A")
    with pytest.raises(KeyError):
        module.metrics(font, "missing")


def demo_namespace(env, monkeypatch, run_name="inspection"):
    import runpy
    from pathlib import Path
    import fontlabapp.qt.safe as safe
    from fontlab_fontport.world import FontWorld

    import fontlabapp

    original_native = fontlabapp._native
    stub_natives(monkeypatch, fontlabapp, lambda name: SimpleNamespace() if name == 'fontlab' else original_native(name))
    monkeypatch.setattr(safe, "main_window", lambda native, qt: env.parent)

    def forbidden(*args, **kwargs):
        raise AssertionError("Native font creation/lookup is forbidden")

    monkeypatch.setattr(FontWorld, "NewFont", forbidden)
    monkeypatch.setattr(FontWorld, "CurrentFont", forbidden)
    path = (
        Path(__file__).resolve().parents[1] / "Scripts/Font Editors/Font UI Lab Demo.py"
    )
    return runpy.run_path(str(path), run_name=run_name)


@pytest.mark.parametrize("route", ["main", "__main__"])
def test_demo_when_run_then_three_actual_detached_views_keep_font_alive(
    composition_env, monkeypatch, route
):
    import gc
    import weakref

    env = composition_env
    namespace = demo_namespace(env, monkeypatch)
    assert all(not m._HANDLES for m in env.modules)
    if route == "main":
        views = namespace["main"]()
    else:
        demo_namespace(env, monkeypatch, "__main__")
        views = tuple(m._HANDLES[-1] for m in env.modules)
    assert [type(c).__name__ for c in views] == [
        "MetricsInspector",
        "AnchorComponentInspector",
        "UnicodeOrderExplorer",
    ]
    font = views[0].font
    assert all(c.font is font for c in views)
    ref = weakref.ref(font)
    backend = font._backend
    before = deepcopy(backend.font)
    del font
    gc.collect()
    assert ref() is not None
    choose(views[0].browser, ["A", "V"])
    assert views[0].rows[0] == ("Advance", 600.5)
    choose(views[1].browser, ["A"])
    assert len(views[1].anchor_rows) == 3
    choose(views[1].browser, ["affine.A"])
    assert views[1].component_rows[0][0] == "A"
    views[2].sequence.text_control.setText("/grin /A /grin")
    views[2].sequence.select_key(env.qt.QtCore.Qt.Key_End)
    assert views[2].occurrence_index == 2 and "U+1F600" in str(views[2].selected_rows)
    assert backend.font == before and not backend.closed
    assert all(c.release() for c in views)
    assert backend.font == before and not backend.closed


@pytest.mark.parametrize("failed_index", [1, 2])
@pytest.mark.parametrize("cleanup", ["normal", "refused", "raises"])
def test_demo_when_later_show_fails_then_original_error_and_exact_earlier_owners(
    composition_env, monkeypatch, failed_index, cleanup
):
    env = composition_env
    namespace = demo_namespace(env, monkeypatch)
    error = ValueError("later show failed")
    opened = []
    release_order = []
    originals = [m.show for m in env.modules]
    for index, module in enumerate(env.modules):

        def show(font, parent=None, index=index):
            c = originals[index](font, parent)
            opened.append(c)
            release = c.release

            def tracked():
                release_order.append(index)
                if index == 0 and cleanup == "refused":
                    return False
                if index == 0 and cleanup == "raises":
                    raise RuntimeError("cleanup failed")
                return release()

            c.release = tracked
            c._original_release = release
            if index == failed_index:
                raise error
            return c

        monkeypatch.setattr(module, "show", show)
    with pytest.raises(ValueError) as caught:
        namespace["main"]()
    assert caught.value is error
    assert release_order == list(reversed(range(failed_index)))
    assert opened[-1] in env.modules[failed_index]._HANDLES
    if cleanup != "normal":
        assert opened[0] in env.modules[0]._HANDLES and error.__notes__
    for c in opened:
        assert c._original_release()


# Task12a F1/F2: actual owned child stages and original-error recovery.
def _new_checked_controller(env, index):
    from fontlab_fontport.live import RFont
    from fontlab_fontport.memory import UFOBackend

    source = owned_font()
    source.lib["cleanup-control"] = {"keep": [1, "unchanged"]}
    source.data["cleanup-control.bin"] = b"\0\xff"
    source["A"].note = "preserve"
    backend = UFOBackend(source)
    font = RFont(backend)
    before = deepcopy(backend.font)
    module = env.modules[index]
    return module, module.show(font, env.parent), font, backend, before


def _controller_child(controller, role):
    if role == "browser":
        return controller.browser
    if role == "preview":
        return controller.browser.preview
    assert role == "sequence"
    return controller.sequence


def _assert_stranded_cleanup(env, monkeypatch, index, role, stage, trigger="direct"):
    module, owner, font, backend, before = _new_checked_controller(env, index)
    browser, preview, sequence, outer = (
        owner.browser,
        owner.browser.preview,
        owner.sequence,
        owner.owned,
    )
    child = _controller_child(owner, role)
    original = getattr(child.widget, stage)
    error = RuntimeError(f"actual {role} {stage} failure")
    calls, later_outer = [], []

    def fail():
        calls.append(stage)
        raise error

    monkeypatch.setattr(child.widget, stage, fail)
    pending_destroyed = owner._destroyed
    pending_release = None
    if trigger == "queued":
        # Schedule while Scope is live, then keep this exact callback pending.
        outer.content.finished.emit()
        assert len(env.queue) == 1
        pending_release = env.queue[0]
        assert pending_release.__self__ is owner
        assert pending_release.__func__ is type(owner).release
    first = owner.release()
    assert first is False
    assert child.closed and not child._close_complete
    observers = tuple(pair for pair in (child._own_observer, child._parent_observer) if pair is not None)
    assert {id(pair) for pair in child.connections} == {id(pair) for pair in observers}
    assert any(problem is error for problem in owner.problems)
    assert owner in module._HANDLES and owner.font is font
    monkeypatch.setattr(child.widget, stage, original)
    original_outer_close = outer.widget.close

    def outer_close():
        later_outer.append("close")
        return original_outer_close()

    monkeypatch.setattr(outer.widget, "close", outer_close)
    dead_calls = []
    if trigger == "parent_after_failure":
        # Model an already-delivered pending handler, not a disconnected signal.
        assert pending_destroyed.__self__ is owner
        assert pending_destroyed.__func__ is type(owner)._destroyed

        def dead_access():
            dead_calls.append("dead widget method")
            raise AssertionError("No widget method after parent destruction")

        widgets = [browser.widget, preview.widget, outer.widget]
        if sequence is not None:
            widgets.append(sequence.widget)
        for widget in widgets:
            monkeypatch.setattr(widget, "hide", dead_access)
            monkeypatch.setattr(widget, "deleteLater", dead_access)
        monkeypatch.setattr(outer.widget, "close", dead_access)
        pending_destroyed()
        assert owner._parent_dead and len(env.queue) == 1
        queued_release = env.queue.pop()
        assert queued_release.__self__ is owner
        assert queued_release.__func__ is type(owner).release
        second = queued_release()
    elif trigger == "queued":
        assert len(env.queue) == 1 and env.queue[0] is pending_release
        assert env.queue.pop() is pending_release
        second = pending_release()
    else:
        second = owner.release()
    assert env.queue == [] and dead_calls == []
    if trigger == "parent_after_failure":
        assert second is False, "Unobserved child death cannot discharge cleanup"
        assert later_outer == []
        assert owner.browser is browser and owner.browser.preview is preview
        assert owner.sequence is sequence and owner.owned is outer
        assert owner.font is font and owner in module._HANDLES
    else:
        assert second is True, "Restored stages must resume substantive cleanup"
        assert later_outer == ["close"]
        assert owner.browser is owner.sequence is owner.owned is owner.font is None
        assert owner not in module._HANDLES
    assert calls == [stage]
    assert any(problem is error for problem in owner.problems)
    assert backend.font == before and not backend.closed


def _assert_preclose_retry(env, monkeypatch, index, role):
    module, owner, font, backend, before = _new_checked_controller(env, index)
    child = _controller_child(owner, role)
    original = child.close
    error = RuntimeError("before actual owned close entry")

    def refuse():
        assert child.closed is False
        raise error

    monkeypatch.setattr(child, "close", refuse)
    assert owner.release() is False
    assert not child.closed and owner.font is font and owner in module._HANDLES
    assert any(problem is error for problem in owner.problems)
    monkeypatch.setattr(child, "close", original)
    assert owner.release() is True and owner.release() is True
    assert owner.font is owner.browser is owner.sequence is owner.owned is None
    assert owner not in module._HANDLES
    assert backend.font == before and not backend.closed


def _assert_setup_cleanup_interruption(
    env, monkeypatch, index, setup_route, cleanup_kind, cleanup_owner="child"
):
    from fontlab_fontport.live import RFont
    from fontlab_fontport.memory import UFOBackend

    module = env.modules[index]
    kind = [
        module.MetricsInspector if hasattr(module, "MetricsInspector") else None,
        module.AnchorComponentInspector
        if hasattr(module, "AnchorComponentInspector")
        else None,
        module.UnicodeOrderExplorer
        if hasattr(module, "UnicodeOrderExplorer")
        else None,
    ]
    kind = next(value for value in kind if value is not None)
    real_build = kind.build
    setup = (
        KeyboardInterrupt("original setup interrupt")
        if setup_route == "interrupt"
        else SystemExit(19)
        if setup_route == "exit"
        else ValueError("exact original setup")
    )
    cleanup = (
        KeyboardInterrupt("exact cleanup interrupt")
        if cleanup_kind == "interrupt"
        else SystemExit(37)
    )
    backend = UFOBackend(owned_font())
    font, before = RFont(backend), deepcopy(backend.font)
    built, outer_calls = [], []

    def interrupt():
        raise cleanup

    def broken_build(self, content):
        real_build(self, content)
        built.append(self)
        if cleanup_owner == "child":
            monkeypatch.setattr(self.browser.widget, "hide", interrupt)
        raise setup

    def refused_outer(self):
        outer_calls.append(self)
        if cleanup_owner == "outer" and len(outer_calls) > 1:
            raise cleanup
        return False

    monkeypatch.setattr(kind, "build", broken_build)
    if setup_route != "plain":
        monkeypatch.setattr(Dialog, "close", refused_outer)
    escaped = None
    try:
        module.show(font, env.parent)
    except BaseException as error:
        escaped = error
    assert escaped is not None and len(built) == 1
    owner = built[0]
    original = owner.problems[0]
    assert escaped is original and escaped is not cleanup, (
        "Cleanup must preserve the original public exception object"
    )
    if setup_route == "plain":
        assert original is setup and owner.owned is None
    else:
        assert isinstance(original, BaseExceptionGroup)
        assert original.exceptions[0] is setup
        assert owner.owned is original.owner
    assert any(problem is cleanup for problem in owner.problems)
    assert any(
        "cleanup" in note.lower() and "retain" in note.lower()
        for note in getattr(original, "__notes__", [])
    )
    assert owner in module._HANDLES and owner.font is font
    assert owner.browser is not None and owner.browser.preview is not None
    if index == 2:
        assert owner.sequence is not None
    assert backend.font == before and not backend.closed


def _assert_public_release_interruption(env, monkeypatch, index, cleanup_kind):
    module, owner, font, backend, before = _new_checked_controller(env, index)
    child = owner.browser
    original = child.widget.hide
    cleanup = (
        KeyboardInterrupt("public release")
        if cleanup_kind == "interrupt"
        else SystemExit(37)
    )

    def interrupt():
        raise cleanup

    monkeypatch.setattr(child.widget, "hide", interrupt)
    with pytest.raises(type(cleanup)) as error:
        owner.release()
    assert error.value is cleanup
    monkeypatch.setattr(child.widget, "hide", original)
    assert owner.release() is True
    assert owner not in module._HANDLES
    assert owner.font is owner.browser is owner.sequence is owner.owned is None
    assert backend.font == before and not backend.closed


def _assert_clean_release_collects_children(env, index):
    import gc
    import weakref

    module, owner, font, backend, before = _new_checked_controller(env, index)
    references = [weakref.ref(owner.browser), weakref.ref(owner.browser.preview)]
    if owner.sequence is not None:
        references.append(weakref.ref(owner.sequence))
    assert owner.release() is True and owner.release() is True
    assert owner.font is owner.browser is owner.sequence is owner.owned is None
    assert owner not in module._HANDLES
    gc.collect()
    assert all(reference() is None for reference in references)
    assert backend.font == before and not backend.closed


@pytest.mark.parametrize("role", ["browser", "preview"])
@pytest.mark.parametrize("stage", ["hide", "deleteLater"])
def test_glyph_metrics_when_child_stage_strands_then_later_release_refuses(
    composition_env, monkeypatch, role, stage
):
    _assert_stranded_cleanup(composition_env, monkeypatch, 0, role, stage)


@pytest.mark.parametrize("stage", ["hide", "deleteLater"])
@pytest.mark.parametrize("trigger", ["queued", "parent_after_failure"])
def test_glyph_metrics_when_terminal_signal_after_stranding_then_owner_stays(
    composition_env, monkeypatch, stage, trigger
):
    _assert_stranded_cleanup(composition_env, monkeypatch, 0, "browser", stage, trigger)


@pytest.mark.parametrize("role", ["browser", "preview"])
def test_glyph_metrics_when_close_refuses_before_entry_then_retry_completes(
    composition_env, monkeypatch, role
):
    _assert_preclose_retry(composition_env, monkeypatch, 0, role)


@pytest.mark.parametrize("setup_route", ["plain", "group", "interrupt", "exit"])
@pytest.mark.parametrize("cleanup_kind", ["interrupt", "exit"])
def test_glyph_metrics_when_setup_cleanup_interrupts_then_original_is_retained(
    composition_env, monkeypatch, setup_route, cleanup_kind
):
    _assert_setup_cleanup_interruption(
        composition_env, monkeypatch, 0, setup_route, cleanup_kind
    )


@pytest.mark.parametrize("cleanup_kind", ["interrupt", "exit"])
def test_glyph_metrics_when_outer_cleanup_interrupts_then_original_group_is_retained(
    composition_env, monkeypatch, cleanup_kind
):
    _assert_setup_cleanup_interruption(
        composition_env, monkeypatch, 0, "group", cleanup_kind, "outer"
    )


@pytest.mark.parametrize("cleanup_kind", ["interrupt", "exit"])
def test_glyph_metrics_when_public_release_interrupts_then_same_interrupt_escapes(
    composition_env, monkeypatch, cleanup_kind
):
    _assert_public_release_interruption(composition_env, monkeypatch, 0, cleanup_kind)


def test_glyph_metrics_when_release_succeeds_then_children_are_collectible(
    composition_env,
):
    _assert_clean_release_collects_children(composition_env, 0)



@pytest.mark.parametrize("case", ['metrics', 'anchors', 'unicode'])
def test_composition_when_all_actual_death_witnesses_arrive_then_retained_release_finishes(composition_env, monkeypatch, case):
    index = {"metrics": 0, "anchors": 1, "unicode": 2}[case]
    module, owner, font, backend, before = _new_checked_controller(composition_env, index)
    child = owner.browser.preview
    normal = child.widget.hide
    error = RuntimeError("pause real child before parent witness")
    def fail():
        raise error
    monkeypatch.setattr(child.widget, "hide", fail)
    assert owner.release() is False and owner.font is font
    monkeypatch.setattr(child.widget, "hide", normal)
    owner._destroyed()
    assert owner.release() is False, "outer controller witness alone cannot prove child death"
    children = [owner.browser.preview, owner.browser]
    if owner.sequence is not None:
        children.append(owner.sequence)
    outer = owner.owned
    roots = [c.widget for c in children]
    signals = [root.destroyed for root in roots] + [outer.widget.destroyed]
    dead_calls = []
    def forbidden():
        dead_calls.append("native Root action")
        raise AssertionError("no Root action after actual supported own witness")
    for root in roots:
        monkeypatch.setattr(root, "hide", forbidden)
        monkeypatch.setattr(root, "deleteLater", forbidden)
    monkeypatch.setattr(outer.widget, "close", forbidden)
    for signal in signals:
        signal.emit()
    assert owner.release() is True and owner.release() is True
    assert dead_calls == [] and owner not in module._HANDLES
    assert owner.font is owner.browser is owner.sequence is owner.owned is None
    assert any(problem is error for problem in owner.problems)
    assert backend.font == before and not backend.closed
