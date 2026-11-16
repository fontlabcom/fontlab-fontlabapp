# this_file: src/fontlabapp/studios/align_nudge/tabs.py
# SPDX-License-Identifier: Apache-2.0
"""The four Align & Nudge tabs over the shared Transform Studio ``Tab`` scaffolding.

What: Align & distribute (eight operations, selected geometry or all nodes,
selection bounds or a typed coordinate), Interpolated nudge (x/y distances),
Overlap nodes (italic angle of each written master) and Simplify (alternate
selected nodes of the preview master, applied to the same structure on every
chosen master). Each tab has a "Preview …" button that fills the table and draws
the ghost without writing, and an apply button that writes one labelled step.
A planner error (conflicting tips, mismatched structures) becomes a row problem,
which refuses the whole write as the original scripts did.
Why: one window replaces four Scriptmix ``Scripts/Contours`` tools (Phase D A24).
"""

from collections.abc import Callable
from typing import Any

from fontlabapp.studios.transform_studio.geometry import Change
from fontlabapp.studios.transform_studio.session import Planner
from fontlabapp.studios.transform_studio.tabs import (
    Tab,
    _check,
    _combo,
    _dspin,
    _index,
    _number,
)

from . import model


def _safe(plan: Callable[[str, str, Any], Any]) -> Planner:
    """Wrap ``plan`` so a ValueError becomes a blocking problem row on that layer."""

    def planner(name: str, master: str, snap: Any) -> Any:
        try:
            return plan(name, master, snap)
        except ValueError as error:
            return [Change("selection", "", "", problem=str(error))]

    return planner


class AlignTab(Tab):
    """Scriptmix Align And Distribute."""

    BASES = False  # the original hid and cleared the bases opt-in

    def controls(self) -> None:
        line = self.line()
        self.operation = _combo(
            self.widget, line, "Operation", [label for label, _ in model.OPERATIONS], 0
        )
        self.geometry = _combo(self.widget, line, "Geometry", model.GEOMETRY, 0)
        line = self.line()
        self.reference = _combo(self.widget, line, "Align to", model.REFERENCES, 0)
        self.coordinate = _dspin(
            self.widget, line, "Coordinate", model.COORDINATE_RANGE, 0.0
        )
        self.operation.currentIndexChanged.connect(lambda *args: self.sync())
        self.reference.currentIndexChanged.connect(lambda *args: self.sync())
        self.sync()
        self.pair(self.line(), "alignment", self.planner, "align")

    def sync(self) -> None:
        """Distribution ignores the reference; the coordinate field is live only for "Coordinate"."""
        distribute = model.OPERATIONS[_index(self.operation)][1].startswith(
            "distribute_"
        )
        self.reference.setEnabled(not distribute)
        self.coordinate.setEnabled(not distribute and _index(self.reference) == 1)

    def planner(self) -> Planner:
        mode = model.OPERATIONS[_index(self.operation)][1]
        all_nodes = _index(self.geometry) == 1
        if mode.startswith("distribute_") and all_nodes:
            raise ValueError(model.DISTRIBUTE_ALL)
        coordinate = (
            _number(self.coordinate)
            if _index(self.reference) == 1 and not mode.startswith("distribute_")
            else None
        )
        return _safe(
            lambda name, master, snap: model.align_changes(
                snap, mode, all_nodes, coordinate
            )
        )


class NudgeTab(Tab):
    """Scriptmix Interpolated Nudge."""

    def controls(self) -> None:
        line = self.line()
        self.dx = _dspin(
            self.widget, line, "X nudge", model.NUDGE_RANGE, model.NUDGE_DEFAULT[0]
        )
        self.dy = _dspin(
            self.widget, line, "Y nudge", model.NUDGE_RANGE, model.NUDGE_DEFAULT[1]
        )
        self.pair(self.line(), "nudge", self.planner, "nudge")

    def planner(self) -> Planner:
        dx, dy = _number(self.dx), _number(self.dy)
        return _safe(lambda name, master, snap: model.nudge_changes(snap, dx, dy))


class OverlapTab(Tab):
    """Scriptmix Overlap Nodes: the italic angle comes from each written master."""

    BASES = False  # the original hid and cleared the bases opt-in

    def controls(self) -> None:
        line = self.line()
        self.angles = _check(self.widget, line, "Use each master’s italic angle", True)
        self.angles.setEnabled(
            False
        )  # informational: the original had no angle control
        self.pair(line, "overlap", self.planner, "overlap")

    def planner(self) -> Planner:
        cache: dict[str, float] = {}

        def plan(name: str, master: str, snap: Any) -> Any:
            if master not in cache:
                cache.update(self.studio.italic_angles([master]))
            return model.overlap_changes(snap, cache[master])

        return _safe(plan)


COMPATIBLE_LABEL = "Keep masters compatible"
DIFFER_NOTE = "masters would differ, kept"
SCOPE_NOTE = "other masters need it too; choose All masters"


class SimplifyTab(Tab):
    """Scriptmix Simplify Selected Nodes: the preview master's selection drives every chosen master.

    The original is structural: it opens with All masters on and "Keep masters
    compatible" ticked, and holds back a glyph whose masters would end up with
    different node structures (``fontlabapp.contours.writer.held_back``).
    """

    def controls(self) -> None:
        self.all_masters.setChecked(True)
        line = self.line()
        self.compatible = _check(self.widget, line, COMPATIBLE_LABEL, True)
        self.pair(line, "simplification", self.planner, "simplify")

    def planner(self) -> Planner:
        studio = self.studio
        compatible, every = bool(self.compatible.isChecked()), self.every_master()

        def changes(name: str, master: str, snap: Any) -> Any:
            reference = (
                snap
                if master == studio.master
                else studio.snapshot(name, studio.master)
            )
            if reference is None:
                return [Change("contours", "", "", problem=model.COUNTS)]
            return model.simplify_changes(snap, reference)

        def keys(name: str, master: str) -> tuple:
            snap = studio.snapshot(name, master)
            if snap is None:
                return ()
            try:
                rows = changes(name, master, snap)
            except ValueError as error:
                return (str(error),)
            return tuple(c.key for c in rows if c.edit and c.key)

        def plan(name: str, master: str, snap: Any) -> Any:
            rows = changes(name, master, snap)
            if compatible and any(c.edit for c in rows):
                found = {other: keys(name, other) for other in studio.masters}
                if len(set(found.values())) > 1:
                    return DIFFER_NOTE
                if not every:
                    return SCOPE_NOTE
            return rows

        return _safe(plan)


TAB_CLASSES = (("Align & distribute", AlignTab), ("Interpolated nudge", NudgeTab),
               ("Overlap nodes", OverlapTab), ("Simplify", SimplifyTab))  # fmt: skip

__all__ = ["COMPATIBLE_LABEL", "DIFFER_NOTE", "SCOPE_NOTE", "TAB_CLASSES", "AlignTab", "NudgeTab", "OverlapTab", "SimplifyTab"]
