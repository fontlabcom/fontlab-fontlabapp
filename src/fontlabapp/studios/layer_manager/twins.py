# this_file: src/fontlabapp/studios/layer_manager/twins.py
# SPDX-License-Identifier: Apache-2.0
"""Twins tab: the Scriptmix "Master Twins" (Scripts/Masters/).

Copy the chosen content kinds (contours, components, anchors, metrics)
of the selected glyphs, or all glyphs, from one master layer to another.
The planning, component-graph check and ``CopyContent`` editor are the
original's, verbatim: refused pairs are listed as "kept: <reason>" and
removed components keep their history alive (``retain``). Copy plans
again, refuses a plan that differs from the list, and writes every target
layer as ONE ``Layer Manager: copy twins <subject>`` Undo step through
``AppShell.history`` (prepare before history, write and settle inside,
read back after), as ``contours.writer.apply_work`` did.
"""

import math
from dataclasses import dataclass
from time import monotonic
from typing import Any

from PythonQt import QtGui

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native

from .._kerning_ui import check, combo, get, row
from ._shared import (
    Modules,
    PlanTab,
    append_note,
    apply_editor,
    ident,
    label as undo_label,
)

contour_copy = Modules("contour_copy")
anchors = Modules("anchors")
outlines = Modules("outlines")
selection = Modules("selection")
catalog = Modules("catalog")


TITLE, KEY = "Master Twins", "masters_master_twins"
METRICS = ("advanceWidth", "metricsLeft", "metricsRight", "metricsWidth")


@dataclass(frozen=True)
class Content:
    """Independent switches for the content kinds supported by this tool."""

    contours: bool = True
    components: bool = True
    anchors: bool = True
    metrics: bool = True


def shape_copy(shape: Any, master: str) -> Any:
    """Copy names, note and transform; shared helper restores node names/flags."""

    cloned = shape.clone()
    cloned.name = shape.name
    cloned.shapeData.name = shape.shapeData.name
    cloned.shapeData.note = shape.shapeData.note
    cloned.transform = shape.transform
    cloned.active = cloned.selected = False
    if shape.isComponent:
        cloned.shapeData.componentLayer = master
    else:
        for before, after in zip(shape.contours, cloned.contours, strict=True):
            contour_copy.repair_nodes(before, after)
    return cloned


def shape_problem(shape: Any) -> str:
    """Refuse shared data and known contour/node fields outside the copy contract."""
    if int(shape.shapeData.referenceCount) > 1:
        return "shared shape data"
    if not shape.isComponent:
        for contour in shape.contours:
            if contour.name:
                return "contour name is not copied"
            for node in contour.nodes():
                if node.getProperty("corner_smooth") is not None:
                    return "explicit corner_smooth is not copied"
    return ""


def anchor_edits(source: Any, target: Any) -> list[tuple[str, str, Any]]:
    """Plan a full anchor replacement through the public anchor writer."""

    for layer in (source, target):
        if anchors.duplicated(layer, [str(pin.name) for pin in layer.anchors]):
            raise ValueError("Duplicate anchor names; make the names unique first.")
    before, after = anchors.anchor_points(target), anchors.anchor_points(source)
    if any(not all(math.isfinite(v) for v in point) for point in after.values()):
        raise ValueError("Anchor positions must be finite.")
    for name, point in after.items():
        if name in before and point == (0.0, 0.0) and before[name] != point:
            raise ValueError(
                f"Anchor {name} would move to the origin; choose another layer."
            )
    return [("remove", n, None) for n in before if n not in after] + [
        ("set", n, point) for n, point in after.items() if before.get(n) != point
    ]


def layer_problem(layer: Any, outlines: bool = True) -> str:
    """Explain why a body layer is not a supported copy source or target."""
    if layer is None or layer.isNull:
        return "missing layer"
    if layer.autoLayer or layer.isMaskLayer or layer.isService:
        return "automatic, mask or service layer"
    if layer.isLocked:
        return "locked layer"
    if outlines and (layer.hasHints or layer.hasTTH):
        return "PostScript/TrueType hints; contour replacement kept"
    if not math.isfinite(float(layer.advanceWidth)):
        return "nonfinite advance width"
    return ""


