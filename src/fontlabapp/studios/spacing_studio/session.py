# this_file: src/fontlabapp/studios/spacing_studio/session.py
# SPDX-License-Identifier: Apache-2.0
"""Spacing Studio state: native layer reads, base-first plans and one-step writes.

What: ``Studio`` keeps the glyph list, the preview master and the last plan.
``plan`` reads each named glyph's explicit layer on the chosen masters
(``flGlyph.findLayer``; never a glyph-level pen or ``fgGlyph``), skips
missing, auto, metrics-linked and hinted layers with a note, and orders
bases before composites, dropping a composite whose base moves
(``model.order_plans``). ``apply`` writes every pending layer through
``AppShell.history`` as one ``"Spacing Studio: <action> <subject>"`` Undo
step on those explicit layers, then reads each layer back.
Why: Contract §1.3/§1.4 and App TODO:37/Scriptmix TODO:74 (no double shift).
Hinted layers stay refused until the user runs "Remove PostScript hints",
the shared Issue 241 remover (``fontui.remove_hints``), one Undo step per layer.
Used by ``fontlabapp.studios.spacing_studio.tabs``.
"""

from collections.abc import Callable, Sequence
from math import radians, tan
from typing import Any, NamedTuple

import fontlabapp.fontui as fontui
from fontlabapp.studios._kerning_ui import get

from . import APP, model
from .model import Metrics, Plan

NO_FONT = "Open a font first."
NO_GLYPHS = "Choose glyphs first: type names or use the font selection."
X_HEIGHT_FALLBACK = 500
TOLERANCE = 0.5


class Row(NamedTuple):
    """One glyph layer of a plan: its state before, the plan (None when skipped) and a note."""

    glyph: str
    master: str
    before: Metrics | None
    plan: Plan | None
    note: str


def _selection() -> list[str]:
    from fontlabapp.core.scripting import names_selected_names

    return names_selected_names()


def _users(package: Any) -> dict[str, set[str]]:
    import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - package __getattr__ is native

    return {base: set(names) for base, names in history.scan_auto_facts(package).users.items()}


def edges(layer: Any) -> tuple[float, float] | None:
    """The ink's left and right edge of a native layer, or None when it has no outline."""
    box = layer.boundingBox
    if box.width() <= 0 and box.height() <= 0:
        return None
    return box.x(), box.x() + box.width()


def has_metrics_link(layer: Any) -> bool:
    return any(str(getattr(layer, field, "") or "") for field in ("metricsLeft", "metricsRight", "metricsWidth"))


def italic_edges(layer: Any, angle: float, pivot: float) -> tuple[float, float] | None:
    """De-slanted ink edges: the outline with component transforms, sheared upright around ``pivot``."""
    from PythonQt import QtGui

    path = QtGui.QPainterPath()
    for shape in layer.shapes:
        part = QtGui.QPainterPath()
        for contour in shape.getContours():
            part.addPath(contour.path())
        path.addPath(shape.transform.map(part))
    if path.isEmpty():
        return None
    slope = tan(radians(angle))
    box = QtGui.QTransform(1, 0, slope, 1, -pivot * slope, 0).map(path).boundingRect()
    return box.x(), box.x() + box.width()


def shift_and_set(layer: Any, plan: Plan) -> None:
    """Move the layer's outline, components and anchors by ``plan.dx``, then set its advance."""
    if plan.dx:
        from PythonQt import QtGui

        layer.applyTransform(QtGui.QTransform(1, 0, 0, 1, plan.dx, 0))
        layer.changed()
        if layer.update() is False:
            raise RuntimeError("FontLab could not update the layer geometry.")
    layer.advanceWidth = plan.width


