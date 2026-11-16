# this_file: src/fontlabapp/vfjo/_edit.py
# SPDX-License-Identifier: Apache-2.0
"""Navigate and edit ``Objects`` in place, and paste them into a font.

What: ``layers``, ``elements``, ``contours`` and ``anchors`` yield boxes;
``edit_nodes``, ``move``, ``scale``, ``rename``, ``set_width`` and
``add_suffix`` change the data in place and return it; ``paste`` sends it
to ``json_data.paste_glyphs`` or ``json_data.paste_shapes``.

How: ``move`` and ``scale`` apply one map ``x' = sx*x + tx``,
``y' = sy*y + ty`` and keep the data consistent. An element with a
``transform`` or a component gets a new transform (offsets and scales are
composed; existing keys stay, new ``xOffset``/``yOffset``/``xScale``/
``yScale`` keys are added only at non-default values) and its nodes stay.
Other elements get new node coordinates, and their nested elements follow
the same rule. Anchors, guideline positions (``vertical`` maps x,
``horizontal`` maps y, ``center`` maps both), hint points and hint
thickness (``vertical`` by ``sx``, ``horizontal`` by ``sy``) follow.
Numbers are rounded to 3 decimals; whole numbers stay ``int``.

Limits: guideline ``vector`` directions are not changed by a non-uniform
scale. ``edit_nodes`` refuses callbacks that change a contour's point
count, because hints address nodes by point index. Nothing here touches a
font until ``paste``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from typing import Any

from fontlabapp.objects import json_data
from fontlabapp.vfjo._data import Objects, _Data
from fontlabapp.vfjo.nodes import Node, Number, format_nodes, parse_nodes

_TRANSFORM_DEFAULTS = {"xOffset": 0, "yOffset": 0, "xScale": 1, "yScale": 1}


def _items(obj: Any) -> list[tuple[str, _Data]]:
    if isinstance(obj, Objects):
        return obj.items()
    level = getattr(obj, "__dict__", {}).get("_level")
    if level in json_data.KINDS:
        return [(level, obj)]
    raise TypeError(
        f"Expected vfjo.Objects or a glyph, layer, element or contour box, got {type(obj).__name__}."
    )


def _labelled_layers(obj: Any) -> Iterator[tuple[str, _Data]]:
    for kind, box in _items(obj):
        if kind == "glyph":
            for layer in box.get("layers") or ():
                yield (
                    f"glyph {box.get('name', '')!r} layer {layer.get('name', '')!r}",
                    layer,
                )
        elif kind == "layer":
            yield f"layer {box.get('name', '')!r}", box


def _walk(elements: Any) -> Iterator[_Data]:
    for element in elements or ():
        yield element
        yield from _walk((element.get("elementData") or {}).get("elements"))


def _labelled_contours(obj: Any) -> Iterator[tuple[str, _Data]]:
    def of(label: str, elements: Any) -> Iterator[tuple[str, _Data]]:
        for element in _walk(elements):
            for index, contour in enumerate(
                (element.get("elementData") or {}).get("contours") or ()
            ):
                yield f"{label} contour {contour.get('id', index)!r}", contour

    for label, layer in _labelled_layers(obj):
        yield from of(label, layer.get("elements"))
    for kind, box in _items(obj):
        if kind == "element":
            yield from of(f"element {box.get('id', '')!r}", [box])
        elif kind == "contour":
            yield f"contour {box.get('id', '')!r}", box


def layers(obj: Any) -> Iterator[_Data]:
    """Yield the layer boxes of all glyph items and layer items."""
    for _, layer in _labelled_layers(obj):
        yield layer


def elements(obj: Any) -> Iterator[_Data]:
    """Yield the element boxes, nested ``elementData.elements`` included."""
    for layer in layers(obj):
        yield from _walk(layer.get("elements"))
    for kind, box in _items(obj):
        if kind == "element":
            yield from _walk([box])


def contours(obj: Any) -> Iterator[_Data]:
    """Yield the contour boxes (coordinates before element transforms)."""
    for _, contour in _labelled_contours(obj):
        yield contour


def anchors(obj: Any) -> Iterator[_Data]:
    """Yield the anchor boxes of all layers."""
    for layer in layers(obj):
        yield from layer.get("anchors") or ()


def _points(nodes: list[Node]) -> int:
    return sum(len(node.points) for node in nodes)


def edit_nodes(obj: Any, fn: Callable[[Node], Node | None]) -> Any:
    """Replace each node by ``fn(node)`` (``None`` keeps it); return ``obj``.

    Raises ``ValueError`` when a contour's point count changes.
    """
    for label, contour in _labelled_contours(obj):
        old = parse_nodes(list(contour.get("nodes") or ()))
        new = [fn(node) or node for node in old]
        if _points(new) != _points(old):
            raise ValueError(
                f"edit_nodes changed the point count of {label}: {_points(old)} -> {_points(new)}"
            )
        contour["nodes"] = format_nodes(new)
    return obj


def _num(value: float) -> Number:
    value = round(value, 3)
    return int(value) if value == int(value) else value


class _Affine:
    def __init__(self, sx: Number, sy: Number, tx: Number, ty: Number) -> None:
        self.sx, self.sy, self.tx, self.ty = sx, sy, tx, ty

    def __call__(self, x: Number, y: Number) -> tuple[Number, Number]:
        return _num(self.sx * x + self.tx), _num(self.sy * y + self.ty)

    def point(self, text: str) -> str:
        return Node.parse(text).mapped(self).format()

    def transform(self, element: _Data) -> None:
        old = element.get("transform") or {}
        unknown = set(old) - set(_TRANSFORM_DEFAULTS)
        if unknown:
            raise ValueError(
                f"Element transform has keys vfjo cannot compose: {sorted(unknown)}"
            )
        value = {
            key: old.get(key, default) for key, default in _TRANSFORM_DEFAULTS.items()
        }
        new = {
            "xOffset": _num(self.sx * value["xOffset"] + self.tx),
            "yOffset": _num(self.sy * value["yOffset"] + self.ty),
            "xScale": _num(self.sx * value["xScale"]),
            "yScale": _num(self.sy * value["yScale"]),
        }
        kept = {
            key: new[key]
            for key in _TRANSFORM_DEFAULTS
            if key in old or new[key] != _TRANSFORM_DEFAULTS[key]
        }
        if "transform" in element:
            for key, number in kept.items():
                element["transform"][key] = number
        elif kept:
            element["transform"] = kept

    def elements(self, items: Any) -> None:
        for element in items or ():
            data = element.get("elementData") or {}
            if "transform" in element or "component" in element or "component" in data:
                self.transform(element)
                continue
            for contour in data.get("contours") or ():
                contour["nodes"] = [
                    self.point(text) for text in contour.get("nodes") or ()
                ]
            self.elements(data.get("elements"))

    def layer(self, layer: _Data, *, anchors: bool, widths: bool) -> None:
        self.elements(layer.get("elements"))
        if anchors:
            for anchor in layer.get("anchors") or ():
                if "point" in anchor:
                    anchor["point"] = self.point(anchor["point"])
        for guide in layer.get("guidelines") or ():
            self.guide(guide)
        for hint in layer.get("hints") or ():
            self.hint(hint)
        if widths and "advanceWidth" in layer:
            layer["advanceWidth"] = round(self.sx * layer["advanceWidth"])

    def guide(self, guide: _Data) -> None:
        if "position" in guide:
            if guide.get("vertical"):
                guide["position"] = _num(self.sx * guide["position"] + self.tx)
            elif guide.get("horizontal"):
                guide["position"] = _num(self.sy * guide["position"] + self.ty)
        if "center" in guide:
            guide["center"] = self.point(guide["center"])

    def hint(self, hint: _Data) -> None:
        for value in hint.values():
            node = value.get("nodeNode") if isinstance(value, Mapping) else None
            if isinstance(node, Mapping) and "point" in node:
                node["point"] = self.point(node["point"])
        if "thickness" in hint:
            factor = self.sx if hint.get("vertical") else self.sy
            hint["thickness"] = _num(factor * hint["thickness"])

    def apply(self, obj: Any, *, anchors: bool, widths: bool) -> Any:
        for kind, box in _items(obj):
            if kind == "glyph":
                for layer in box.get("layers") or ():
                    self.layer(layer, anchors=anchors, widths=widths)
            elif kind == "layer":
                self.layer(box, anchors=anchors, widths=widths)
            elif kind == "element":
                self.elements([box])
            else:
                box["nodes"] = [self.point(text) for text in box.get("nodes") or ()]
        return obj


def move(obj: Any, dx: Number, dy: Number, *, anchors: bool = True) -> Any:
    """Move outlines, components, anchors, guidelines and hints by ``(dx, dy)``; return ``obj``."""
    return _Affine(1, 1, dx, dy).apply(obj, anchors=anchors, widths=False)


def scale(
    obj: Any,
    sx: Number,
    sy: Number | None = None,
    *,
    origin: tuple[Number, Number] = (0, 0),
    anchors: bool = True,
    widths: bool = False,
) -> Any:
    """Scale by ``sx`` (and ``sy``, default ``sx``) around ``origin``; ``widths`` scales ``advanceWidth``."""
    sy = sx if sy is None else sy
    ox, oy = origin
    return _Affine(sx, sy, ox * (1 - sx), oy * (1 - sy)).apply(
        obj, anchors=anchors, widths=widths
    )


def rename(obj: Objects, rename: Mapping[str, str] | Callable[[str], str]) -> Objects:
    """Rename glyph items from a mapping (missing names stay) or a function; return ``obj``.

    Unicode values stay; ``paste`` drops values that clash in the font.
    """
    for glyph in obj.glyphs:
        old = str(glyph.get("name", ""))
        glyph["name"] = (
            rename.get(old, old) if isinstance(rename, Mapping) else rename(old)
        )
    return obj


def set_width(obj: Any, width: Number | Callable[[Number], Number]) -> Any:
    """Set every layer's ``advanceWidth`` to a number or ``width(old_width)``; return ``obj``."""
    for layer in layers(obj):
        old = layer.get("advanceWidth", 0)
        layer["advanceWidth"] = width(old) if callable(width) else width
    return obj


