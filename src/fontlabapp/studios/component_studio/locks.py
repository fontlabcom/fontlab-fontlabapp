# this_file: src/fontlabapp/studios/component_studio/locks.py
# SPDX-License-Identifier: Apache-2.0
"""Locks tab (Unlock Lock): show which components are locked; lock or unlock them.

The original's rules are kept unchanged (``data_tool``, ``element_name``,
``explicit_locks``, ``lock_states``, ``word``, ``lock_changes``,
``LockEditor``): FontLab's Python property reports every component as
locked, so each element's own lock flag is read from FontLab's glyph data
(``get_glyph``, the data a .vfj file stores) and trusted only when its
elements match the layer's shapes one to one with the same component
names; otherwise the state is "unknown, kept". The listing (Reload
selection and every dry run) only reads: no history, no write. "Action":
Lock (default) or Unlock; "Masters": current master (default) or all.
Apply reads the stored flags again, sets ``contentLocked`` on each listed
component in place as one ``Component Studio: lock components <subject>``
(or ``unlock components``) Undo step, then reads the flags back. Auto
layers are listed and kept; a glyph that owns auto layers or is a base of
one is refused (no opt-in, as in the original). The original's
``from fly import pr`` is the module-level ``pr`` below (FontLab's
in-process data tools through ``core.scripting.component_studio_backends``).
"""

from typing import Any

import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - the package __getattr__ is native

from .._kerning_ui import combo, get, row
from . import _shared

#: The original's module names, read by the verbatim functions below.
component_writer = _shared.Modules("components")
pr = _shared.Modules("pr")

Entries = list[tuple[str, bool]]  # per element: (component base name or '', locked)


# ---------------------------------------------------------------- verbatim original
# Unlock Lock
def data_tool(tool: str, **arguments: Any) -> Any:
    """Call one of FontLab's own data tools in-process (fly.pr is native fontpr).

    An error answer becomes RuntimeError with FontLab's text.
    """
    result = pr.call(tool, **arguments)
    if isinstance(result, dict) and (
        result.get("error") or result.get("status") == "error"
    ):
        raise RuntimeError(str(result.get("error") or result.get("message")))
    return result


def element_name(element: Any) -> str:
    """Base glyph name of a component element, '' for any other element."""
    component = element.get("component") if isinstance(element, dict) else None
    return str(component.get("glyphName", "")) if isinstance(component, dict) else ""


def explicit_locks(package: Any, name: str) -> dict[str, Entries]:
    """{layer name: element entries} from FontLab's stored glyph data."""
    data = data_tool("get_glyph", font_id=scripting.font_id(package), glyph_name=name)
    data = data.get("glyph", data) if isinstance(data, dict) else {}
    found: dict[str, Entries] = {}
    for layer in data.get("layers", None) or []:
        elements = layer.get("elements", None) or []
        found[str(layer.get("name"))] = [
            (element_name(e), bool(e.get("locked", False))) for e in elements
        ]
    return found


def lock_states(layer: Any, entries: Entries | None) -> list[bool | None]:
    """Own lock flag per layer shape; all None when data and shapes differ.

    The data counts only when it has one element per shape, components at the
    same positions, with the same base names.
    """
    shapes = list(layer.shapes)
    unknown: list[bool | None] = [None] * len(shapes)
    if entries is None or len(entries) != len(shapes):
        return unknown
    for shape, (name, _) in zip(shapes, entries, strict=True):
        if bool(shape.isComponent) != bool(name):
            return unknown
        if shape.isComponent and name != component_writer.base_of(shape):
            return unknown
    return [locked for _, locked in entries]


def word(state: bool | None) -> str:
    """'locked', 'unlocked' or 'unknown'."""
    return "unknown" if state is None else ("locked" if state else "unlocked")


