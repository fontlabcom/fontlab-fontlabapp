# this_file: tests/test_scripting.py
"""Owned doubles exercise safe package access and selection."""

from importlib import import_module
from types import SimpleNamespace as NS

import pytest

scripting = import_module("fontlabapp.core.scripting")


@pytest.fixture
def host(monkeypatch):
    package = NS(id=7, isNull=False)
    state = NS(package=package, selected={0}, clears=0)
    frame = NS(inherits=lambda name: name == "YFrameWindow")
    tab = NS(inherits=lambda name: name == "QTabWidget", parentWidget=lambda: frame)
    stack = NS(inherits=lambda name: name == "QStackedWidget", parentWidget=lambda: tab)
    state.font_panel = NS(
        inherits=lambda name: name == "FontWindow", parentWidget=lambda: stack
    )
    glyphs = [NS(name=n) for n in ["A", "é", "space"]]

    def clear():
        state.clears += 1
        state.selected.clear()

    fl = NS(
        font=glyphs,
        Unselect=clear,
        Select=state.selected.add,
        Selected=lambda i: i in state.selected,
    )
    native = NS(
        flWorkspace=NS(
            instance=lambda: NS(
                currentPackage=state.package, activeFontPanel=state.font_panel
            )
        ),
        UpdateAll=lambda: state.refreshes.append("UpdateAll"),
    )
    state.refreshes = []
    state.fl, state.native = fl, native
    monkeypatch.setattr(
        scripting, "_native", lambda name: native if name == "fontlab" else NS(fl=fl)
    )
    return state


def test_current_package_when_missing_null_or_stale_then_none(host):
    assert scripting.current_package(7).id == 7
    assert scripting.current_package(8) is None
    host.package = None
    assert scripting.current_package() is None
    host.package = NS(id=7, isNull=True)
    assert scripting.current_package() is None


def test_select_when_duplicates_unicode_then_font_order(host):
    assert scripting.select_glyphs(["é", "A", "é"], package_id=7) == ["A", "é"]
    assert scripting.select_glyphs([], package_id=7) == []


@pytest.mark.parametrize("add", [False, True])
def test_select_glyphs_when_selection_written_then_no_global_refresh(host, add):
    assert scripting.select_glyphs(["space"], package_id=7, add=add) == (
        ["A", "space"] if add else ["space"]
    ), "select_glyphs must return the selection in font order"
    assert host.refreshes == [], f"UpdateAll queues glyph ids (fl#8537): {host.refreshes}"


@pytest.mark.parametrize("names,package_id", [(["missing"], 7), (["A"], 8)])
def test_select_when_invalid_then_preserves_selection(host, names, package_id):
    with pytest.raises(ValueError):
        scripting.select_glyphs(names, package_id=package_id)
    assert host.clears == 0
    assert host.selected == {0}


def test_select_when_no_font_then_preserves_selection(host):
    host.package = None
    with pytest.raises(ValueError):
        scripting.select_glyphs([], package_id=7)
    assert host.clears == 0


@pytest.mark.parametrize("add", [False, True])
def test_select_when_glyph_window_active_then_refuses_before_legacy_writers(host, add):
    host.font_panel = None
    with pytest.raises(ValueError, match="Font window"):
        scripting.select_glyphs(["é"], package_id=7, add=add)
    assert host.clears == 0 and host.selected == {0}, (
        "Read availability never proves legacy write context"
    )


def test_select_when_panel_type_unknown_then_refuses_before_legacy_writers(host):
    host.font_panel = NS(inherits=lambda name: False)
    with pytest.raises(ValueError, match="Font window"):
        scripting.select_glyphs(["é"], package_id=7)
    assert host.clears == 0 and host.selected == {0}


def test_select_when_parent_access_returns_transient_proxies_then_retains_traversal_lifetime(
    host,
):
    import gc
    import weakref

    returned = []
    classes = ("FontWindow", "QStackedWidget", "QTabWidget", "YFrameWindow")

    class Proxy:
        def __init__(self, depth):
            self.depth = depth
            if depth:
                returned.append(weakref.ref(self))

        def parentWidget(self):
            return Proxy(self.depth + 1)

        def inherits(self, name):
            if self.depth == 3:
                assert all(reference() is not None for reference in returned), (
                    "Every transient ancestor proxy must remain alive until traversal completes"
                )
            return name == classes[self.depth]

    host.font_panel = Proxy(0)
    assert scripting.select_glyphs(["é"], package_id=7) == ["é"]
    assert host.clears == 1 and host.selected == {1}
    gc.collect()
    assert all(reference() is None for reference in returned), (
        "The guard must release borrowed ancestor proxies after the call"
    )


