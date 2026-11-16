# this_file: src/fontlabapp/anchors/crossfont/capture.py
# SPDX-License-Identifier: Apache-2.0
"""Registered two-font reads with source-specific selection and no activation.

Canonical FontGate glyph lists avoid flGlyph.fgGlyph's note-mirror mutation.
No source completeData/UpdateAll, font switch or legacy selection setter is used.
"""

from dataclasses import dataclass, field
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fontlabapp import _native
from fontlabapp.anchors.duplicates.capture import check, pin_value, require_main_thread
from fontlabapp.anchors.crossfont.model import Pin, layer_pairs
from fontlabapp.core.scripting import (
    _require_selection_window,
    names_font_window_selection,
)


@dataclass(frozen=True)
class Font:
    """Stable package identity, readable basename and canonical font-order names."""

    identity: int
    fg_id: int
    label: str
    masters: tuple[str, ...]
    names: tuple[str, ...]
    package: Any = field(compare=False, repr=False)
    font: Any = field(compare=False, repr=False)


def fonts(
    deadline: float, *, checkpoint: Callable[[], None] | None = None
) -> tuple[Font, ...]:
    """Resolve registered carriers; optional caller checks run inside metadata loops.

    Default callers retain their identity/order/filter policy. Both the native
    deadline and caller cancellation are checked per package/font/master/glyph;
    synchronous native list conversions are checked immediately on return.
    """

    def tick() -> None:
        """Preserve the shared deadline while propagating optional cancellation."""
        check(deadline)
        if checkpoint is not None:
            checkpoint()

    tick()
    require_main_thread()
    native = _native("fontlab")
    registered = {}
    raw_packages = native.flWorkspace.instance().packages()
    tick()
    for item in raw_packages:
        tick()
        package = native.flPackage(item)
        tick()
        registered[int(package.fgId)] = package
    result = []
    raw_fonts = native.AllFonts()
    tick()
    for font in raw_fonts:
        tick()
        package = registered.get(int(font.id))
        if package is None:
            raise ValueError("An open font is not registered in the workspace.")
        masters, names = [], []
        raw_masters = package.masters
        tick()
        for master in raw_masters:
            tick()
            text = str(master)
            if "#" not in text:
                masters.append(text)
        raw_glyphs = font.glyphs
        tick()
        for glyph in raw_glyphs:
            tick()
            names.append(str(glyph.name))
        tick()
        result.append(
            Font(
                int(package.id),
                int(font.id),
                Path(str(font.path)).name,
                tuple(masters),
                tuple(names),
                package,
                font,
            )
        )
    tick()
    return tuple(result)


def resolve(rows: tuple[Font, ...], identity: int) -> Font:
    """A stale selector never resolves by duplicate basename or shifted row index."""
    row = next((row for row in rows if row.identity == identity), None)
    if row is None:
        raise ValueError("A chosen font closed; refresh the font lists.")
    return row


def selected(source: Font, deadline: float) -> tuple[str, ...]:
    """Read selection only from a verified chosen-source Font-window carrier."""
    try:
        _require_selection_window(source.identity)
        return tuple(
            names_font_window_selection(expected_fg_id=source.fg_id, deadline=deadline)
        )
    except ValueError as error:
        raise ValueError(
            "Activate the chosen source Font window before copying Selected glyphs."
        ) from error


def dependencies(destination: Font, deadline: float) -> tuple:
    """Read this actual destination font, not the current-font helper's domain."""
    rows = []
    for name in destination.names:
        check(deadline)
        glyph = destination.package.findName(name)
        if glyph is None or glyph.isNull:
            raise ValueError("A destination glyph disappeared during capture.")
        for layer in glyph.layers:
            check(deadline)
            bases = tuple(
                str(s.shapeData.componentGlyph) for s in layer.shapes if s.isComponent
            )
            rows.append((name, bool(layer.autoLayer), bases))
    return tuple(rows)


def pin_record(pin: Any, deadline: float) -> Pin:
    """One explicit native pin value, without reconstructing effective flags."""
    p = pin_value(pin, deadline)
    return Pin(p.identity, p.name, p.x, p.y, p.state)


def pins(layer: Any, deadline: float) -> tuple[Pin, ...]:
    """Reuse explicit fields without inferring raw hidden mark state."""
    return tuple(pin_record(pin, deadline) for pin in layer.anchors)


@dataclass(frozen=True)
class Layer:
    """One captured existing layer; a missing layer is represented separately."""

    identity: int
    width: float
    automatic: bool
    history: int
    pins: tuple[Pin, ...]


@dataclass(frozen=True)
class Snapshot:
    """Complete relevant source/target facts with native handles out of equality."""

    fonts: tuple[Font, ...]
    names: tuple[str, ...]
    pairs: tuple[tuple[str, str], ...]
    layers: tuple
    dependencies: tuple
    skipped: tuple[str, ...]
    handles: dict = field(compare=False, repr=False)


def read(
    source_id: int,
    destination_id: int,
    source_layer: str,
    destination_layer: str,
    only_selected: bool,
    deadline: float,
) -> Snapshot:
    """One full pass; callers compare two passes before staging and history."""
    rows = fonts(deadline)
    a, b = resolve(rows, source_id), resolve(rows, destination_id)
    names = selected(a, deadline) if only_selected else a.names
    pairs = layer_pairs(a.masters, b.masters, source_layer, destination_layer)
    facts, handles, skipped = [], {}, []
    for name in names:
        check(deadline)
        if name not in a.names:
            skipped.append(f"Source glyph not found: {name}")
            continue
        if name not in b.names:
            skipped.append(f"Destination glyph not found: {name}")
            continue
        for left, right in pairs:
            captured = []
            for font, master in ((a, left), (b, right)):
                check(deadline)
                glyph = font.package.findName(name)
                if glyph is None or glyph.isNull:
                    raise ValueError("A captured glyph identity changed.")
                layer = glyph.findLayer(master)
                if layer is None or layer.isNull:
                    captured.append(None)
                    continue
                value = Layer(
                    int(layer.id),
                    float(layer.advanceWidth),
                    bool(layer.autoLayer),
                    int(glyph.currentHistoryState()),
                    pins(layer, deadline),
                )
                captured.append(value)
                handles[value.identity] = (glyph, layer)
            facts.append((name, left, right, *captured))
            if any(v is None for v in captured):
                skipped.append(f"Missing layer: {name}/{left} → {right}")
    check(deadline)
    return Snapshot(
        rows,
        names,
        pairs,
        tuple(facts),
        dependencies(b, deadline),
        tuple(skipped),
        handles,
    )
