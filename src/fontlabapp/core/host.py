# this_file: src/fontlabapp/core/host.py
"""FontLab's menus, QActions, panels and glyph actions as a live Python tree.

Built on demand from the running host's English labels::

    from fly.ap import host
    host.menu.glyph.add_component()            # trigger a menu command
    host.actions["Glyph > Add Component"]      # same Action, by menu path
    host.actions["actionAdd_Component"]        # same Action, by Qt objectName
    host.menu.view.snap                         # <Menu 'View > Snap' (15 items)>
    host.panels.preview.show()                 # explicit visibility, never a toggle
    host.glyph_actions.remove_overlap(glyph_names=["B"])

Nothing is triggered by attribute access, ``dir()`` or ``repr()``. Names follow
``fontlabapp.core.menu_names``; the generated static shim uses the same rules. The tree
reads the menu bar live, so menus FontLab rebuilds (Script, Recent Fonts)
stay current.
"""

from __future__ import annotations

import difflib
from collections.abc import Iterator, Mapping
from typing import Any

from fontlabapp.qt.safe import qt_list
from fontlabapp.core.menu_names import assign_names, clean_label, object_slug, snake

SEPARATOR = " > "
MENU_API = frozenset()  # set after class Menu: every public Menu attribute

# Panel QAction objectName -> (Python name, native PanelId for showPanel, root widget
# status tip). Names are fixed here because FontLab relabels some panel actions with
# their state ("Preview" becomes "Hide Preview"). PanelIds come from flworkspace.h
# (see views._PANEL_IDS); None means no verified id.
PANELS: dict[str, tuple[str, int | None, str | None]] = {
    "actionPinsPanel": ("anchors_and_pins", 13, "@pinspanel.PinsPanel"),
    "actionPropertyPanel": ("brush", 14, "@brushproperties.BrushProperties"),
    "actionChatPanel": ("chat", None, "@chatpanel.ChatPanel"),
    "actionGroupsPanel": ("classes", 18, "@classespanel.ClassesPanel"),
    "actionColorsPanel": ("color", 2, "@colorpanel.ColorPanel"),
    "actionShapesPanel": ("elements", 1, "@shapespanel.ShapesPanel"),
    "actionFeaturesPanel": ("features", 19, "@featurespanel.FeaturesPanel"),
    "actionFont_Info_Panel": ("font_info", 12, "@fontinfopanel.FontInfoPanel"),
    "actionFont_Browser_Panel": ("font_map", None, None),
    "actionAuditPanel": ("fontaudit", 5, "@auditpanel.AuditPanel"),
    "actionFonts_Panel": ("fonts", 11, "@fontspanel.FontsPanel"),
    "actionGalleryPanel": ("gallery", 28, "@gallerypanel.GalleryPanel"),
    "actionGlyphPanel": ("glyph", 10, "@inspector_glyph.InspectorGlyph"),
    "actionGuidesPanel": ("guide", 16, "@inspector_guide.InspectorGuide"),
    "actionHistoryPanel": ("history", 8, "@historypanel.HistoryPanel"),
    "actionFiltersPanel": ("image", 25, "@filterpanel.FilterPanel"),
    "actionKerningPanel": ("kerning", 23, "@kerningpanel.KerningPanel"),
    "actionLayersPanel": ("layers_and_masters", 9, "@inspector_layers.InspectorLayers"),
    "actionLookupsPanel": ("lookups", 35, "@lookupspanel.LookupsPanel"),
    "actionMeasurePanel": ("measurements", 33, "@measurepanel.MeasurePanel"),
    "actionMetricsDataPanel": ("metrics", 24, "@metricsdatapanel.MetricsDataPanel"),
    "actionNodesPanel": ("node", 15, "@inspector_node.InspectorNode"),
    "actionOutputPanel": ("output", 22, "@outputpanel.OutputPanel"),
    "actionPairsPanel": ("pairs_and_phrases", 29, "@pairspanel.PairsPanel"),
    "actionPreviewPanel": ("preview", 21, "@previewpanel.PreviewPanel"),
    "actionPythonPanel": ("scripting", 20, "@pythonpanel.PythonPanel"),
    "actionSelectionsPanel": ("selections", 36, "@selectionspanel.SelectionsPanel"),
    "actionSourcePanel": ("source", 32, "@sourcepanel.SourcePanel"),
    "actionStrokePanel": ("stroke", 7, "@strokepanel.StrokePanel"),
    "actionSuperkerningPanel": ("superkerning", None, "@superkerningpanel.SuperkerningPanel"),
    "actionTablesPanel": ("tables", 34, "@tablespanel.TablesPanel"),
    "actionTransformPanel": ("transform", 4, "@paneltransform.PanelTransform"),
    "actionTTHPanel": ("tt_hinting", 27, "@tthpanel.TTHPanel"),
    "actionLocationPanel": ("variations", 26, "@locationpanel.LocationPanel"),
    "actionEditingLayersPanel": ("view", 3, "@editinglayerspanel.EditingLayersPanel"),
    "actionQuickTipsPanel": ("help", 31, "@quicktipspanel.QuickTipsPanel"),
    "actionToolbarPanel": ("toolbar", None, "@toolbarpanel.ToolbarPanel"),
    "actionPanelsPanel": ("panels_list", None, "@panelspanel.PanelsPanel"),
}


