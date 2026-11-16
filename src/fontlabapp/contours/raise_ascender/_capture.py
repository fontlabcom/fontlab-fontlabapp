# this_file: src/fontlabapp/contours/raise_ascender/_capture.py
# SPDX-License-Identifier: MIT AND Apache-2.0
"""Resolve original target occurrences without initializing native active layers."""

from typing import Any

import fontlabapp.masters.layers.selection as selection
import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - the package __getattr__ is native
from fontlabapp import _native
from fontlabapp.contours.raise_ascender.model import check, number


def selected(all_layers: bool, deadline: float) -> tuple:
    """All mode needs only first parent; selected mode needs explicit slot layers."""
    document = selection._document(deadline)
    package, rows = document.package, []
    if document.context[2] == "font":
        names = selection.names_font_window_selection(
            expected_fg_id=int(package.fgId), deadline=deadline
        )
        for name in names:
            check(deadline)
            glyph = package.findName(name)
            layer = None if all_layers else glyph.findLayer(document.context[1])
            rows.append((glyph, layer))
    else:
        for block in document.blocks:
            check(deadline)
            for index in range(int(block.glyphsCount())):
                check(deadline)
                info = block.getGlyphAt(index)
                if info is None or not (info.isSelected or info.isActive):
                    continue
                glyph, layer = info.glyph, None
                if not all_layers:
                    name = str(info.symbol.layerName)
                    if not name:
                        raise ValueError(
                            "Selected editor slot has no explicit layer; native mapping remains unsupported."
                        )
                    layer = glyph.findLayer(name)
                rows.append((glyph, layer))
    for glyph, layer in rows:
        check(deadline)
        if glyph is None or glyph.isNull or int(glyph.package.id) != int(package.id):
            raise ValueError("A selected glyph changed owner or disappeared.")
        if not all_layers and (layer is None or layer.isNull):
            raise ValueError("A selected layer disappeared.")
    if all_layers:
        if not rows:
            raise ValueError("Select a glyph before raising all its layers.")
        glyph = rows[0][0]
        rows = []
        for layer in glyph.layers:
            check(deadline)
            if type(layer.isMaskLayer) is not bool:
                raise ValueError("Unreadable background role.")
            if not layer.isMaskLayer:
                rows.append((glyph, layer))
    return document, tuple(rows)


def masters(package: Any, deadline: float) -> tuple:
    """Named master JSON avoids key-master fallback in native metric getters."""
    check(deadline)
    data = _native("fontpr").call("get_font_info", font_id=scripting.font_id(package))
    names = tuple(str(name) for name in package.masters)
    entries = data.get("masters") if isinstance(data, dict) else None
    if not isinstance(entries, (list, tuple)) or len(set(names)) != len(names):
        raise ValueError("Unreadable or ambiguous declared master domain.")
    result = []
    for name in names:
        check(deadline)
        matches = [
            entry["fontMaster"]
            for entry in entries
            if isinstance(entry, dict)
            and isinstance(entry.get("fontMaster"), dict)
            and entry["fontMaster"].get("name") == name
        ]
        if len(matches) != 1:
            raise ValueError("A declared master lacks unique serialized metrics.")
        result.append((name, number(matches[0].get("xHeight", 0))))
    check(deadline)
    return tuple(result)


def dependencies(package: Any, deadline: float) -> tuple:
    """Read complete glyph/layer component dependencies, including auxiliaries."""
    font = _native("fontlab").CurrentFont()
    if font is None or int(font.id) != int(package.fgId):
        raise ValueError("Current FontGate carrier changed.")
    result = []
    for item in font.glyphs:
        check(deadline)
        glyph = package.findFgId(int(item.id))
        if glyph is None or glyph.isNull or str(glyph.name) != str(item.name):
            raise ValueError("Font glyph identity mapping changed.")
        layers = []
        for layer in glyph.layers:
            check(deadline)
            bases = []
            for shape in layer.shapes:
                check(deadline)
                if shape.isComponent:
                    bases.append(str(shape.shapeData.componentGlyph))
            layers.append(
                (int(layer.id), str(layer.name), bool(layer.autoLayer), tuple(bases))
            )
        result.append((int(glyph.id), str(glyph.name), tuple(layers)))
    check(deadline)
    return tuple(result)


def closure(dependencies: tuple, targets: set[str], deadline: float) -> set[str]:
    """Walk complete normal-component chains with a checkpoint for each layer."""
    affected = set(targets)
    while True:
        added = set()
        for _, name, layers in dependencies:
            check(deadline)
            for _, _, _, bases in layers:
                check(deadline)
                if affected.intersection(bases):
                    added.add(name)
        if added.issubset(affected):
            return affected
        affected.update(added)
