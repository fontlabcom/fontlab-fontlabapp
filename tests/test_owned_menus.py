# this_file: tests/test_owned_menus.py
"""OwnedMenus over FontLab-shaped Qt doubles (native proof is a separate gate)."""

import gc
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import fontlabapp.qt.menus as om
from fontlabapp.qt.menus import OwnedMenus

VIOLATIONS: list[str] = []  # teardown calls made while a slot dispatches
DISPATCHING: list[bool] = [False]


@pytest.fixture(autouse=True)
def _reset_violations():
    VIOLATIONS.clear()
    DISPATCHING[0] = False
    yield


def _note(what: str) -> None:
    if DISPATCHING[0]:
        VIOLATIONS.append(what)


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot):
        _note("disconnect")
        self.slots.remove(slot)

    def emit(self, *args):
        DISPATCHING[0] = True
        try:
            for slot in list(self.slots):
                slot(*args)  # PythonQt passes every signal argument
        finally:
            DISPATCHING[0] = False


class Action:
    def __init__(self, text, parent=None):
        self.text, self.parent = text, parent
        self.triggered = Signal()
        self.checkable, self.deleted = False, False
        self._menu = None

    def menu(self):
        return self._menu

    def setCheckable(self, flag):
        self.checkable = flag

    def trigger(self):
        self.triggered.emit(False)

    def deleteLater(self):
        _note("deleteLater")
        self.deleted = True


class Menu:
    def __init__(self, title="", fail_on=()):
        self.title, self._actions, self.removed = title, [], []
        self.fail_on, self.deleted = list(fail_on), False

    def actions(self):
        return list(self._actions)

    def addAction(self, action):
        self._actions.append(action)

    def insertAction(self, before, action):
        self._actions.insert(self._actions.index(before), action)

    def removeAction(self, action):
        _note("removeAction")
        self.removed.append(action.text)
        if action.text in self.fail_on:
            raise RuntimeError("remove " + action.text)
        self._actions.remove(action)

    def deleteLater(self):
        _note("deleteLater")
        self.deleted = True

    def addMenu(self, menu):
        action = Action(menu.title)
        action._menu = menu
        self._actions.append(action)
        return action


class MenuBar(Menu):
    pass


class Widget:
    def __init__(self, parent=None):
        self.parent, self.visible, self.deleted = parent, False, False
        self.flags, self.title = None, None

    def setWindowFlags(self, flags):
        self.flags = flags

    def setWindowTitle(self, title):
        self.title = title

    def setParent(self, parent):
        _note("setParent")
        self.parent = parent

    def move(self, x, y):
        pass

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def isVisible(self):
        return self.visible

    def closeEvent(self, event):
        pass

    def close(self):
        _note("close")
        if self.visible:
            self.visible = False
            self.closeEvent(None)

    def deleteLater(self):
        _note("deleteLater")
        self.deleted = True


class Timer:
    def __init__(self):
        self.timeout, self.active = Signal(), False

    def setSingleShot(self, flag):
        pass

    def setInterval(self, ms):
        pass

    def start(self):
        self.active = True

    def fire(self):
        self.active = False
        for slot in list(self.timeout.slots):
            slot()


class MainWindow:
    def __init__(self, menubar):
        self._bar = menubar

    def menuBar(self):
        return self._bar


class TopLevel:
    def __init__(self, name):
        self.name = name

    def className(self):
        return self.name


def make_qt(top_levels=None):
    app = SimpleNamespace(topLevelWidgets=lambda: list(top_levels or []))
    return SimpleNamespace(
        QtGui=SimpleNamespace(QAction=Action, QMenu=Menu, QWidget=Widget, QApplication=app),
        QtCore=SimpleNamespace(QTimer=Timer, Qt=SimpleNamespace(Tool=11, WindowStaysOnTopHint=0x40000)),
    )


def make_menus(titles=("File", "&Edit"), **kwargs):
    """Return (OwnedMenus, errors, menubar, {title: Menu}) over a fake FontLab."""
    bar = MenuBar()
    menus = {}
    for title in titles:
        menu = Menu(title)
        bar.addMenu(menu).text = title
        menus[title.replace("&", "")] = menu
    errors = []
    fontlab = SimpleNamespace(MainWindow=lambda: MainWindow(bar))
    owned = OwnedMenus(
        make_qt(), fontlab, error_sink=lambda e, o: errors.append(e), **kwargs
    )
    return owned, errors, bar, menus


