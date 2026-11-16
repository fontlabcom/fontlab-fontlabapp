# this_file: src/fontlabapp/anchors/duplicates/capture.py
# SPDX-License-Identifier: Apache-2.0
"""Bound, complete duplicate-anchor reads with no FontGate glyph conversion.

Known pin attributes are scalar snapshots. Reflections, pin selection, extended
property enumeration and complete history payload lack Python bindings; their
preservation remains an explicit owned native acceptance requirement.
"""

from threading import current_thread, main_thread
from time import monotonic
from typing import Any

from fontlabapp import _native
from fontlabapp.anchors.duplicates.model import Layer, Pin, findings
from fontlabapp.core.scripting import _carrier_id


def check(deadline: float) -> None:
    """Refuse incomplete scans or writes after the one absolute deadline."""
    if monotonic() >= deadline:
        raise TimeoutError("Anchor operation expired; no complete result is available.")


def context(package: Any, deadline: float) -> tuple:
    """Fence package/carrier identity, font order, selection and master domain."""
    check(deadline)
    fl = _native("FL").fl
    font = fl.font
    if font is None or _carrier_id(font, int(package.fgId)) != int(package.fgId):
        raise ValueError("Font-window carrier differs from the current package.")
    names, selected = [], []
    for index in range(len(font)):
        check(deadline)
        name = str(font[index].name)
        names.append(name)
        if fl.Selected(index):
            selected.append(name)
    check(deadline)
    return (
        (int(package.id), int(package.fgId), str(package.master)),
        tuple(names),
        tuple(selected),
        tuple(str(m) for m in package.masters),
    )


def pin_value(pin: Any, deadline: float) -> Pin:
    """Read bound values; retain native style scalars without enum coercion.

    Removal never rebuilds surviving native pins or writes any style field.
    """
    check(deadline)
    return Pin(
        int(pin.id),
        str(pin.name),
        float(pin.point.x()),
        float(pin.point.y()),
        (
            int(pin.appearance),
            bool(pin.anchor),
            bool(pin.cloudEnabled),
            bool(pin.markEnabled),
            pin.style,
            str(pin.expressionX),
            str(pin.expressionY),
        ),
    )


def read(package: Any, names: tuple, masters: tuple, deadline: float) -> tuple:
    """Capture every existing named master and every layer's dependency record."""
    layers, dependencies = [], []
    seen_layers, seen_pins = set(), set()
    for name in names:
        check(deadline)
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            raise ValueError("Glyph source changed during capture.")
        for layer in glyph.layers:
            check(deadline)
            bases = []
            for shape in layer.shapes:
                check(deadline)
                if shape.isComponent:
                    bases.append(str(shape.shapeData.componentGlyph))
            dependencies.append((name, bool(layer.autoLayer), tuple(bases)))
        for master in masters:
            check(deadline)
            layer = glyph.findLayer(master)
            if layer is None or layer.isNull:
                continue
            pins = tuple(pin_value(pin, deadline) for pin in layer.anchors)
            findings(pins)
            pin_ids = {pin.identity for pin in pins}
            if int(layer.id) in seen_layers or seen_pins.intersection(pin_ids):
                raise ValueError(
                    "Shared layer or anchor identity has ambiguous ownership."
                )
            seen_layers.add(int(layer.id))
            seen_pins.update(pin_ids)
            layers.append(
                Layer(
                    name,
                    master,
                    int(glyph.id),
                    int(layer.id),
                    bool(layer.autoLayer),
                    pins,
                )
            )
    return tuple(layers), tuple(dependencies)


def require_main_thread() -> None:
    """Keep native reads and writes on the existing FontLab UI thread."""
    if current_thread() is not main_thread():
        raise RuntimeError("Run duplicate-anchor operations on the main UI thread.")
