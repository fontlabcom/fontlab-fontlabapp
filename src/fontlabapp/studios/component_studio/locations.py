# this_file: src/fontlabapp/studios/component_studio/locations.py
# SPDX-License-Identifier: Apache-2.0
"""Locations tab (Set Component Locations): set or reset component source locations.

The original's rules are kept unchanged (``encode_location``,
``component_targets``, ``location_plan``, ``current_coordinates``,
``LocationEditor``): give components a font-axis location such as
``#wt=650,wd=100``, or Reset each base layer name to the host master layer
(as Reset to current layer does). Each component/master occurrence gets one
row of the per-axis table, starting at its current location; Set writes
only edited rows and keeps an existing ``@node`` suffix. "Action": Set
location (default) or Reset to current layer; "Components": Selected
components or All components in selected glyphs (default); "Source": an
optional exact source name; "Masters": all masters (default). Automatic
layers, their owners and bases, locked layers, shared element data and
missing sources are listed as kept; other eligible occurrences still write.
Set refuses unknown axes and non-finite or out-of-range coordinates; Set
without edits writes nothing. Apply writes ``componentLayer`` in place as
one ``Component Studio: set component locations <subject>`` (or ``reset
component locations``) Undo step, then reads it back. From a Glyph window,
Apply refuses an edit that includes glyphs the window does not show
(``AppShell.history``'s Glyph-window guard, the original's refusal).

Credit: independent behaviour rewrite after Fernando Díaz, Reset Type
Studio, Glyphs-Scripts (Apache-2.0). No source code was copied.
"""

import math
import re
from typing import Any

from PythonQt import QtGui

import fontlabapp.core.edit_guards as guards  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native

from .._kerning_ui import combo, get, line_edit, row
from . import _shared

#: The original's module names, read by the verbatim functions below.
writer = _shared.Modules("components")

RowKey = tuple[str, str, Any]
#: Kept for the verbatim functions' module-level names.
_ = (math, re, history)


# ---------------------------------------------------------------- verbatim original
# Set Component Locations
def encode_location(package: Any, values: dict[str, float]) -> str:
    """Encode native # syntax in declared-axis order, within design bounds.

    The native builder replaces # with : before decodeMasterPosition parses
    comma-separated shortName=value pairs. Use design units, not user units.
    """
    axes = list(package.axes)
    keys = [str(axis.shortName).lower() for axis in axes]
    if (
        not keys
        or len(set(keys)) != len(keys)
        or any(not key.isascii() or not key.isalnum() for key in keys)
    ):
        raise ValueError("Declare axes with unique short names in Font Info.")
    if set(values) != set(keys):
        raise ValueError("Set one coordinate for each declared font axis.")
    pairs = []
    for key, axis in zip(keys, axes, strict=True):
        number = float(values[key])
        if not math.isfinite(number) or not float(axis.designMin) <= number <= float(
            axis.designMax
        ):
            raise ValueError(
                f"{key}: choose a finite coordinate inside the design range."
            )
        text = str(int(number)) if number.is_integer() else repr(number)
        pairs.append(f"{key}={text}")
    return "#" + ",".join(pairs)


def component_targets(
    glyph: Any, layer: Any, selected_only: bool
) -> list[tuple[Any, str]]:
    """Resolve selection by position and base name; never substitute a sibling."""
    if not selected_only:
        source = layer if layer is not None else glyph.updateActiveLayer(False)
        return (
            [
                (shape, "" if layer is not None else "missing master layer")
                for shape in writer.components(source)
            ]
            if source is not None
            else []
        )
    active = glyph.updateActiveLayer(False)
    if active is None or active.isNull:
        return []
    targets = []
    for index, source in enumerate(active.shapes):
        if not source.isComponent or not source.selected:
            continue
        shape = (
            layer.shapes[index]
            if layer is not None and index < len(layer.shapes)
            else None
        )
        same = (
            shape is not None
            and shape.isComponent
            and writer.base_of(shape) == writer.base_of(source)
        )
        targets.append(
            (
                shape if same else source,
                "" if same else "component position or source differs in this master",
            )
        )
    return targets


