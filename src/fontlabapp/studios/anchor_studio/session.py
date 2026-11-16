# this_file: src/fontlabapp/studios/anchor_studio/session.py
# SPDX-License-Identifier: Apache-2.0
"""Anchor Studio state: native layer reads, anchor plans and one-step writes.

What: ``Studio`` keeps the glyph list, the preview master and the last plan.
``plan`` reads each named glyph's explicit layer on the chosen masters
(``flGlyph.findLayer``; never ``fgGlyph``), snapshots its anchors into
``model.Facts`` and runs a planner. Missing, auto, empty-planner and hinted
layers are skipped with a note. ``apply`` builds every native pin first, then
writes all pending layers through ``AppShell.history`` as one
``"Anchor Studio: <action> <subject>"`` Undo step on those explicit layers,
reads every layer back and checks it with ``model.verify``: a move beyond
``model.TOLERANCE`` or a sub-unit move that FontLab rounded to no change is
reported as "Partly applied", never as success (Scriptmix TODO:78).
Why: Contract §1.3/§1.4. Hinted layers stay refused until the user runs
"Remove PostScript hints", the shared Issue 241 remover (``fontui.remove_hints``).
Read-only paths (``plan``, ``census``, ``cloud``, ``rings``, ``optical``)
never open history. Used by ``fontlabapp.studios.anchor_studio.tabs``.
"""

from collections.abc import Callable, Sequence
from time import monotonic
from typing import Any, NamedTuple

import fontlabapp.fontui as fontui
from fontlabapp.studios._kerning_ui import get

from . import APP, model
from .model import Change, Facts, Pin

NO_FONT = "Open a font first."
NO_GLYPHS = "Choose glyphs first: type names or use the font selection."
MISSING_NOTE = "no layer in this master"
AUTO_NOTE = "auto layer, skipped"
HINT_NOTE = " Use Remove PostScript hints first."
ROUNDING_NOTE = "Check Preferences > Rounding."


class Row(NamedTuple):
    """One glyph layer of a plan: its anchors before, its changes and a skip note."""

    glyph: str
    master: str
    facts: Facts | None
    changes: tuple[Change, ...]
    note: str

    @property
    def edits(self) -> list[tuple]:
        return [change.edit for change in self.changes if change.edit is not None]

    @property
    def blocked(self) -> bool:
        return any(change.problem for change in self.changes)


def _selection() -> list[str]:
    from fontlabapp.core.scripting import names_selected_names

    return names_selected_names()


def _font_names() -> list[str]:
    from fontlabapp.core.scripting import names_font_glyphs

    return [str(name) for name, _ in names_font_glyphs()]


def _metrics(package: Any, master: str) -> Any:
    import fontlab

    return fontlab.FontMetrics(package, master)


def pins_of(layer: Any) -> tuple[Pin, ...]:
    """The layer's anchors as ``Pin`` tuples, in native order."""
    return tuple(Pin(str(pin.name), float(pin.point.x()), float(pin.point.y())) for pin in layer.anchors)


def facts_of(layer: Any) -> Facts:
    box = layer.boundingBox
    empty = box.width() <= 0 and box.height() <= 0
    ink = None if empty else (box.x(), box.y(), box.x() + box.width(), box.y() + box.height())
    return Facts(pins_of(layer), ink, float(layer.advanceWidth))


def layer_rings(layer: Any) -> list[list[tuple[float, float]]]:
    """Closed polygons of the outline with component transforms (PythonQt ``QPolygonF`` is read by index)."""
    from PythonQt import QtGui

    path = QtGui.QPainterPath()
    for shape in layer.shapes:
        part = QtGui.QPainterPath()
        for contour in shape.getContours():
            part.addPath(contour.path())
        path.addPath(shape.transform.map(part))
    rings = []
    for polygon in path.toSubpathPolygons():
        points = [(polygon.at(i).x(), polygon.at(i).y()) for i in range(polygon.size())]
        if len(points) > 1 and points[0] == points[-1]:
            points.pop()
        if len(points) >= 3:
            rings.append(points)
    return rings