def copy_work(
    package: Any,
    names: list[str],
    source: str,
    target: str,
    content: Content,
    facts: Any,
    kept: list[tuple[str, str]] | None = None,
) -> list[Any]:
    """Check every pair before history. Return (glyph, layer, [source/options])."""

    if (
        source == target
        or source not in package.masters
        or target not in package.masters
    ):
        raise ValueError("Choose two different masters.")
    if not any(
        (content.contours, content.components, content.anchors, content.metrics)
    ):
        raise ValueError("Choose at least one content kind.")
    if not names:
        raise ValueError("Select glyphs or choose All glyphs.")
    work = []
    notes = kept if kept is not None else []
    for name in dict.fromkeys(names):
        try:
            glyph = package.findName(name)
            if glyph is None or glyph.isNull:
                raise ValueError("missing glyph")
            old, new = glyph.findLayer(source), glyph.findLayer(target)
            reason = (
                history.refusal(facts, name, "geometry")
                or layer_problem(old, content.contours)
                or layer_problem(new, content.contours)
            )
            if reason:
                raise ValueError(reason)
            if content.anchors:
                anchor_edits(old, new)
            for layer in (old, new):
                for shape in layer.shapes:
                    chosen = (
                        content.components if shape.isComponent else content.contours
                    )
                    if chosen and (problem := shape_problem(shape)):
                        raise ValueError(problem)
            if content.components:
                for shape in old.shapes:
                    if not shape.isComponent:
                        continue
                    base = package.findName(str(shape.shapeData.componentGlyph))
                    if (
                        base is None
                        or base.isNull
                        or base.name == name
                        or layer_problem(base.findLayer(target), False)
                    ):
                        raise ValueError(
                            "component base absent, self-referencing or not editable"
                        )
            work.append((glyph, new, [(old, content)]))
        except ValueError as error:
            notes.append((name, str(error)))
    if content.components:
        # Dropping one replacement can expose a cycle through the kept layer.
        while work:
            bad = []
            for job in work:
                try:
                    check_component_graph(package, work, target, [str(job[0].name)])
                except ValueError as error:
                    notes.append((str(job[0].name), str(error)))
                    bad.append(job)
            if not bad:
                break
            work = [job for job in work if job not in bad]
    return work


def check_component_graph(
    package: Any, work: list[Any], master: str, roots: list[str]
) -> None:
    """Refuse any component cycle reachable after the planned replacement."""
    replacements = {str(glyph.name): edits[0][0] for glyph, _, edits in work}
    done: set[str] = set()
    deadline = monotonic() + 2.0
    for start in roots:
        stack: list[tuple[str, bool]] = [(start, False)]
        visiting: set[str] = set()
        while stack:
            if monotonic() > deadline:
                raise TimeoutError("Component check timed out; no layers were changed.")
            name, leaving = stack.pop()
            if leaving:
                visiting.remove(name)
                done.add(name)
                continue
            if name in visiting:
                raise ValueError(f"Component cycle through {name} in {master}.")
            if name in done:
                continue
            glyph = package.findName(name)
            layer = (
                replacements.get(name)
                if name in replacements
                else glyph.findLayer(master)
                if glyph is not None
                else None
            )
            if layer is None or layer.isNull or layer.autoLayer:
                raise ValueError(
                    f"Component base {name} is missing or automatic in {master}."
                )
            visiting.add(name)
            stack.append((name, True))
            stack.extend(
                (str(s.shapeData.componentGlyph), False)
                for s in layer.shapes
                if s.isComponent
            )


def editor_type() -> type:
    """Use the shared geometry and anchor kernels for one history action."""

    class CopyContent(outlines.Editor):
        """Stage copies before history and keep removed component history alive."""

        def prepare(self, layer: Any, edits: list[Any]) -> list[Any]:
            source, options = edits[0]

            def chosen(shape: Any) -> bool:
                return options.components if shape.isComponent else options.contours

            removed = [shape for shape in layer.shapes if chosen(shape)]
            added = [
                shape_copy(shape, str(layer.name))
                for shape in source.shapes
                if chosen(shape)
            ]
            pins = (
                anchors.prepare(layer, anchor_edits(source, layer))
                if options.anchors
                else []
            )
            metrics = (
                {key: getattr(source, key) for key in METRICS}
                if options.metrics
                else {}
            )
            return [(removed, added, pins, metrics)]

        def retain(self, steps: list[Any]) -> list[Any]:
            return [
                item
                for removed, _, _, _ in steps
                for shape in removed
                for item in history.component_history(shape)
            ]

        def write(self, layer: Any, steps: list[Any]) -> None:
            for removed, added, pins, metrics in steps:
                for shape in removed:
                    layer.removeShape(shape)
                for shape in added:
                    layer.addShape(shape)
                anchors.write(layer, pins)
                for key, value in metrics.items():
                    setattr(layer, key, value)

        def check(self, prepared: list[Any]) -> list[str]:
            errors = []
            for layer, steps in prepared:
                for removed, added, pins, metrics in steps:
                    stored = {shape.id for shape in layer.shapes}
                    if any(s.id in stored for s in removed) or any(
                        s.id not in stored for s in added
                    ):
                        errors.append(f"{layer.name}: shape replacement")
                    if any(getattr(layer, k) != v for k, v in metrics.items()):
                        errors.append(f"{layer.name}: metrics")
                    points = anchors.anchor_points(layer)
                    for action, pin, value in pins:
                        if action == "remove" and str(pin.name) in points:
                            errors.append(f"{layer.name}: anchor removal")
                        if action in ("move", "add"):
                            name = str(pin.name if action == "move" else value.name)
                            point = value if action == "move" else value.point
                            if points.get(name) != (float(point.x()), float(point.y())):
                                errors.append(f"{layer.name}: anchor {name}")
            return errors

    return CopyContent


