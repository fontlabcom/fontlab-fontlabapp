# this_file: src/fontlabapp/studios/layer_manager/_use_master.py
# SPDX-License-Identifier: Apache-2.0
"""Backups tab, Use as master mode: the Scriptmix "Use Layer As Master" (Scripts/Masters/).

Swap the roles of a chosen layer and the master layer it belongs to by
renaming only: the old master layer becomes "<Master>@ HH:MM:SS, DD/MM/YY",
the chosen layer takes the master name, and their masks follow FontLab's
mask-name rule. The naming and swap planning (``mask_name_for``,
``plan_swap``, ``_mask_of``) are the original's, verbatim, and every
original refusal is kept. Host-mode deviation (disclosed): the original
promoted the layer selected in a Glyph window; here the tab lists the
selected glyphs' layers that belong to a master but are not its master
layer, and the "Layer" choice names the layer to promote. Use as master
writes all renames as ONE ``Layer Manager: use as master <subject>`` Undo
step through ``AppShell.history`` (names put back on failure, as the
original did).
"""

from collections.abc import Collection, Sequence
from datetime import datetime
from typing import Any


from .._kerning_ui import combo, get, row
from ._shared import (
    Modules,
    PlanTab,
    append_note,
    commit,
    ident,
    label as undo_label,
    result_dict,
)

masters_api = Modules("masters")

TITLE = "Use Layer As Master"
STAMP_FORMAT = "%H:%M:%S, %d/%m/%y"
DEADLINE_SECONDS = 2.0


def mask_name_for(layer_name: str, masters: Sequence[str]) -> str:
    """Return the mask layer name FontLab expects for a body layer name.

    A single-master font keeps the mask of its master layer as plain "mask".
    Every other layer uses "mask.<layer name>".
    """
    if len(masters) == 1 and layer_name.lower() == masters[0].lower():
        return "mask"
    return f"mask.{layer_name}"


def plan_swap(
    master: str,
    chosen: str,
    taken: Collection[str],
    stamp: str,
    masters: Sequence[str],
    masks: tuple[bool, bool],
) -> list[tuple[str, str, str]]:
    """Return renames [(role, old name, new name)] in a safe order.

    `master` is the master layer name, `chosen` the layer to promote, `taken`
    all layer names of the glyph, `masks` tells if (master, chosen) own a mask.
    Raise ValueError when a new name would clash. Names are compared without case.
    """
    used = {name.lower() for name in taken}
    backup = f"{master}@ {stamp}"
    number = 2
    while backup.lower() in used or mask_name_for(backup, masters).lower() in used:
        backup = f"{master}@ {stamp} ({number})"
        number += 1
    steps = []
    if masks[0]:
        steps.append(
            (
                "master mask",
                mask_name_for(master, masters),
                mask_name_for(backup, masters),
            )
        )
    steps.append(("master", master, backup))
    if masks[1]:
        steps.append(
            (
                "chosen mask",
                mask_name_for(chosen, masters),
                mask_name_for(master, masters),
            )
        )
    steps.append(("chosen", chosen, master))
    for role, old, new in steps:
        used.discard(old.lower())
        if new.lower() in used:
            raise ValueError(f"The {role} cannot take the name '{new}': it is in use.")
        used.add(new.lower())
    return steps


def _valid(layer: Any) -> bool:
    """True for a real native layer object."""
    return layer is not None and not layer.isNull and layer.isValid


def _mask_of(layer: Any, masters: Sequence[str]) -> Any | None:
    """Return the mask layer of a body layer, or None. Never create one.

    Raise ValueError if the mask name does not follow the FontLab rule.
    """
    mask = layer.getMaskLayer(False)
    if not _valid(mask):
        return None
    expected = mask_name_for(str(layer.name), masters)
    if str(mask.name).lower() != expected.lower():
        raise ValueError(
            f"The background of '{layer.name}' is named '{mask.name}', not '{expected}'."
        )
    return mask


def candidates(glyphs: Sequence[Any], masters: Sequence[str]) -> list[str]:
    """Sorted names of the body layers that belong to a master but are not its master layer."""
    found = set()
    for glyph in glyphs:
        for layer in glyph.layers:
            name = str(layer.name)
            master = masters_api.associated_master(name, masters)
            if (
                master is not None
                and name != master
                and not layer.isMaskLayer
                and not layer.isService
            ):
                found.add(name)
    return sorted(found)