# --- add_action ---------------------------------------------------------------


def test_add_action_when_menu_title_matches_without_ampersand_then_existing_menu_used():
    owned, errors, _, menus = make_menus()
    calls = []
    token = owned.add_action("Edit", "Hello", lambda: calls.append(1))
    action = owned.action(token)
    assert menus["Edit"].actions() == [action] and owned._owned_menu is None
    action.trigger()
    assert calls == [1] and errors == []


def test_add_action_when_no_menu_matches_then_one_owned_menu_created_and_reused():
    owned, _, bar, _ = make_menus(owned_title="Glyphs Plugins")
    first = owned.add_action("Nowhere", "A", lambda: None)
    second = owned.add_action("Other", "B", lambda: None)
    owned_menus = [a.menu() for a in bar.actions() if a.text == "Glyphs Plugins"]
    assert len(owned_menus) == 1, "exactly one owned menu"
    assert [a.text for a in owned_menus[0].actions()] == ["A", "B"]
    assert owned.action(first) is not owned.action(second)


def test_own_menu_when_menubar_has_same_title_then_owned_menu_is_separate_and_reused():
    owned, _, bar, menus = make_menus(titles=("File", "Glyphs Plugins"), owned_title="Glyphs Plugins")
    first = owned.own_menu()
    assert first is not menus["Glyphs Plugins"], "never another host's same-titled menu"
    assert owned.own_menu() is first and owned._owned_menu[0] is first
    assert sum(a.menu() is first for a in bar.actions()) == 1, "added to the menubar once"


def test_own_menu_when_passed_to_add_action_then_action_lands_in_owned_menu():
    owned, _, _, menus = make_menus()
    token = owned.add_action(owned.own_menu(), "Mine", lambda: None)
    assert [a.text for a in owned.own_menu().actions()] == ["Mine"]
    assert all(not m.actions() for m in menus.values()), "no FontLab menu touched"
    owned.remove(token)
    assert owned.own_menu().actions() == []


def test_close_when_menu_created_only_via_own_menu_then_menu_removed():
    owned, errors, bar, _ = make_menus()
    menu = owned.own_menu()
    owned.close()
    assert menu.deleted and owned._owned_menu is None
    assert [a.text for a in bar.actions()] == ["File", "&Edit"], "owned menu left the bar"
    assert errors == []


def test_add_action_when_index_given_then_inserted_before_that_action():
    owned, _, _, menus = make_menus()
    owned.add_action("File", "one", lambda: None)
    owned.add_action("File", "two", lambda: None)
    owned.add_action("File", "first", lambda: None, index=0)
    owned.add_action("File", "last", lambda: None, index=99)
    owned.add_action("File", "tail", lambda: None, index=-1)
    assert [a.text for a in menus["File"].actions()] == [
        "first", "one", "two", "last", "tail",
    ]


def test_add_menu_when_actions_added_to_it_then_close_removes_them_then_submenu():
    owned, errors, _, menus = make_menus()
    owned.add_action("File", "before", lambda: None)
    token = owned.add_menu("File", "Sub")
    submenu = owned.menu(token)
    assert [a.text for a in menus["File"].actions()] == ["before", "Sub"]
    assert menus["File"].actions()[1].menu() is submenu
    calls = []
    inner = owned.add_action(submenu, "Inner", lambda: calls.append(1))
    assert submenu.actions() == [owned.action(inner)] and owned._owned_menu is None
    owned.action(inner).trigger()
    owned.close()
    assert calls == [1] and errors == []
    assert submenu.removed == ["Inner"] and submenu.deleted
    assert menus["File"].removed == ["Sub", "before"]
    assert owned.menu(token) is None


def test_add_action_when_checkable_then_action_is_checkable():
    owned, _, _, _ = make_menus()
    assert owned.action(owned.add_action("File", "x", lambda: None, checkable=True)).checkable
    assert not owned.action(owned.add_action("File", "y", lambda: None)).checkable


def test_callback_when_it_raises_then_error_goes_to_sink_not_qt():
    owned, errors, _, _ = make_menus()
    token = owned.add_action("File", "boom", lambda: 1 / 0)
    owned.action(token).trigger()
    assert len(errors) == 1 and isinstance(errors[0], ZeroDivisionError)


