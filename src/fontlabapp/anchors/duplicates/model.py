# this_file: src/fontlabapp/anchors/duplicates/model.py
# SPDX-License-Identifier: Apache-2.0
"""Exact original anchor families, rounded coincidences and ordered removals.

Values are detached from FontLab. Native preservation and history require the
separate writer's complete preflight and owned-font acceptance.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Any

TITLE, KEY = "Anchor Duplicates", "anchors_duplicates_finder"


@dataclass(frozen=True)
class Pin:
    """Identity and source coordinates; state keeps additional native values."""

    identity: int
    name: str
    x: float
    y: float
    state: tuple = ()


@dataclass(frozen=True)
class Layer:
    """One existing named master layer, including automatic finding rows."""

    name: str
    master: str
    glyph_id: int
    identity: int
    auto: bool
    pins: tuple[Pin, ...]


@dataclass(frozen=True)
class Snapshot:
    """Complete font-order/master-order domain and dependency facts."""

    context: tuple
    names: tuple[str, ...]
    selection: tuple[str, ...]
    masters: tuple[str, ...]
    layers: tuple[Layer, ...]
    dependencies: tuple


@dataclass(frozen=True)
class Finding:
    """A complete original group; only extras are removed, in source order."""

    kind: str
    names: tuple[str, ...]
    extras: tuple[int, ...]


def findings(pins: tuple[Pin, ...]) -> tuple[Finding, ...]:
    """Retain one suffix pass, Unicode digits, first occurrence and ties-even."""
    names = {p.name for p in pins}
    if len({p.identity for p in pins}) != len(pins):
        raise ValueError(
            "Repeated anchor identity cannot identify a removable occurrence."
        )
    if any(not isfinite(value) for p in pins for value in (p.x, p.y)):
        raise ValueError("Anchor coordinates must be finite.")

    def family(name: str) -> str:
        stem, dot, tail = name.rpartition(".")
        return stem if dot and tail.isdigit() and stem in names else name

    groups: dict[str, list[Pin]] = {}
    spots: dict[tuple[int, int], list[Pin]] = {}
    for pin in pins:
        groups.setdefault(family(pin.name), []).append(pin)
    for pin in pins:
        if len(groups[family(pin.name)]) == 1:
            spots.setdefault((round(pin.x), round(pin.y)), []).append(pin)
    return tuple(
        Finding(
            kind, tuple(p.name for p in group), tuple(p.identity for p in group[1:])
        )
        for kind, collections in (("duplicate name", groups), ("coincident", spots))
        for group in collections.values()
        if len(group) > 1
    )


def rows(facts: Snapshot, selected: bool) -> tuple[tuple[Layer, Finding], ...]:
    """Keep the original glyph/master scan order; selection is captured at open."""
    names = facts.selection if selected else facts.names
    return tuple(
        (layer, finding)
        for layer in facts.layers
        if layer.name in names
        for finding in findings(layer.pins)
    )


def plan(facts: Snapshot, coincident: bool, selected: bool = False) -> tuple:
    """Group all editable findings in source order, without reconstructing pins."""
    grouped = {}
    for layer, finding in rows(facts, selected):
        if not layer.auto and (finding.kind != "coincident" or coincident):
            grouped.setdefault(layer, []).extend(finding.extras)
    return tuple((layer, tuple(extras)) for layer, extras in grouped.items())


def show() -> Any:
    """Open the complete native workflow lazily through the owned registry."""
    from fontlabapp import _native
    from fontlabapp.anchors.duplicates.native import Backend
    from fontlabapp.anchors.duplicates.ui import panel_type
    from fontlabapp.core.scripting import show_script_dialog

    qt = _native("PythonQt")
    kind = panel_type(qt.QtCore, qt.QtGui)
    return show_script_dialog(lambda parent: kind(parent, Backend()), KEY)