class UnsupportedOperation(RuntimeError):
    """FontLab offers no verified way to do this for this object."""


class ActionDisabledError(RuntimeError):
    """The QAction is disabled in the current context; triggering would do nothing."""


def _entry_key(qaction: Any) -> tuple[str, str, bool]:
    sub = qaction.menu()
    label = sub.title if sub is not None else qaction.text
    name = sub.objectName if sub is not None else qaction.objectName
    return label, name or "", bool(qaction.visible)


def _forms(text: str) -> set[str]:
    """Lower-case readings of a user-typed label: literal ``&`` and menu markup."""
    literal = clean_label(text.replace("&", "&&"))
    return {literal.lower(), clean_label(text).lower()}


def _aliases(child: Action | Menu) -> set[str]:
    """Context-free names for a child whose label FontLab changes with state.

    FontLab relabels some actions ("Print..." becomes "Print Preview...", "Preview"
    becomes "Hide Preview"); their objectName and tooltip stay put.
    """
    if isinstance(child, Menu):
        return {object_slug(child.qmenu.objectName)}
    tip = child.tooltip.split(": ", 1)[-1]
    return {object_slug(child.code), snake(tip.removesuffix(" panel").replace("&", "&&"))}


def _missing(kind: str, key: str, names: list[str]) -> str:
    near = difflib.get_close_matches(key, names, n=3)
    return f"{kind} has no {key!r}" + (f"; did you mean {', '.join(near)}?" if near else "")


class Action:
    """One QAction. Call it (or ``trigger()``) to run the command."""

    def __init__(self, qaction: Any, path: tuple[str, ...] = ()) -> None:
        self.qaction = qaction
        self.parts = path or (clean_label(qaction.text),)

    @property
    def label(self) -> str:
        return self.parts[-1]

    @property
    def path(self) -> str:
        return SEPARATOR.join(self.parts)

    @property
    def code(self) -> str:
        """Qt objectName, e.g. ``actionAdd_Component`` (stable across languages)."""
        return self.qaction.objectName

    @property
    def shortcut(self) -> str:
        return self.qaction.shortcut.toString()

    @property
    def tooltip(self) -> str:
        return self.qaction.toolTip

    @property
    def checkable(self) -> bool:
        return bool(self.qaction.checkable)

    @property
    def checked(self) -> bool:
        return bool(self.qaction.checked)

    @property
    def enabled(self) -> bool:
        return bool(self.qaction.enabled)

    @property
    def visible(self) -> bool:
        return bool(self.qaction.visible)

    def trigger(self) -> Action:
        """Run the command; a disabled action raises instead of silently doing nothing."""
        if not self.enabled:
            raise ActionDisabledError(f"{self.path} is disabled in the current context")
        self.qaction.trigger()
        return self

    __call__ = trigger

    def set_checked(self, checked: bool) -> Action:
        """Trigger a checkable action only when its state differs from ``checked``."""
        if not isinstance(checked, bool):
            raise TypeError("checked must be bool")
        if not self.checkable:
            raise TypeError(f"{self.path} is not checkable")
        if self.checked == checked:
            return self
        group = self.qaction.actionGroup()
        if not checked and group is not None and group.isExclusive():
            raise ValueError(f"{self.path} is in an exclusive group; check another option instead")
        self.trigger()
        if self.checked != checked:
            raise RuntimeError(f"{self.path} is still {'checked' if self.checked else 'unchecked'}")
        return self

    def __repr__(self) -> str:
        state = [self.shortcut] if self.shortcut else []
        if self.checkable:
            state.append("checked" if self.checked else "unchecked")
        if not self.enabled:
            state.append("disabled")
        return f"<Action {self.path!r}{' ' + ', '.join(state) if state else ''}>"


