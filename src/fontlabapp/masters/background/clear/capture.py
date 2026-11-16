# this_file: src/fontlabapp/masters/background/clear/capture.py
# SPDX-License-Identifier: Apache-2.0
"""Whole-font physical layer/mask mapping, without creating any background.

Native getMaskLayer(False) reverses direction on mask objects. Only foreground
entries call it. Declared master names, not interpolatable auxiliary-name flags,
identify the original master-only scope. Captured facts fence mapping and dates;
they do not claim arbitrary getter/cache or unenumerable metadata preservation.
"""

from time import monotonic
from typing import Any

from fontlabapp.masters.background.clear.model import Layer


def check(deadline: float) -> None:
    """Reject incomplete capture/preflight under the caller's absolute deadline."""
    if monotonic() >= deadline:
        raise TimeoutError("Background operation expired; refresh before clearing.")


def flag(obj: Any, name: str) -> bool:
    """Require the measured non-callable native boolean property contract."""
    result = getattr(obj, name)
    if type(result) is not bool:
        raise TypeError(f"Unreadable native layer flag: {name}.")
    return result


def read(package: Any, font: Any, deadline: float, stamp: Any) -> tuple:
    """Keep font/layer order, complete dependency links and original identities."""
    masters = tuple(package.masters)
    if any(not isinstance(name, str) for name in masters) or len(set(masters)) != len(masters):
        raise ValueError("Declared master names are unreadable or repeated.")
    layers, dependencies, glyphs = [], [], []
    seen_glyphs, seen_names, seen_layers = set(), set(), set()
    for record in font.glyphs:
        check(deadline)
        glyph = package.findFgId(int(record.id))
        if glyph is None or glyph.isNull or not glyph.isValid:
            raise ValueError("A native glyph mapping is missing or invalid.")
        identity, name = int(glyph.id), record.name
        if (
            not isinstance(name, str)
            or identity in seen_glyphs
            or name in seen_names
            or int(glyph.fgGlyphId) != int(record.id)
            or glyph.name != name
            or int(glyph.package.id) != int(package.id)
        ):
            raise ValueError("Glyph identity, name, owner or complete order changed.")
        seen_glyphs.add(identity)
        seen_names.add(name)
        layer_ids = []
        for layer in glyph.layers:
            check(deadline)
            layer_id, label = int(layer.id), layer.name
            if (
                layer_id in seen_layers
                or not isinstance(label, str)
                or int(layer.glyph.id) != identity
                or layer.isNull
                or not layer.isValid
            ):
                raise ValueError("Layer identity, name or ownership is ambiguous.")
            seen_layers.add(layer_id)
            layer_ids.append(layer_id)
            mask, service, auto = (flag(layer, field) for field in ("isMaskLayer", "isService", "autoLayer"))
            background_id = None
            if not mask:
                background = layer.getMaskLayer(False)
                if background is not None and not background.isNull and background.isValid:
                    background_id = int(background.id)
            layers.append(Layer(identity, name, layer_id, label,
                                label in masters and not mask and not service,
                                service, mask, auto, background_id, flag(layer, "isLocked")))
            bases = []
            for shape in layer.shapes:
                check(deadline)
                if flag(shape, "isComponent"):
                    bases.append(str(shape.shapeData.componentGlyph))
            dependencies.append((name, auto, tuple(bases)))
        # activeLayer/isActive getters initialize a null active pointer. This
        # resolver(False) never assigns; a locked target is refused separately.
        active = glyph.updateActiveLayer(False)
        active_id = None
        if active is None or flag(active, "isNull"):
            if layer_ids:
                raise ValueError("Native active resolver is missing for nonempty layers.")
        else:
            if not flag(active, "isValid") or int(active.id) not in layer_ids or int(active.glyph.id) != identity:
                raise ValueError("Native active resolver ownership is unreadable.")
            active_id = int(active.id)
        glyphs.append((int(record.id), identity, name, stamp(glyph), tuple(layer_ids), active_id))
    check(deadline)
    return tuple(layers), tuple(dependencies), tuple(glyphs)