# --- remove and deferral ----------------------------------------------------------


def test_remove_when_unknown_or_repeated_then_noop():
    owned, errors, _, menus = make_menus()
    token = owned.add_action("File", "x", lambda: None)
    action = owned.action(token)
    owned.remove(token)
    owned.remove(token)
    owned.remove(999)
    assert menus["File"].actions() == [] and menus["File"].removed == ["x"]
    assert action.triggered.slots == [] and action.deleted and errors == []
    assert owned.action(token) is None


def test_remove_when_called_inside_its_own_slot_then_deferred_and_runs_once():
    owned, errors, _, menus = make_menus()
    tokens = []

    def callback():
        owned.remove(tokens[0])
        owned.remove(tokens[0])  # a second request must not undo twice

    tokens.append(owned.add_action("File", "self", callback))
    action = owned.action(tokens[0])
    action.trigger()
    assert VIOLATIONS == [] and menus["File"].actions() == [action]
    assert owned._reaper.active, "the outermost slot exit scheduled one drain"
    owned._reaper.fire()
    assert menus["File"].actions() == [] and menus["File"].removed == ["self"]
    assert action.triggered.slots == [] and action.deleted
    assert VIOLATIONS == [] and errors == []


def test_reap_when_drain_already_scheduled_and_nested_tick_inside_slot_then_work_waits_for_slot_exit():
    """The batch holds the owner before the slot starts, so the nested tick really reaches `_reap`."""
    owned, errors, _, menus = make_menus()
    seen, tokens, ran = [], [], []

    def callback():
        seen.append(("before tick", len(owned._pending)))
        owned._reaper.fire()  # nested tick: the batch calls _reap while this slot runs
        seen.append(("after tick", len(owned._pending), ran[:]))

    tokens.append(owned.add_action("File", "self", callback))
    owned._defer(lambda: ran.append("deferred"))  # outside any slot: queued and the shared drain is scheduled
    assert owned._pending and owned._reaper.active and ran == []
    owned.action(tokens[0]).trigger()
    assert seen == [("before tick", 1), ("after tick", 1, [])], "reap must not run while our slot runs"
    assert owned._reaper.active, "the slot exit scheduled the drain again"
    owned._reaper.fire()
    assert ran == ["deferred"] and owned._pending == []
    assert VIOLATIONS == [] and errors == []


def test_remove_when_slot_ticks_nested_event_loop_then_queue_untouched_and_no_spin():
    owned, errors, _, menus = make_menus()
    seen, tokens = [], []

    def callback():
        owned.remove(tokens[0])
        seen.append(len(owned._pending))
        owned._reaper.fire()  # nested tick inside the slot
        seen.append(len(owned._pending))

    tokens.append(owned.add_action("File", "self", callback))
    owned.action(tokens[0]).trigger()
    assert seen == [1, 1], "the nested tick neither runs nor re-queues blocked work"
    assert owned._reaper.active
    owned._reaper.fire()
    assert menus["File"].actions() == [] and owned._pending == []
    assert VIOLATIONS == [] and errors == []


def test_two_instances_when_same_qt_then_share_one_timer():
    qt = make_qt()
    fontlab = SimpleNamespace(MainWindow=lambda: MainWindow(MenuBar()))
    one = OwnedMenus(qt, fontlab, error_sink=lambda e, o: None)
    two = OwnedMenus(qt, fontlab, error_sink=lambda e, o: None)
    assert one._reaper is two._reaper


# --- close -------------------------------------------------------------------------


def test_close_when_items_exist_then_newest_first_and_owned_menu_dropped():
    owned, errors, bar, menus = make_menus()
    owned.add_action("File", "a", lambda: None)
    owned.add_action("Nowhere", "b", lambda: None)
    owned.add_action("File", "c", lambda: None)
    owned_menu = owned._owned_menu[0]
    owned.close()
    assert menus["File"].removed == ["c", "a"] and owned_menu.removed == ["b"]
    assert owned_menu.deleted and owned._owned_menu is None
    assert [a.text for a in bar.actions()] == ["File", "&Edit"], "owned menu left the bar"
    assert errors == [] and owned._tokens == {}