class Menu:
    """A QMenu whose entries are attributes named by ``fontlabapp.core.menu_names``."""

    def __init__(self, qmenu: Any, path: tuple[str, ...] = (), names: dict | None = None,
                 identity: tuple[str, ...] = ()) -> None:
        self.qmenu = qmenu
        self.parts = path
        # Name bindings shared by every Menu of one Host: {menu identity: {entry identity: name}}.
        self._names = {} if names is None else names
        self._identity = identity

    @property
    def title(self) -> str:
        return self.parts[-1] if self.parts else ""

    @property
    def path(self) -> str:
        return SEPARATOR.join(self.parts)

    def _qactions(self) -> list[Any]:
        return [a for a in self.qmenu.actions() if not a.isSeparator()]

    def _registry(self) -> dict:
        """This menu's bindings, shared by every Menu object of one Host.

        ``names``: every name ever handed out (primary or alias) -> identity;
        ``primary``: identity -> its primary name; ``keep``: QAction wrappers
        whose ``id()`` serves as identity, retained so the id is never reused.
        """
        return self._names.setdefault(self._identity, {"names": {}, "primary": {}, "keep": {}})

    def _ident(self, qaction: Any) -> str:
        """Identity of an entry: its (sub)menu or action objectName, else the QAction itself.

        PythonQt returns the same wrapper for a QAction while a reference is held,
        so an unnamed entry stays itself across relabels and among identical labels.
        """
        sub = qaction.menu()
        name = sub.objectName if sub is not None else qaction.objectName
        if name:
            return name
        keep = self._registry()["keep"]
        keep.setdefault(id(qaction), qaction)
        return f"object:{id(qaction)}"

    def _children(self) -> tuple[dict[str, Action | Menu], dict[str, Action | Menu]]:
        """(primary name -> child, identity -> child), live, in menu order.

        Every name, once handed out in a Host, stays bound to its first identity:
        an entry's primary name is bound at first discovery, and its current
        label's name is bound as an alias if still free. A later label that
        collides gets no alias; it never takes a bound name.
        """
        qactions = self._qactions()
        keys = [_entry_key(a) for a in qactions]
        proposals = assign_names(keys, reserved=MENU_API)
        registry = self._registry()
        names, primary = registry["names"], registry["primary"]
        children: dict[str, Action | Menu] = {}
        by_ident: dict[str, Action | Menu] = {}
        for proposal, qaction, (label, obj, _) in zip(proposals, qactions, keys):
            ident = self._ident(qaction)
            if ident not in primary:
                name = proposal
                if name in names:
                    name = object_slug(obj)
                    if not name or name in names or name in MENU_API:
                        n = 2
                        while f"{proposal}_{n}" in names:
                            n += 1
                        name = f"{proposal}_{n}"
                primary[ident] = name
                names[name] = ident
            names.setdefault(proposal, ident)  # alias for the current label, if free
            path = (*self.parts, clean_label(label))
            sub = qaction.menu()
            child = (Menu(sub, path, self._names, (*self._identity, ident)) if sub is not None
                     else Action(qaction, path))
            children[primary[ident]] = child
            by_ident[ident] = child
        return children, by_ident

    def items(self) -> dict[str, Action | Menu]:
        """Live ``name -> Action | Menu`` mapping in menu order."""
        return self._children()[0]

    def __getattr__(self, name: str) -> Action | Menu:
        if name.startswith("_") or name in ("qmenu", "parts"):
            raise AttributeError(name)
        children, by_ident = self._children()
        names = self._registry()["names"]
        if name in names:  # primary or alias, bound for the Host's life
            child = by_ident.get(names[name])
            if child is None:
                raise AttributeError(f"{name} belongs to an entry no longer in {self!r}")
            return child
        matches = [i for i, c in by_ident.items() if name in _aliases(c)]
        if len(matches) == 1:
            names[name] = matches[0]  # bind the objectName/tooltip alias too
            return by_ident[matches[0]]
        raise AttributeError(_missing(repr(self), name, list(children)))

    def __getitem__(self, key: str) -> Action | Menu:
        """Child by name or label, or a ``"Sub > Item"`` path below this menu."""
        head, _, rest = key.partition(">")
        head = head.strip()
        children = self.items()
        child = children.get(head)
        if child is None:
            forms = _forms(head)
            child = next((c for c in children.values() if (c.title if isinstance(c, Menu) else c.label).lower() in forms), None)
        if child is None:
            raise KeyError(_missing(repr(self), head, list(children)))
        if rest:
            if not isinstance(child, Menu):
                raise KeyError(f"{child.path} is not a menu")
            return child[rest]
        return child

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(self.items()))

    def __iter__(self) -> Iterator[Action | Menu]:
        return iter(self.items().values())

    def __len__(self) -> int:
        return len(self._qactions())

    def find(self, text: str) -> list[Action]:
        """Actions below this menu whose label contains ``text`` (case-insensitive)."""
        text = text.lower()
        found: list[Action] = []
        for child in self:
            if isinstance(child, Menu):
                found += child.find(text)
            elif text in child.label.lower():
                found.append(child)
        return found

    def __repr__(self) -> str:
        return f"<Menu {self.path or 'menu bar'!r} ({len(self)} items)>"