def point(x: float, y: float) -> Any:
    from PythonQt import QtCore

    return QtCore.QPointF(float(x), float(y))


def new_pin(name: str, x: float, y: float) -> Any:
    """A native anchor pin with the name-derived appearance; built before history opens."""
    import fontlab

    pin = fontlab.flPinPoint(point(x, y))
    pin.name, pin.anchor = name, True
    pin.appearance = model.APPEARANCE.get(name.lower(), 0)
    return pin


def prepare(layer: Any, edits: Sequence[tuple]) -> list[tuple[str, Any, Any]]:
    """Native steps ``(step, pin, value)`` for ``edits``; every pin and point exists before the write."""
    pins = list(layer.anchors)
    steps = []
    for edit in edits:
        if edit[0] == "set":
            same = [pin for pin in pins if str(pin.name) == edit[1]]
            x, y = edit[2]
            steps.append(("move", same[0], point(x, y)) if same else ("add", None, new_pin(edit[1], x, y)))
        elif edit[0] == "remove":
            steps.append(("remove", pins[edit[1]], None))
        else:
            steps.append(("rename", pins[edit[1]], edit[2]))
    return steps


def write(layer: Any, steps: Sequence[tuple[str, Any, Any]]) -> None:
    for step, pin, value in steps:
        if step == "add":
            layer.addAnchor(value)
        elif step == "move":
            pin.point = value
        elif step == "remove":
            layer.removeAnchor(pin)
        else:
            pin.name = value


