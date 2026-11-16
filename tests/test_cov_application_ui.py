# this_file: tests/test_cov_application_ui.py
"""Coverage for ``fontlabapp.core.application.ui``: widget, menu, action and window lookups.

The module imports ``PythonQt`` at import time, so each test loads a private copy
of it against a fake ``PythonQt`` whose ``QMenu``/``QAction`` are plain classes.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from fontlabapp.core.utils import attribdict

MODULE = "fontlabapp.core.application.ui"


class FakeAction:
    """Stand-in for QAction: ``text`` is an attribute, the rest are methods."""

    def __init__(
        self,
        text: str,
        *,
        visible: bool = True,
        separator: bool = False,
        menu: Any = None,
    ) -> None:
        self.text = text
        self._visible, self._separator, self._menu = visible, separator, menu
        self.trigger = lambda: f"triggered {text}"

    def isVisible(self) -> bool:
        return self._visible

    def isSeparator(self) -> bool:
        return self._separator

    def menu(self) -> Any:
        return self._menu


class FakeMenu:
    """Stand-in for QMenu: ``title`` is an attribute, ``actions()`` a method."""

    def __init__(self, title: str, actions: list[FakeAction] | None = None) -> None:
        self.title = title
        self._actions = actions or []

    def actions(self) -> list[FakeAction]:
        return self._actions


class FakeWidget:
    """Widget with a ``statusTip`` attribute, as used by ``buildWidgetsDict``."""

    def __init__(self, status_tip: str) -> None:
        self.statusTip = status_tip


class ClassedWidget:
    """Widget answering ``className()`` plus optional title and children."""

    def __init__(self, name: str, title: str = "", children: list[Any] | None = None) -> None:
        self._name, self.windowTitle, self._children = name, title, children or []

    def className(self) -> str:
        return self._name

    def children(self) -> list[Any]:
        return self._children


@pytest.fixture
def ui_module(monkeypatch: pytest.MonkeyPatch):
    """Import a private copy of the module against a fake PythonQt."""
    qt = ModuleType("PythonQt")
    qt.QtGui = SimpleNamespace(QMenu=FakeMenu, QAction=FakeAction)
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    monkeypatch.delitem(sys.modules, MODULE, raising=False)
    module = importlib.import_module(MODULE)
    yield module
    sys.modules.pop(MODULE, None)


@pytest.fixture
def ui(ui_module: Any):
    """An ``ApplicationUI`` whose constructor never ran."""
    return ui_module.ApplicationUI.__new__(ui_module.ApplicationUI)


def test_init_when_given_app_then_copies_services_and_loads_ui_once(
    ui_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The constructor mirrors the app services and then calls ``loadUI``."""
    calls: list[str] = []
    monkeypatch.setattr(ui_module.ApplicationUI, "loadUI", lambda self: calls.append("load"))
    app = SimpleNamespace(
        ws="ws", main="main", qmenus="qmenus", item="item", qapp="qapp", pref="pref", paths="paths"
    )
    result = ui_module.ApplicationUI(app)
    assert calls == ["load"], f"loadUI must run exactly once, ran {calls}"
    assert (result.app, result.ws, result.main, result.qmenus) == (
        app,
        "ws",
        "main",
        "qmenus",
    ), "app, ws, main and qmenus are copied from the app"
    assert (result.item, result.qapp, result.pref, result.paths) == (
        "item",
        "qapp",
        "pref",
        "paths",
    ), "item, qapp, pref and paths are copied from the app"


