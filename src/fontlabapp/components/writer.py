# this_file: src/fontlabapp/components/writer.py
# SPDX-License-Identifier: Apache-2.0
"""Shared plan, eject and write kernel of the component writer scripts.

What: the Components writer scripts (Align By Anchor, Build From Recipes,
Copy Offsets Between Masters, Decompose, Nested Finder, Replace Reference,
Unlock Lock) share one model. A script planner turns one layer into
``Change`` rows. A row can hold one edit, which the script's ``Editor``
writes: ``EjectEditor`` (Decompose, Nested Finder) replaces a component with
the parts of its base glyph, one level per press; ``MoveEditor`` (Align By
Anchor, Copy Offsets) sets the offset of a component that ``plain_move``
accepts; other scripts subclass ``Editor``.

- ``collect`` runs the planner on every editable layer and returns a
  ``Plan``. Auto layers are listed and skipped, never edited.
- ``copy_problem`` gives the reason why the parts of a component cannot be
  copied safely, or "". It walks every base level as FontLab's builder does:
  a plain (not auto) base layer, affine transforms only, no composite shape
  that is not a component, no loop, not deeper than ``MAX_DEPTH``.
- ``require_safe`` refuses the whole batch before any history exists:
  a glyph that owns an auto layer or is a base of one (also through other composites).
- ``apply_work`` writes all edits through ONE ``history.commit`` with
  ``operation="geometry"``. ``EjectEditor`` builds the copies first, gives
  each removed component with its data and builder as ``retain=``
  (``history.component_history``), and reads the layers back.

How: ``eject`` refreshes the component cache, then copies the base parts
with ``ejectTo()`` BEFORE history opens. ``keep_raw_state`` copies back what
a native copy drops: the raw node connection bits (FontLab issue 8516), the
element note (FontLab issue 8538) and the element name. Inside history, the
write only removes the component and inserts the copies at its place.
``history.commit`` puts the retained objects first in the notification and
asks for deep history, which FontLab's Undo needs for a removed component
(FontLab issue 7641).

Why: the logic was a private copy in each script. One App module keeps the
refusals and the Undo protocol the same in every script that uses it. The
generic kernel (``Change``, ``Plan``, ``Editor``, ``apply_work``, ``fmt``,
``plural``, ``layer_of``, ``shown``, ``settle``) lives in
``fontlabapp.masters.layers.writer``; this module re-exports it, so the Components
scripts keep one import.

This module imports only the standard library and stdlib-only App modules
(``history``, ``edit_guards``, ``layer_writer``) at load time. The ``fontlab`` module loads
inside the functions, so FontLab's 5-second cold import stays fast. Offline
tests do not prove native Undo/Redo.

How to use (a script)::

    import fly.ap.components.writer as component_writer

    def planner(glyph, master, layer):
        rows = []
        for shape in component_writer.components(layer):
            why = component_writer.copy_problem(
                package, (glyph.name, master), shape, master
            )
            edit = None if why else shape.id
            name = component_writer.base_of(shape)
            rows.append(component_writer.Change(name, "", "parts", edit, why))
        return rows

    plan = component_writer.collect(glyphs, masters, planner)
    facts = history.scan_auto_facts(package)
    component_writer.require_safe(plan.work, facts)
    component_writer.apply_work(
        plan.work, "Decompose", facts, component_writer.EjectEditor(unlock=True)
    )
"""

import math
from collections.abc import Iterable
from typing import Any

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native
from fontlabapp import _native
from fontlabapp.masters.layers.writer import (
    EPSILON,
    Change,
    Editor,
    Plan,
    Planner,
    Work,
    apply_work,
    fmt,
    layer_of,
    plural,
    settle,
    shown,
)

#: FontLab's composite builder refuses deeper component nesting.
MAX_DEPTH = 64


def half_up(value: float) -> int:
    """Round half up: 14.5 -> 15 and -14.5 -> -14, on every platform."""
    return math.floor(value + 0.5)


def components(layer: Any) -> list[Any]:
    """Component shapes of the layer, in layer order."""
    return [shape for shape in layer.shapes if shape.isComponent]


def base_of(shape: Any) -> str:
    """Name of the glyph that a component shape refers to."""
    return str(shape.shapeData.componentGlyph)


def offset(shape: Any) -> tuple[float, float]:
    """Translation part of the shape transform, unrounded."""
    matrix = shape.transform
    return float(matrix.dx()), float(matrix.dy())


def offset_text(point: tuple[float, float]) -> str:
    """'40, -12' for a preview cell."""
    return f"{fmt(point[0])}, {fmt(point[1])}"


def shape_index(layer: Any, shape_id: Any) -> int:
    """Position of the shape with `shape_id` in the layer. ValueError if gone."""
    for index, shape in enumerate(layer.shapes):
        if shape.id == shape_id:
            return index
    raise ValueError("A component changed since the scan; press Reload selection.")


