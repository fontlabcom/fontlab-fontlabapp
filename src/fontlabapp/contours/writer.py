# this_file: src/fontlabapp/contours/writer.py
# SPDX-License-Identifier: Apache-2.0
"""Shared plan kernel of the outline writer scripts (Contours folder).

What: the Contours writer scripts (Round Coordinates, Remove Overlap, Add
Extremes, Correct Contour Direction, Straighten Short Curves, Optimize Start
Points, Delete Small Contours, Fix Zero Handles, Delete Duplicate Contours,
Transform, Slant) share one model. A script planner turns one layer into
``Change`` rows; the script's ``Editor`` writes them through
``apply_work`` (one Undo step). This module adds the outline parts to the
generic ``fontlabapp.masters.layers.writer`` kernel and re-exports that kernel:

- ``outline_shapes`` gives the own contour shapes that a script may edit in
  place, and a note for every shape that it keeps (shared outline data,
  scaled or rotated shapes). ``note_rows`` turns the notes into rows.
- ``node_points`` and ``translation`` read nodes and plain shape moves.
- ``collect`` runs the planner on every chosen layer. A glyph that the
  geometry policy refuses is listed and skipped as a whole; the other
  glyphs are still written. With ``compatible``, a glyph whose structure
  edits would differ between masters is held back (``held_back``).
- ``require_safe`` is a compatibility hook; ``apply_work`` discloses queued
  glyph updates through history (FontLab issue 8537).

How: a ``Change.key`` names a structure edit (for example the index of a
deleted contour). ``held_back`` compares the keys of all masters: the
masters stay compatible only when every master gets the same keys and
every master with a key edit is in scope.

Why: the logic was a private copy in each of the eleven scripts. The
refusal policy differs from ``component_writer`` on purpose: an outline
batch skips each refused glyph, with a row that says why, and asks for
consent (``allow_bases``) before it edits bases of automatic composites.

This module imports only the standard library and stdlib-only App modules
(``history``, ``edit_guards``, ``layer_writer``) at load time, so FontLab's
5-second cold import stays fast. The panel base is in
``fontlabapp.contours.panel.model``. Offline tests do not prove native Undo/Redo.

How to use (a script)::

    import fly.ap.contours.writer as outline_writer

    def planner(glyph, master, layer):
        shapes, notes = outline_writer.outline_shapes(layer)
        rows = [outline_writer.Change("nodes", "3", "4", ("nodes", shapes))]
        return rows + outline_writer.note_rows(notes)

    plan = outline_writer.collect(glyphs, masters, planner, facts)
    outline_writer.require_safe()
    outline_writer.apply_work(plan.work, "Example", facts, ExampleEditor())
"""

from collections.abc import Iterable
from typing import Any

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.masters.layers.writer as layer_writer  # noqa: PLR0402 - the package __getattr__ is native
from fontlabapp.core.sharing import element_shared, sharing_operation
from fontlabapp.masters.layers.writer import (
    EPSILON,
    Change,
    Editor,
    Plan,
    Planner,
    Work,
    apply_work,
    layer_of,
    plural,
    settle,
    shown,
)

#: One node: x, y and on-curve, in shape coordinates.
Point = tuple[float, float, bool]
#: Label of the tick that holds glyphs whose masters would differ.
COMPATIBLE_LABEL = "Keep masters compatible"
#: Label of the consent tick for bases of automatic composites.
BASES_LABEL = "Also edit bases of automatic composites"
#: Decimal places of preview numbers in the outline scripts.
PLACES = 2


def fmt(value: float) -> str:
    """Short number text with PLACES decimals: 700.0 -> 700, 12.254 -> 12.25."""
    return layer_writer.fmt(value, PLACES)


def node_points(contour: Any) -> list[Point]:
    """(x, y, on-curve) of every node, in stored order and shape coordinates."""
    return [(float(n.x), float(n.y), bool(n.isOn())) for n in contour.nodes()]



# Element sharing lives in ``fontlabapp.core.sharing`` so studios can reach it;
# ``element_shared`` and ``sharing_operation`` stay importable from here.


def translation(shape: Any) -> tuple[float, float] | None:
    """(dx, dy) when the shape transform only moves; None for scale, slant or turn."""
    matrix = shape.transform
    plain = (
        abs(matrix.m11() - 1) < EPSILON
        and abs(matrix.m22() - 1) < EPSILON
        and abs(matrix.m12()) < EPSILON
        and abs(matrix.m21()) < EPSILON
    )
    return (float(matrix.dx()), float(matrix.dy())) if plain else None