def test_close_when_several_undos_fail_then_all_tried_and_first_failure_raised():
    owned, _, _, menus = make_menus()
    menus["File"].fail_on = ["a", "c"]
    for name in "abc":
        owned.add_action("File", name, lambda: None)
    with pytest.raises(RuntimeError, match="remove c"):
        owned.close()
    assert menus["File"].removed == ["c", "b", "a"], "newest first, every item tried"
    assert owned._tokens == {}


def test_close_when_called_inside_a_slot_then_everything_deferred():
    owned, errors, _, menus = make_menus()
    owned.add_action("File", "closer", lambda: owned.close())
    owned.add_action("File", "other", lambda: None)
    closer = menus["File"].actions()[0]
    closer.trigger()
    assert VIOLATIONS == [] and len(menus["File"].actions()) == 2
    owned._reaper.fire()
    assert menus["File"].actions() == [] and menus["File"].removed == ["other", "closer"]
    assert VIOLATIONS == [] and errors == [] and owned._pending == []


# --- tool windows ------------------------------------------------------------------


def _window(owned, closed):
    widget = Widget()
    token, window = owned.tool_window(widget, "Tool", on_close=lambda: closed.append(1))
    return token, window, widget


def test_tool_window_when_shown_then_widget_inside_tool_window():
    owned, _, _, _ = make_menus()
    token, window, widget = _window(owned, [])
    assert window.flags == 11 | 0x40000 and window.title == "Tool" and window.visible
    assert widget.parent is window and widget.visible and token in owned._tokens


def test_tool_window_when_title_bar_closes_then_on_close_once_and_teardown_deferred():
    owned, errors, _, _ = make_menus()
    closed = []
    token, window, widget = _window(owned, closed)
    window.closeEvent(None)
    window.closeEvent(None)
    window.close()
    assert closed == [1] and not window.visible
    assert not window.deleted, "deletion waits for the event loop"
    owned._reaper.fire()
    assert window.deleted and widget.parent is None and not widget.visible
    owned.remove(token)
    assert closed == [1], "a finished window's token does nothing"
    assert errors == []


def test_tool_window_when_token_removed_then_on_close_once_and_cleaned():
    owned, errors, _, _ = make_menus()
    closed = []
    token, window, widget = _window(owned, closed)
    owned.remove(token)
    owned.remove(token)
    assert closed == [1] and not window.visible
    owned.close()
    assert window.deleted and widget.parent is None
    assert owned._pending == [] and errors == []


def test_tool_window_when_on_close_closes_owner_then_nothing_torn_down_in_dispatch():
    owned, errors, _, _ = make_menus()
    widget = Widget()
    _, window = owned.tool_window(widget, "T", on_close=lambda: owned.close())
    DISPATCHING[0] = True  # a title-bar close arrives from the native event loop
    try:
        window.closeEvent(None)
    finally:
        DISPATCHING[0] = False
    assert VIOLATIONS == [], VIOLATIONS
    assert not window.deleted
    owned._reaper.fire()
    assert window.deleted and errors == [] and owned._tokens == {}


def test_tool_window_when_widget_reopened_before_reaper_then_new_window_keeps_it():
    owned, _, _, _ = make_menus()
    widget = Widget()
    _, first = owned.tool_window(widget, "A")
    first.closeEvent(None)
    token, second = owned.tool_window(widget, "B")
    owned._reaper.fire()
    assert first.deleted and not second.deleted
    assert widget.parent is second and widget.visible
    assert token in owned._tokens


def test_tool_window_when_on_close_raises_then_error_goes_to_sink():
    owned, errors, _, _ = make_menus()
    _, window = owned.tool_window(Widget(), "T", on_close=lambda: 1 / 0)
    window.closeEvent(None)
    assert len(errors) == 1 and isinstance(errors[0], ZeroDivisionError)


# --- main window ------------------------------------------------------------------


def test_main_window_when_fontlab_has_it_then_used_and_cached():
    owned, _, bar, _ = make_menus()
    first = owned.main_window()
    assert first.menuBar() is bar and owned.main_window() is first


def test_main_window_when_getter_missing_then_gc_safe_top_level_scan():
    states = []
    window = MainWindow(MenuBar())
    widgets = [TopLevel("Dialog"), window]
    window.className = lambda: "MainWindow"
    qt = make_qt(widgets)

    def top_level():
        states.append(gc.isenabled())
        return widgets

    qt.QtGui.QApplication.topLevelWidgets = top_level
    owned = OwnedMenus(qt, SimpleNamespace(), error_sink=lambda e, o: None)
    previous = gc.isenabled()
    gc.enable()
    try:
        assert owned.main_window() is window
        assert gc.isenabled(), "GC state restored"
    finally:
        (gc.enable if previous else gc.disable)()
    assert states == [False], "native list converted with GC off"