def collect(glyphs: Iterable[Any], masters: Iterable[str], planner: Planner) -> Plan:
    """Run `planner` on every editable layer. Auto layers are listed, never edited."""
    plan = Plan()
    masters = list(masters)
    for glyph in glyphs:
        for master in masters:
            layer = layer_of(glyph, master)
            changes = planner(glyph, master, layer) if layer is not None else []
            if not changes:
                continue
            label = f"{glyph.name} · {master}"
            if layer.autoLayer:
                plan.skipped.append(f"{glyph.name}/{master}")
                note = Change(plural(len(changes), "row"), "", "auto layer, skipped")
                plan.rows.append((label, note))
                continue
            plan.rows.extend((label, change) for change in changes)
            blocked = [c.problem for c in changes if c.problem]
            plan.problems.extend(f"{label}: {text}" for text in blocked)
            edits = [c.edit for c in changes if c.edit is not None]
            if edits and not blocked:
                plan.work.append((glyph, layer, edits))
    return plan


def blocked_rows(work: Work, facts: history.AutoFacts) -> list[tuple[str, Change]]:
    """One blocking row per edited glyph that the geometry policy refuses.

    A glyph that owns an auto layer, or is a base of one (also through other
    composites), is refused: FontLab rebuilds the auto composite and Undo does
    not restore it.
    """
    names = list(dict.fromkeys(glyph.name for glyph, _, _ in work))
    found = history.refusals(facts, names, "geometry")
    return [
        (name, Change("blocked", "", "", problem=why)) for name, why in found.items()
    ]


def require_safe(work: Work, facts: history.AutoFacts) -> None:
    """Refuse the whole batch before any history exists, when Undo would fail.

    A glyph that owns an auto layer or is a base of one (blocked_rows).
    """
    found = blocked_rows(work, facts)
    if found:
        reasons = [f"{name}: {change.problem}" for name, change in found]
        raise ValueError(
            f"FontLab cannot undo edits to these glyphs: {shown(reasons)}. "
            "Choose other glyphs."
        )


# ---------------------------------------------------------------- offset writer
def plain_move(shape: Any) -> bool:
    """True when the transform is a pure translation: no scale, slant or rotation.

    Anchor arithmetic and offset copies are exact only for such components.
    """
    matrix = shape.transform
    return (
        bool(matrix.isAffine())
        and abs(matrix.m11() - 1) < EPSILON
        and abs(matrix.m22() - 1) < EPSILON
        and abs(matrix.m12()) < EPSILON
        and abs(matrix.m21()) < EPSILON
    )


class MoveEditor(Editor):
    """Set the offset of planned components; keep the rest of their transform.

    Edits are (component shape id, (dx, dy)). The original shape is edited in
    place: no copy, so its name, note, lock and flags stay as they are.
    """

    def prepare(self, layer: Any, edits: list[Any]) -> list[Any]:
        """Return (component shape, (dx, dy)) per edit, found before history."""
        return [
            (layer.shapes[shape_index(layer, shape_id)], point)
            for shape_id, point in edits
        ]

    def write(self, layer: Any, steps: list[Any]) -> None:
        """Give each shape a new QTransform: same matrix, new dx and dy."""
        gui = _native("PythonQt").QtGui
        for shape, (dx, dy) in steps:
            matrix = shape.transform
            shape.transform = gui.QTransform(
                matrix.m11(), matrix.m12(), matrix.m21(), matrix.m22(), dx, dy
            )
            shape.changed()

    def check(self, prepared: list[tuple[Any, list[Any]]]) -> list[str]:
        """Return "layer/base" of each component whose offset FontLab did not keep."""
        missed: list[str] = []
        for layer, steps in prepared:
            for shape, point in steps:
                now = offset(shape)
                if any(abs(now[axis] - point[axis]) >= EPSILON for axis in (0, 1)):
                    missed.append(f"{layer.name}/{base_of(shape)}")
        return missed


# ---------------------------------------------------------------- one-level eject
def refreshed(shape: Any) -> None:
    """Rebuild the component cache first: its includes can describe an older base."""
    if shape.shapeData.builder.update() is False:
        raise RuntimeError(f"FontLab could not refresh component {base_of(shape)}.")


def keep_raw_state(source: Any, copy: Any) -> None:
    """Restore what a native copy drops.

    A copied outline gets its Smooth flags recomputed from geometry (fl#8516):
    copy back only the raw connection bits of every node. A copy also loses
    the stored element note (fl#8538) and can lose the element name: copy
    them back. All edits touch only the detached copy, never the source. The
    active (current element) state of the base is not copied into this glyph.
    """
    if source.name and copy.name != source.name:
        copy.name = source.name
    note = source.shapeData.note
    if note and copy.shapeData.note != note:
        copy.shapeData.note = note
    if source.isComponent:
        return
    mask = _native("fontlab").flNode.NodeKind["SmoothMask"]
    for old_contour, new_contour in zip(source.contours, copy.contours, strict=True):
        for old, new in zip(old_contour.nodes(), new_contour.nodes(), strict=True):
            new.nodeState = (new.nodeState & ~mask) | (old.nodeState & mask)


