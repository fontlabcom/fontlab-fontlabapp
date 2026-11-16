# this_file: src/fontlabapp/studios/layer_manager/intermediate.py
# SPDX-License-Identifier: Apache-2.0
"""Intermediate tab: the Scriptmix "Set Intermediate Layer" (Scripts/Masters/).

Add one interpolated layer per selected glyph at an explicit design
location: one coordinate control per declared axis, the new layer named
in FontLab's location form (``:wt=550``). The planning is the original's,
verbatim: automatic glyphs and their bases, an existing layer or
location, missing, locked, service, image or incompatible master layers
are listed and kept. Add Layers plans again, refuses a plan that differs
from the list, and adds every interpolated layer as ONE
``Layer Manager: add intermediate layers <subject>`` Undo step through
``AppShell.history`` with no target layers (the original's
layer-creating route). The new layers are not master and not automatic
layers (an automatic interpolation result is refused, as before).
"""

import math
from dataclasses import dataclass
from typing import Any

from PythonQt import QtGui

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native

from .._kerning_ui import get, row as form_row, spin
from ._shared import (
    Modules,
    PlanTab,
    commit,
    ident,
    label as undo_label,
)

guards = Modules("guards")
fl = Modules("fontlab")

TITLE = "Set Intermediate Layer"
KEY = "masters_set_intermediate_layer"


@dataclass
class IntermediateRow:
    """One glyph, an explicit location, and an optional reason to keep it."""

    glyph: Any
    name: str
    values: dict[str, float]
    note: str = ""


def location_values(
    package: Any, values: dict[str, float]
) -> tuple[dict[str, float], str]:
    """Validate declared design coordinates and encode FontLab's layer-name form."""
    axes = list(package.axes)
    keys = [str(axis.shortName) for axis in axes]
    if (
        not axes
        or len({key.lower() for key in keys}) != len(keys)
        or any(not key.isalnum() for key in keys)
    ):
        raise ValueError("Declare axes with unique short names in Font Info first.")
    if set(values) != set(keys):
        raise ValueError("Set one coordinate for each declared axis.")
    result = {}
    for key, axis in zip(keys, axes, strict=True):
        number = float(values[key])
        if not math.isfinite(number) or not float(axis.designMin) <= number <= float(
            axis.designMax
        ):
            raise ValueError(
                f"{axis.name}: choose a finite coordinate inside the design range."
            )
        result[key] = 0.0 if number == 0 else number
    return result, ":" + ",".join(
        f"{key.lower()}={int(value) if value.is_integer() else repr(value)}"
        for key, value in result.items()
    )


def keep_reason(
    package: Any,
    glyph: Any,
    name: str,
    values: dict[str, float],
    facts: history.AutoFacts,
) -> str:
    """Keep unsafe, duplicate or incompatible glyphs; the other glyphs still write."""
    why = history.refusal(facts, glyph.name, "geometry")
    if why:
        return why
    existing = glyph.findLayer(name)
    if existing is not None and not existing.isNull:
        return "layer already exists"
    masters = [glyph.findLayer(str(master)) for master in package.masters]
    if len(masters) < 2 or any(layer is None or layer.isNull for layer in masters):
        return "needs at least two existing master layers"
    if any(layer.isLocked or layer.isService or layer.isImg for layer in masters):
        return "locked, service or image master layer"
    if any(not masters[0].isCompatible(layer, True) for layer in masters[1:]):
        return "master outlines are incompatible"
    for layer in glyph.layers:
        if layer.isMaskLayer or layer.isService:
            continue
        position = layer.getMasterPosition()
        if position_matches(position, values):
            return f"location already exists on {layer.name}"
    return ""


def position_matches(position: Any, values: dict[str, float]) -> bool:
    """Subscript only; a missing key reads as None. Layer names lower-case keys."""
    if position is None:
        return False
    for key, value in values.items():
        actual = position[key]
        if actual is None:
            actual = position[key.lower()]
        if not isinstance(actual, (float, int)) or actual != value:
            return False
    return True


def survey(
    package: Any, names: list[str], values: dict[str, float], facts: history.AutoFacts
) -> list[IntermediateRow]:
    """One row per selected glyph, with all refusals visible before writing."""
    coordinates, name = location_values(package, values)
    rows = []
    for glyph_name in dict.fromkeys(names):
        glyph = package.findName(glyph_name)
        if glyph is None or glyph.isNull:
            rows.append(
                IntermediateRow(
                    None, name, coordinates, f"{glyph_name}: missing glyph, kept"
                )
            )
            continue
        why = keep_reason(package, glyph, name, coordinates, facts)
        rows.append(
            IntermediateRow(glyph, name, coordinates, "kept: " + why if why else "")
        )
    return rows


