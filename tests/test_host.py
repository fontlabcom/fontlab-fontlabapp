# this_file: tests/test_host.py
"""The live tree over fake Qt objects: naming, lookup, triggering and panels."""

import gc
import sys
from types import SimpleNamespace

import pytest

from fontlabapp.core.host import (
    Action,
    ActionDisabledError,
    Host,
    Menu,
    UnsupportedOperation,
)
from fontlabapp.core.menu_names import snake


class Keys:
    def __init__(self, text):
        self.text = text

    def toString(self):
        return self.text


class Group:
    def __init__(self, exclusive):
        self.exclusive = exclusive

    def isExclusive(self):
        return self.exclusive


class QAction:
    def __init__(self, text, name="", shortcut="", checkable=False, checked=False,
                 enabled=True, visible=True, menu=None, separator=False, group=None):
        self.text, self.objectName, self.shortcut = text, name, Keys(shortcut)
        self.toolTip, self.statusTip = text.replace("&", ""), f"@mainwindow.{name}" if name else ""
        self.checkable, self.checked, self.enabled, self.visible = checkable, checked, enabled, visible
        self._menu, self._separator, self.triggered, self._group = menu, separator, 0, group
        self.toggles = True

    def actionGroup(self):
        return self._group

    def menu(self):
        return self._menu

    def isSeparator(self):
        return self._separator

    def trigger(self):
        self.triggered += 1
        if self.checkable and self.toggles and not (self.checked and self._group and self._group.exclusive):
            self.checked = not self.checked


class QMenu:
    def __init__(self, title, name, entries):
        self.title, self.objectName, self._entries = title, name, entries

    def actions(self):
        return self._entries


def submenu(title, name, entries):
    return QAction(title, menu=QMenu(title, name, entries))


class Widget:
    def __init__(self, tip, visible=False):
        self.statusTip, self._visible, self.raised = tip, visible, 0

    def isVisible(self):
        return self._visible

    def raise_(self):
        self.raised += 1


class Main:
    def __init__(self, bar, children):
        self._bar, self._children, self.shown = bar, children, []

    def menuBar(self):
        return self._bar

    def children(self):
        return self._children

    def showPanel(self, panel_id, visible):
        self.shown.append((panel_id, visible))


@pytest.fixture
def world():
    add = QAction("Add Component...", "actionAdd_Component", "Meta+Shift+A")
    anchor = QAction("Add Anchor", "actionAdd_Anchor", enabled=False)
    flatten_fog = QAction("Flatten Glyph", "actionFogFlatten_Glyph", visible=False)
    flatten = QAction("&Flatten Glyph", "actionFlatten_Glyph")
    snap = QAction("&Snap", "actionSnap", checkable=True)
    glyph_panel = QAction("Gl&yph", "actionGlyphPanel", "Ctrl+I")
    chat_panel = QAction("&Chat", "actionChatPanel")
    pins_panel = QAction("&Anchors && Pins", "actionPinsPanel")
    toolbar = QAction("&Toolbar", "actionToolbarPanel", checkable=True, checked=True)
    imp = QAction("Import", "actionImport")
    hidden_main = QAction("Secret", "actionSecret")
    bar = QMenu("", "", [
        submenu("&Glyph", "menuGlyph", [add, QAction("", separator=True), anchor, flatten_fog, flatten,
                                        submenu("Flag", "menuFlag", [QAction("Red", "actionRed")])]),
        submenu("&View", "menuView", [snap, imp]),
        submenu("&Window", "menuWindow", [submenu("&Panels", "menuPanels", [glyph_panel, chat_panel, pins_panel]), toolbar]),
        submenu("&Help", "menuHelp", [glyph_panel]),
    ])
    widgets = [Widget("@inspector_glyph.InspectorGlyph", visible=True), Widget("@chatpanel.ChatPanel")]
    calls = []

    def call(name, **arguments):
        calls.append((name, arguments))
        if name == "list_actions":
            return {"actions": [{"id": "remove_overlap", "label": "remove overlap"}]}
        return {"ok": True}

    main = Main(bar, [add, snap, hidden_main, "not an action"])
    host = Host(main, qaction_type=QAction, widgets=lambda: widgets, call=call)
    return host, main, calls, locals()