# Children named like Menu's own API get a trailing underscore ("Parts" -> parts_).
MENU_API = frozenset(n for n in dir(Menu) if not n.startswith("_")) | {"qmenu", "parts"}


class MenuBar(Menu):
    """The main window's menu bar; its menus are ``file``, ``edit``, ``glyph``..."""

    def _qactions(self) -> list[Any]:
        return [a for a in self.qmenu.actions() if a.menu() is not None]


class Actions(Mapping[str, Action]):
    """Every menu QAction by ``"Menu > Item"`` path, plus main-window QActions.

    Keys are clean English paths; main-window QActions outside the menus are
    keyed by objectName. Lookup also accepts the Qt objectName
    (``actionAdd_Component``), a status-tip code (``@mainwindow.actionAdd_Component``)
    and paths with menu markup or different case. Keys are remembered, but each
    lookup resolves to the QAction that is in the menu *now*, so menus FontLab
    rebuilds (Script, Recent Fonts) never return a replaced action.
    """

    def __init__(self, menu: MenuBar, extra: Any = list) -> None:
        self._menu = menu
        self._extra = extra  # callable: current main-window QActions
        # key -> (menu path parts, objectName, main-window?, ordinal among same path+name)
        self._keys: dict[str, tuple[tuple[str, ...], str, bool, int]] | None = None

    def _build(self) -> dict[str, Action]:
        """Fresh index in one pass over the live menu bar and main window."""
        found: list[Action] = []

        def walk(menu: Menu) -> None:
            for child in menu:
                if isinstance(child, Menu):
                    walk(child)
                else:
                    found.append(child)

        walk(self._menu)

        # The same label path twice (e.g. a hidden variant): the action whose
        # objectName matches the label keeps the plain path (else the smallest
        # objectName); never decided by visibility. Others get "path (objectName)".
        def rank(i: int) -> tuple:
            code = found[i].code
            return (object_slug(code) != snake(found[i].label), not code, code, i)

        keyed: dict[str, int] = {}
        for i in sorted(range(len(found)), key=rank):
            path, code = found[i].path, found[i].code
            key = path if path not in keyed else f"{path} ({code})" if code else path
            n = 2
            while key in keyed:  # unnamed entries with identical paths: "path (#2)"
                key, n = f"{path} (#{n})", n + 1
            keyed[key] = i
        index = {key: found[i] for key, i in sorted(keyed.items(), key=lambda item: item[1])}
        seen: dict[tuple, int] = {}
        ordinal = {}
        for a in found:
            ordinal[id(a)] = seen.get((a.parts, a.code), 0)
            seen[(a.parts, a.code)] = ordinal[id(a)] + 1
        self._keys = {k: (a.parts, a.code, False, ordinal[id(a)]) for k, a in index.items()}
        known = {a.code for a in index.values() if a.code}
        for qaction in self._extra():
            if qaction.objectName and qaction.objectName not in known:
                index[qaction.objectName] = Action(qaction)
                self._keys[qaction.objectName] = ((), qaction.objectName, True, 0)
        return index

    def _resolve(self, key: str) -> Action | None:
        """The action now at a remembered key, or None if it moved or vanished."""
        if self._keys is None or key not in self._keys:
            return None
        parts, code, main_window, nth = self._keys[key]
        if main_window:
            return next((Action(q) for q in self._extra() if q.objectName == code), None)
        menu: Menu = self._menu
        for title in parts[:-1]:
            menu = next((c for c in menu if isinstance(c, Menu) and c.title == title), None)
            if menu is None:
                return None
        same = [c for c in menu if isinstance(c, Action) and c.label == parts[-1] and c.code == code]
        return same[nth] if nth < len(same) else None

    def __getitem__(self, key: str) -> Action:
        found = self._resolve(key)
        if found is not None:
            return found
        index = self._build()
        if key in index:
            return index[key]
        code = key.rsplit(".", 1)[-1] if key.startswith("@") else key
        parts = [_forms(p) for p in key.split(">")]
        for action in index.values():
            if action.code == code or (
                len(parts) == len(action.parts)
                and all(p.lower() in f for p, f in zip(action.parts, parts))
            ):
                return action
        raise KeyError(_missing("FontLab actions", key, list(index)))

    def values(self):  # one pass instead of a lookup per key
        return self._build().values()

    def items(self):
        return self._build().items()

    def __iter__(self) -> Iterator[str]:
        return iter(self._build())

    def __len__(self) -> int:
        return len(self._build())

    def search(self, text: str) -> list[Action]:
        """Actions whose path, objectName or tooltip contains ``text``."""
        text = text.lower()
        return [
            a
            for a in self._build().values()
            if text in a.path.lower() or text in a.code.lower() or text in a.tooltip.lower()
        ]

    def __repr__(self) -> str:
        return f"<Actions ({len(self)} QActions)>"