def write_rows(
    tool: Any,
    package: Any,
    rows: list[IntermediateRow],
    facts: history.AutoFacts,
    title: str = TITLE,
) -> dict[str, Any] | None:
    """Interpolate and append in one history action; retain partial additions on error (the original's).

    The original's checks, interpolation, mutate and read-back, verbatim;
    the step goes through ``tool.shell.history`` titled ``title`` with no
    target layers (None when refused).
    """
    ready = [
        row
        for row in rows
        if not row.note
        and row.glyph is not None
        and not keep_reason(package, row.glyph, row.name, row.values, facts)
    ]
    kept = [
        f"{r.glyph.name if r.glyph is not None else r.note}: {r.note}"
        for r in rows
        if r.note
    ]
    if not ready:
        return {
            "pending_note": "",
            "layers": 0,
            "mismatches": [],
            "kept": kept,
            "pending_updates": (),
        }
    ids = guards.pending_updates()
    prepared = []
    for row in ready:
        try:
            layer = row.glyph.interpolateInstance(fl.flLocation(row.values), False)
        except (ValueError, RuntimeError, TimeoutError) as error:
            kept.append(f"{row.glyph.name}: interpolation refused, kept: {error}")
            continue
        if layer is None or layer.isNull or layer.autoLayer:
            kept.append(f"{row.glyph.name}: interpolation refused, kept")
            continue
        layer.name = row.name
        prepared.append((row, layer))
    if not prepared:
        return {
            "pending_note": guards.pending_note(ids),
            "layers": 0,
            "mismatches": [],
            "kept": kept,
            "pending_updates": ids,
        }
    created: list[tuple[IntermediateRow, Any]] = []
    failures: list[str] = []

    def mutate() -> list[Any]:
        for row, layer in prepared:
            try:
                row.glyph.addLayer(layer)
                added = row.glyph.findLayer(row.name)
                if added is None or added.isNull or str(added.name) != row.name:
                    raise RuntimeError("FontLab did not add the layer.")
                created.append((row, added))
            except Exception as error:  # noqa: BLE001 - finish the one history action
                failures.append(f"{row.glyph.name}: {error}")
                try:
                    stored = row.glyph.findLayer(row.name)
                    if stored is not None and not stored.isNull:
                        created.append((row, stored))
                except (ValueError, RuntimeError, TimeoutError) as read_error:
                    failures.append(str(read_error))
                break
        return [layer for _, layer in created]

    def read_back() -> list[str]:
        missed = []
        for row, added in created:
            stored = row.glyph.findLayer(row.name)
            position = (
                None if stored is None or stored.isNull else stored.getMasterPosition()
            )
            if (
                stored is None
                or stored.isNull
                or stored.id != added.id
                or not position_matches(position, row.values)
            ):
                missed.append(f"{row.glyph.name}/{row.name}")
        return missed

    done = commit(
        tool, title, [], [row.glyph for row, _ in prepared], mutate, read_back=read_back
    )
    if done is None:
        return None
    if done.mismatches or failures:
        raise RuntimeError(
            "FontLab did not finish adding layers: "
            + "; ".join([*failures, *done.mismatches])
            + ". Native changes may remain; use Edit > Undo."
        )
    return {
        "pending_note": guards.pending_note(ids),
        "layers": len(created),
        "mismatches": [],
        "kept": kept,
        "pending_updates": ids,
    }


class IntermediatePanel(PlanTab):
    """One coordinate control per declared axis, the new-layer table, Use selection and Add Layers."""

    ACTION = "Add Layers"
    HEADERS = ("Glyph", "New layer", "Action")
    NO_FONT_TEXT = "Open a font first."
    CHANGED_TEXT = "The font changed. Run this script again."

    def build_controls(self, form: Any) -> None:
        self.axes_form = QtGui.QVBoxLayout()
        form.addLayout(self.axes_form)
        self.axis_controls: dict[str, Any] = {}
        self.axes_key: tuple = ()

    def bind(self) -> None:
        """Bind to the current font; one coordinate control per declared axis (kept while the axes are)."""
        super().bind()
        package = self.tool.shell.package()
        axes = [] if package is None else list(package.axes)
        key = tuple(
            (str(a.name), str(a.shortName), float(a.designMin), float(a.designMax))
            for a in axes
        )
        if key == self.axes_key:
            return
        self.axes_key = key
        while self.axes_form.count():
            item = self.axes_form.takeAt(0)
            line = item.layout()
            while line is not None and line.count():
                widget = line.takeAt(0).widget()
                if widget is not None:
                    widget.deleteLater()
        self.axis_controls = {}
        for axis in axes:
            low, high = float(axis.designMin), float(axis.designMax)
            box = spin(
                self.widget,
                low,
                high,
                (low + high) / 2,
                decimals=6,
                slot=self.contain(self.redraw),
            )
            short = str(axis.shortName)
            self.axis_controls[short] = form_row(
                self.widget, self.axes_form, f"{axis.name} ({short})", box
            )

    def plan(self) -> list[IntermediateRow]:
        package = self.bound()
        if not self.names:
            raise ValueError(
                "Select glyphs in the Font window. Then press Use selection."
            )
        values = {key: float(get(box.value)) for key, box in self.axis_controls.items()}
        return survey(package, self.names, values, history.scan_auto_facts(package))

    def rows(self, items: list[IntermediateRow]) -> list[tuple]:
        return [(str(r.glyph.name) if r.glyph is not None else "Missing glyph", None,
                 (r.name, r.note or "add interpolated layer")) for r in items]  # fmt: skip

    def key(self, items: list[IntermediateRow]) -> Any:
        return tuple(self.rows(items)), tuple(ident(r.glyph) for r in items)

    def ready_items(self, items: list[IntermediateRow]) -> bool:
        return any(not r.note for r in items)

    def summary(self, items: list[IntermediateRow]) -> str:
        count = sum(not r.note for r in items)
        return (
            f"{count} intermediate layer(s) will be added"
            if count
            else "Nothing to add"
        )

    def write(self, items: list[IntermediateRow]) -> str | None:
        package = self.bound()
        names = [r.glyph.name for r in items if not r.note and r.glyph is not None]
        result = write_rows(self.tool, package, items, history.scan_auto_facts(package),
                            undo_label("add intermediate layers", names))  # fmt: skip
        if result is None:
            return None
        text = f"Added {result['layers']} intermediate layer(s)"
        if result.get("kept"):
            text += "; " + "; ".join(result["kept"])
        return text


__all__ = ["TITLE", "IntermediatePanel", "IntermediateRow", "keep_reason", "location_values", "position_matches",
           "survey", "write_rows"]  # fmt: skip