def add_suffix(obj: Objects, suffix: str, *, drop_unicodes: bool = True) -> Objects:
    """Append ``suffix`` to every glyph name and return ``obj``.

    By default the Unicode values (``unicode``, ``unicodes``) are removed too,
    so pasted copies do not clash with the originals; pass
    ``drop_unicodes=False`` to keep them.
    """
    rename(obj, lambda name: name + suffix)
    if drop_unicodes:
        for glyph in obj.glyphs:
            for key in ("unicode", "unicodes"):
                glyph.pop(key, None)
    return obj


def _current_package() -> Any:
    from fontlabapp.core.scripting import current_package

    return current_package()


def _current_glyph() -> Any:
    from fontlabapp import _native

    return _native("fontlab").CurrentGlyph()


def _facts(package: Any) -> Any:
    from fontlabapp.core.history.glyphs import scan_auto_facts

    return scan_auto_facts(package)


def paste(
    objs: Objects, font: Any = None, *, on_conflict: str = "rename", **kw: Any
) -> json_data.Pasted:
    """Paste ``objs`` into ``font`` (default: the current font), with Undo.

    Glyph data goes to ``json_data.paste_glyphs`` (new glyphs; ``on_conflict``
    is ``"rename"`` or ``"skip"`` and applies to glyph data only). FontLab may
    order the new glyph's layers differently from the JSON. Layer, element or
    contour data (one kind at a time) goes to ``json_data.paste_shapes`` on
    the current glyph's active layer. Empty data, glyphs mixed with shapes or
    more than one shape kind raise ``ValueError``; no font or no current glyph
    raises ``RuntimeError``.
    """
    kind = objs.kind
    if not kind:
        raise ValueError("Nothing to paste: the object JSON is empty.")
    if kind == "mixed" and objs.glyphs:
        raise ValueError("Cannot paste glyphs and shapes together; split them first.")
    if kind == "mixed":
        kinds = sorted({k for k, _ in objs.items()})
        raise ValueError(
            f"Cannot paste more than one shape kind at once ({', '.join(kinds)}); split them first."
        )
    package = font if font is not None else _current_package()
    if package is None:
        raise RuntimeError("No font is open.")
    envelope = objs.envelope()
    if kind == "glyph":
        return json_data.paste_glyphs(
            package, envelope, facts=_facts(package), on_conflict=on_conflict, **kw
        )
    glyph = _current_glyph()
    if glyph is None:
        raise RuntimeError("No current glyph to paste shapes into.")
    return json_data.paste_shapes(
        glyph.activeLayer(), glyph, envelope, facts=_facts(package), **kw
    )


__all__ = [
    "add_suffix",
    "anchors",
    "contours",
    "edit_nodes",
    "elements",
    "layers",
    "move",
    "paste",
    "rename",
    "scale",
    "set_width",
]