class _WidgetFinder:
    """Panel root widgets by status tip, from a fresh ``allWidgets()`` scan.

    Nothing is cached: FontLab creates, deletes and rebuilds panel widgets, so
    every visibility decision looks at the widget that exists now.
    """

    def __init__(self, widgets: Any) -> None:
        self._widgets = widgets

    def __call__(self, tip: str) -> Any:
        return next((w for w in self._widgets() if w.statusTip == tip), None)


class Panel:
    """A FontLab panel, shown and hidden explicitly (never toggled blindly)."""

    def __init__(self, action: Action, main: Any, widgets: Any) -> None:
        self.action = action
        self._main = main
        self._widgets = widgets  # callable: status tip -> widget or None
        self.name, self.panel_id, self._tip = PANELS[action.code]

    @property
    def label(self) -> str:
        """Human name, e.g. ``"Anchors & Pins"`` (from the panel action's tooltip)."""
        tip = self.action.tooltip
        return tip.removesuffix(" panel") if tip.endswith(" panel") else self.action.label

    @property
    def widget(self) -> Any:
        """The panel's root widget, or None while FontLab has not created it."""
        return None if self._tip is None else self._widgets(self._tip)

    @property
    def supported(self) -> bool:
        """Whether FontLab offers a verified way to read or set this panel's visibility."""
        return self.panel_id is not None or self.action.checkable or self._tip is not None

    def _require(self) -> None:
        if not self.supported:
            raise UnsupportedOperation(
                f"{self.label} panel: FontLab exposes no panel id, widget or checked state "
                f"to read or set its visibility; use the menu ({self.action.path})"
            )

    @property
    def visible(self) -> bool:
        self._require()
        if self.action.checkable:
            return self.action.checked
        widget = self.widget
        return bool(widget is not None and widget.isVisible())

    def set_visible(self, visible: bool) -> Panel:
        if not isinstance(visible, bool):
            raise TypeError("Panel visibility must be bool")
        self._require()
        if self.panel_id is not None:
            self._main.showPanel(self.panel_id, visible)
        elif self.action.checkable:
            self.action.set_checked(visible)
        elif self.visible != visible:  # decided on the widget that exists now
            self.action.trigger()
        return self

    def show(self) -> Panel:
        return self.set_visible(True)

    def hide(self) -> Panel:
        return self.set_visible(False)

    def focus(self) -> Panel:
        self.show()
        widget = self.widget
        if widget is not None:
            widget.raise_()
        return self

    def __repr__(self) -> str:
        if not self.supported:
            return f"<Panel {self.label!r} visibility unknown>"
        return f"<Panel {self.label!r} {'visible' if self.visible else 'hidden'}>"