def test_main_window_when_absent_then_runtime_error():
    qt = make_qt([TopLevel("Dialog")])
    owned = OwnedMenus(qt, SimpleNamespace(MainWindow=lambda: None), error_sink=lambda e, o: None)
    with pytest.raises(RuntimeError, match="main window"):
        owned.main_window()
    with pytest.raises(RuntimeError, match="main window"):
        owned.add_action("File", "x", lambda: None)


def test_main_window_when_injected_then_no_lookup():
    window = MainWindow(MenuBar())
    owned = OwnedMenus(make_qt(), SimpleNamespace(), error_sink=lambda e, o: None,
                       main_window=window)
    assert owned.main_window() is window


def test_main_window_when_absent_then_typed_main_window_not_found():
    from fontlabapp.qt.safe import MainWindowNotFound

    qt = make_qt([TopLevel("Dialog")])
    owned = OwnedMenus(qt, SimpleNamespace(MainWindow=lambda: None), error_sink=lambda e, o: None)
    with pytest.raises(MainWindowNotFound, match="main window not found"):
        owned.main_window()


# --- issue 122 T14: teardown seam, close and cross-token removal ----------------


def test_defer_when_first_then_runs_before_already_queued_teardown():
    owned, errors, _, _ = make_menus()
    order = []
    owned._defer(lambda: order.append("teardown"))
    owned._defer(lambda: order.append("release"), first=True)
    owned._reaper.fire()
    assert order == ["release", "teardown"] and errors == []


def test_defer_when_first_during_a_drain_then_runs_after_the_running_batch():
    owned, errors, _, _ = make_menus()
    order = []

    def teardown():
        order.append("a")
        owned._defer(lambda: order.append("late"), first=True)

    owned._defer(teardown)
    owned._defer(lambda: order.append("b"))
    owned._reaper.fire()
    assert order == ["a", "b", "late"] and errors == [], "documented limit of first=True"


def test_defer_when_first_then_same_order_as_legacy_pending_reorder():
    """Glyport's current ``_pending.insert(0, _pending.pop())`` keeps working."""

    def drain(use_seam: bool) -> list[str]:
        owned, _, _, _ = make_menus()
        order: list[str] = []
        owned._defer(lambda: order.append("a"))
        owned._defer(lambda: order.append("b"))
        if use_seam:
            owned._defer(lambda: order.append("front"), first=True)
        else:
            owned._defer(lambda: order.append("front"))
            owned._pending.insert(0, owned._pending.pop())
        owned._reaper.fire()
        return order

    assert drain(True) == drain(False) == ["front", "a", "b"]


def test_close_when_owned_menu_removal_fails_then_items_removed_and_error_raised():
    owned, _, bar, _ = make_menus()
    owned.add_action("Nowhere", "b", lambda: None)
    owned_menu = owned._owned_menu[0]
    bar.fail_on = [om.OWNED_MENU_TITLE]
    with pytest.raises(RuntimeError, match="remove " + om.OWNED_MENU_TITLE):
        owned.close()
    assert owned_menu.removed == ["b"], "items go first, then the owned menu"
    assert owned._tokens == {} and owned._owned_menu is None
    assert not owned_menu.deleted, "a menu still on the bar is not deleted"


def test_remove_when_slot_removes_another_token_then_deferred_and_runs_once():
    owned, errors, _, menus = make_menus()
    tokens = {}

    def remove_other():
        owned.remove(tokens["other"])
        owned.remove(tokens["other"])

    tokens["self"] = owned.add_action("File", "remover", remove_other)
    tokens["other"] = owned.add_action("File", "other", lambda: None)
    remover, other = owned.action(tokens["self"]), owned.action(tokens["other"])
    remover.trigger()
    assert VIOLATIONS == [] and menus["File"].actions() == [remover, other]
    owned._reaper.fire()
    assert menus["File"].actions() == [remover] and menus["File"].removed == ["other"]
    assert other.deleted and owned.action(tokens["other"]) is None
    assert VIOLATIONS == [] and errors == [] and owned._pending == []


# --- import hygiene ---------------------------------------------------------------


