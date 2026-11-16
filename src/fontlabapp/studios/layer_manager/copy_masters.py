# this_file: src/fontlabapp/studios/layer_manager/copy_masters.py
# SPDX-License-Identifier: Apache-2.0
"""Copy between masters tab: the Scriptmix "Copy Layer Between Masters" (Scripts/Masters/).

For each selected glyph, replace the contours of the checked target
master layers with repaired clones of the source master's contours;
optionally move same-named anchors to the source positions and set the
source advance width. Components of the targets stay. The planning
functions are the original's, verbatim: auto layers, glyphs refused by
the auto-glyph facts, locked layers, metrics links or expressions, a
source without outline, duplicated anchor names and anchors that would
move to 0, 0 (fl#8527) are listed and skipped. Copy plans again, refuses
a plan that differs from the list, and writes every target layer as one
``Layer Manager: copy layers <subject>`` Undo step through
``AppShell.history``, then reads contours, widths and anchors back.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from PythonQt import QtGui

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native

from .._kerning_ui import check, combo, get, row
from ._shared import (
    Modules,
    PlanTab,
    Qt,
    append_note,
    commit,
    ident,
    label as undo_label,
    result_dict,
)

contour_copy = Modules("contour_copy")
qt = Qt

TITLE = "Copy Layer Between Masters"
LINK_FIELDS = ("metricsLeft", "metricsRight", "metricsWidth")
MAX_NAMES = 8  # glyph names shown in the subtitle
Move = tuple[str, float, float]


@dataclass(frozen=True)
class Pair:
    """One source/target layer pair and its plan.

    ``moves``: (anchor name, x, y) for each target anchor that moves.
    ``missing``: source anchor names the target lacks. ``note`` is empty for
    a pair that will be copied; else it says why the pair is skipped.
    """

    glyph: Any
    master: str
    source: Any
    target: Any
    contours_now: int
    contours_after: int
    width_now: float
    width_after: float
    moves: tuple[Move, ...] = ()
    missing: tuple[str, ...] = ()
    note: str = ""


def _valid(layer: Any) -> bool:
    """True for a real native layer object."""
    return layer is not None and not layer.isNull


def outline_shapes(layer: Any) -> list[Any]:
    """Return the non-component shapes of ``layer`` that hold contours."""
    return [s for s in layer.shapes if not s.isComponent and len(s.contours)]


def contours_in(layer: Any) -> int:
    """Return the number of contours in the non-component shapes of ``layer``."""
    return sum(len(s.contours) for s in layer.shapes if not s.isComponent)


def clone_shape(shape: Any) -> Any:
    """Return a repaired clone of ``shape``. Raise RuntimeError on a lost contour."""

    copy = shape.clone()
    if len(copy.contours) != len(shape.contours):
        raise RuntimeError("FontLab clone changed the contour count of a shape.")
    contour_copy.restore_shape(shape, copy)
    return copy


def replace_outline(source: Any, target: Any) -> None:
    """Remove the non-component shapes of ``target``; add clones of the source outline."""
    for shape in [s for s in target.shapes if not s.isComponent]:
        target.removeShape(shape)
    for shape in outline_shapes(source):
        target.addShape(clone_shape(shape))


def _point(pin: Any) -> tuple[float, float]:
    """Stored anchor position, unrounded."""
    return float(pin.point.x()), float(pin.point.y())


def plan_anchors(
    source: Any, target: Any
) -> tuple[tuple[Move, ...], tuple[str, ...], str]:
    """Return (moves, missing names, problem) for same-named anchors.

    ``problem`` is empty, or says why the layer must be skipped.
    """
    for layer in (source, target):
        names = [str(pin.name) for pin in layer.anchors]
        twice = sorted({n for n in names if names.count(n) > 1})
        if twice:
            return (), (), f"several anchors named {', '.join(twice)} (skipped)"
    own = {str(pin.name): _point(pin) for pin in target.anchors}
    moves, missing = [], []
    for pin in source.anchors:
        name, where = str(pin.name), _point(pin)
        if name not in own:
            missing.append(name)
        elif own[name] != where:
            if where == (0.0, 0.0):
                return (
                    (),
                    (),
                    f"anchor {name} would move to 0, 0; FontLab cannot redo it (fl#8527)",
                )
            moves.append((name, *where))
    return tuple(moves), tuple(missing), ""


def has_metrics_link(layer: Any) -> bool:
    """True when a sidebearing or the width holds a link or an expression."""
    return any(str(getattr(layer, field)) for field in LINK_FIELDS)


def plan_pair(
    glyph: Any,
    master: str,
    source: Any,
    target: Any,
    anchors: bool,
    width: bool,
    reason: str,
) -> Pair:
    """Plan one pair. ``reason`` is the geometry refusal of the glyph, or ""."""
    now, after = contours_in(target), contours_in(source)
    base = Pair(
        glyph,
        master,
        source,
        target,
        now,
        after,
        target.advanceWidth,
        source.advanceWidth if width else target.advanceWidth,
    )
    note = ""
    if source.autoLayer or target.autoLayer:
        note = "auto layer (skipped)"
    elif reason:
        note = f"{reason} (skipped)"
    elif target.isLocked:
        note = "locked layer (skipped)"
    elif has_metrics_link(target):
        note = "metrics link or expression (skipped)"
    elif not outline_shapes(source):
        note = "source has no outline (skipped)"
    if note:
        return Pair(
            glyph,
            master,
            source,
            target,
            now,
            now,
            target.advanceWidth,
            target.advanceWidth,
            note=note,
        )
    if not anchors:
        return base
    moves, missing, problem = plan_anchors(source, target)
    if problem:
        return Pair(
            glyph,
            master,
            source,
            target,
            now,
            now,
            target.advanceWidth,
            target.advanceWidth,
            note=problem,
        )
    return Pair(
        base.glyph,
        master,
        source,
        target,
        now,
        after,
        base.width_now,
        base.width_after,
        moves,
        missing,
    )


def survey(
    package: Any, names: Sequence[str], source_master: str, targets: Sequence[str],
    anchors: bool, width: bool, facts: Any,
) -> list[Pair]:  # fmt: skip
    """Plan every glyph and target master. Change nothing.

    A glyph without a source layer or without a target layer gives no row.
    """

    pairs: list[Pair] = []
    for name in names:
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            continue
        source = glyph.findLayer(source_master)
        if not _valid(source):
            continue
        reason = history.refusal(facts, str(glyph.name), "geometry")
        for master in targets:
            target = glyph.findLayer(master)
            if master != source_master and _valid(target):
                pairs.append(
                    plan_pair(glyph, master, source, target, anchors, width, reason)
                )
    return pairs


def copy_pairs(
    tool: Any, pairs: Sequence[Pair], title: str = TITLE
) -> dict[str, Any] | None:
    """Write the planned pairs as ONE Undo step and read them back (the original's ``copy_pairs``).

    The original's mutate and read-back, verbatim; the step goes through
    ``tool.shell.history`` titled ``title`` (None when refused).
    """
    todo = [p for p in pairs if not p.note]
    missing = sorted({n for p in todo for n in p.missing})
    if not todo:
        return {
            "pending_updates": (),
            "pending_note": "",
            "layers": 0,
            "glyphs": 0,
            "contours": 0,
            "missing": missing,
            "mismatches": [],
        }
    glyphs = list({str(p.glyph.name): p.glyph for p in todo}.values())

    def mutate() -> None:
        for pair in todo:
            replace_outline(pair.source, pair.target)
            pins = {str(pin.name): pin for pin in pair.target.anchors}
            for name, x, y in pair.moves:
                pins[name].point = qt.QtCore.QPointF(x, y)
            if pair.width_after != pair.width_now:
                pair.target.advanceWidth = pair.width_after
            pair.target.changed()
            if pair.target.update() is False:
                raise RuntimeError(
                    f"FontLab could not update '{pair.glyph.name}' in '{pair.master}'."
                )

    def read_back() -> list[str]:
        found = []
        for pair in todo:
            label = f"{pair.glyph.name} · {pair.master}"
            count = contours_in(pair.target)
            if count != pair.contours_after:
                found.append(
                    f"{label}: {count} contours, planned {pair.contours_after}"
                )
            if pair.target.advanceWidth != pair.width_after:
                found.append(
                    f"{label}: width {pair.target.advanceWidth:g}, planned {pair.width_after:g}"
                )
            stored = {str(pin.name): _point(pin) for pin in pair.target.anchors}
            found.extend(
                f"{label}: anchor {name} at {stored.get(name)}, planned {(x, y)}"
                for name, x, y in pair.moves
                if stored.get(name) != (x, y)
            )
        return found

    done = commit(
        tool, title, [p.target for p in todo], glyphs, mutate, read_back=read_back
    )
    if done is None:
        return None
    return result_dict(done, layers=len(todo), glyphs=len(glyphs),
                       contours=sum(p.contours_after for p in todo), missing=missing)  # fmt: skip


def plural(count: int, word: str) -> str:
    """Return "1 layer" or "2 layers"."""
    return f"{count} {word}{'' if count == 1 else 's'}"


class CopyMastersPanel(PlanTab):
    """From, To, Anchors and Advance width, the per-target table, Use selection and Copy."""

    ACTION = "Copy"
    HEADERS = (
        "Glyph",
        "Target",
        "Contours now",
        "Contours after",
        "Width now",
        "Width after",
        "Note",
    )

    def build_controls(self, form: Any) -> None:
        self.source = row(
            self.widget,
            form,
            "From",
            combo(self.widget, [], self.contain(self.source_changed)),
        )
        line = QtGui.QHBoxLayout()
        form.addLayout(line)
        self.to_line = line
        self.target_checks: dict[str, Any] = {}
        also = QtGui.QHBoxLayout()
        form.addLayout(also)
        self.anchors = check(
            self.widget, also, "Anchors", True, self.contain(self.redraw)
        )
        self.copy_width = check(
            self.widget, also, "Advance width", True, self.contain(self.redraw)
        )
        self.masters: list[str] = []

    def bind(self) -> None:
        """Bind to the current font: its masters (the current one is the source) and selection."""
        super().bind()
        package = self.tool.shell.package()
        masters = [] if package is None else [str(m) for m in package.masters]
        if masters == self.masters:
            return
        self.masters = masters
        self.source.blockSignals(True)
        self.source.clear()
        for master in masters:
            self.source.addItem(master)
        if package is not None and str(package.master) in masters:
            self.source.setCurrentIndex(masters.index(str(package.master)))
        self.source.blockSignals(False)
        for box in self.target_checks.values():
            self.to_line.removeWidget(box)
            box.deleteLater()
        self.target_checks = {}
        for master in masters:
            self.target_checks[master] = check(
                self.widget, self.to_line, master, True, self.contain(self.redraw)
            )
        self.fill_targets()

    def source_master(self) -> str:
        return str(get(self.source.currentText))

    def fill_targets(self) -> None:
        """Disable the source checkbox; preserve the other checked choices."""
        for master, box in self.target_checks.items():
            box.setEnabled(master != self.source_master())

    def source_changed(self) -> None:
        """A source master cannot also be a target; changing it checks every other master again."""
        for box in self.target_checks.values():
            box.blockSignals(True)
            box.setChecked(True)
            box.blockSignals(False)
        self.fill_targets()
        self.redraw()

    def chosen_targets(self) -> list[str]:
        """Return the checked subset, in font order, excluding the source."""
        return [master for master, box in self.target_checks.items()
                if master != self.source_master() and get(box.isChecked)]  # fmt: skip

    def plan(self) -> list[Pair]:
        package = self.bound()
        if not self.names:
            raise ValueError(
                "Select glyphs in the Font window. Then press Use selection."
            )
        return survey(package, self.names, self.source_master(), self.chosen_targets(),
                      bool(get(self.anchors.isChecked)), bool(get(self.copy_width.isChecked)),
                      history.scan_auto_facts(package))  # fmt: skip

    def rows(self, items: list[Pair]) -> list[tuple]:
        return [
            (str(p.glyph.name), p.master, (p.master, "", "", "", "", p.note) if p.note else
             (p.master, p.contours_now, p.contours_after, f"{p.width_now:g}", f"{p.width_after:g}", ""))
            for p in items
        ]  # fmt: skip

    def key(self, items: list[Pair]) -> Any:
        return tuple(
            (ident(p.target), *self.rows([p])[0][2], p.moves, p.missing) for p in items
        )

    def ready_items(self, items: list[Pair]) -> bool:
        return any(not p.note for p in items)

    def summary(self, items: list[Pair]) -> str:
        todo = [p for p in items if not p.note]
        return (
            f"{plural(len(todo), 'layer')} will be replaced from {self.source_master()}"
            if todo
            else "Nothing to copy"
        )

    def write(self, items: list[Pair]) -> str | None:
        todo = [p for p in items if not p.note]
        result = copy_pairs(
            self.tool, items, undo_label("copy layers", [p.glyph.name for p in todo])
        )
        if result is None:
            return None
        text = f"Replaced {plural(result['layers'], 'layer')} in {plural(result['glyphs'], 'glyph')}"
        if result["missing"]:
            text += " · anchors missing in targets: " + ", ".join(result["missing"])
        if result["mismatches"]:
            text += " · did not read back as planned: " + "; ".join(
                result["mismatches"][:5]
            )
        return append_note(text, result)


__all__ = [
    "LINK_FIELDS", "TITLE", "CopyMastersPanel", "Pair", "clone_shape", "contours_in", "copy_pairs",
    "has_metrics_link", "outline_shapes", "plan_anchors", "plan_pair", "replace_outline", "survey",
]  # fmt: skip