def test_menu_attributes_when_labels_then_snake_names(world):
    host, _, _, objects = world
    repr(host.menu), repr(host.menu.glyph), dir(host.menu.glyph), repr(host.actions), list(host.actions.values())
    triggered = {k: v.triggered for k, v in objects.items() if isinstance(v, QAction) and v.triggered}
    assert triggered == {}, "dir()/repr()/indexing must never trigger"
    assert {"glyph", "view", "window", "help"} <= set(dir(host.menu))
    assert {"add_component", "add_anchor", "flatten_glyph", "fog_flatten_glyph", "flag"} <= set(dir(host.menu.glyph))
    assert host.menu.view.import_.code == "actionImport"


@pytest.mark.parametrize("enabled", [True, False], ids=["gc-enabled", "gc-disabled"])
@pytest.mark.parametrize("fail", [False, True], ids=["success", "error"])
@pytest.mark.parametrize("attribute", ["widget", "visible"])
def test_panel_when_native_widgets_enumerated_then_gc_disabled_and_restored(
    world, monkeypatch, enabled, fail, attribute
):
    _, main, _, objects = world
    states = []

    def all_widgets():
        states.append(gc.isenabled())
        if fail:
            raise RuntimeError("enumeration failed")
        return objects["widgets"]

    qapp = SimpleNamespace(allWidgets=all_widgets)
    qt = SimpleNamespace(QtGui=SimpleNamespace(QApplication=SimpleNamespace(instance=lambda: qapp)))
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    panel = Host(main, qaction_type=QAction, call=lambda *a, **kw: None).panels.glyph
    previous = gc.isenabled()
    (gc.enable if enabled else gc.disable)()
    try:
        if fail:
            with pytest.raises(RuntimeError, match="enumeration failed"):
                getattr(panel, attribute)
        elif attribute == "widget":
            assert panel.widget is objects["widgets"][0]
        else:
            assert panel.visible is True
        assert states == [False], "allWidgets must run with cyclic GC disabled"
        assert gc.isenabled() is enabled, "panel lookup must restore the caller's GC state"
    finally:
        (gc.enable if previous else gc.disable)()


def test_action_when_called_then_triggers_once_and_reports_path(world):
    host, _, _, objects = world
    action = host.menu.glyph.add_component
    assert action.path == "Glyph > Add Component"
    assert objects["add"].triggered == 0, "attribute access must not trigger"
    assert action() is action
    assert objects["add"].triggered == 1
    assert repr(action) == "<Action 'Glyph > Add Component' Meta+Shift+A>"


def test_action_when_disabled_then_raises_without_trigger(world):
    host, _, _, objects = world
    with pytest.raises(ActionDisabledError, match="Glyph > Add Anchor"):
        host.menu.glyph.add_anchor()
    assert objects["anchor"].triggered == 0


def test_set_checked_when_state_matches_then_no_trigger(world):
    host, _, _, objects = world
    snap = host.menu.view.snap
    snap.set_checked(False)
    assert objects["snap"].triggered == 0
    snap.set_checked(True)
    assert snap.checked and objects["snap"].triggered == 1
    with pytest.raises(TypeError):
        host.menu.glyph.add_component.set_checked(True)


def test_menu_missing_attribute_when_typo_then_suggests(world):
    host, *_ = world
    with pytest.raises(AttributeError, match="add_component"):
        host.menu.glyph.add_componnt  # noqa: B018 - lookup must raise


def test_menu_getitem_when_label_or_path_then_child(world):
    host, *_ = world
    assert host.menu["Glyph > Flag > Red"].code == "actionRed"
    assert host.menu.glyph["Add Component"].code == "actionAdd_Component"
    assert isinstance(host.menu["Glyph"]["Flag"], Menu)
    assert repr(host.menu.glyph.flag) == "<Menu 'Glyph > Flag' (1 items)>"


