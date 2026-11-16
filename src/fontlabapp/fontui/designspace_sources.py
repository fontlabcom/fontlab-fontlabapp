# this_file: src/fontlabapp/fontui/designspace_sources.py
# SPDX-License-Identifier: Apache-2.0
"""Detached UFO source comparison, without Qt, interpolation or font writes.

``compare(path)`` reads continuous-axis designspaces through Fontport's
fontTools adapter. Missing/extra glyphs are relative to the first source.
``refresh(path, view.setPlainText)`` updates the source-comparison view only
after a complete read. Optional checkpoints bound cooperative GUI reads.
Compatibility has exactly the existing App model's structural scope: ordered
node types and anchor/component name sets, not interpolation certification.
"""

from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any

from fontlabapp.masters.layers.compatibility.model import (
    Difference, GlyphLayers, Layer, differences,
)

METRICS = ("unitsPerEm", "ascender", "descender", "xHeight", "capHeight", "italicAngle")


@dataclass(frozen=True)
class Axis:
    """Continuous user-axis bounds and user-to-design mapping."""

    name: str
    tag: str
    minimum: float
    default: float
    maximum: float
    mapping: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class Source:
    """One source row; metrics follow METRICS and may be unset."""

    name: str
    path: str
    layer: str
    design_location: tuple[tuple[str, float], ...]
    user_location: tuple[tuple[str, float], ...]
    metrics: tuple[float | None, ...]
    missing: tuple[str, ...]
    extra: tuple[str, ...]


@dataclass(frozen=True)
class Glyph:
    """Advances follow source order; None compatibility means not comparable."""

    name: str
    advances: tuple[float | None, ...]
    compatible: bool | None
    differences: tuple[Difference, ...]


@dataclass(frozen=True)
class Report:
    """Detached rows retain file order for sources and sorted glyph names."""

    axes: tuple[Axis, ...]
    sources: tuple[Source, ...]
    glyphs: tuple[Glyph, ...]


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("Source metrics and advance widths must be finite numbers")
    return float(value)


def _source(descriptor: Any, check: Callable[[], None]) -> tuple[str, tuple, dict]:
    from ufoLib2 import Font
    from fontlab_fontport.memory import UFOBackend

    if descriptor.path is None:
        raise ValueError("Designspace source has no file path")
    check()
    with Font.open(descriptor.path) as font:
        check()
        backend = UFOBackend(font)
        layer = descriptor.layerName or backend.default_layer()
        if layer not in backend.layer_names():
            raise ValueError(f"Source layer does not exist: {layer}")
        metrics = tuple(backend.get_info(key) for key in METRICS)
        metrics = tuple(None if v is None else _number(v) for v in metrics)
        glyphs = {}
        for name in backend.glyph_names(layer):
            check()
            glyphs[name] = backend.read_glyph(name, layer)
        check()
    return layer, metrics, glyphs


def _glyph(name: str, rows: list[dict], labels: tuple[str, ...], check: Callable[[], None]) -> Glyph:
    advances, layers = [], []
    for glyphs, label in zip(rows, labels, strict=True):
        check()
        glyph = glyphs.get(name)
        advances.append(None if glyph is None else _number(glyph.width))
        if glyph is not None:
            layers.append(Layer(
                label,
                tuple(tuple(p.type or "offcurve" for p in c) for c in glyph.contours),
                frozenset(a.name for a in glyph.anchors if a.name),
                frozenset(c.baseGlyph for c in glyph.components),
            ))
    comparable = len(layers) == len(rows) and len(layers) > 1
    found = differences(GlyphLayers(name, tuple(layers))) if comparable else ()
    return Glyph(name, tuple(advances), not found if comparable else None, found)


def compare(path: str | Path, *, check: Callable[[], None] = lambda: None) -> Report:
    """Read all sources or raise; missing files/layers never yield partial success.

    Discrete axes, anisotropic locations and multi-axis maps are refused.
    fontTools ignores dimensions with undefined axes when parsing the file.
    Metrics are raw source units, not rescaled when UPM differs. Named source
    layers use their own glyphs and the containing UFO's shared font info.
    check runs between source/glyph reads; blocking I/O cannot be preempted.
    """
    from fontlabapp.fontui._fontport import require_fontport

    with require_fontport(__name__):
        from fontlab_fontport.designspace import Designspace

    check()
    designspace = Designspace.open(path)
    check()
    document = designspace.document
    if not document.sources:
        raise ValueError("The designspace has no sources")
    rows, sources = [], []
    for descriptor, location in zip(document.sources, designspace.sources, strict=True):
        if any(isinstance(value, tuple) for value in descriptor.designLocation.values()):
            raise ValueError("Anisotropic source locations are unsupported")
        check()
        layer, metrics, glyphs = _source(descriptor, check)
        rows.append(glyphs)
        reference = set(rows[0])
        sources.append(Source(
            location.name, descriptor.path, layer,
            tuple(descriptor.getFullDesignLocation(document).items()),
            location.coordinates, metrics,
            tuple(sorted(reference - glyphs.keys())),
            tuple(sorted(glyphs.keys() - reference)),
        ))
    labels = tuple(f"{i + 1}: {s.name}" for i, s in enumerate(sources))
    names = sorted(set().union(*(set(row) for row in rows)))
    axes = tuple(Axis(a.name, a.tag, a.minimum, a.default, a.maximum, tuple(a.map))
                 for a in designspace.axes)
    return Report(axes, tuple(sources), tuple(_glyph(n, rows, labels, check) for n in names))


def render(report: Report, *, check: Callable[[], None] = lambda: None) -> str:
    """Render a plain-text metrics table and per-glyph diagnostic summary."""
    lines = ["Source metrics (raw units; missing/extra relative to source 1)",
             "Source\tUPM\tascender\tdescender\txHeight\tcapHeight\titalicAngle"]
    for axis in report.axes:
        check()
        lines.append(f"Axis {axis.name} ({axis.tag}): {axis.minimum:g}–{axis.maximum:g}; "
                     f"default {axis.default:g}; map {axis.mapping}")
    for i, source in enumerate(report.sources, 1):
        check()
        values = "\t".join("unset" if v is None else f"{v:g}" for v in source.metrics)
        lines.extend((f"{i}: {source.name}\t{values}",
                      f"  {source.path}; layer {source.layer}",
                      f"  design location: {dict(source.design_location)}; "
                      f"user location: {dict(source.user_location)}",
                      f"  Missing: {', '.join(source.missing) or 'none'}; "
                      f"extra: {', '.join(source.extra) or 'none'}"))
    lines.append("Structural checks only; not an interpolation certificate.")
    for glyph in report.glyphs:
        check()
        status = "not comparable" if glyph.compatible is None else (
            "compatible" if glyph.compatible else "not compatible")
        widths = ", ".join("missing" if v is None else f"{v:g}" for v in glyph.advances)
        lines.append(f"{glyph.name}: advances [{widths}]; {status}")
        lines.extend(f"  {d.kind}: {d.previous_layer}={d.previous}; {d.layer}={d.current}"
                     for d in glyph.differences)
    return "\n".join(lines)


def refresh(path: str | Path, set_text: Callable[[str], Any], *,
            check: Callable[[], None] = lambda: None) -> Report:
    """Thin view hook: callback exceptions propagate; no widget is owned here."""
    result = compare(path, check=check)
    text = render(result, check=check)
    check()
    set_text(text)
    return result