def test_loadui_when_called_then_builds_in_dependency_order(
    ui: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Widgets come first, panels next, then actions, the menu and the panel wiring."""
    order: list[str] = []

    def step(name: str, value: str):
        def run(*args: Any) -> str:
            order.append(name)
            return value

        return run

    for name, value in (
        ("buildWidgetsDict", "W"),
        ("buildPanels", "P"),
        ("getActions", "A"),
        ("buildMainMenu", "M"),
        ("updatePanels", "U"),
    ):
        monkeypatch.setattr(type(ui), name, step(name, value))
    ui.loadUI()
    assert order == [
        "buildWidgetsDict",
        "buildPanels",
        "getActions",
        "buildMainMenu",
        "updatePanels",
    ], "build steps must run in dependency order"
    assert (ui.widgets, ui.panels, ui.actions, ui.menu) == (
        "W",
        "P",
        "A",
        "M",
    ), "each step result is stored on the matching attribute"


def test_build_widgets_dict_when_status_tips_vary_then_only_group_subgroup_tips_are_kept(
    ui: Any,
) -> None:
    """Only ``@group.subgroup`` tips register; other tips and empty ones are ignored."""
    keep_a, keep_b, keep_c = FakeWidget("@pins.Panel"), FakeWidget("@pins.Other"), FakeWidget("@brush.Panel")
    skipped = [
        FakeWidget(""),
        FakeWidget("plain tip"),
        FakeWidget("@toomany.a.b"),
        FakeWidget("@single"),
    ]
    ui.qapp = SimpleNamespace(allWidgets=lambda: [keep_a, *skipped, keep_b, keep_c])
    widgets = ui.buildWidgetsDict()
    assert sorted(widgets.keys()) == ["brush", "pins"], f"unexpected groups: {sorted(widgets.keys())}"
    assert widgets["pins"]["Panel"] is keep_a, "first pins tip registers under its subgroup"
    assert widgets["pins"]["Other"] is keep_b, "second pins tip shares the pins group"
    assert widgets["brush"]["Panel"] is keep_c, "brush tip registers under its own group"


def test_build_widgets_dict_when_no_widgets_then_returns_empty_dict(ui: Any) -> None:
    """An application without widgets yields an empty mapping."""
    ui.qapp = SimpleNamespace(allWidgets=lambda: [])
    assert len(ui.buildWidgetsDict()) == 0, "no widgets must give no groups"


def test_find_widgets_when_top_level_and_class_name_then_filters_by_class(ui: Any) -> None:
    """Top-level widgets are filtered by ``className()``."""
    frame, other = ClassedWidget("YFrameWindow"), ClassedWidget("Other")
    parent = SimpleNamespace(topLevelWidgets=lambda: [frame, other])
    assert ui.findWidgets(parent, "YFrameWindow") == [frame], "only the matching class may remain"


def test_find_widgets_when_top_level_without_class_name_then_returns_all(ui: Any) -> None:
    """Without a class name every top-level widget is returned."""
    one, two = ClassedWidget("A"), ClassedWidget("B")
    parent = SimpleNamespace(topLevelWidgets=lambda: [one, two])
    assert ui.findWidgets(parent) == [one, two], "no class filter keeps every top-level widget"


def test_find_widgets_when_class_name_and_find_children_then_appends_children_matches(ui: Any) -> None:
    """``findChildren`` results are appended after the top-level matches."""
    top, child = ClassedWidget("Target"), ClassedWidget("Target")
    parent = SimpleNamespace(
        topLevelWidgets=lambda: [top],
        findChildren=lambda name: [child],
    )
    assert ui.findWidgets(parent, "Target") == [top, child], "child matches follow the top-level ones"


def test_find_widgets_when_only_children_and_class_name_then_filters_children(ui: Any) -> None:
    """A parent without ``findChildren`` falls back to ``children()`` with a class filter."""
    wanted, unwanted = ClassedWidget("Wanted"), ClassedWidget("Unwanted")
    parent = SimpleNamespace(children=lambda: [wanted, unwanted])
    assert ui.findWidgets(parent, "Wanted") == [wanted], "children are filtered by class name"


def test_find_widgets_when_only_children_and_no_class_name_then_returns_all_children(ui: Any) -> None:
    """Without a class filter every child is returned."""
    kids = [ClassedWidget("A"), ClassedWidget("B")]
    assert ui.findWidgets(SimpleNamespace(children=lambda: kids)) == kids, "no filter keeps all children"


def test_find_widgets_when_nothing_to_enumerate_then_returns_empty_list(ui: Any) -> None:
    """An object with no enumeration API yields an empty list."""
    assert ui.findWidgets(SimpleNamespace(), "X") == [], "no enumeration API with a class name gives nothing"
    assert ui.findWidgets(SimpleNamespace()) == [], "no enumeration API without a class name gives nothing"


def test_make_entries_when_given_qt_objects_then_wrap_them(ui: Any) -> None:
    """Menu and action entries expose the Qt object and, for actions, its trigger."""
    menu, action = FakeMenu("File"), FakeAction("Open")
    assert ui.makeMenuEntry(menu).qmenu is menu, "menu entry exposes the Qt menu"
    entry = ui.makeActionEntry(action)
    assert entry.qaction is action, "action entry exposes the Qt action"
    assert entry.trigger is action.trigger, "action entry exposes the action's trigger"


def test_recurse_menu_when_mixed_actions_then_skips_hidden_and_separators_and_nests_submenus(
    ui: Any,
) -> None:
    """Hidden actions and separators vanish; submenus recurse; plain actions get entries."""
    sub_open = FakeAction("Open Recent File")
    submenu = FakeMenu("Recent", [sub_open])
    plain = FakeAction("New Font")
    menu = FakeMenu(
        "File",
        [
            plain,
            FakeAction("Hidden", visible=False),
            FakeAction("---", separator=True),
            FakeAction("Recent", menu=submenu),
        ],
    )
    result = ui.recurseMenu(menu, ui.makeMenuEntry(menu))
    assert result.qmenu is menu, "the root entry keeps the menu"
    assert result["new_font"].qaction is plain, f"keys: {sorted(result.keys())}"
    assert "hidden" not in result.keys(), "hidden actions are skipped"
    assert "---" not in result.keys(), "separators are skipped"
    assert result["recent"].qmenu is submenu, "an action with a menu becomes a nested menu entry"
    assert result["recent"]["open_recent_file"].qaction is sub_open, "nested actions are slugged"


def test_build_main_menu_when_children_mixed_then_only_menus_are_listed(ui: Any) -> None:
    """Non-menu children of the menu bar are ignored; menu titles become slugs."""
    action = FakeAction("Save As")
    menu = FakeMenu("File Menu", [action])
    ui.qmenus = SimpleNamespace(children=lambda: [object(), menu])
    result = ui.buildMainMenu()
    assert list(result.keys()) == ["file_menu"], f"unexpected menus: {list(result.keys())}"
    assert result["file_menu"]["save_as"].qaction is action, "menu actions are reachable by slug"


def test_get_actions_when_no_panel_name_then_reads_main_window_actions(ui: Any) -> None:
    """Visible, named QActions of the main window become entries; menus recurse."""
    leaf = FakeAction("Undo")
    sub = FakeMenu("Sub", [FakeAction("Inner")])
    with_menu = FakeAction("Edit", menu=sub)
    ui.main = SimpleNamespace(
        children=lambda: [
            leaf,
            FakeAction("Hidden", visible=False),
            FakeAction("", visible=True),
            with_menu,
            object(),
        ]
    )
    actions = ui.getActions()
    assert sorted(actions.keys()) == ["edit", "undo"], f"unexpected: {sorted(actions.keys())}"
    assert actions["undo"].qaction is leaf, "visible named action becomes an entry"
    assert actions["edit"].qmenu is sub, "an action with a menu keeps that menu"
    assert "inner" in actions["edit"].keys(), "the submenu is recursed"


def test_get_actions_when_panel_name_then_reads_that_panels_widget(ui: Any) -> None:
    """With a panel name the panel widget's children are scanned instead of main."""
    action = FakeAction("Reset")
    ui.main = SimpleNamespace(children=lambda: [FakeAction("Wrong")])
    ui.panels = attribdict([("brush", attribdict([("widget", SimpleNamespace(children=lambda: [action]))]))])
    actions = ui.getActions("brush")
    assert list(actions.keys()) == ["reset"], "only the panel's actions are listed"
    assert actions["reset"].qaction is action, "the panel action is wrapped"


def test_get_actions_when_widget_missing_then_returns_empty_mapping(ui: Any) -> None:
    """A missing main window or panel widget gives an empty mapping."""
    ui.main = None
    assert len(ui.getActions()) == 0, "no main window means no actions"
    ui.panels = attribdict([("brush", attribdict([("widget", None)]))])
    assert len(ui.getActions("brush")) == 0, "no panel widget means no actions"


def _frame(windows: list[ClassedWidget]) -> ClassedWidget:
    stacked = SimpleNamespace(children=lambda: windows)
    inner = SimpleNamespace(qt_tabwidget_stackedwidget=stacked)
    return ClassedWidget("YFrameWindow", children=[inner])


def test_get_windows_by_class_when_titles_repeat_then_later_ones_get_frame_index(ui: Any) -> None:
    """Windows of the requested class are keyed by title; a repeated title gains ``" <n>"``."""
    first = ClassedWidget("FontWindow", "Roman")
    second = ClassedWidget("FontWindow", "Roman")
    glyph = ClassedWidget("GlyphWindow", "A")
    ui.qapp = SimpleNamespace(
        topLevelWidgets=lambda: [_frame([first, glyph]), _frame([second]), ClassedWidget("Other")]
    )
    fonts = ui.getWindowsByClass("FontWindow")
    assert fonts["Roman"] is first and fonts["Roman 1"] is second, f"keys: {list(fonts.keys())}"
    assert "A" not in fonts.keys(), "windows of another class must be excluded"


def test_font_and_glyph_windows_when_called_then_select_their_window_class(
    ui: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``fontWindows`` and ``glyphWindows`` delegate with their class names."""
    seen: list[str] = []
    monkeypatch.setattr(type(ui), "getWindowsByClass", lambda self, name: seen.append(name) or name)
    assert ui.fontWindows() == "FontWindow", "fontWindows returns the FontWindow lookup"
    assert ui.glyphWindows() == "GlyphWindow", "glyphWindows returns the GlyphWindow lookup"
    assert seen == ["FontWindow", "GlyphWindow"], "each helper delegates with its own class name"


def test_get_windows_by_class_when_no_frames_then_returns_empty_mapping(ui: Any) -> None:
    """No frame windows means no windows."""
    ui.qapp = SimpleNamespace(topLevelWidgets=lambda: [])
    assert len(ui.getWindowsByClass("FontWindow")) == 0, "no frame windows means no windows"