def test_actions_mapping_when_path_code_or_markup_then_same_action(world):
    host, *_ = world
    by_path = host.actions["Glyph > Add Component"]
    assert host.actions["actionAdd_Component"].qaction is by_path.qaction
    assert host.actions["@mainwindow.actionAdd_Component"].qaction is by_path.qaction
    assert host.actions["glyph > add component..."].qaction is by_path.qaction
    assert "actionSecret" in host.actions, "main-window QActions outside menus are listed by objectName"
    assert [a.code for a in host.actions.search("flatten")] == ["actionFogFlatten_Glyph", "actionFlatten_Glyph"]
    with pytest.raises(KeyError):
        host.actions["Glyph > Nope"]


def test_find_when_text_then_actions_below_menu(world):
    host, *_ = world
    assert [a.path for a in host.menu.glyph.find("add")] == ["Glyph > Add Component", "Glyph > Add Anchor"]


def test_panels_when_known_id_then_show_panel_not_toggle(world):
    host, main, _, objects = world
    assert set(dir(host.panels)) >= {"glyph", "chat", "toolbar"}
    glyph = host.panels.glyph
    assert glyph.visible and glyph.panel_id == 10
    glyph.hide().show()
    assert main.shown == [(10, False), (10, True)]
    assert objects["glyph_panel"].triggered == 0


def test_panels_when_no_id_then_trigger_only_if_state_differs(world):
    host, _, _, objects = world
    host.panels.chat.hide()
    assert objects["chat_panel"].triggered == 0, "hidden panel stays hidden without a toggle"
    host.panels.chat.show()
    assert objects["chat_panel"].triggered == 1
    host.panels.toolbar.show()
    assert objects["toolbar"].triggered == 0, "checked toolbar already visible"
    host.panels.toolbar.hide()
    assert not objects["toolbar"].checked


def test_panel_focus_when_widget_then_raised(world):
    host, *_ = world
    panel = host.panels.glyph.focus()
    assert panel.widget.raised == 1
    assert repr(panel) == "<Panel 'Glyph' visible>"


def test_glyph_actions_when_called_then_run_actions_payload(world):
    host, _, calls, _ = world
    assert dir(host.glyph_actions).count("remove_overlap") == 1
    host.glyph_actions.remove_overlap(["B"], layer_mode="masters", amount=3)
    assert calls[-1] == ("run_actions", {"actions": [{"id": "remove_overlap", "amount": 3}],
                                         "glyph_names": ["B"], "layer_mode": "masters"})
    with pytest.raises(AttributeError, match="remove_overlap"):
        host.glyph_actions.remove_overlaps  # noqa: B018 - lookup must raise


def test_import_when_outside_fontlab_then_no_native_modules():
    import sys

    import fontlabapp.core.host  # noqa: F401

    assert "PythonQt" not in sys.modules and "fontlab" not in sys.modules


def test_panels_when_ampersand_label_then_and_name_and_label_lookup(world):
    host, *_ = world
    assert "anchors_and_pins" in dir(host.panels)
    assert host.panels["Anchors & Pins"].panel_id == 13
    assert host.panels["anchors_and_pins"].label == "Anchors & Pins"
    assert host.menu.window.panels.anchors_and_pins.path == "Window > Panels > Anchors & Pins"
    assert host.menu["Window > Panels > Anchors & Pins"].code == "actionPinsPanel"
    assert host.actions["Window > Panels > Anchors & Pins"].code == "actionPinsPanel"
    assert host.actions["&Window > &Panels > &Anchors && Pins"].code == "actionPinsPanel"


def test_actions_index_when_menu_changes_then_refresh_on_miss(world):
    host, _, _, objects = world
    assert len(host.actions) == len(list(host.actions.values()))
    new = QAction("Brand New", "actionBrand_New")
    objects["bar"]._entries[0]._menu._entries.append(new)
    assert host.actions["Glyph > Brand New"].qaction is new


def test_panels_when_action_relabelled_by_state_then_name_is_stable():
    preview = QAction("Hide Preview", "actionPreviewPanel")
    preview.toolTip = "Preview panel"
    bar = QMenu("", "", [submenu("&Window", "menuWindow", [preview])])
    host = Host(Main(bar, []), qaction_type=QAction, widgets=list, call=None)
    assert list(host.panels.items()) == ["preview"]
    assert host.panels.preview.label == "Preview"


