# this_file: src/fontlabapp/components/decompose.py
"""Decompose a layer's components into placed base contours, read-only.

Evidence classes follow Issue 209 ``native-data-map.md`` §5: ``shape.isComponent``
(a-src, b), ``shapeData.componentGlyph`` / ``componentLayer`` (a-src, b),
``shape.transform`` as a QTransform (b), ``package.findName`` and
``glyph.findLayer`` (a-stub, b). An empty ``componentLayer`` means the master
that owns the shown layer at every nesting level, as Glyport's natively run
``native_reference`` resolves it (b); that FontLab draws the same is (c).
Used by ``fontlabapp.plugins.snapshot.capture``; it never calls a writer.
"""

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from fontlabapp.contours import affine

__all__ = ["MAX_DEPTH", "owner_master", "read"]

#: Deepest nesting decomposed; deeper references are cut and reported.
MAX_DEPTH = 8

Row = tuple[str, affine.Affine, tuple[Any, ...]]


def _place(contour: Any, transform: affine.Affine) -> Any:
    """Map one contour record's nodes through ``transform``."""
    nodes = []
    for node in contour.nodes:
        x, y = affine.apply(transform, node.x, node.y)
        nodes.append(replace(node, x=x, y=y, selected=False))
    return replace(contour, nodes=tuple(nodes))


def owner_master(
    package: Any, layer: Any, items: Callable[[Callable[[], Any]], list[Any]]
) -> str:
    """The master that owns the shown layer: its name when it is a master.

    Else ``package.master``, so a shown mask or brace layer uses the current
    master (b: Glyport ``native_reference``). Plugmix metrics, kerning groups
    and requested glyphs use the same rule. The current master's own layer
    skips the ``masters`` read, which every Plugmix paint would otherwise pay.
    """
    shown, current = str(layer.name), str(package.master)
    if shown == current:
        return current
    masters = {str(master) for master in items(lambda: package.masters)}
    return shown if shown in masters else current


def _refusal(base: str, path: tuple[str, ...], shape: Any) -> str | None:
    """Why a component cannot be decomposed here, or None."""
    if base in path:
        return "cycle"
    if len(path) > MAX_DEPTH:  # path holds the top glyph, so this is depth
        return f"nested deeper than {MAX_DEPTH}"
    if not shape.transform.isAffine():
        return "transform is not affine"
    return None


def read(
    package: Any,
    name: str,
    layer: Any,
    contours: Callable[[Any], tuple[Any, ...]],
    *,
    items: Callable[[Callable[[], Any]], list[Any]],
    revision: Callable[[Any], Any],
    report: Callable[[Exception], object],
) -> tuple[tuple[Row, ...], tuple[tuple[str, Any], ...]]:
    """Return ``(rows, stamps)`` for glyph ``name``'s displayed ``layer``.

    Each row is ``(base, transform, contours)`` for one top-level component;
    its contours include nested components and are in ``layer`` units.
    ``contours(layer)`` reads a layer's own outlines. ``stamps`` holds
    ``(base name, revision or None)`` for every base looked up, so a cache
    can notice base edits, which do not move the composite's stamp (c).
    An empty ``componentLayer`` names the owner master: ``layer.name`` when
    it is in ``package.masters``, else ``package.master`` (so a shown mask
    or brace layer uses the current master). A non-empty name applies only
    to its own reference. A cycle (by glyph name, so a reference to another
    layer of the same glyph is refused too), a nesting deeper than
    ``MAX_DEPTH``, a non-affine transform or a missing base or layer skips
    that component; each base is reported once.
    """
    owner = owner_master(package, layer, items)
    stamps: dict[str, Any] = {}
    reported: set[str] = set()

    def fail(base: str, why: str) -> None:
        if base not in reported:
            reported.add(base)
            report(ValueError(f"Component {base!r} skipped: {why}"))

    def base_layer(base: str, layer_name: str) -> Any:
        glyph = package.findName(base)
        if glyph is None or glyph.isNull:
            stamps[base] = None
            fail(base, "no such glyph")
            return None
        stamps[base] = revision(glyph)
        found = glyph.findLayer(layer_name)
        if found is not None and not found.isNull:
            return found
        fail(base, f"no layer {layer_name!r}")
        return None

    def expand(source: Any, path: tuple[str, ...]) -> list[Row]:
        rows = []
        for shape in items(lambda: source.shapes):
            if not shape.isComponent:
                continue
            data = shape.shapeData
            base = str(data.componentGlyph)
            why = _refusal(base, path, shape)
            if why is not None:
                fail(base, why)
                continue
            found = base_layer(base, str(data.componentLayer or "") or owner)
            if found is not None:
                transform = affine.from_qtransform(shape.transform)
                inner = list(contours(found))
                for row in expand(found, (*path, base)):
                    inner.extend(row[2])
                rows.append(
                    (base, transform, tuple(_place(c, transform) for c in inner))
                )
        return rows

    rows = tuple(expand(layer, (name,)))
    return rows, tuple(stamps.items())
