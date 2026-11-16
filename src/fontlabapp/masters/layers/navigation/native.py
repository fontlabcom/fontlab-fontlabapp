# this_file: src/fontlabapp/masters/layers/navigation/native.py
# SPDX-License-Identifier: Apache-2.0
"""Source-backed direct MainWindow occurrence replacement, awaiting native proof.

The native formatter retains logical anchor/position on same-count replacement.
They are opaque here: getSelectedCharacters is a witness, not their coordinates.
Unique native layer names and exact master-name/root-prefix associations are
supported, with unprefixed auxiliaries unambiguous only in single-master fonts.
Text/preview modes and shaped source mappings refuse before writing.
"""

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from fontlabapp.masters.layers.navigation.context import _context, _layers, _restore
from fontlabapp.masters.layers.navigation.data import NavigationRefused
from fontlabapp.masters.layers.navigation.symbols import freeze, tokens


@dataclass(frozen=True)
class Capture:
    """Bound source and opaque selection witness; no fabricated cursor fields."""

    layer: str
    layers: tuple[tuple[str, str], ...]
    index: int
    token: tuple
    symbols: tuple
    selected: tuple
    binding: tuple
    active: Any
    block: Any
    canvas: Any
    glyph: Any
    context: tuple


class Backend:
    """Lazy native adapter; no events are pumped between capture and write."""

    def __init__(self) -> None:
        self.native = import_module("fontlab")
        self.window = self.native.MainWindow()
        if not callable(getattr(self.window, "doRequestSubContent", None)):
            raise TypeError("Native MainWindow occurrence slot unavailable")
        self.user_area = int(self.native.fgSymbol.DataCode["UserAreaBegin"])
        if self.user_area != 100:
            raise ValueError("Unsupported native symbol data profile")

    def capture(self) -> Capture:
        native = self.native
        package = native.CurrentFont()
        workspace = native.flWorkspace.instance()
        canvas, block = workspace.getActiveCanvas(), workspace.getActiveTextBlock()
        if package is None or canvas is None or block is None:
            raise ValueError("No exact current font/canvas/text block")
        if not package.isValid or block.package.id != package.id:
            raise ValueError("Stale or foreign text block")
        modes = native.EditMode
        if block.editMode not in (modes["emEditOutline"], modes["emEditMetrics"]):
            raise ValueError("Text, preview or unsupported editor mode")
        active = block.getActiveGlyph()
        if active is None or not active.isActive or active.isNullGlyph:
            raise ValueError("No exact active occurrence")
        symbols = tuple(block.symbolList().symbols())
        symbol = active.symbol
        matches = [
            i
            for i, item in enumerate(symbols)
            if item.glyphIndex == symbol.glyphIndex and not item.cr
        ]
        if len(matches) != 1 or symbol.glyphIndex < 0 or symbol.ligatureIndex != 0:
            raise ValueError("Ambiguous or shaped source occurrence")
        index = matches[0]
        if tokens((symbols[index],), self.user_area) != tokens(
            (symbol,), self.user_area
        ):
            raise ValueError("Rendered occurrence differs from source symbol")
        glyph = active.glyph
        name = symbol.layerName or glyph.activeLayer.name
        layers = _layers(package, glyph, name)
        current = next(layer for layer in layers if layer.name == name)
        rows = tuple((str(layer.id), layer.name) for layer in layers)
        selected_list = block.getSelectedCharacters()
        selected = (
            ()
            if selected_list is None
            else tokens(selected_list.symbols(), self.user_area)
        )
        source = tokens(symbols, self.user_area)
        if selected.count(source[index]) > 1:
            raise ValueError("Ambiguous selected occurrence witness")
        binding = (
            package.id,
            canvas.id,
            block.id,
            glyph.id,
            block.editMode,
            tuple(package.masters),
            package.master,
        )
        context = _context(canvas, glyph)
        token = (
            binding,
            active.id,
            source,
            selected,
            rows,
            index,
            current.id,
            context,
            tuple(
                (layer.id, layer.name, layer.isService, layer.isMaskLayer)
                for layer in glyph.layers
            ),
        )
        return Capture(
            str(current.id),
            rows,
            index,
            token,
            source,
            selected,
            binding,
            active,
            block,
            canvas,
            glyph,
            context,
        )

    def replace(self, before: Capture, target: str) -> None:
        try:
            if self.capture().token != before.token:
                raise ValueError("Navigation source changed immediately before write")
            name = dict(before.layers)[target]
            symbol = self.native.fgSymbol(
                before.block.symbolList().symbols()[before.index]
            )
            symbol.layerName = name
            content = self.native.fgSymbolList([symbol])
            point = before.canvas.viewPoint
            transform = self.native.flTransform(before.canvas.viewTransform.transform)
            active_layer = before.glyph.activeLayer
            shapes = tuple(
                (shape, bool(shape.active))
                for layer in before.glyph.layers
                for shape in layer.shapes
            )
            format_mode = before.block.formatMode
            writer = self.window.doRequestSubContent
            if not callable(writer):
                raise TypeError("Native MainWindow occurrence slot unavailable")
        except Exception as error:
            raise NavigationRefused(str(error)) from error
        try:
            writer(content, 0, format_mode)
        finally:
            assignments = [(before.glyph, "activeLayer", active_layer)] + [
                (shape, "active", active) for shape, active in shapes
            ]
            assignments.extend(
                (
                    (before.canvas, "viewTransform", transform),
                    (before.canvas, "viewPoint", point),
                )
            )
            _restore(assignments)

    def verify(self, before: Capture, target: str) -> None:
        after = self.capture()
        expected = list(before.symbols)
        selected = list(expected[before.index])
        selected[4] = freeze(dict(before.layers)[target])
        expected[before.index] = tuple(selected)
        expected_selected = tuple(
            tuple(selected) if item == before.symbols[before.index] else item
            for item in before.selected
        )
        if (
            after.layers != before.layers
            or after.context != before.context
            or after.selected != expected_selected
            or after.binding != before.binding
            or after.index != before.index
            or after.layer != target
            or after.symbols != tuple(expected)
        ):
            raise RuntimeError("Native occurrence postcondition failed")