@pytest.mark.parametrize("context", ["docked", "cycle", "exhausted", "unreadable"])
def test_select_when_font_panel_has_no_verified_frame_then_refuses_before_writers(
    host, context
):
    panel = NS(inherits=lambda name: name == "FontWindow")
    if context == "docked":
        dock = NS(
            inherits=lambda name: name == "QDockWidget", parentWidget=lambda: None
        )
        panel.parentWidget = lambda: dock
    elif context == "cycle":
        panel.parentWidget = lambda: panel
    elif context == "exhausted":
        parents = [NS(inherits=lambda name: False) for _ in range(20)]
        for index, ancestor in enumerate(parents):
            next_parent = parents[index + 1] if index + 1 < len(parents) else None
            ancestor.parentWidget = lambda next_parent=next_parent: next_parent
        panel.parentWidget = lambda: parents[0]
    else:

        def fail():
            raise RuntimeError("owned unreadable ancestry")

        panel.parentWidget = fail
    host.font_panel = panel
    with pytest.raises(ValueError, match="Font window"):
        scripting.select_glyphs(["é"], package_id=7)
    assert host.clears == 0 and host.selected == {0}


def test_select_when_active_panel_unreadable_then_refuses_before_legacy_writers(host):
    class Workspace:
        currentPackage = host.package

        @property
        def activeFontPanel(self):
            raise RuntimeError("owned unreadable context")

    host.native.flWorkspace.instance = Workspace
    with pytest.raises(ValueError, match="Font window"):
        scripting.select_glyphs(["é"], package_id=7)
    assert host.clears == 0 and host.selected == {0}


def test_select_when_font_changes_during_name_iteration_then_refuses_before_writers(
    host,
):
    def names():
        host.package = NS(id=8, isNull=False)
        yield "é"

    with pytest.raises(ValueError, match="Font window"):
        scripting.select_glyphs(names(), package_id=7)
    assert host.clears == 0 and host.selected == {0}


def test_current_package_when_host_errors_then_propagates(monkeypatch):
    def fail(name):
        raise RuntimeError("host unavailable")

    monkeypatch.setattr(scripting, "_native", fail)
    with pytest.raises(RuntimeError, match="host unavailable"):
        scripting.current_package()


@pytest.fixture
def lifecycle(monkeypatch):
    import sys

    calls = []
    native = NS(MainWindow=lambda: "parent")
    gui = NS(QDialog=NS(closeEvent=lambda d, e: calls.append("native-close")))
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda n: native
        if n == "fontlab"
        else NS(QtGui=gui, QtCore=NS(Qt=NS(WindowStaysOnTopHint=0x40000))),
    )
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    return calls, sys._fontlab_samples


def test_guard_when_callback_fails_then_exact_plain_wrapper_and_error(lifecycle):
    slots = []
    dialog = NS(_connections=[], status=NS(setText=slots.append))
    signal = NS(connect=slots.append)

    def fail(value):
        raise ValueError(value)

    scripting.connect_guarded(dialog, signal, fail)
    wrapper = slots.pop()
    assert dialog._connections == [(signal, wrapper)]
    assert wrapper is not fail and wrapper.__closure__
    wrapper("bad")
    assert dialog.slot_error == "ValueError('bad')"
    assert slots == ["Error: ValueError('bad')"]


def test_close_when_owned_resources_then_order_and_identity(lifecycle):
    calls, registry = lifecycle
    signal = NS(disconnect=lambda slot: calls.append(("disconnect", slot)))
    slot = lambda: None
    dialog = NS(
        _connections=[(signal, slot)], deleteLater=lambda: calls.append("delete")
    )
    replacement = object()
    registry["key"] = replacement
    timer = NS(stop=lambda: calls.append("stop"))
    child = NS(
        close=lambda: calls.append("child-close"),
        deleteLater=lambda: calls.append("child-delete"),
    )
    scripting.close_script_dialog(
        dialog, None, "key", timers=(timer,), children=(child,)
    )
    assert calls == [
        "stop",
        ("disconnect", slot),
        "child-close",
        "child-delete",
        "native-close",
        "delete",
    ]
    assert dialog._connections == [] and registry["key"] is replacement
    registry["key"] = dialog
    scripting.close_script_dialog(dialog, None, "key")
    assert "key" not in registry