def test_menu_when_label_changes_with_context_then_stable_aliases_resolve():
    printing = QAction("Print Preview...", "actionPrint")
    printing.toolTip = "File: Print"
    close = QAction("Close Project", "actionClose_Window")
    close.toolTip = "Window: Close tab / window"
    preview = QAction("Hide Preview", "actionPreviewPanel")
    preview.toolTip = "Preview panel"
    bar = QMenu("", "", [submenu("&File", "menuFile", [printing, close, preview])])
    host = Host(Main(bar, []), qaction_type=QAction, widgets=list, call=None)
    file = host.menu.file
    assert "print_preview" in dir(file) and "print" not in dir(file)
    assert file.print.qaction is printing
    assert file.close_window.qaction is close
    assert file.preview.qaction is preview
    with pytest.raises(AttributeError):
        file.close_tab_windows  # noqa: B018 - lookup must raise


def test_actions_refresh_when_main_window_gains_action_then_found(world):
    host, main, _, _ = world
    assert "actionLater" not in host.actions
    main._children.append(QAction("Later", "actionLater"))
    assert host.actions["actionLater"].code == "actionLater"



def test_actions_when_menu_replaces_entry_under_same_path_then_new_qaction(world):
    host, _, _, objects = world
    assert host.actions["Glyph > Add Component"].qaction is objects["add"]
    replacement = QAction("Add Component...", "actionAdd_Component")
    entries = objects["bar"]._entries[0]._menu._entries
    entries[entries.index(objects["add"])] = replacement
    assert host.actions["Glyph > Add Component"].qaction is replacement
    assert host.actions["actionAdd_Component"].qaction is replacement
    assert any(a.qaction is replacement for a in host.actions.values())


def test_names_when_visibility_changes_then_same_action_keeps_its_name(world):
    host, _, _, objects = world
    before = {n: a.code for n, a in host.menu.glyph.items().items() if "flatten" in n}
    paths = {k: a.code for k, a in host.actions.items() if "Flatten" in k}
    objects["flatten"].visible, objects["flatten_fog"].visible = False, True
    assert {n: a.code for n, a in host.menu.glyph.items().items() if "flatten" in n} == before
    assert {k: a.code for k, a in host.actions.items() if "Flatten" in k} == paths
    assert before["flatten_glyph"] == "actionFlatten_Glyph"


def test_panel_when_no_visibility_mechanism_then_unsupported_not_retriggered():
    font_map = QAction("Font Map", "actionFont_Browser_Panel")
    bar = QMenu("", "", [submenu("&Window", "menuWindow", [font_map])])
    panel = Host(Main(bar, []), qaction_type=QAction, widgets=list, call=None).panels.font_map
    for operation in (lambda: panel.visible, panel.hide, panel.show, lambda: panel.set_visible(True)):
        with pytest.raises(UnsupportedOperation, match="Font Map"):
            operation()
    assert font_map.triggered == 0
    assert "unknown" in repr(panel)


def test_retained_panel_when_widget_created_later_then_seen():
    chat_action = QAction("&Chat", "actionChatPanel")
    widgets = []
    bar = QMenu("", "", [submenu("&Window", "menuWindow", [chat_action])])
    chat = Host(Main(bar, []), qaction_type=QAction, widgets=lambda: widgets, call=None).panels.chat
    assert chat.widget is None and not chat.visible
    widget = Widget("@chatpanel.ChatPanel", visible=True)
    widgets.append(widget)
    assert chat.widget is widget and chat.visible, "absence must not be cached"
    chat.show()
    assert chat_action.triggered == 0, "already visible"


def test_set_checked_when_exclusive_group_unchecks_then_refuses():
    radio = QAction("Do Not Apply", "actionItalicAngleNone", checkable=True, checked=True, group=Group(True))
    bar = QMenu("", "", [submenu("&View", "menuView", [radio])])
    action = Host(Main(bar, []), qaction_type=QAction, widgets=list, call=None).menu.view.do_not_apply
    with pytest.raises(ValueError, match="exclusive"):
        action.set_checked(False)
    assert radio.triggered == 0


def test_set_checked_when_state_does_not_change_then_raises():
    stuck = QAction("Stuck", "actionStuck", checkable=True)
    stuck.toggles = False
    bar = QMenu("", "", [submenu("&View", "menuView", [stuck])])
    action = Host(Main(bar, []), qaction_type=QAction, widgets=list, call=None).menu.view.stuck
    with pytest.raises(RuntimeError, match="still unchecked"):
        action.set_checked(True)


