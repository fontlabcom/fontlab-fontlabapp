# this_file: src/fontlabapp/masters/layers/compatibility/model.py
# SPDX-License-Identifier: MIT
"""Complete adjacent-layer diagnostics from Why You Not Compatible?; see NOTICE.

These are the source's structural checks, not a variable-font/export certificate.
Coordinates, path closure, component order/transforms/multiplicity, anchor
positions, hints and styles are outside the source report's comparison.
"""

from dataclasses import dataclass
from typing import Any, Literal

NodeType = Literal["line", "curve", "qcurve", "offcurve"]


@dataclass(frozen=True)
class Layer:
    """One layer's ordered paths/types and anchor/component NAME SETS."""

    name: str
    paths: tuple[tuple[NodeType, ...], ...]
    anchors: frozenset[str] = frozenset()
    components: frozenset[str] = frozenset()


@dataclass(frozen=True)
class GlyphLayers:
    """One selected occurrence; keep repeated glyph groups and all layers."""

    name: str
    layers: tuple[Layer, ...]


@dataclass(frozen=True)
class Difference:
    """One ordered diagnosis between adjacent layers of this glyph."""

    kind: str
    previous_layer: str
    layer: str
    previous: int | str
    current: int | str


def _paths(before: Layer, after: Layer) -> list[tuple[str, int | str, int | str]]:
    """Compare ordered path/node types only where the preceding counts match."""
    if len(before.paths) != len(after.paths):
        return [("path counts", len(before.paths), len(after.paths))]
    result = []
    for i, (left, right) in enumerate(zip(before.paths, after.paths, strict=True), 1):
        if len(left) != len(right):
            result.append((f"path {i}, node count", len(left), len(right)))
            continue
        result.extend(
            (f"path {i}, node {j} node types", a, b)
            for j, (a, b) in enumerate(zip(left, right, strict=True), 1)
            if a != b
        )
    return result


def differences(group: GlyphLayers) -> tuple[Difference, ...]:
    """Check every adjacent pair, repairing global path suppression/label bugs.

    A mismatch skips only that pair's unmatched node lists. Deterministic sorted
    name-set output preserves the source's order/multiplicity-insensitive checks.
    """
    if not group.layers:
        raise ValueError("A glyph has no reportable foreground layer.")
    result = []
    for before, after in zip(group.layers, group.layers[1:]):
        fields = _paths(before, after)
        for label, left, right in (
            ("anchors", before.anchors, after.anchors),
            ("components", before.components, after.components),
        ):
            if left != right:
                fields.append(
                    (label, ", ".join(sorted(left)), ", ".join(sorted(right)))
                )
        result.extend(
            Difference(kind, before.name, after.name, left, right)
            for kind, left, right in fields
        )
    return tuple(result)


def render(groups: tuple[GlyphLayers, ...]) -> str:
    """Keep source headings, difference text and per-occurrence blank lines."""
    parts = []
    for group in groups:
        found = differences(group)
        parts.append(f"{group.name} is {'not compatible' if found else 'compatible'}\n")
        for d in found:
            parts.append(
                f"{d.kind} differ:\n  {d.previous_layer} has {d.previous}\n  {d.layer} has {d.current}\n"
            )
        parts.append("\n\n")
    return "".join(parts)


def show() -> Any:
    """Lazily open/raise this owned modeless report through the shared registry."""
    from fontlabapp.masters.layers.compatibility.ui import LayerCompatibilityDialog
    from fontlabapp.core.scripting import show_script_dialog

    return show_script_dialog(LayerCompatibilityDialog, LayerCompatibilityDialog.KEY)