@pytest.mark.parametrize("flags", [0x1, 0xB, 0x8000001, 0x40001])
def test_show_when_replacing_or_constructor_fails_then_publication_order(
    lifecycle, flags
):
    calls, registry = lifecycle
    registry["key"] = NS(close=lambda: calls.append("old-close"))

    def factory(parent):
        assert parent == "parent" and "key" not in registry
        calls.append("construct")
        return NS(
            windowFlags=lambda: flags,
            setWindowFlags=lambda value: calls.append(("flags", value)),
            show=lambda: calls.append("show"),
            raise_=lambda: calls.append("raise"),
        )

    dialog = scripting.show_script_dialog(factory, "key")
    assert registry["key"] is dialog
    assert calls == [
        "old-close",
        "construct",
        ("flags", flags | 0x40000),
        "show",
        "raise",
    ], "Preserve existing type/chrome and set priority before showing the new owner"
    registry.clear()

    def broken(parent):
        raise ValueError("constructor")

    with pytest.raises(ValueError, match="constructor"):
        scripting.show_script_dialog(broken, "key")
    assert "key" not in registry


def test_show_when_priority_setter_fails_then_owner_retained_without_show(lifecycle):
    calls, registry = lifecycle

    def fail(flags):
        raise RuntimeError("flags unavailable")

    dialog = NS(
        windowFlags=lambda: 1,
        setWindowFlags=fail,
        show=lambda: calls.append("show"),
        raise_=lambda: calls.append("raise"),
    )
    with pytest.raises(RuntimeError, match="flags unavailable"):
        scripting.show_script_dialog(lambda parent: dialog, "key")
    assert registry["key"] is dialog, (
        "Retain the owned dialog for existing close/retry cleanup"
    )
    assert calls == [], "Never show a window after priority configuration failed"


@pytest.mark.parametrize("result", [False, RuntimeError("close failed")])
def test_show_when_old_close_refuses_or_raises_then_retains_owner_without_constructor(
    lifecycle, result
):
    calls, registry = lifecycle

    def close():
        assert registry["key"] is old, "Removed owner before attempting cleanup"
        registry.pop("key")
        if isinstance(result, Exception):
            raise result
        return result

    old = NS(
        close=close,
        show=lambda: calls.append("old-show"),
        raise_=lambda: calls.append("old-raise"),
    )
    registry["key"] = old

    def factory(parent):
        pytest.fail("Constructed replacement before old cleanup completed")

    if isinstance(result, Exception):
        with pytest.raises(RuntimeError, match="close failed"):
            scripting.show_script_dialog(factory, "key")
        assert not calls
    else:
        assert scripting.show_script_dialog(factory, "key") is old
        assert calls == ["old-show", "old-raise"]
    assert registry["key"] is old


def test_show_when_old_widget_destroyed_then_entry_dropped_and_new_dialog_opens(lifecycle):
    calls, registry = lifecycle

    def close():
        raise ValueError("Trying to call 'close' on a destroyed QWidget object")

    registry["key"] = NS(close=close)
    dialog = NS(
        windowFlags=lambda: 1,
        setWindowFlags=lambda value: None,
        show=lambda: calls.append("show"),
        raise_=lambda: calls.append("raise"),
    )
    assert scripting.show_script_dialog(lambda parent: dialog, "key") is dialog
    assert registry["key"] is dialog and calls == ["show", "raise"]


def test_show_when_old_close_raises_other_value_error_then_owner_retained(lifecycle):
    calls, registry = lifecycle

    def close():
        raise ValueError("something else")

    old = NS(close=close)
    registry["key"] = old
    with pytest.raises(ValueError, match="something else"):
        scripting.show_script_dialog(lambda parent: pytest.fail("constructed"), "key")
    assert registry["key"] is old


def test_guard_when_no_label_then_success_arguments_and_contained_error(lifecycle):
    slots, received = [], []
    dialog = NS(_connections=[])
    signal = NS(connect=slots.append)
    scripting.connect_guarded(dialog, signal, lambda *args: received.append(args))
    slots[-1](1, "two")
    assert received == [(1, "two")], "Forward the native signal arguments"

    def fail():
        raise RuntimeError("owned failure")

    scripting.connect_guarded(dialog, signal, fail)
    slots[-1]()
    assert dialog.slot_error == "RuntimeError('owned failure')"