def eject(shape: Any) -> list[Any]:
    """Detached copies of the shapes inside a component, placed by its transform.

    One level only: a component inside the base stays a component. The copies
    exist before any history opens; the write only swaps them in.
    """
    refreshed(shape)
    sources = list(shape.includesList)
    copies = list(shape.ejectTo())
    if len(copies) != len(sources):
        raise RuntimeError(f"FontLab could not copy the parts of {base_of(shape)}.")
    for source, copy in zip(sources, copies, strict=True):
        keep_raw_state(source, copy)
    return copies


def copy_problem(package: Any, owner: tuple[str, str], shape: Any, master: str) -> str:
    """Why the parts of `shape` cannot be copied safely, or "".

    Walks every base level as FontLab's builder does. Each base needs a plain
    (not auto) layer whose shapes have affine transforms and are outlines or
    components; a loop back to a visited layer, or nesting deeper than
    MAX_DEPTH, is refused. `owner` is (glyph name, layer name) of the edit.
    """
    active, done = {owner}, set()

    def visit(name: str, layer_name: str) -> str:
        key = (name, layer_name or master)
        if key in active:
            return f"components loop through {name}"
        if key in done:
            return ""
        if len(active) >= MAX_DEPTH:
            return f"components nest more than {MAX_DEPTH} levels"
        glyph = package.findName(name)
        base = layer_of(glyph, key[1]) if glyph is not None else None
        if base is None or base.autoLayer:
            return f"base {name} has no plain layer {key[1]}"
        active.add(key)
        for inner in base.shapes:
            other = inner.isComposite and not inner.isComponent
            if other or not inner.transform.isAffine():
                return f"base {name} holds a shape that cannot be copied"
            why = (
                visit(base_of(inner), inner.shapeData.componentLayer)
                if inner.isComponent
                else ""
            )
            if why:
                return why
        active.discard(key)
        done.add(key)
        return ""

    if not shape.transform.isAffine():
        return "perspective transform: decompose it in FontLab"
    return visit(base_of(shape), shape.shapeData.componentLayer)


def part_counts(package: Any, shape: Any, master: str) -> tuple[int, int]:
    """(contours, components) that one eject of `shape` gives, read from its base."""
    glyph = package.findName(base_of(shape))
    layer = layer_of(glyph, shape.shapeData.componentLayer or master) if glyph else None
    if layer is None:
        return 0, 0
    inner = components(layer)
    contours = sum(len(s.contours) for s in layer.shapes if not s.isComponent)
    return contours, len(inner)


def parts_text(contours: int, inner: int) -> str:
    """'3 contours', '2 contours + 1 component'."""
    text = plural(contours, "contour")
    return text + (f" + {plural(inner, 'component')}" if inner else "")


class EjectEditor(Editor):
    """Swap each planned component for the copies of its parts.

    Edits are component shape ids. `prepare` builds the copies before history.
    `write` removes the component and inserts the copies at its place.
    `check` confirms that the component is gone and every copy is in the layer.
    """

    def __init__(self, unlock: bool) -> None:
        """`unlock` True: the new contours are unlocked (FontLab's Decompose)."""
        self.unlock = unlock

    def prepare(self, layer: Any, edits: list[Any]) -> list[Any]:
        """Return (component, copies, placed) per edit, built before history."""
        steps: list[Any] = []
        for shape_id in edits:
            shape = layer.shapes[shape_index(layer, shape_id)]
            copies = eject(shape)
            if self.unlock:
                for copy in copies:
                    if not copy.isComponent:
                        copy.contentLocked = False
            steps.append((shape, copies, []))
        return steps

    def write(self, layer: Any, steps: list[Any]) -> None:
        """Remove each component and insert its copies at its place."""
        for shape, copies, placed in steps:
            index = shape_index(layer, shape.id)
            layer.removeShape(shape)
            for step, copy in enumerate(copies):
                inserted = layer.insertShape(index + step, copy)
                placed.append(inserted if inserted is not None else copy)

    def retain(self, steps: list[Any]) -> list[Any]:
        """Each removed component with its data and builder, read before the write."""
        return [
            item for shape, _, _ in steps for item in history.component_history(shape)
        ]

    def check(self, prepared: list[tuple[Any, list[Any]]]) -> list[str]:
        """Return "layer/base" of each component that is still there or not replaced."""
        missed: list[str] = []
        for layer, steps in prepared:
            present = {shape.id for shape in layer.shapes}
            for shape, copies, placed in steps:
                label = f"{layer.name}/{base_of(shape)}"
                gone = shape.id not in present and len(placed) == len(copies)
                if not gone or any(item.id not in present for item in placed):
                    missed.append(label)
        return missed


__all__ = [
    "EPSILON",
    "MAX_DEPTH",
    "Change",
    "Editor",
    "EjectEditor",
    "MoveEditor",
    "Plan",
    "Planner",
    "Work",
    "apply_work",
    "base_of",
    "blocked_rows",
    "collect",
    "components",
    "copy_problem",
    "eject",
    "fmt",
    "half_up",
    "keep_raw_state",
    "layer_of",
    "offset",
    "offset_text",
    "part_counts",
    "parts_text",
    "plain_move",
    "plural",
    "refreshed",
    "require_safe",
    "settle",
    "shape_index",
    "shown",
]