class Studio:
    """Shared state of one Spacing Studio window; tabs subscribe with ``views``."""

    def __init__(
        self,
        shell: Any,
        *,
        font: Callable[[], Any] | None = None,
        selection: Callable[[], list[str]] | None = None,
        users: Callable[[Any], dict[str, set[str]]] | None = None,
    ) -> None:
        self.shell = shell
        self._font = font or fontui.current_font
        self._selection = selection or _selection
        self._users = users or _users
        self.masters: list[str] = []
        self.current: str | None = None
        self.master: str | None = None
        self.glyphs: list[str] = []
        self.rows: list[Row] = []
        self.views: list[Callable[[], None]] = []
        self.preview: Any = None
        self.preview_factory: Any = None
        self.status = ""

    def say(self, text: str) -> None:
        self.status = text
        self.shell.set_status(text)

    # Reads -----------------------------------------------------------------
    def font(self) -> Any:
        return self._font()

    def reload(self, *, preserve: bool = False) -> None:
        """Read the captured font; preserving refresh never retargets controls."""
        package = self.shell.package()
        if package is None:
            self.masters, self.current = [], None
            self.say(NO_FONT)
        else:
            masters = [str(name) for name in package.masters]
            if preserve and self.master is not None:
                missing = [name for name in self.masters if name not in masters]
                if self.master not in masters or missing:
                    raise ValueError("A captured master was removed; reopen this tool.")
                self.masters = list(self.masters) or masters
            else:
                self.masters = masters
                self.current = str(package.master)
        if self.preview is None and self.preview_factory is not None:
            self.font()
            self.preview = self.preview_factory()
            if self.preview is not None:
                self.shell.set_preview(self.preview)
        if self.master not in self.masters:
            self.master = self.current
        if not preserve:
            for view in list(self.views):
                view()

    def choose_master(self, name: str | None) -> None:
        """Show ``name`` in the preview and make it the master that writes and reads use."""
        self.master = name
        if self.preview is not None and name:
            self.preview.set_layer(name)

    def set_glyphs(self, names: Sequence[str]) -> None:
        self.glyphs = list(dict.fromkeys(n for n in names if n))

    def use_selection(self) -> list[str]:
        """Take the Font window selection (else the current glyph) as the glyph list."""
        self.set_glyphs(self._selection())
        return self.glyphs

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

    def metrics(self, name: str, master: str) -> Metrics | None:
        layer = self.layer(name, master)
        return None if layer is None else model.measure(edges(layer), layer.advanceWidth)

    def targets(self, all_masters: bool) -> list[str]:
        if not self.masters or self.master is None:
            raise ValueError(NO_FONT)
        return list(self.masters) if all_masters else [self.master]

    def _names(self, names: Sequence[str] | None) -> list[str]:
        chosen = list(names) if names is not None else list(self.glyphs)
        if not chosen:
            raise ValueError(NO_GLYPHS)
        return chosen

    # Planning --------------------------------------------------------------
    def plan(self, planner: model.Planner, names: Sequence[str] | None = None, *, all_masters: bool = False,
             masters: Sequence[str] | None = None) -> list[Row]:  # fmt: skip
        """Plan ``planner(name, before, layer, master)`` for each glyph layer; skipped layers carry a note."""
        package = self.package()
        chosen = self._names(names)
        targets = list(masters) if masters is not None else self.targets(all_masters)
        entries: list[tuple[str, str, Plan | None, str]] = []
        befores: dict[tuple[str, str], Metrics | None] = {}
        users = self._users(package)
        for name in chosen:
            glyph = self.native_glyph(name)
            owns_auto = any(layer.autoLayer for layer in glyph.layers)
            for master in targets:
                layer = self.layer(name, master)
                before = None if layer is None else model.measure(edges(layer), layer.advanceWidth)
                befores[name, master] = before
                note, plan = self._check(layer, owns_auto, before), None
                if not note:
                    result = planner(name, before, layer, master)  # type: ignore[arg-type]
                    plan, note = (None, result) if isinstance(result, str) else (result, "")
                if plan is not None and plan.dx:
                    hinted = fontui.layer_is_hinted(layer)
                    if hinted:
                        plan, note = None, hinted.text() + " Use Remove PostScript hints first."
                for shape in layer.shapes if layer is not None else ():
                    if shape.isComponent:
                        users.setdefault(str(shape.shapeData.componentGlyph), set()).add(name)
                entries.append((name, master, plan, note))
        ordered = model.order_plans(entries, users)
        self.rows = [Row(g, m, befores[g, m], p, n) for g, m, p, n in ordered]
        return self.rows

    @staticmethod
    def _check(layer: Any, owns_auto: bool, before: Metrics | None) -> str:
        if layer is None:
            return model.MISSING_NOTE
        if layer.autoLayer:
            return model.AUTO_LAYER_NOTE
        if owns_auto:
            return model.AUTO_GLYPH_NOTE
        if has_metrics_link(layer):
            return model.LINK_NOTE
        return "" if before is not None else model.EMPTY_NOTE

    # Writes ----------------------------------------------------------------
    def apply(self, action: str, planner: model.Planner, names: Sequence[str] | None = None, *,
              all_masters: bool = False, masters: Sequence[str] | None = None, allow_bases: bool = False) -> bool:  # fmt: skip
        """Plan, then write every changed layer as one ``"Spacing Studio: <action> <subject>"`` step.

        ``allow_bases`` is the "Edit bases of auto glyphs anyway" opt-in; off, a base of an auto glyph is refused.
        """
        try:
            rows = self.plan(planner, names, all_masters=all_masters, masters=masters)
        except (ValueError, KeyError, TypeError, TimeoutError, RuntimeError) as error:
            self.say(f"{APP}: {error}")
            return False
        pending = [row for row in rows if row.plan is not None and row.plan.changed]
        skipped = [row.note for row in rows if row.plan is None and row.note]
        if not pending:
            self.say(f"{APP}: no change." + (" " + " ".join(dict.fromkeys(skipped)) if skipped else ""))
            self._refresh()
            return False
        label = f"{APP}: {action} {model.subject([row.glyph for row in pending])}"
        layers = [self.layer(row.glyph, row.master) for row in pending]
        glyphs = list({row.glyph: self.native_glyph(row.glyph) for row in pending}.values())

        def mutate() -> None:
            for row, layer in zip(pending, layers):
                shift_and_set(layer, row.plan)  # type: ignore[arg-type]

        def read_back() -> list[str]:
            problems = []
            for row, layer in zip(pending, layers):
                plan, before = row.plan, row.before
                where = f"{row.glyph} ({row.master})"
                if layer.advanceWidth != plan.width:  # type: ignore[union-attr]
                    problems.append(f"{where}: advance {layer.advanceWidth:g}, planned {plan.width:g}")  # type: ignore[union-attr]
                found = edges(layer)
                if before is not None and found is not None and abs(found[0] - before.left - plan.dx) > TOLERANCE:  # type: ignore[union-attr]
                    problems.append(f"{where}: left edge {found[0]:g}, planned {before.left + plan.dx:g}")  # type: ignore[union-attr]
            return problems

        done = self.shell.history(label, glyphs, mutate, layers=layers, read_back=read_back,
                                  allow_bases=allow_bases) is not None  # fmt: skip
        if done and skipped:
            self.say(f"{self.shell_status()} Skipped: " + " ".join(dict.fromkeys(skipped)))
        self._refresh()
        return done

    def shell_status(self) -> str:
        status = getattr(self.shell, "status", None)
        return str(get(status.text)) if hasattr(status, "text") else self.status

    def _refresh(self) -> None:
        for view in list(self.views):
            view()

    def remove_hints(self, names: Sequence[str] | None = None, *, all_masters: bool = False) -> int:
        """Remove PostScript hints from the chosen layers: one ``"Spacing Studio: remove hints <glyph>"`` step each."""
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
    def reference_planner(self, reference: str, mode: str, offset: int) -> model.Planner:
        """Copy Metrics From Reference: each master copies the reference glyph's layer of that master."""

        def plan(name: str, before: Metrics, layer: Any, master: str) -> Plan | str:
            source = self.layer(reference, master)
            if source is None:
                return "no reference layer in this master"
            ref = model.measure(edges(source), source.advanceWidth)
            if ref is None:
                if mode != "width":
                    return "reference has no outline"
                return model.copied(before, (0, 0, source.advanceWidth), mode, offset)
            return model.copied(before, (ref.lsb, ref.rsb, ref.width), mode, offset)

        return plan

    def sync_planner(self, reference_master: str, proportional: bool) -> model.Planner:
        """Sync Sidebearings: each layer follows its glyph's layer in ``reference_master``."""

        def plan(name: str, before: Metrics, layer: Any, master: str) -> Plan | str:
            ref = self.metrics(name, reference_master)
            if ref is None:
                return "no layer in the reference master"
            return model.synced(before, ref, proportional)

        return plan

    def sync_targets(self, reference_master: str, all_masters: bool) -> list[str]:
        targets = [m for m in self.targets(all_masters) if m != reference_master]
        if not targets:
            raise ValueError("The current master is the reference. Choose All masters or another reference.")
        return targets

    def italic_defaults(self) -> tuple[float, int]:
        """The font's italic angle and half its x-height (the de-slant pivot)."""
        package = self.package()
        angle = float(getattr(package, "italicAngle_value", 0.0) or 0.0)
        x_height = getattr(package, "xHeight_value", X_HEIGHT_FALLBACK) or X_HEIGHT_FALLBACK
        return angle, model.unit(x_height / 2)

    @staticmethod
    def italic_planner(angle: float, pivot: float, mode: str, lsb: float | None, rsb: float | None) -> model.Planner:
        def plan(name: str, before: Metrics, layer: Any, master: str) -> Plan | str:
            found = italic_edges(layer, angle, pivot)
            if found is None:
                return model.EMPTY_NOTE
            return model.italic(before, found, mode, lsb, rsb)

        return plan

    # Read-only views -------------------------------------------------------
    def offset_preview(self, offset: int, names: Sequence[str] | None = None) -> list[tuple[str, str, str, str]]:
        """Sidebearing Offset Preview on the preview master; reads only."""
        master = self.targets(False)[0]
        chosen = self._names(names)
        return model.offset_rows([(name, self.metrics(name, master)) for name in chosen], offset)

    def comparison(self, which: str, reference: tuple[str, str] | None, mode: str,
                   names: Sequence[str] | None = None, *, all_masters: bool = True) -> list[tuple[str, str, str, str]]:  # fmt: skip
        """Layer Metric Comparison: (glyph, master, value, against reference); reads only."""
        if which not in model.MEASURES or mode not in model.COMPARE_MODES:
            raise ValueError("Choose a measurement and a mode.")
        cells: list[tuple[str, str, float | None]] = []
        for name in self._names(names):
            for master in self.targets(all_masters):
                cells.append((name, master, self._value(name, master, which)))
        if reference is None or not reference[0]:
            ref_value = cells[0][2]
        else:
            ref_name, ref_master = reference[0], reference[1] or self.master or ""
            if self.layer(ref_name, ref_master) is None:
                raise ValueError(f"{ref_name} has no layer {ref_master}.")
            ref_value = self._value(ref_name, ref_master, which)
        return [
            (name, master, "" if value is None else f"{value:g}", model.compared(value, ref_value, mode))
            for name, master, value in cells
        ]

    def _value(self, name: str, master: str, which: str) -> float | None:
        layer = self.layer(name, master)
        if layer is None:
            return None
        box = layer.boundingBox
        height = box.height() if edges(layer) is not None else None
        return model.measure_value(model.measure(edges(layer), layer.advanceWidth), height, which)

    def string_rows(self, text: str) -> list[tuple[str, str, str, str]]:
        """Spacing String Preview numbers: (glyph, LSB, RSB, advance) on the preview master; reads only."""
        master = self.targets(False)[0]
        rows = []
        for name in dict.fromkeys(self.names_in(text)):
            try:
                metrics = self.metrics(name, master)
            except ValueError:
                continue
            if metrics is None:
                layer = self.layer(name, master)
                rows.append((name, "", "", "" if layer is None else f"{layer.advanceWidth:g}"))
            else:
                rows.append((name, str(metrics.lsb), str(metrics.rsb), f"{metrics.width:g}"))
        return rows

    def names_in(self, text: str) -> list[str]:
        """Glyph names in preview text: ``/name`` tokens and characters through the font's cmap."""
        font = self.font()
        cmap: dict[int, str] = {}
        if font is not None:
            for name in font.keys():
                for code in getattr(font[name], "unicodes", ()) or ():
                    cmap.setdefault(code, name)
        names, index = [], 0
        while index < len(text):
            char = text[index]
            if char == "/":
                end = index + 1
                while end < len(text) and not text[end].isspace() and text[end] != "/":
                    end += 1
                if end > index + 1:
                    names.append(text[index + 1 : end])
                index = end + (1 if end < len(text) and text[end] == " " else 0)
                continue
            if not char.isspace() and ord(char) in cmap:
                names.append(cmap[ord(char)])
            index += 1
        return names


__all__ = ["NO_FONT", "NO_GLYPHS", "Row", "Studio", "edges", "italic_edges", "shift_and_set"]