def test_menu_when_entry_named_like_api_then_suffixed_and_reachable():
    parts = QAction("Parts", "actionParts")
    path = QAction("Path", "actionPath")
    bar = QMenu("", "", [submenu("&View", "menuView", [parts, path])])
    view = Host(Main(bar, []), qaction_type=QAction, widgets=list, call=None).menu.view
    assert set(view.items()) == {"parts_", "path_"}
    assert view.parts_.qaction is parts and view.path_.qaction is path
    assert view.parts == ("View",)


def test_names_when_action_relabelled_then_name_stays_bound_and_label_is_alias(world):
    host, _, _, objects = world
    glyph = host.menu.glyph
    assert glyph.flatten_glyph.code == "actionFlatten_Glyph"
    objects["flatten"].text = "Flatten Selection"
    glyph = host.menu.glyph  # fresh Menu object, same Host
    assert glyph.flatten_glyph.code == "actionFlatten_Glyph", "a relabel must not retarget"
    assert glyph.fog_flatten_glyph.code == "actionFogFlatten_Glyph"
    assert glyph.flatten_selection.code == "actionFlatten_Glyph", "new label is an alias"
    assert "flatten_glyph" in dir(glyph)


def test_retained_panel_when_widget_replaced_then_decides_on_current_widget():
    chat_action = QAction("&Chat", "actionChatPanel")
    widgets = [Widget("@chatpanel.ChatPanel", visible=False)]
    bar = QMenu("", "", [submenu("&Window", "menuWindow", [chat_action])])
    chat = Host(Main(bar, []), qaction_type=QAction, widgets=lambda: widgets, call=None).panels.chat
    assert not chat.visible
    widgets[:] = [Widget("@chatpanel.ChatPanel", visible=True)]  # FontLab rebuilt the panel
    assert chat.visible, "stale cached widget"
    chat.show()
    assert chat_action.triggered == 0, "show() must not toggle the visible replacement off"


def _menu_with(*entries):
    bar = QMenu("", "", [submenu("&View", "menuView", list(entries))])
    return Host(Main(bar, []), qaction_type=QAction, widgets=list, call=None)


def test_alias_when_labels_swap_then_alias_keeps_first_target():
    a = QAction("Flatten Glyph", "actionFlatten_Glyph")
    b = QAction("Flatten Glyph", "actionFogFlatten_Glyph")
    host = _menu_with(a, b)
    a.text = "Flatten Selection"
    assert host.menu.view.flatten_selection.code == "actionFlatten_Glyph"
    a.text, b.text = "Flatten Current", "Flatten Selection"
    assert host.menu.view.flatten_selection.code == "actionFlatten_Glyph", "alias stolen"
    assert host.menu.view.flatten_current.code == "actionFlatten_Glyph"


def test_unnamed_siblings_with_identical_labels_all_named_and_indexed():
    entries = [QAction("Default") for _ in range(3)]
    host = _menu_with(*entries)
    items = host.menu.view.items()
    assert list(items) == ["default", "default_2", "default_3"]
    assert [items[n].qaction for n in items] == entries
    found = [host.actions[k].qaction for k in host.actions if k.startswith("View > Default")]
    assert found == entries, list(host.actions)


def test_names_when_random_relabels_then_no_handed_out_name_changes_target():
    import random

    rng = random.Random(104)
    labels = ["Flatten Glyph", "Flatten Selection", "Flatten Current", "Default", "Snap", "Import"]
    actions = [QAction(rng.choice(labels), name) for name in ("actionA", "actionB", "actionC", "", "")]
    host = _menu_with(*actions)
    first: dict[str, int] = {}
    for _ in range(300):
        rng.choice(actions).text = rng.choice(labels)
        view = host.menu.view
        names = set(dir(view)) | {snake(a.text) for a in actions}
        for name in names:
            try:
                target = getattr(view, name)
            except AttributeError:
                continue
            if not isinstance(target, Action):
                continue
            first.setdefault(name, id(target.qaction))
            assert first[name] == id(target.qaction), f"{name} retargeted"