class TwinsPanel(PlanTab):
    """From, To, All glyphs and the four content switches, the copy/kept table, Refresh and Copy."""

    ACTION = "Copy"
    RESELECT = "Refresh"
    HEADERS = ("Glyph", "From", "To", "Action")
    NO_FONT_TEXT = "Open a font with at least two masters."
    CHANGED_TEXT = "The font changed; press Refresh."

    def build_controls(self, form: Any) -> None:
        self.from_master = row(
            self.widget, form, "From", combo(self.widget, [], self.contain(self.redraw))
        )
        self.to_master = row(
            self.widget, form, "To", combo(self.widget, [], self.contain(self.redraw))
        )
        self.all_glyphs = check(
            self.widget, form, "All glyphs", False, self.contain(self.redraw)
        )
        line = QtGui.QHBoxLayout()
        form.addLayout(line)
        self.switches = [check(self.widget, line, t, True, self.contain(self.redraw))
                         for t in ("Contours", "Components", "Anchors", "Metrics")]  # fmt: skip
        self.kept_rows: list[tuple[str, str]] = []
        self.all_names: list[str] = []

    def selection(self) -> list[str]:
        """The captured layer selection's glyphs, as the original read them."""
        capture = selection.capture(monotonic() + 2.0)
        return list(dict.fromkeys(o.glyph_name for o in capture.occurrences))

    def bind(self) -> None:
        """Bind to the current font; retain master choices when possible."""
        self.package_id = None
        package = self.tool.shell.package()
        if package is None or len(package.masters) < 2:
            self.names = []
            return
        super().bind()
        self.all_names = [row[0] for row in catalog.capture().rows]
        masters = [str(m) for m in package.masters]
        for box in (self.from_master, self.to_master):
            box.blockSignals(True)
            previous = str(get(box.currentText))
            box.clear()
            for master in masters:
                box.addItem(master)
            if previous in masters:
                box.setCurrentIndex(masters.index(previous))
            box.blockSignals(False)
        if get(self.from_master.currentText) == get(self.to_master.currentText):
            self.to_master.setCurrentIndex(
                (get(self.from_master.currentIndex) + 1) % len(masters)
            )

    def plan(self) -> list[Any]:
        package = self.bound()
        names = self.all_names if get(self.all_glyphs.isChecked) else self.names
        self.kept_rows = []
        return copy_work(package, names, str(get(self.from_master.currentText)), str(get(self.to_master.currentText)),
                         Content(*(bool(get(s.isChecked)) for s in self.switches)),
                         history.scan_auto_facts(package), self.kept_rows)  # fmt: skip

    def rows(self, items: list[Any]) -> list[tuple]:
        done = [(str(g.name), str(layer.name), (str(edits[0][0].name), str(layer.name), "copy"))
                for g, layer, edits in items]  # fmt: skip
        return done + [
            (name, None, ("", "", f"kept: {reason}")) for name, reason in self.kept_rows
        ]

    def key(self, items: list[Any]) -> Any:
        return tuple(self.rows(items)), tuple(ident(layer) for _, layer, _ in items)

    def summary(self, items: list[Any]) -> str:
        return f"{len(items)} layers to copy · {len(self.kept_rows)} kept. Check master compatibility afterwards."

    def write(self, items: list[Any]) -> str | None:
        try:
            result = apply_editor(self.tool, undo_label("copy twins", [g.name for g, _, _ in items]), items,
                                  editor_type()())  # fmt: skip
        except RuntimeError as error:
            raise RuntimeError(
                str(error)
                + (
                    " Native changes may remain; use Edit > Undo"
                    if "use Edit > Undo" not in str(error)
                    else ""
                )
            ) from error
        if result is None:
            return None
        return append_note(f"Copied {result['layers']} layers.", result)


__all__ = ["METRICS", "TITLE", "Content", "TwinsPanel", "anchor_edits", "check_component_graph", "copy_work",
           "editor_type", "layer_problem", "shape_copy", "shape_problem"]  # fmt: skip
