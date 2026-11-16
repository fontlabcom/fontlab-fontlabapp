# this_file: src/fontlabapp/core/shimgen.py
"""Generate the static ``fontlabapp_shim`` package (tiny ``__init__.py`` + typed ``__init__.pyi``) from a UI capture.

The capture (``capture.json``) is a read-only snapshot of FontLab's menu bar,
main-window QActions and Tools > Actions catalogue. It is replayed through
``fontlabapp.core.host.Host`` itself, so the shim's names, paths and panels are the
ones the live tree produces. Output is deterministic for a given capture.

    python -m fontlabapp.core.shimgen generated/fontlabapp_shim/capture.json \
        generated/fontlabapp_shim
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fontlabapp.core.host import Action, Host, Menu

DEST = "generated/fontlabapp_shim/"
GENERATOR_VERSION = "2"  # issue 205: canonical domain imports; bump when output changes
API = '''
class Action:
    """One FontLab QAction. Call it (or ``trigger()``) to run the command.

    Attribute access, ``dir()`` and ``repr()`` never trigger. A disabled action
    raises ``ActionDisabledError`` instead of silently doing nothing.
    """
    qaction: Any
    @property
    def label(self) -> str: ...
    @property
    def path(self) -> str:
        """Menu path such as ``"Glyph > Add Component"``."""
    @property
    def code(self) -> str:
        """Qt objectName such as ``actionAdd_Component``; stable across UI languages."""
    @property
    def shortcut(self) -> str: ...
    @property
    def tooltip(self) -> str: ...
    @property
    def checkable(self) -> bool: ...
    @property
    def checked(self) -> bool: ...
    @property
    def enabled(self) -> bool: ...
    @property
    def visible(self) -> bool: ...
    def trigger(self) -> Action: ...
    def __call__(self) -> Action: ...
    def set_checked(self, checked: bool) -> Action:
        """Trigger a checkable action only when its state differs from ``checked``."""

class ActionDisabledError(RuntimeError):
    """The QAction is disabled in the current context."""

class Menu:
    """A FontLab menu; entries are attributes named from their English labels."""
    qmenu: Any
    @property
    def title(self) -> str: ...
    @property
    def path(self) -> str: ...
    def items(self) -> dict[str, Action | Menu]: ...
    def find(self, text: str) -> list[Action]:
        """Actions below this menu whose label contains ``text``."""
    def __getitem__(self, key: str) -> Action | Menu:
        """Child by name or label, or a ``"Sub > Item"`` path below this menu."""
    def __iter__(self) -> Iterator[Action | Menu]: ...
    def __len__(self) -> int: ...

class Panel:
    """A FontLab panel, shown and hidden explicitly (never toggled blindly)."""
    action: Action
    panel_id: int | None
    @property
    def label(self) -> str: ...
    @property
    def widget(self) -> Any:
        """The panel's root widget, or None while FontLab has not created it."""
    @property
    def visible(self) -> bool: ...
    def set_visible(self, visible: bool) -> Panel: ...
    def show(self) -> Panel: ...
    def hide(self) -> Panel: ...
    def focus(self) -> Panel: ...

class GlyphAction:
    """One Tools > Actions entry, run through fontpr ``run_actions``."""
    id: str
    label: str
    def __call__(self, glyph_names: list[str] | None = None, *, layer_mode: str | None = None,
                 font_id: int | None = None, font_name: str | None = None, undo: bool | None = None,
                 **parameters: Any) -> Any:
        """Apply to ``glyph_names`` (default: the selection); returns native JSON.

        ``layer_mode`` is ``"active"`` (default), ``"visible"`` or ``"masters"``;
        extra keyword arguments are the action's own parameters.
        """
