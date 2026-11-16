# this_file: src/fontlabapp/masters/layers/writer.py
# SPDX-License-Identifier: Apache-2.0
"""Generic plan and write kernel of the layer writer scripts.

What: the writer scripts of the Components and Contours folders share one
model. A script planner turns one layer into ``Change`` rows. A row can hold
one edit. A ``collect`` function of the script family (``component_writer``,
``outline_writer``) runs the planner on the chosen layers and fills a
``Plan``. The script's ``Editor`` writes the edits, and ``apply_work`` makes
that write ONE ``history.commit`` with ``operation="geometry"``.

How: ``apply_work`` calls ``editor.prepare`` for every layer BEFORE history
opens, so native objects exist before the first ``init``. Inside history,
``editor.write`` changes each layer and ``settle`` lets FontLab rebuild the
layer caches. ``editor.retain`` names the native objects that the write
removes; ``history.commit`` puts them first in the notification with deep
history (FontLab issue 7641). An editor that removes nothing gives the
two-argument notification. ``editor.check`` reads the font back: a value
that FontLab did not keep raises ``RuntimeError``. A failure after history
started raises ``history.PartialWriteError`` ("... use Edit > Undo").

Why: the component and outline families used private copies of the same
kernel. One App module keeps the Undo protocol, the read-back and the error
texts the same everywhere. The two families keep their own ``collect`` and
refusal policy: ``component_writer`` refuses the whole batch, and
``outline_writer`` lists and skips each refused glyph.

This module imports only the standard library and stdlib-only App modules
(``history``) at load time, so FontLab's 5-second cold import stays fast.
Offline tests do not prove native Undo/Redo.

How to use (a family module)::

    from fly.ap.masters.layers.writer import Change, Editor, Plan, apply_work

    class Shift(Editor):
        def write(self, layer, steps):
            ...

    apply_work(plan.work, "Shift", facts, Shift())
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native

#: The write list: (glyph, layer, edits) per edited layer. No auto layer.
Work = list[tuple[Any, Any, list[Any]]]
#: Units. Two values closer than this count as equal.
EPSILON = 1e-6
#: Names shown before " …" in a list text.
SHOWN_NAMES = 8


@dataclass(frozen=True)
class Change:
    """One preview row. `edit` None: shown only. `problem` set: blocks Apply.

    `key` names a change of the node structure (for example the index of a
    deleted contour). It never holds coordinates. Masters stay compatible
    only when every master gets the same keys. Rows that do not change the
    structure keep the default None.
    """

    name: str
    old: str
    new: str
    edit: Any = None
    problem: str = ""
    key: Any = None


@dataclass
class Plan:
    """Everything one Apply would do, plus the reasons it may not."""

    work: Work = field(default_factory=list)
    rows: list[tuple[str, Change]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # auto layers
    refused: list[str] = field(default_factory=list)  # glyphs the policy refuses
    held: list[str] = field(default_factory=list)  # glyphs kept for compatibility
    problems: list[str] = field(default_factory=list)

    @property
    def edits(self) -> int:
        """Return the number of planned edits on all layers."""
        return sum(len(edits) for _, _, edits in self.work)


#: A planner takes (glyph, master name, layer) and returns the layer's rows.
Planner = Callable[[Any, str, Any], list[Change]]


def plural(count: int, word: str) -> str:
    """'1 layer', '2 layers'."""
    return f"{count} {word}{'' if count == 1 else 's'}"


def fmt(value: float, places: int | None = None) -> str:
    """Short number text: 700.0 -> 700.

    `places` None keeps every digit that ``:g`` shows (the component
    scripts). `places` 2 rounds first: 12.254 -> 12.25 (the outline scripts).
    """
    return f"{value:g}" if places is None else f"{round(value, places):g}"


def layer_of(glyph: Any, master: str) -> Any | None:
    """Existing master layer, or None. Never creates a layer."""
    layer = glyph.findLayer(master)
    return None if layer is None or layer.isNull else layer


def shown(names: list[str]) -> str:
    """'a, b, c …' for long lists: the first SHOWN_NAMES names."""
    more = " …" if len(names) > SHOWN_NAMES else ""
    return ", ".join(names[:SHOWN_NAMES]) + more


def settle(layer: Any) -> None:
    """Mark the layer changed and let FontLab rebuild its caches.

    `update()` returning False means FontLab refused the new geometry.
    """
    layer.changed()
    if layer.update() is False:
        raise RuntimeError(f"FontLab could not update layer {layer.name}.")


class Editor:
    """Write strategy of one script: prepare, write and check.

    `prepare(layer, edits)` returns the steps; it runs before any history.
    `write(layer, steps)` changes the layer, inside history.
    `check(prepared)` returns texts for steps that the font does not hold.
    `retain(steps)` returns the native objects that the write removes.
    """

    def prepare(self, layer: Any, edits: list[Any]) -> list[Any]:
        """Return the steps for `edits`. The default keeps the edits as steps."""
        return list(edits)

    def write(self, layer: Any, steps: list[Any]) -> None:
        """Change the layer. A subclass must override it."""
        raise NotImplementedError

    def check(self, prepared: list[tuple[Any, list[Any]]]) -> list[str]:
        """Return one text per step that the font does not hold. Default: none."""
        return []

    def retain(self, steps: list[Any]) -> list[Any]:
        """Native objects that the write removes and FontLab's Undo must keep."""
        return []


def apply_work(
    work: Work,
    title: str,
    facts: history.AutoFacts,
    edit: Editor,
    *,
    allow_bases: bool = False,
) -> dict[str, Any]:
    """Write all edits as ONE native Undo step through history.commit.

    `edit.prepare` builds every native object BEFORE history opens.
    `edit.write` changes one layer; the write strategy decides what is kept.
    `edit.retain` names the native objects that the write removes (for a
    removed component: the component, its data and its builder);
    history.commit puts them first in the notification with deep history
    (fl#7641). An editor that removes nothing returns no objects, and the
    notification is the two-argument one. `edit.check` reads the font back
    and returns one text per edit that FontLab did not keep.

    Auto layers are never in `work`; `facts` is a fresh
    history.scan_auto_facts. `allow_bases` passes the user's consent to edit
    bases of automatic composites to history.commit. No rollback is
    attempted: a failure after history started raises
    history.PartialWriteError ("... use Edit > Undo").
    """
    layers = [layer for _, layer, _ in work]
    if not layers:
        return {"pending_updates": (), "pending_note": "", "edits": 0, "layers": 0}
    glyphs = list({glyph.name: glyph for glyph, _, _ in work}.values())
    prepared = [(layer, edit.prepare(layer, edits)) for _, layer, edits in work]
    retain = [item for _, steps in prepared for item in edit.retain(steps)]

    def mutate() -> None:
        for layer, steps in prepared:
            edit.write(layer, steps)
            settle(layer)

    done = history.commit(
        title,
        layers,
        glyphs,
        mutate,
        operation="geometry",
        facts=facts,
        allow_bases=allow_bases,
        retain=retain,
        read_back=lambda: edit.check(prepared),
    )
    if done.mismatches:
        raise history.unstored_error(done.mismatches)
    return {"pending_note": done.pending_note, "edits": sum(len(edits) for _, _, edits in work), "layers": len(work), "pending_updates": done.pending_updates}


__all__ = [
    "EPSILON",
    "SHOWN_NAMES",
    "Change",
    "Editor",
    "Plan",
    "Planner",
    "Work",
    "apply_work",
    "fmt",
    "layer_of",
    "plural",
    "settle",
    "shown",
]