class Panels:
    """Panels from Window > Panels plus the Help, Toolbar and Panels List panels."""

    def __init__(self, actions: Actions, main: Any, widgets: Any) -> None:
        self._actions, self._main, self._widgets = actions, main, widgets

    def items(self) -> dict[str, Panel]:
        index = self._actions._build()
        # A QAction may sit in several menus; one Panel per objectName.
        found = list({a.code: a for a in reversed(index.values()) if a.code in PANELS}.values())[::-1]
        widget = _WidgetFinder(self._widgets)
        panels = [Panel(a, self._main, widget) for a in found]
        return {p.name: p for p in sorted(panels, key=lambda p: p.name)}

    def __getattr__(self, name: str) -> Panel:
        if name.startswith("_"):
            raise AttributeError(name)
        items = self.items()
        if name in items:
            return items[name]
        raise AttributeError(_missing("<Panels>", name, list(items)))

    def __getitem__(self, name: str) -> Panel:
        """Panel by name or label (``"Anchors & Pins"``)."""
        items = self.items()
        if name in items:
            return items[name]
        forms = _forms(name)
        for panel in items.values():
            if panel.label.lower() in forms:
                return panel
        raise KeyError(_missing("<Panels>", name, list(items)))

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(self.items()))

    def __iter__(self) -> Iterator[Panel]:
        return iter(self.items().values())

    def __repr__(self) -> str:
        return f"<Panels ({len(self.items())})>"


class GlyphAction:
    """One Tools > Actions entry, run through fontpr ``run_actions``."""

    def __init__(self, action_id: str, label: str, call: Any) -> None:
        self.id, self.label, self._call = action_id, label, call

    def __call__(
        self,
        glyph_names: list[str] | None = None,
        *,
        layer_mode: str | None = None,
        font_id: int | None = None,
        font_name: str | None = None,
        undo: bool | None = None,
        **parameters: Any,
    ) -> Any:
        """Apply to ``glyph_names`` (default: the selection); returns native JSON."""
        options = {
            "glyph_names": glyph_names,
            "layer_mode": layer_mode,
            "font_id": font_id,
            "font_name": font_name,
            "undo": undo,
        }
        arguments = {k: v for k, v in options.items() if v is not None}
        return self._call("run_actions", actions=[{"id": self.id, **parameters}], **arguments)

    def __repr__(self) -> str:
        return f"<GlyphAction {self.id!r} ({self.label})>"


class GlyphActions:
    """FontLab's Tools > Actions catalogue (``fontpr.list_actions``) by id."""

    def __init__(self, call: Any) -> None:
        self._call = call
        self._cache: dict[str, GlyphAction] | None = None

    def items(self) -> dict[str, GlyphAction]:
        if self._cache is None:
            catalogue = self._call("list_actions")["actions"]
            self._cache = {
                a["id"]: GlyphAction(a["id"], a.get("label", a["id"]), self._call)
                for a in catalogue
            }
        return self._cache

    def __getattr__(self, name: str) -> GlyphAction:
        if name.startswith("_"):
            raise AttributeError(name)
        items = self.items()
        if name in items:
            return items[name]
        raise AttributeError(_missing("<GlyphActions>", name, list(items)))

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(self.items()))

    def __iter__(self) -> Iterator[GlyphAction]:
        return iter(self.items().values())

    def __repr__(self) -> str:
        return f"<GlyphActions ({len(self.items())})>"


class Host:
    """The tree for one main window; ``fontlabapp.core.host.menu`` etc. use the live one."""

    def __init__(self, main: Any, qaction_type: Any = None, widgets: Any = None, call: Any = None) -> None:
        if qaction_type is None:
            from fontlabapp import _native

            qaction_type = _native("PythonQt").QtGui.QAction
        if widgets is None:
            def widgets() -> list[Any]:
                from fontlabapp import _native

                return qt_list(_native("PythonQt").QtGui.QApplication.instance().allWidgets)
        if call is None:
            def call(name: str, **arguments: Any) -> Any:
                from fontlabapp import _native

                return _native("fontpr").call(name, **arguments)
        self.main = main
        self.menu = MenuBar(main.menuBar(), names={})
        self.actions = Actions(
            self.menu, lambda: [c for c in main.children() if isinstance(c, qaction_type)]
        )
        self.panels = Panels(self.actions, main, widgets)
        self.glyph_actions = GlyphActions(call)

    def __repr__(self) -> str:
        return f"<FontLab host: {self.menu!r}, {self.actions!r}>"


_live: Host | None = None


def live() -> Host:
    """The tree for FontLab's running main window (created once per session)."""
    global _live
    if _live is None:
        from fontlabapp import _native

        _live = Host(_native("fontlab").flWorkspace.instance().mainWindow)
    return _live


def __getattr__(name: str) -> Any:
    if name in ("menu", "actions", "panels", "glyph_actions"):
        return getattr(live(), name)
    raise AttributeError(name)