def plan_layers(
    package: Any, names: Sequence[str], layer_name: str, stamp: str
) -> list[dict[str, Any]]:
    """The original ``plan()`` for layer ``layer_name`` of each glyph in ``names`` that has it.

    The per-layer checks and refusals are the original's, verbatim (the
    selection capture is replaced by the chosen layer name).
    """
    masters = tuple(str(name) for name in package.masters)
    jobs = []
    for glyph_name in dict.fromkeys(names):
        glyph = package.findName(glyph_name)
        if glyph is None or glyph.isNull:
            continue
        chosen = glyph.findLayer(layer_name)
        if not _valid(chosen):
            continue
        master = masters_api.associated_master(layer_name, masters)
        if master is None:
            raise ValueError(
                f"Layer '{layer_name}' of '{glyph_name}' belongs to no master."
            )
        if layer_name == master:
            raise ValueError(
                f"Layer '{layer_name}' of '{glyph_name}' is already the master layer."
            )
        old = glyph.findLayer(master)
        if not _valid(old):
            raise ValueError(f"'{glyph_name}' has no master layer '{master}'.")
        for layer in (chosen, old):
            if (
                layer.isMaskLayer
                or layer.isService
                or layer.autoLayer
                or layer.isLocked
            ):
                raise ValueError(
                    f"Layer '{layer.name}' of '{glyph_name}' is locked, automatic, "
                    "a mask or a service layer."
                )
            if _valid(layer.getImgLayer(False)):
                raise ValueError(
                    f"Layer '{layer.name}' has an image layer; not supported."
                )
        old_mask, new_mask = _mask_of(old, masters), _mask_of(chosen, masters)
        steps = plan_swap(
            master,
            layer_name,
            [str(x.name) for x in glyph.layers],
            stamp,
            masters,
            (old_mask is not None, new_mask is not None),
        )
        targets = {
            "master": old,
            "chosen": chosen,
            "master mask": old_mask,
            "chosen mask": new_mask,
        }
        jobs.append({"glyph": glyph, "steps": steps, "targets": targets})
    return jobs


def apply_renames(
    tool: Any, jobs: Sequence[dict[str, Any]], title: str = TITLE
) -> dict[str, Any] | None:
    """Rename all planned layers in ONE Undo step; restore the names on failure (the original's).

    The step goes through ``tool.shell.history`` titled ``title`` with
    every renamed layer as a target (None when refused).
    """
    layers = [t for job in jobs for t in job["targets"].values() if t is not None]
    glyphs = [job["glyph"] for job in jobs]

    def mutate() -> Sequence[Any]:
        done: list[tuple[Any, str]] = []
        try:
            for job in jobs:
                for role, old, new in job["steps"]:
                    layer = job["targets"][role]
                    layer.name = new
                    done.append((layer, old))
                    if str(layer.name) != new:
                        raise RuntimeError(
                            f"FontLab kept the name '{layer.name}' instead of '{new}'."
                        )
        except Exception:
            for layer, old in reversed(done):
                layer.name = old
            raise
        return ()

    done = commit(tool, title, layers, glyphs, mutate)
    return None if done is None else result_dict(done)


class UseMasterPanel(PlanTab):
    """Layer choice, the rename table, Use selection and Use as master."""

    ACTION = "Use as master"
    HEADERS = ("Glyph", "Layer", "Renamed to")
    NO_FONT_TEXT = "Select a glyph first."
    NO_LAYER = "No backup or alternate layer in these glyphs."
    STATUS_REFUSALS = (NO_LAYER,)

    def build_controls(self, form: Any) -> None:
        self.stamp = datetime.now().astimezone().strftime(STAMP_FORMAT)
        self.layer = row(
            self.widget,
            form,
            "Layer",
            combo(self.widget, [], self.contain(self.redraw)),
        )

    def bind(self) -> None:
        super().bind()
        package = self.tool.shell.package()
        if package is None:
            return
        glyphs = [
            g
            for g in (package.findName(n) for n in self.names)
            if g is not None and not g.isNull
        ]
        chosen = str(get(self.layer.currentText))
        names = candidates(glyphs, [str(m) for m in package.masters])
        self.layer.blockSignals(True)
        self.layer.clear()
        for name in names:
            self.layer.addItem(name)
        if chosen in names:
            self.layer.setCurrentIndex(names.index(chosen))
        self.layer.blockSignals(False)

    def redraw(self) -> None:
        """A new list gets a new backup stamp; Apply writes the names the list shows."""
        self.stamp = datetime.now().astimezone().strftime(STAMP_FORMAT)
        super().redraw()

    def plan(self) -> list[dict[str, Any]]:
        package = self.bound()
        if not self.names:
            raise ValueError("Select a glyph first.")
        if get(self.layer.count) == 0:
            raise ValueError(self.NO_LAYER)
        return plan_layers(
            package, self.names, str(get(self.layer.currentText)), self.stamp
        )

    def rows(self, items: list[dict[str, Any]]) -> list[tuple]:
        return [
            (str(job["glyph"].name), old, (role, old, new))
            for job in items
            for role, old, new in job["steps"]
        ]

    def key(self, items: list[dict[str, Any]]) -> Any:
        return tuple(self.rows(items)), tuple(
            ident(t) for job in items for t in job["targets"].values()
        )

    def summary(self, items: list[dict[str, Any]]) -> str:
        return (
            f"{len(items)} glyph(s) will use “{get(self.layer.currentText)}” as master"
            if items
            else "Nothing to swap"
        )

    def write(self, items: list[dict[str, Any]]) -> str | None:
        captured = apply_renames(
            self.tool,
            items,
            undo_label("use as master", [j["glyph"].name for j in items]),
        )
        if captured is None:
            return None
        return append_note("; ".join(f"{job['glyph'].name}: '{job['steps'][-1][1]}' is now the master layer"
                                     for job in items), captured)  # fmt: skip


__all__ = ["STAMP_FORMAT", "TITLE", "UseMasterPanel", "apply_renames", "candidates", "mask_name_for", "plan_layers",
           "plan_swap"]  # fmt: skip