class Studio:
    """Shared state of one Anchor Studio window; tabs subscribe with ``views``."""

    def __init__(
        self,
        shell: Any,
        *,
        font: Callable[[], Any] | None = None,
        selection: Callable[[], list[str]] | None = None,
        font_names: Callable[[], list[str]] | None = None,
        metrics: Callable[[Any, str], Any] | None = None,
        rings: Callable[[Any], list] | None = None,
    ) -> None:
        self.shell = shell
        self._font = font or fontui.current_font
        self._selection = selection or _selection
        self._font_names = font_names or _font_names
        self._metrics = metrics or _metrics
        self._rings = rings or layer_rings
        self.masters: list[str] = []
        self.current: str | None = None
        self.master: str | None = None
        self.glyphs: list[str] = []
        self.rows: list[Row] = []
        self.views: list[Callable[[], None]] = []
        self.preview: Any = None
        self.status = ""

    def say(self, text: str) -> None:
        self.status = text
        self.shell.set_status(text)

    # Reads -----------------------------------------------------------------
    def font(self) -> Any:
        return self._font()

    def reload(self) -> None:
        """Re-read the masters (no writes), then refresh every view."""
        package = self.shell.package()
        if package is None:
            self.masters, self.current = [], None
            self.say(NO_FONT)
        else:
            self.masters = [str(name) for name in package.masters]
            self.current = str(package.master)
        if self.master not in self.masters:
            self.master = self.current
        self._refresh()

    def choose_master(self, name: str | None) -> None:
        self.master = name
        self.show_glyph(self.glyphs[0] if self.glyphs else None)

    def show_glyph(self, name: str | None) -> None:
        """Load ``name`` on the chosen master in the TGlyph preview (read-only)."""
        if self.preview is not None and name and self.master:
            self.preview.load(name, self.master)

    def set_glyphs(self, names: Sequence[str]) -> None:
        self.glyphs = list(dict.fromkeys(n for n in names if n))

    def use_selection(self) -> list[str]:
        self.set_glyphs(self._selection())
        return self.glyphs

    def font_glyphs(self) -> list[str]:
        """Every glyph name of the font, for the "Whole font" scope."""
        self.package()
        return self._font_names()

    def package(self) -> Any:
        package = self.shell.package()
        if package is None:
            raise ValueError(NO_FONT)
        return package

    def native_glyph(self, name: str) -> Any:
        glyph = self.package().findName(name)
        if glyph is None or getattr(glyph, "isNull", False):
            raise ValueError(f"Glyph {name} is not in the font.")
        return glyph

    def layer(self, name: str, master: str) -> Any:
        """The live layer of ``name`` on ``master``, or None."""
        layer = self.native_glyph(name).findLayer(master)
        return None if layer is None or getattr(layer, "isNull", False) else layer

    def targets(self, all_masters: bool) -> list[str]:
        if not self.masters or self.master is None:
            raise ValueError(NO_FONT)
        return list(self.masters) if all_masters else [self.master]

    def _names(self, names: Sequence[str] | None) -> list[str]:
        chosen = list(names) if names is not None else list(self.glyphs)
        if not chosen:
            raise ValueError(NO_GLYPHS)
        return chosen

    def metric(self, master: str, attribute: str | None) -> int:
        return model.metric_value(None if attribute is None else self._metrics(self.package(), master), attribute)

    def italic_angle(self) -> float:
        return float(getattr(self.package(), "italicAngle_value", 0) or 0)

    # Planning (read-only) ----------------------------------------------------
    def plan(self, planner: model.Planner, names: Sequence[str] | None = None, *, all_masters: bool = False,
             masters: Sequence[str] | None = None) -> list[Row]:  # fmt: skip
        """Plan ``planner(name, facts, layer, master)`` for each glyph layer; skipped layers carry a note."""
        chosen = self._names(names)
        targets = list(masters) if masters is not None else self.targets(all_masters)
        rows = []
        for name in chosen:
            self.native_glyph(name)
            for master in targets:
                layer = self.layer(name, master)
                if layer is None:
                    rows.append(Row(name, master, None, (), MISSING_NOTE))
                    continue
                facts = facts_of(layer)
                if layer.autoLayer:
                    rows.append(Row(name, master, facts, (), AUTO_NOTE))
                    continue
                result = planner(name, facts, layer, master)
                if isinstance(result, str):
                    rows.append(Row(name, master, facts, (), result))
                    continue
                note = ""
                if any(change.edit for change in result):
                    hinted = fontui.layer_is_hinted(layer)
                    note = hinted.text() + HINT_NOTE if hinted else ""
                rows.append(Row(name, master, facts, tuple(result), note))
        self.rows = rows
        return rows

    def census(self, names: Sequence[str] | None = None, *, all_masters: bool = False) -> dict[str, list[int]]:
        """Anchor names over the chosen layers with editable/auto layer counts."""
        rows = []
        for name in self._names(names):
            for master in self.targets(all_masters):
                layer = self.layer(name, master)
                if layer is not None:
                    rows.append((pins_of(layer), bool(layer.autoLayer)))
        return model.census(rows)

    def optical(self, layer: Any) -> int | str:
        """Optical x of ``layer`` within the per-layer time budget, or the reason it failed."""
        try:
            return model.estimate_rings(self._rings(layer), monotonic() + model.OPTICAL_BUDGET)
        except (ValueError, TimeoutError, RuntimeError, TypeError) as error:
            return str(error)

    def cloud(self, anchor: str, names: Sequence[str] | None = None) -> tuple[dict[str, Any], list[tuple[str, str, float, float]]]:
        """The ``anchor`` cloud on every master, as Cloud View drew it per master.

        Returns one overlay per master (faint outlines plus a marker per anchor)
        and every hit as ``(glyph, master, x, y)``. Reads only.
        """
        self.targets(False)
        chosen = self._names(names)
        overlays, points = {}, []
        for master in self.masters:
            contours, hits = [], []
            for name in chosen:
                layer = self.layer(name, master)
                if layer is None:
                    continue
                found = [(name, master, pin.x, pin.y) for pin in pins_of(layer) if pin.name == anchor]
                if found:
                    contours.extend(model.outline(self._rings(layer)))
                    hits.extend(found)
            contours.extend(model.marker(x, y, 6) for _, _, x, y in hits)
            overlays[master] = model.Overlay(tuple(contours))
            points.extend(hits)
        return overlays, points

    def anchor_rows(self, names: Sequence[str] | None = None) -> list[tuple[str, str, str, float, float]]:
        """Every anchor of the glyph list on every master: ``(glyph, master, anchor, x, y)``. Reads only."""
        self.targets(False)
        rows = []
        for name in self._names(names):
            for master in self.masters:
                layer = self.layer(name, master)
                if layer is not None:
                    rows.extend((name, master, pin.name, pin.x, pin.y) for pin in pins_of(layer))
        return rows

    def rings(self, name: str, size: int, names: Sequence[str] | None = None) -> tuple[Any, list[tuple[str, str, Pin]]]:
        """Rings around stacked anchors of ``name`` and every stacked anchor of the glyph list."""
        master = self.targets(False)[0]
        found = []
        overlay = model.Overlay(())
        for glyph in self._names(names):
            layer = self.layer(glyph, master)
            if layer is None:
                continue
            pins = pins_of(layer)
            found.extend((glyph, master, pin) for group in model.stacked(pins) for pin in group)
            if glyph == name:
                overlay = model.rings_overlay(pins, size)
        return overlay, found

    # Writes ----------------------------------------------------------------
    def apply(self, action: str, planner: model.Planner, names: Sequence[str] | None = None, *,
              all_masters: bool = False, masters: Sequence[str] | None = None, allow_bases: bool = False) -> bool:  # fmt: skip
        """Plan, then write every changed layer as one ``"Anchor Studio: <action> <subject>"`` step."""
        try:
            rows = self.plan(planner, names, all_masters=all_masters, masters=masters)
        except (ValueError, KeyError, TypeError, TimeoutError, RuntimeError) as error:
            self.say(f"{APP}: {error}")
            return False
        blocked = [row for row in rows if row.blocked]
        if blocked:
            first = next(change.problem for change in blocked[0].changes if change.problem)
            self.say(f"{APP}: refused. {blocked[0].glyph} ({blocked[0].master}): {first}")
            self._refresh()
            return False
        pending = [row for row in rows if row.edits and not row.note]
        skipped = [f"{row.glyph} ({row.master}): {row.note}" for row in rows if row.note and row.edits]
        if not pending:
            self.say(f"{APP}: no change." + (" Skipped: " + " ".join(skipped) if skipped else ""))
            self._refresh()
            return False
        label = f"{APP}: {action} {model.subject([row.glyph for row in pending])}"
        try:
            layers = [self.layer(row.glyph, row.master) for row in pending]
            glyphs = list({row.glyph: self.native_glyph(row.glyph) for row in pending}.values())
            steps = [prepare(layer, row.edits) for row, layer in zip(pending, layers)]
        except (ValueError, KeyError, TypeError, IndexError, RuntimeError) as error:
            self.say(f"{APP}: {error}")
            return False

        def mutate() -> None:
            for layer, layer_steps in zip(layers, steps):
                write(layer, layer_steps)

        def read_back() -> list[str]:
            problems = []
            for row, layer in zip(pending, layers):
                problems += model.verify(f"{row.glyph} ({row.master})", row.facts.pins, row.edits, pins_of(layer))  # type: ignore[union-attr]
            return problems

        committed = self.shell.history(label, glyphs, mutate, layers=layers, read_back=read_back, allow_bases=allow_bases)
        if committed is None:
            self._refresh()
            return False
        mismatches = list(getattr(committed, "mismatches", ()) or ())
        if mismatches:
            self.say(f"Partly applied: {label}. " + "; ".join(mismatches) + f". {ROUNDING_NOTE}")
        elif skipped:
            self.say(f"{self.shell_status()} Skipped: " + " ".join(skipped))
        if self.preview is not None:
            self.preview.refresh()
        self._refresh()
        return not mismatches

    def shell_status(self) -> str:
        status = getattr(self.shell, "status", None)
        return str(get(status.text)) if hasattr(status, "text") else self.status

    def _refresh(self) -> None:
        for view in list(self.views):
            view()

    def remove_hints(self, names: Sequence[str] | None = None, *, all_masters: bool = False) -> int:
        """Remove PostScript hints from the chosen layers: one ``"Anchor Studio: remove hints <glyph>"`` step each."""
        try:
            chosen, targets = self._names(names), self.targets(all_masters)
            removed = 0
            for name in chosen:
                glyph = self.native_glyph(name)
                for master in targets:
                    layer = self.layer(name, master)
                    if layer is None or not fontui.layer_is_hinted(layer).ps_hints:
                        continue
                    state = fontui.remove_hints(layer, f"{APP}: remove hints {name}", glyph=glyph, commit=self._commit)
                    removed += 0 if state.ps_hints else 1
        except (ValueError, KeyError, TypeError, RuntimeError) as error:
            self.say(f"{APP}: {error}")
            return 0
        if not removed:
            self.say(f"{APP}: no PostScript hints removed.")
        self._refresh()
        return removed

    def _commit(self, label: str, layers: list[Any], glyphs: list[Any], mutate: Any, read_back: Any) -> Any:
        return self.shell.history(label, glyphs, mutate, layers=layers, read_back=read_back)

    # Planner factories -----------------------------------------------------
    def bounds_planner(self, wanted: Sequence[tuple[str, str, float]]) -> model.Planner:
        if not wanted:
            raise ValueError("Tick at least one anchor.")
        return lambda name, facts, layer, master: model.bounds_changes(facts, wanted)

    def centre_planner(self, anchors: Sequence[str], reference: str, fraction: float, angle: float) -> model.Planner:
        if not anchors:
            raise ValueError("Type the anchor names to centre.")
        return lambda name, facts, layer, master: model.centre_changes(facts, anchors, reference, fraction, angle)

    def snap_planner(self, anchors: Sequence[str], attribute: str | None, offset: float) -> model.Planner:
        if not anchors:
            raise ValueError("Type the anchor names to snap.")

        def plan(name: str, facts: Facts, layer: Any, master: str) -> list[Change]:
            return model.snap_changes(facts, anchors, self.metric(master, attribute) + offset)

        return plan

    def round_planner(self, step: int, do_x: bool, do_y: bool, anchors: Sequence[str]) -> model.Planner:
        model.round_changes(Facts((), None, 0), step, do_x, do_y, ())  # validate the controls at once
        return lambda name, facts, layer, master: model.round_changes(facts, step, do_x, do_y, anchors)

    def optical_planner(self) -> model.Planner:
        return lambda name, facts, layer, master: model.optical_changes(facts, self.optical(layer))

    def rename_planner(self, find: str, replace: str, regex: bool) -> model.Planner:
        rename = model.renamer(find, replace, regex)
        return lambda name, facts, layer, master: model.rename_changes(facts, rename)

    def delete_planner(self, anchors: Sequence[str]) -> model.Planner:
        if not anchors:
            raise ValueError("Tick the names to delete.")
        return lambda name, facts, layer, master: model.delete_changes(facts, anchors)

    def duplicates_planner(self, coincident: bool) -> model.Planner:
        return lambda name, facts, layer, master: model.duplicate_changes(facts, coincident)

    def extraneous_planner(self) -> model.Planner:
        return lambda name, facts, layer, master: model.opposite_changes(facts)


__all__ = ["NO_FONT", "NO_GLYPHS", "Row", "Studio", "facts_of", "layer_rings", "pins_of", "prepare", "write"]