def location_plan(
    package: Any,
    glyphs: list[Any],
    masters: list[str],
    values: dict[str, dict[str, float]],
    facts: history.AutoFacts,
    *,
    reset: bool = False,
    name: str = "",
    selected_only: bool = True,
    row_values: dict[RowKey, dict[str, float]] | None = None,
    changed: set[RowKey] | None = None,
    observed: dict[RowKey, str] | None = None,
    row_errors: dict[RowKey, str] | None = None,
) -> writer.Plan:
    """Preview each eligible edit or kept occurrence; a refusal stays local."""
    if any(c in name for c in ("\x00", "\u00a0", "\u2028", "\u2029")):
        raise ValueError(
            "Enter a source name without control or non-breaking characters."
        )
    plan = writer.Plan()
    refused = history.refusals(facts, [g.name for g in glyphs], "geometry")
    for glyph in glyphs:
        for master in masters:
            label = f"{glyph.name} · {master}"
            layer = writer.layer_of(glyph, master)
            reason = refused.get(glyph.name, "")
            if layer is None:
                reason = "missing master layer"
            elif (
                layer.autoLayer
                or layer.isLocked
                or layer.isMaskLayer
                or layer.isService
            ):
                reason = "automatic, locked or service layer"
            edits = []
            for shape, mismatch in component_targets(glyph, layer, selected_only):
                base = writer.base_of(shape)
                if name.strip() and base != name.strip():
                    continue
                why = reason or mismatch
                if not why and int(shape.shapeData.referenceCount) != 1:
                    why = "shared element data"
                if not why and package.findName(base) is None:
                    why = f"missing source glyph {base}"
                old = str(shape.shapeData.componentLayer)
                key = (str(glyph.name), master, shape.id)
                location = str(layer.name) if reset and layer is not None else old
                untouched = not reset and changed is not None and key not in changed
                if not reset and not untouched and not why:
                    try:
                        coordinates = (
                            row_values.get(key, {})
                            if row_values is not None
                            else values.get(master, {})
                        )
                        location = encode_location(package, coordinates)
                        if "@" in old:
                            location += old[old.index("@") :]
                    except (ValueError, RuntimeError, TimeoutError) as error:
                        why = str(error)
                if not reset and observed is not None and observed.get(key) != old:
                    why = "component location changed; reload selection"
                if not reset and row_errors is not None and key in row_errors:
                    why = row_errors[key]
                edit = None if why or old == location else (shape.id, location)
                result = f"kept: {why}" if why else (location or "current layer")
                if not why and edit is None:
                    result = "same, kept"
                plan.rows.append(
                    (
                        label,
                        writer.Change(
                            base, old or "base active layer", result, edit, key=key
                        ),
                    )
                )
                if edit is not None:
                    edits.append(edit)
            if edits:
                plan.work.append((glyph, layer, edits))
    return plan


def current_coordinates(package: Any, shape: Any, master: str) -> dict[str, float]:
    """Read a component's explicit coordinates or named source-layer position.

    flLocation supports key reads: the native mapping returns None for an
    absent key, a float for a scalar and a tuple for an anisotropic value.
    Do not iterate it or reinterpret an anisotropic position as a scalar.
    """
    reference = str(shape.shapeData.componentLayer).split("@", 1)[0]
    head, marker, text = reference.partition("#")
    position = None
    if head in package.masters:
        position = package.location(head)
    elif head:
        base = package.findName(writer.base_of(shape))
        layer = writer.layer_of(base, head) if base is not None else None
        if layer is None:
            raise ValueError(
                f"Cannot read source layer {head}; use Reset or the native instance control."
            )
        position = layer.getMasterPosition()
    elif not marker:
        base = package.findName(writer.base_of(shape))
        layer = base.updateActiveLayer(False) if base is not None else None
        if layer is None:
            raise ValueError("Cannot read the base active layer; use Reset.")
        position = layer.getMasterPosition()
    values = {}
    aliases = {}
    for axis in package.axes:
        key = str(axis.shortName).lower()
        aliases[key] = aliases[str(axis.name).lower()] = key
        number = position[key] if position is not None else None
        if number is None:
            number = float(axis.designDef)
        if not isinstance(number, (int, float)) or not math.isfinite(number):
            raise ValueError(
                f"Cannot edit anisotropic or non-finite {key}; use the native instance control."
            )
        values[key] = float(number)
    if marker:
        for pair in re.split(r"[,;\s]+", text.strip()):
            if not pair:
                continue
            name, sign, value = pair.partition("=")
            if not sign or name.lower() not in aliases:
                raise ValueError(
                    "Cannot read custom or bounded axis coordinates; use the native instance control."
                )
            values[aliases[name.lower()]] = float(value)
    if any(not math.isfinite(value) for value in values.values()):
        raise ValueError("Current location is non-finite; use Reset.")
    return values