def lock_changes(
    glyph: Any, layer: Any, entries: Entries | None, locked: bool
) -> list[component_writer.Change]:
    """One row per component: state now and after the action."""
    rows: list[component_writer.Change] = []
    states = lock_states(layer, entries)
    for shape, state in zip(layer.shapes, states, strict=True):
        if not shape.isComponent:
            continue
        name, now = component_writer.base_of(shape), word(state)
        if state is None:
            rows.append(component_writer.Change(name, now, "unknown, kept"))
        elif state == locked:
            rows.append(component_writer.Change(name, now, "already " + now))
        else:
            edit = (shape.id, locked, glyph.name)
            rows.append(component_writer.Change(name, now, word(locked), edit))
    return rows


class LockEditor(component_writer.Editor):
    """Set the own lock flag of each planned component in place."""

    def __init__(self, package: Any) -> None:
        self.package = package

    def prepare(self, layer: Any, edits: list[Any]) -> list[Any]:
        return [
            (layer.shapes[component_writer.shape_index(layer, shape_id)], locked, name)
            for shape_id, locked, name in edits
        ]

    def write(self, layer: Any, steps: list[Any]) -> None:
        for shape, locked, _ in steps:
            shape.contentLocked = locked
            shape.changed()

    def check(self, prepared: list[tuple[Any, list[Any]]]) -> list[str]:
        missed: list[str] = []
        stored: dict[str, dict[str, Entries]] = {}
        for layer, steps in prepared:
            for shape, locked, name in steps:
                if name not in stored:
                    stored[name] = explicit_locks(self.package, name)
                states = lock_states(layer, stored[name].get(str(layer.name)))
                if states[component_writer.shape_index(layer, shape.id)] is not locked:
                    missed.append(
                        f"{name}/{layer.name}/{component_writer.base_of(shape)}"
                    )
        return missed


# ---------------------------------------------------------------- tab
class LocksPanel(_shared.ComponentPanel):
    """Action (Lock or Unlock) plus master scope; one row per component."""

    ACTION, DONE = "Apply", "Changed"
    HEADERS: tuple[str, ...] = ("Glyph · master", "Component", "Now", "After")

    def build_controls(self, form: Any) -> None:
        self.flags: dict[str, dict[str, Entries]] = {}
        self.tolerant = False
        self.action = combo(self.widget, ["Lock", "Unlock"], self.contain(self.replan))
        row(self.widget, form, "Action", self.action)
        self.scope_box(form)

    def locking(self) -> bool:
        return get(self.action.currentIndex) == 0

    @property
    def UNDO(self) -> str:  # noqa: N802 - the panel attribute the base reads
        return "lock components" if self.locking() else "unlock components"

    def read_flags(self, package: Any = None) -> None:
        """Read the stored lock flags of the scanned glyphs from FontLab (read-only)."""
        package = self.tool.shell.package() if package is None else package
        if package is None or package.id != self.package_id:
            self.flags = {}
            if self.package is not None:
                raise ValueError("The font changed; press Reload selection.")
            return
        self.flags = {g.name: explicit_locks(package, g.name) for g in self.glyphs}

    def on_reload(self) -> None:
        try:
            self.read_flags(self.package)
        except (ValueError, RuntimeError, TimeoutError):
            if not self.tolerant:
                raise
            self.flags = {}

    def summary(self, plan: Any) -> str:
        if plan.rows and not plan.work:
            return "Nothing to change"
        return super().summary(plan)

    def planner(self) -> Any:
        flags, locked = self.flags, self.locking()
        return lambda glyph, master, layer: lock_changes(
            glyph, layer, flags.get(glyph.name, {}).get(str(layer.name)), locked
        )

    def editor(self) -> Any:
        return LockEditor(self.package)

    def live_plan(self) -> tuple[Any, Any, Any]:
        """Read the stored flags again, then plan and write."""
        self.read_flags()
        return super().live_plan()

    def after_apply(self) -> None:
        """Show the stored state after the write; a read error leaves 'unknown'."""
        self.tolerant = True
        try:
            self.tool.reload()
        finally:
            self.tolerant = False


__all__ = [
    "Entries", "LockEditor", "LocksPanel", "data_tool", "element_name", "explicit_locks",
    "lock_changes", "lock_states", "word",
]  # fmt: skip