def outline_shapes(layer: Any) -> tuple[list[Any], list[str]]:
    """Own contour shapes that a script may edit in place, and notes for the rest.

    Kept: components (edit their base glyph instead); shared outline data
    (an edit would change every glyph that uses it, and those glyphs are not
    in the Undo step; components of this glyph do not count, see
    ``element_shared``); shapes with scale, slant or rotation
    (lengths, areas and directions in stored coordinates differ from what
    you see).
    A plain move is allowed: the measures here do not change under a move.
    """
    editable, notes = [], []
    for shape in layer.shapes:
        if shape.isComponent or not shape.contours:
            continue
        if element_shared(shape, layer):
            notes.append("shared outline, kept")
        elif translation(shape) is None:
            notes.append("scaled or rotated shape, kept")
        else:
            editable.append(shape)
    return editable, notes


def note_rows(notes: list[str]) -> list[Change]:
    """One muted row per distinct note, with the number of shapes."""
    counts: dict[str, int] = {}
    for text in notes:
        counts[text] = counts.get(text, 0) + 1
    return [Change(plural(n, "shape"), "", text) for text, n in counts.items()]


def held_back(planned: dict[str, tuple[Any, list[Change]]], chosen: list[str]) -> str:
    """Why the structure edits of one glyph would break master compatibility, or "".

    `planned` holds the rows of every master that has the glyph. The edits
    keep the masters compatible only when all masters get the same keys and
    every master with a key edit is in scope.
    """
    keys = {
        master: tuple(c.key for c in rows if c.edit is not None and c.key is not None)
        for master, (layer, rows) in planned.items()
    }
    if not any(keys.values()):
        return ""
    if len(set(keys.values())) > 1:
        return "masters would differ, kept"
    if any(found and master not in chosen for master, found in keys.items()):
        return "other masters need it too; choose All masters"
    return ""


@sharing_operation()
def collect(
    glyphs: Iterable[Any],
    masters: Iterable[str],
    planner: Planner,
    facts: history.AutoFacts,
    *,
    compatible: bool = False,
    all_masters: Iterable[str] = (),
    allow_bases: bool = False,
) -> Plan:
    """Run `planner` on every chosen layer and return the Plan.

    A glyph that the geometry policy refuses is listed and skipped as a whole:
    it owns an automatic layer, or it is a base of an automatic composite
    (unless `allow_bases`). FontLab rebuilds those composites and Undo does
    not restore them. With `compatible`, the planner also runs on the other
    masters, and a glyph whose structure edits would differ is held back.
    """
    plan = Plan()
    chosen = list(masters)
    every = list(dict.fromkeys([*chosen, *all_masters])) if compatible else chosen
    for glyph in glyphs:
        why = history.refusal(facts, glyph.name, "geometry", allow_bases=allow_bases)
        if why:
            plan.refused.append(glyph.name)
            plan.rows.append((glyph.name, Change("glyph", "", f"skipped: {why}")))
            continue
        planned: dict[str, tuple[Any, list[Change]]] = {}
        for master in every:
            layer = layer_of(glyph, master)
            if layer is None:
                continue
            if layer.autoLayer:
                if master in chosen:
                    plan.skipped.append(f"{glyph.name}/{master}")
                    note = Change("layer", "", "auto layer, skipped")
                    plan.rows.append((f"{glyph.name} · {master}", note))
                continue
            planned[master] = (layer, planner(glyph, master, layer))
        hold = held_back(planned, chosen) if compatible else ""
        if hold:
            plan.held.append(glyph.name)
        for master in chosen:
            if master not in planned:
                continue
            layer, changes = planned[master]
            label = f"{glyph.name} · {master}"
            if hold:
                changes = [
                    Change(c.name, c.old, hold) if c.edit is not None else c
                    for c in changes
                ]
            plan.rows.extend((label, change) for change in changes)
            blocked = [c.problem for c in changes if c.problem]
            plan.problems.extend(f"{label}: {text}" for text in blocked)
            edits = [c.edit for c in changes if c.edit is not None]
            if edits and not blocked:
                plan.work.append((glyph, layer, edits))
    return plan


def require_safe() -> None:
    """Compatibility hook; the writer discloses queued ids through history.commit."""


__all__ = [
    "BASES_LABEL",
    "COMPATIBLE_LABEL",
    "EPSILON",
    "PLACES",
    "Change",
    "Editor",
    "Plan",
    "Planner",
    "Point",
    "Work",
    "apply_work",
    "collect",
    "element_shared",
    "fmt",
    "held_back",
    "layer_of",
    "node_points",
    "note_rows",
    "outline_shapes",
    "plural",
    "require_safe",
    "settle",
    "sharing_operation",
    "shown",
    "translation",
]
