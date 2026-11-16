# this_file: src/fontlabapp/guides/inspect/sources.py
# SPDX-License-Identifier: Apache-2.0
"""Original guide source readers and plain snapshots for the three complete panels."""

from typing import Any

from fontlabapp import _native
from fontlabapp.components.inspect.model import (
    selected_glyphs,
    source_values as shape_source,
)
from fontlabapp.masters.inspect.model import muted
from fontlabapp.proof.inspect.model import layer_path

METRICS = [
    ("Baseline", None),
    ("x-height", "xHeight"),
    ("Cap height", "capsHeight"),
    ("Ascender", "ascender"),
    ("Descender", "descender"),
]


def master_layers(glyph: Any, masters: list[str]) -> list[tuple[str, Any]]:
    """Keep the original ordered present-layer lookup without creating missing layers."""
    found = []
    for master in masters:
        layer = glyph.findLayer(master)
        if layer is not None and not layer.isNull:
            found.append((master, layer))
    return found


def font_guide_names(package: Any) -> list[str]:
    """List original current-master font-guide names; geometry is not Python-bound."""
    names = []
    for item in package.guidelines:
        try:
            names.append(str(item.name) or "(unnamed)")
        except Exception:  # noqa: BLE001 - original unknown-name display fallback
            names.append("?")
    return names


def metric_values(package: Any, master: str) -> dict[str, float]:
    """Read the original five reference levels without switching the current master."""
    metrics = _native("fontlab").FontMetrics(package, master)
    return {
        label: float(getattr(metrics, attr)) if attr else 0.0 for label, attr in METRICS
    }


def source_values(
    package: Any,
    names: list[str],
    masters: list[str],
    *,
    geometry: bool = False,
    font_guides: bool = False,
) -> tuple:
    """Bind raw guide coordinates, metrics, dependencies and optional preview geometry."""
    from fontlabapp.guides.inspect.model import dependency_values

    guide_rows = []
    for name in names:
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            raise ValueError("Glyph source changed; reopen this tool.")
        for master, layer in master_layers(glyph, masters):
            records = tuple(
                (
                    float(g.centerPoint.x()),
                    float(g.centerPoint.y()),
                    float(g.angle),
                    str(g.name),
                )
                for g in layer.guidelines
                if not g.isHint
            )
            guide_rows.append((name, master, records))
    return (
        dependency_values(package),
        tuple(guide_rows),
        tuple(
            (master, tuple(metric_values(package, master).items()))
            for master in masters
        ),
        shape_source(package, names, masters, geometry=geometry),
        tuple(font_guide_names(package)) if font_guides else None,
    )


__all__ = [
    "METRICS",
    "font_guide_names",
    "layer_path",
    "master_layers",
    "metric_values",
    "muted",
    "selected_glyphs",
    "source_values",
]