def test_close_when_disconnect_raises_then_still_releases_owned_dialog(lifecycle):
    calls, registry = lifecycle

    def fail(slot):
        raise RuntimeError("already disconnected")

    dialog = NS(
        _connections=[(NS(disconnect=fail), lambda: None)],
        deleteLater=lambda: calls.append("delete"),
    )
    registry["key"] = dialog
    scripting.close_script_dialog(dialog, None, "key")
    assert calls == ["native-close", "delete"]
    assert dialog._connections == [] and "key" not in registry


def test_select_add_when_valid_then_preserves_existing_in_font_order(host):
    assert scripting.select_glyphs(["space"], package_id=7, add=True) == ["A", "space"]
    assert host.selected == {0, 2} and host.clears == 0


def test_select_add_when_missing_then_never_clears_existing_selection(host):
    with pytest.raises(ValueError, match="Unknown glyph names"):
        scripting.select_glyphs(["space", "missing"], package_id=7, add=True)
    assert host.selected == {0} and host.clears == 0


def test_names_exact_selection_when_empty_then_no_current_glyph_fallback(host):
    host.selected.clear()
    assert scripting.names_font_window_selection() == []
    host.selected.add(1)
    assert scripting.names_font_window_selection() == ["é"]


@pytest.mark.parametrize("contours,components", [(0, 0), (0, 1), (1, 0)])
def test_names_fallback_when_valid_current_glyph_then_ignores_contour_truthiness(
    host, contours, components
):
    class Glyph:
        name = "é"
        shapes = [object()] * components

        def __len__(self):
            return contours

    host.selected.clear()
    host.native.CurrentGlyph = Glyph
    assert scripting.names_selected_names() == ["é"], (
        "Valid current glyphs must survive with no own contours"
    )
    assert host.selected == set() and host.clears == 0


def test_names_fallback_when_selection_present_then_preserves_font_order(host):
    host.selected = {2, 0}
    host.fl.Selected = lambda index: index in host.selected
    host.native.CurrentGlyph = lambda: pytest.fail("Selection must take priority")
    assert scripting.names_selected_names() == ["A", "space"]
    assert host.selected == {0, 2} and host.clears == 0


def test_names_fallback_when_font_closed_then_skips_stale_current_glyph(host):
    host.fl.font = None
    host.native.CurrentGlyph = lambda: pytest.fail("Closed font has no fallback")
    assert scripting.names_font_window_selection() == []
    assert scripting.names_selected_names() == []


def test_names_fallback_when_current_glyph_missing_then_empty(host):
    host.selected.clear()
    host.native.CurrentGlyph = lambda: None
    assert scripting.names_selected_names() == []


@pytest.mark.parametrize("boundary", ["selection", "current", "name"])
def test_names_fallback_when_native_read_fails_then_propagates(host, boundary):
    def fail(*args):
        raise RuntimeError(f"{boundary} read failed")

    class BrokenGlyph:
        @property
        def name(self):
            return fail()

    host.selected.clear()
    host.native.CurrentGlyph = fail if boundary == "current" else BrokenGlyph
    if boundary == "selection":
        host.fl.Selected = fail
    with pytest.raises(RuntimeError, match=f"{boundary} read failed"):
        scripting.names_selected_names()
    assert host.selected == set() and host.clears == 0


@pytest.mark.parametrize("names", [[], ["A"], ["A", "A"]])
def test_add_when_no_new_names_then_does_not_write(host, names):
    calls = []
    host.fl.Select = calls.append
    assert scripting.select_glyphs(names, package_id=7, add=True) == ["A"]
    assert host.clears == 0 and calls == [], "Add must not rewrite existing selection"


def test_add_when_requested_names_overlap_then_only_selects_missing(host):
    calls = []

    def select(index):
        calls.append(index)
        host.selected.add(index)

    host.fl.Select = select
    assert scripting.select_glyphs(["é", "A", "é"], package_id=7, add=True) == ["A", "é"]
    assert host.clears == 0 and calls == [1], "Only new names require native writes"


@pytest.mark.parametrize("failure_index", [1, 2])
@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt])
def test_add_when_native_write_fails_then_retains_prior_selection(host, failure_index, error_type):
    error = error_type("owned selection failure")

    def select(index):
        assert 0 in host.selected, "Existing selection must survive every addition"
        if index == failure_index:
            raise error
        host.selected.add(index)

    host.fl.Select = select
    with pytest.raises(error_type) as caught:
        scripting.select_glyphs(["é", "space"], package_id=7, add=True)
    assert caught.value is error, "Preserve the original native error"
    assert host.clears == 0
    assert host.selected == ({0} if failure_index == 1 else {0, 1}), "Retain old selection and completed additions"