'''


class _Keys:
    def __init__(self, text: str) -> None:
        self.text = text

    def toString(self) -> str:
        return self.text


class _ReplayAction:
    """Captured QAction stand-in with the attributes ``fontlabapp.core.host`` reads."""

    def __init__(self, record: dict[str, Any], menu: Any = None) -> None:
        self.text = record.get("text", "")
        self.objectName = record.get("objectName", "")
        self.statusTip = record.get("statusTip", "")
        self.toolTip = record.get("toolTip", self.text.replace("&", ""))
        self.shortcut = _Keys(record.get("shortcut", ""))
        self.checkable = record.get("checkable", False)
        self.checked = record.get("checked", False)
        self.enabled = record.get("enabled", True)
        self.visible = record.get("visible", True)
        self.dynamic = record.get("dynamic", False)
        self._menu = menu

    def menu(self) -> Any:
        return self._menu

    def isSeparator(self) -> bool:
        return False


class _ReplayMenu:
    def __init__(self, node: dict[str, Any]) -> None:
        self.title = node.get("title", "")
        self.objectName = node.get("objectName", "")
        self.dynamic = node.get("dynamic", False)
        self._actions = [
            _ReplayAction(e, _ReplayMenu(e)) if "entries" in e else _ReplayAction(e)
            for e in node.get("entries", [])
        ]

    def actions(self) -> list[_ReplayAction]:
        return self._actions


class _ReplayMain:
    def __init__(self, capture: dict[str, Any]) -> None:
        bar = {"entries": capture["menus"]}
        self._bar = _ReplayMenu(bar)
        self._children = [_ReplayAction(a) for a in capture["actions"]]

    def menuBar(self) -> _ReplayMenu:
        return self._bar

    def children(self) -> list[_ReplayAction]:
        return self._children


def replay(capture: dict[str, Any]) -> Host:
    """A ``Host`` over the captured UI (never touches FontLab)."""

    def call(name: str, **arguments: Any) -> Any:
        if name != "list_actions":
            raise RuntimeError("replayed capture cannot run actions")
        return capture["catalogue"]

    return Host(_ReplayMain(capture), qaction_type=_ReplayAction, widgets=list, call=call)


def _doc(text: str, indent: str = "    ") -> str:
    text = text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return f'{indent}"""{text}"""\n'


def _action_doc(action: Action) -> str:
    parts = [action.path + "."]
    if action.shortcut:
        parts.append(f"Shortcut: {action.shortcut}.")
    if action.code:
        parts.append(f"objectName ``{action.code}``.")
    tip = action.tooltip
    if tip and tip.replace("&", "") not in (action.label, action.qaction.text.replace("&", "")):
        parts.append(f"Tooltip: {tip}.")
    if action.checkable:
        parts.append("Checkable: use ``.checked`` / ``.set_checked(bool)``.")
    if not action.visible:
        parts.append("Hidden in the captured session.")
    return " ".join(parts)


def _class_name(parts: list[str], used: set[str]) -> str:
    base = "".join(p.strip("_").title().replace("_", "") for p in parts) + "Menu"
    name, n = base, 2
    while name in used:
        name, n = f"{base}{n}", n + 1
    used.add(name)
    return name


def generate_pyi(capture: dict[str, Any], dest: str = DEST) -> str:
    host = replay(capture)
    meta = capture["host"]
    classes: list[str] = []
    used: set[str] = {"Menu", "MenuBar"}

    def emit(menu: Menu, names: list[str], class_name: str, base: str = "Menu") -> None:
        body: list[str] = []
        children = menu.items()
        for name, child in children.items():
            if isinstance(child, Menu):
                sub = _class_name([*names, name], used)
                emit(child, [*names, name], sub)
                body.append(f"    {name}: {sub}\n")
                body.append(_doc(f"{child.path} menu (objectName ``{child.qmenu.objectName}``)."))
            else:
                body.append(f"    {name}: Action\n")
                body.append(_doc(_action_doc(child)))
        title = menu.path or "Menu bar"
        doc = f"{title}: ``fontlabapp.menu{''.join('.' + n for n in names)}``."
        if getattr(menu.qmenu, "dynamic", False):
            doc += (" FontLab fills this menu at run time (recent files, windows or the"
                    " user's scripts); its entries are not listed here.")
            body.append("    def __getattr__(self, name: str) -> Action | Menu: ...\n")
        classes.append(f"class {class_name}({base}):\n" + _doc(doc) + "".join(body))

    emit(host.menu, [], "MenuBar")

    paths = list(host.actions)
    literal = "".join(f"    {json.dumps(p, ensure_ascii=False)},\n" for p in paths)
    actions = (
        "ActionPath = Literal[\n" + literal + "]\n\n"
        "class Actions(Mapping[str, Action]):\n"
        + _doc("Every menu QAction by ``\"Menu > Item\"`` path, plus main-window QActions by objectName.\n\n"
               "    Lookup also accepts objectNames, ``@mainwindow.`` status-tip codes and paths with menu markup.")
        + "    def __getitem__(self, key: ActionPath | str) -> Action: ...\n"
        "    def __iter__(self) -> Iterator[str]: ...\n"
        "    def __len__(self) -> int: ...\n"
        "    def search(self, text: str) -> list[Action]:\n"
        + _doc("Actions whose path, objectName or tooltip contains ``text``.", "        ")
    )

    panel_lines = []
    for name, panel in host.panels.items().items():
        how = f"PanelId {panel.panel_id}" if panel.panel_id is not None else "shown via its menu action"
        shortcut = f", {panel.action.shortcut}" if panel.action.shortcut else ""
        panel_lines.append(f"    {name}: Panel\n" + _doc(f"{panel.label} panel ({panel.action.path}{shortcut}; {how})."))
    panels = "class Panels:\n" + _doc("FontLab panels: ``fontlabapp.panels.preview.show()``.") + "".join(panel_lines)
    panels += "    def items(self) -> dict[str, Panel]: ...\n    def __getitem__(self, name: str) -> Panel: ...\n"

    glyph_lines = [
        f"    {a.id}: GlyphAction\n" + _doc(f"Tools > Actions: {a.label}.")
        for a in host.glyph_actions.items().values()
    ]
    glyph = "class GlyphActions:\n" + _doc(
        "FontLab's Tools > Actions catalogue: ``fontlabapp.glyph_actions.remove_overlap([\"B\"])``."
    ) + "".join(glyph_lines) + "    def items(self) -> dict[str, GlyphAction]: ...\n"

    header = (
        f"# this_file: {dest}__init__.pyi\n"
        f"# Generated by `python -m fontlabapp.core.shimgen` from a read-only capture of "
        f"{meta['app']} {meta['app_version']} ({meta['locale']} UI, {capture['captured']}). Do not edit.\n"
        '"""FontLab menus, QActions, panels and Tools > Actions as a typed Python tree.\n\n'
        "The live objects come from ``fontlabapp.core.host`` inside FontLab: names derive from the\n"
        "English menu labels (``fontlabapp.core.menu_names``), so ``menu.glyph.add_component()`` runs\n"
        "Glyph > Add Component. Menus FontLab fills at run time are typed but not enumerated.\n"
        '"""\n'
        "from __future__ import annotations\n\n"
        "from collections.abc import Iterator, Mapping\n"
        "from typing import Any, Literal\n"
    )
    footer = (
        "menu: MenuBar\n" + _doc("The menu bar: ``menu.file``, ``menu.glyph``, ``menu.window.panels``...", "")
        + "actions: Actions\n" + _doc("QActions by path: ``actions[\"Glyph > Add Component\"]``.", "")
        + "panels: Panels\n" + _doc("Panels with explicit visibility.", "")
        + "glyph_actions: GlyphActions\n" + _doc("The Tools > Actions catalogue.", "")
    )
    blocks = [header, API.strip() + "\n", *reversed(classes), actions, panels, glyph, footer]
    return "\n\n".join(b.rstrip("\n") + "\n" for b in blocks)


def _public_names() -> set[str]:
    """What the facade forwards: fontlabapp.core.host's public classes, functions and tree roots."""
    from fontlabapp.core import host

    names = {n for n, v in vars(host).items() if not n.startswith("_") and getattr(v, "__module__", None) == host.__name__}
    return (names | {"menu", "actions", "panels", "glyph_actions"}) - {"annotations"}


def generate_py(capture: dict[str, Any], dest: str = DEST) -> str:
    meta = capture["host"]
    return (
        f"# this_file: {dest}__init__.py\n"
        f"# Generated by `python -m fontlabapp.core.shimgen` ({meta['app']} {meta['app_version']}, "
        f"{capture['captured']}). Do not edit.\n"
        '"""FontLab menus, QActions, panels and glyph actions; the typed tree is in the adjacent .pyi."""\n\n'
        "\n"
        f"_NAMES = frozenset({sorted(_public_names())!r})\n\n\n"
        "def __getattr__(name):\n"
        "    # Lazy: importing this module never touches FontLab (RULINGS.md ruling 5).\n"
        "    # Unknown names (docs-tool probes such as __wrapped__) stay AttributeError\n"
        "    # without importing fontlabapp.\n"
        "    if name not in _NAMES:\n"
        "        raise AttributeError(name)\n"
        "    try:\n"
        "        from fontlabapp.core import host\n"
        "    except ModuleNotFoundError as error:\n"
        "        if error.name != 'fontlabapp':\n"
        "            raise\n"
        "        raise AttributeError(f'{name}: install fontlab-fontlabapp inside FontLab') from error\n"
        "    return getattr(host, name)\n"
    )


def write(capture_path: Path, out: Path, dest: str = DEST) -> list[Path]:
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    if capture.get("schema") != 1:
        raise ValueError(f"Unsupported capture schema: {capture.get('schema')!r}")
    out.mkdir(parents=True, exist_ok=True)
    raw = capture_path.read_bytes()
    provenance = {
        "capture": capture_path.name,
        "capture_sha256": hashlib.sha256(raw).hexdigest(),
        "captured": capture["captured"],
        "host": capture["host"],
        "generator": "fontlabapp.core.shimgen",
        "generator_version": GENERATOR_VERSION,
        "command": "python -m fontlabapp.core.shimgen capture.json OUT",
    }
    files = {
        "__init__.py": generate_py(capture, dest),
        "__init__.pyi": generate_pyi(capture, dest),
        "provenance.json": json.dumps(provenance, indent=1, sort_keys=True) + "\n",
    }
    written = []
    for name, text in files.items():
        path = out / name
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m fontlabapp.core.shimgen", description=__doc__.split("\n")[0])
    parser.add_argument("capture", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--dest", default=DEST, help="this_file prefix of the installed shim")
    args = parser.parse_args(argv)
    for path in write(args.capture, args.out, args.dest):
        print(path)


if __name__ == "__main__":
    main()