class LocationEditor(writer.Editor):
    """Change only the source-layer choice; no element is removed or cloned."""

    def prepare(self, layer: Any, edits: list[Any]) -> list[Any]:
        """Resolve existing shape IDs before history opens."""
        return [
            (layer.shapes[writer.shape_index(layer, shape_id)], location)
            for shape_id, location in edits
        ]

    def write(self, layer: Any, steps: list[Any]) -> None:
        """Rebuild each existing component after setting its location."""
        for shape, location in steps:
            shape.shapeData.componentLayer = location
            writer.refreshed(shape)

    def check(self, prepared: list[tuple[Any, list[Any]]]) -> list[str]:
        """Read back each stored location and its occurrence identity."""
        return [
            f"{layer.name}/{writer.base_of(shape)}"
            for layer, steps in prepared
            for shape, location in steps
            if str(shape.shapeData.componentLayer) != location
            or shape.id not in {part.id for part in layer.shapes}
        ]


# ---------------------------------------------------------------- tab
class LocationsPanel(_shared.ComponentPanel):
    """Per-occurrence coordinate table and read-only action preview."""

    ACTION, DONE = "Apply", "Changed"
    HEADERS: tuple[str, ...] = ("Glyph · master", "Component", "Current", "New")
    SCOPE = 1

    def build_controls(self, form: Any) -> None:
        """Keep one table signal; rebuilding rows creates no widget connections."""
        self.mode_box = combo(
            self.widget,
            ["Set location", "Reset to current layer"],
            self.contain(self.replan),
        )
        row(self.widget, form, "Action", self.mode_box)
        self.target_box = combo(self.widget, ["Selected components", "All components in selected glyphs"],
                                self.contain(self.replan))  # fmt: skip
        self.target_box.setCurrentIndex(1)
        row(self.widget, form, "Components", self.target_box)
        self.filter_edit = line_edit(
            self.widget, "", "Optional exact source name", self.contain(self.replan)
        )
        row(self.widget, form, "Source", self.filter_edit)
        self.scope_box(form)
        self.axis_table = QtGui.QTableWidget(0, 0, self.widget)
        self.axis_table.setMinimumHeight(120)
        self.axis_table.setMaximumHeight(200)
        form.addWidget(self.axis_table)
        self.axis_table.itemChanged.connect(self.contain(lambda *_item: self.replan()))
        self.control_schema: list[tuple[str, float, float]] | None = None
        self.control_masters: list[str] = []
        self.coordinate_rows: list[RowKey] = []
        self.axis_controls: dict[tuple[RowKey, str], Any] = {}
        self.baselines: dict[RowKey, dict[str, float]] = {}
        self.source_names: dict[RowKey, str] = {}
        self.coordinate_errors: dict[RowKey, str] = {}

    @property
    def UNDO(self) -> str:  # noqa: N802 - the panel attribute the base reads
        return (
            "reset component locations"
            if self.resetting()
            else "set component locations"
        )

    def resetting(self) -> bool:
        return get(self.mode_box.currentIndex) == 1

    def selected_only(self) -> bool:
        return get(self.target_box.currentIndex) == 0

    def on_reload(self) -> None:
        """Discard field edits so the next preview reads current component data.

        The original fixed the axis columns when the panel opened; the tab
        takes them from the font on the first Reload selection.
        """
        self.coordinate_rows = []
        self.axis_controls = {}
        package = self.package
        if package is not None and self.control_schema is None:
            axes = list(package.axes)
            self.control_schema = [
                (str(a.shortName).lower(), float(a.designMin), float(a.designMax))
                for a in axes
            ]
            self.control_masters = list(package.masters)
            self.axis_table.setColumnCount(len(axes))
            self.axis_table.setHorizontalHeaderLabels(
                [f"{a.name} ({a.shortName})" for a in axes]
            )

    def ensure_rows(self, package: Any, glyphs: list[Any]) -> None:
        """Read current locations when the selected occurrences change."""
        targets = []
        name = str(get(self.filter_edit.text)).strip()
        for glyph in glyphs:
            for master in self.chosen_masters():
                layer = writer.layer_of(glyph, master)
                for shape, mismatch in component_targets(
                    glyph, layer, self.selected_only()
                ):
                    if not mismatch and (not name or writer.base_of(shape) == name):
                        targets.append(((str(glyph.name), master, shape.id), shape))
        keys = [key for key, shape in targets]
        if keys == self.coordinate_rows:
            return
        self.coordinate_rows = keys
        (
            self.axis_controls,
            self.baselines,
            self.source_names,
            self.coordinate_errors,
        ) = {}, {}, {}, {}
        labels = []
        self.axis_table.blockSignals(True)
        try:
            self.axis_table.setRowCount(len(targets))
            for line, (key, shape) in enumerate(targets):
                text = f"{key[0]} · {key[1]} · {writer.base_of(shape)}"
                self.source_names[key] = str(shape.shapeData.componentLayer)
                values = {}
                try:
                    values = current_coordinates(package, shape, key[1])
                except (ValueError, RuntimeError, TimeoutError) as error:
                    self.coordinate_errors[key] = str(error)
                    text += f" — {error}"
                self.baselines[key] = values
                labels.append(text)
                for column, (axis, _low, _high) in enumerate(self.control_schema or []):
                    item = QtGui.QTableWidgetItem(
                        str(values[axis]) if axis in values else ""
                    )
                    self.axis_controls[key, axis] = item
                    self.axis_table.setItem(line, column, item)
            self.axis_table.setVerticalHeaderLabels(labels)
        finally:
            self.axis_table.blockSignals(False)

    def current_plan(self, package: Any, glyphs: list[Any], facts: Any) -> Any:
        """Set only changed occurrence rows; Reset uses the host layer names."""
        schema = [
            (str(a.shortName).lower(), float(a.designMin), float(a.designMax))
            for a in package.axes
        ]
        if (
            list(package.masters) != self.control_masters
            or schema != self.control_schema
        ):
            raise ValueError(
                "Axes or masters changed; close this panel and run it again."
            )
        self.ensure_rows(package, glyphs)
        reset = self.resetting()
        self.axis_table.setEnabled(not reset)
        values, changed, errors = {}, set(), dict(self.coordinate_errors)
        if not reset:
            for key in self.coordinate_rows:
                coordinates = {}
                try:
                    coordinates = {
                        axis: float(get(self.axis_controls[key, axis].text))
                        for axis, low, high in schema
                    }
                except ValueError:
                    errors[key] = "Enter numeric axis coordinates."
                values[key] = coordinates
                if coordinates != self.baselines[key]:
                    changed.add(key)
        return location_plan(
            package, glyphs, self.chosen_masters(), {}, facts, reset=reset,
            name=str(get(self.filter_edit.text)), selected_only=self.selected_only(),
            row_values=values, changed=changed, observed=self.source_names, row_errors=errors,
        )  # fmt: skip

    def make_plan(self, package: Any, glyphs: list[Any], facts: Any) -> tuple[Any, str]:
        """Kept rows do not block other occurrences (the original wrote without ``require_safe``)."""
        try:
            plan = self.current_plan(package, glyphs, facts)
        except (ValueError, RuntimeError, TimeoutError) as error:
            return writer.Plan(), str(error)
        if not plan.rows and self.selected_only():
            return (
                plan,
                "Select components in a Glyph window, or choose All components in selected glyphs.",
            )
        return plan, ""

    def editor(self) -> Any:
        return LocationEditor()

    def done_text(self, result: dict, plan: Any) -> str:
        message = f"Changed {result['edits']} components; review kept rows above."
        return guards.append_note(message, result)


__all__ = [
    "LocationEditor", "LocationsPanel", "RowKey", "component_targets", "current_coordinates",
    "encode_location", "location_plan",
]  # fmt: skip