def test_owned_menus_when_cold_imported_then_no_native_or_heavy_modules_load():
    import fontlabapp

    package_root = str(Path(fontlabapp.__file__).resolve().parent.parent)
    script = """
import importlib.abc
import sys

class StdlibOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split('.')[0]
        # 'org' is the Jython probe in stdlib copy.py; it handles its own failure.
        if root not in ('fontlabapp', 'org') and root not in sys.stdlib_module_names:
            raise AssertionError('Non-stdlib import: ' + fullname)

sys.meta_path.insert(0, StdlibOnly())
sys.path.insert(0, sys.argv[1])
import fontlabapp.qt.menus as m
assert m.OWNED_MENU_TITLE
banned = {'PythonQt', 'fontlab', 'fontgate', 'FL', 'fontpr', 'PySide2',
          'PySide6', 'fontport', 'fontlab_fontport', 'glyport',
          'fontlab_glyport', 'fontTools', 'fontParts'}
loaded = {n.split('.')[0] for n in sys.modules} & banned
assert not loaded, loaded
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, package_root],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_all_when_listed_then_every_name_exists():
    assert all(hasattr(om, name) for name in om.__all__)


def test_public_state_when_action_dispatches_then_read_only_properties_follow_lifetime():
    owned, errors, _, _ = make_menus()
    assert not owned.has_items and not owned.dispatching
    seen = []
    token = owned.add_action("Edit", "State", lambda: seen.append((owned.has_items, owned.dispatching)))
    assert owned.has_items and not owned.dispatching
    owned.action(token).trigger()
    assert seen == [(True, True)] and not errors
    assert not owned.dispatching
    owned.remove(token)
    assert not owned.has_items
    for name in ("has_items", "dispatching"):
        with pytest.raises(AttributeError):
            setattr(owned, name, True)


def test_remove_menu_when_child_triggers_removal_then_children_disconnect_after_dispatch():
    owned, errors, bar, _ = make_menus()
    token = owned.add_menu("Missing", "Reporters")
    submenu = owned.menu(token)
    other = owned.add_action("File", "same title", lambda: None)
    child = owned.add_action(submenu, "same title", lambda: owned.remove(token))
    action = owned.action(child)
    action.trigger()
    assert owned.menu(token) is submenu and not action.deleted
    assert VIOLATIONS == []
    owned._reaper.fire()
    assert owned.action(child) is None and owned.menu(token) is None
    assert action.deleted and action.triggered.slots == []
    assert owned.action(other) is not None and not owned.action(other).deleted
    assert submenu.deleted and submenu.removed == ["same title"]
    owned.remove(token)
    owned.close()
    assert VIOLATIONS == [] and errors == []
    assert [a.text for a in bar.actions()] == ["File", "&Edit"]


def test_remove_menu_when_qt_deletes_it_then_later_close_has_no_dead_action(monkeypatch):
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import isValid

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    parent = QtWidgets.QMenu("View")
    qt = SimpleNamespace(
        QtGui=SimpleNamespace(QAction=QtGui.QAction, QMenu=QtWidgets.QMenu),
        QtCore=QtCore,
    )
    errors = []
    owned = OwnedMenus(qt, SimpleNamespace(), error_sink=lambda e, o: errors.append(e))
    monkeypatch.setattr(owned, "_menu", lambda title: parent)
    token = owned.add_menu("View", "Reporters")
    submenu = owned.menu(token)
    child = owned.add_action(submenu, "Reporter", lambda: None)
    action = owned.action(child)
    owned.remove(token)
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(submenu) and not isValid(action)
    owned.close()
    assert owned.action(child) is None and not owned.has_items and errors == []
    assert parent.actions() == [] and app is not None


def test_remove_when_deferred_undo_fails_inside_slot_then_error_goes_to_sink_not_qt():
    owned, errors, _, menus = make_menus()
    menus["File"].fail_on = ["victim"]
    victim = owned.add_action("File", "victim", lambda: None)
    owned.add_action("File", "caller", lambda: owned.remove(victim))
    menus["File"].actions()[1].trigger()  # the removal fails later, not in the slot
    assert errors == [] and owned._reaper.active
    owned._reaper.fire()
    assert [type(e) for e in errors] == [RuntimeError] and "remove victim" in str(errors[0])
    assert victim not in owned._tokens and VIOLATIONS == []
