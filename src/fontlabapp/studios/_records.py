# this_file: src/fontlabapp/studios/_records.py
# SPDX-License-Identifier: Apache-2.0
"""Shared metadata-safe glyph catalogue read for the studios (Scriptmix TODO:48).

What: ``glyph_records(package)`` returns exactly what the three private copies
in the Font Info tools (Calculate Vertical Metrics, Glyph Order Preview and
Export, Unicode Ranges and Codepages) return: ``[(name, [code, ...])]`` in
legacy ``FL.fl.font`` order, refused with the same message when the package
is not the current one. ``catalogue(package)`` adds the per-glyph facts the
Font Audit tabs read: per-master advance widths and contour counts, the
current master's components, composite and mark/note/export flags.
How: codes come from ``core.scripting.names_font_glyphs`` (``CurrentFont``
glyphs), never from ``flGlyph.fgGlyph``; the legacy names must list the same
glyphs in the same order, otherwise the read is refused (no silent reorder).
Layers are read with ``findLayer``, components through ``shapeData``; no
FontGate attribute is probed. Read-only and Qt-free. Used by
``fontlabapp.studios.font_audit``; A12/A29/A30 replace their copies with it.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from fontlabapp.core.scripting import current_package, names_font_glyphs, names_legacy_font

STALE = "Activate the original font and reopen this tool."
ORDER = "Font encoding order changed; reopen this tool."
SKIP_KEY = "public.skipExportGlyphs"


@dataclass(frozen=True)
class GlyphRecord:
    """One glyph of the catalogue; ``None`` marks a master without that layer."""

    name: str
    unicodes: tuple[int, ...]
    found: bool  # False: ``package.findName`` returned None (the originals skip it)
    widths: tuple[float | None, ...] = ()  # per ``Catalogue.masters``
    contours: tuple[int | None, ...] = ()  # per ``Catalogue.masters``
    components: tuple[str, ...] = ()  # on the current master
    current_contours: int | None = None  # on the current master
    composite: bool = False  # a component on any master
    mark: int = 0
    note: str = ""
    export: bool = True  # not in ``public.skipExportGlyphs``


@dataclass(frozen=True)
class Catalogue:
    """The complete read of one package, in font order."""

    package_id: Any
    family: str
    upm: int
    master: str
    masters: tuple[str, ...]
    records: tuple[GlyphRecord, ...]

    def by_name(self) -> dict[str, GlyphRecord]:
        """First record per name (font order)."""
        out: dict[str, GlyphRecord] = {}
        for record in self.records:
            out.setdefault(record.name, record)
        return out


def component_names(layer: Any) -> list[str]:
    """Base glyph names of the layer's components (the originals' helper)."""
    names = []
    for shape in layer.shapes:
        base = shape.shapeData.componentGlyph if shape.shapeData is not None else ""
        if base:
            names.append(base)
    return names


def glyph_records(package: Any) -> list[tuple[str, list[int]]]:
    """``[(name, [code, ...])]`` in legacy font order; the Font Info copies' contract."""
    active = current_package()
    if active is None or active.id != package.id:
        raise ValueError(STALE)
    names = names_legacy_font()
    encoded = names_font_glyphs()
    if [name for name, _ in encoded] != names:
        raise ValueError(ORDER)
    return [(name, list(codes)) for name, codes in encoded]


def skipped(package: Any) -> frozenset[str]:
    """Names in ``public.skipExportGlyphs`` (absent: none), as Smallcap Consistency reads it."""
    skip = package.packageLib.get(SKIP_KEY, ())
    if not isinstance(skip, (list, tuple)) or not all(isinstance(name, str) for name in skip):
        raise ValueError(f"{SKIP_KEY} must be a list of glyph names.")
    return frozenset(skip)


def _record(package: Any, name: str, codes: Iterable[int], masters: tuple[str, ...], current: str,
            skip: frozenset[str]) -> GlyphRecord:
    glyph = package.findName(name)
    if glyph is None:
        return GlyphRecord(name, tuple(codes), False)
    layers = [glyph.findLayer(master) for master in masters]
    layer = glyph.findLayer(current)
    return GlyphRecord(
        name,
        tuple(codes),
        True,
        widths=tuple(None if each is None else float(each.advanceWidth) for each in layers),
        contours=tuple(None if each is None else len(each.getContours()) for each in layers),
        components=tuple(component_names(layer)) if layer is not None else (),
        current_contours=None if layer is None else len(layer.getContours()),
        composite=any(component_names(each) for each in layers if each is not None),
        mark=int(glyph.mark or 0),
        note=glyph.note or "",
        export=name not in skip,
    )


def catalogue(package: Any) -> Catalogue:
    """Read every glyph of ``package`` (the current package) once; see the module text."""
    pairs = glyph_records(package)
    masters = tuple(package.masters)
    current = package.master
    skip = skipped(package)
    records = tuple(_record(package, name, codes, masters, current, skip) for name, codes in pairs)
    return Catalogue(package.id, package.info.familyName, int(package.upm), current, masters, records)


__all__ = ["Catalogue", "GlyphRecord", "catalogue", "component_names", "glyph_records", "skipped"]
