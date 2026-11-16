# this_file: src/fontlabapp/components/creation.py
# SPDX-License-Identifier: Apache-2.0
"""Add plain components to EXISTING glyphs, inside the caller's one history step.

What: a script that adds components to glyphs that exist (Make Lower
Unicase, Set Default Figures) needs a new component shape for each (base
glyph, layer). No component constructor is measured on this FontLab
build (fl#8505: ``setGlyphComponents`` rejects every argument form,
``addComponent`` only records a recipe entry; the source has an
``flShape(glyph, layer)`` constructor, ``pyflshape.cpp:66-79``, which is a
native probe item and is not used). Two calls:

1. ``build_components(package, target, wanted, facts)``, BEFORE the
   caller's ``history.commit``. It clones one plain component that the font
   already has (the prototype), once per ``NewComponent``, and points each
   detached clone at its base glyph, layer and offset. Nothing is added to
   the font yet. Refusals raise ``ValueError`` and name the target glyph,
   so a script can show a kept row: an unknown base, a base without that
   layer, a bad offset, and a font without any plain component
   (``NO_PROTOTYPE``).
2. ``add_component(layer, shape)``, INSIDE ``mutate`` of the caller's
   ``history.commit(..., operation="geometry")``: it adds one built shape
   to the target layer and checks that the layer holds one more component
   of that base. Declare the target layers and glyphs in the commit.

The caller's commit is then the ONE Undo step of the edit.

NEW glyphs get their components another way: put them in the glyph's own
Add Glyph data (``glyph_creation.NewGlyph(components=(Part(...), ...))``).
That works also in a font without any component, and each new glyph is its
own Undo step with its components.

Why no scratch glyph: a temporary glyph made with fontpr ``set_glyph``
adds an Add Glyph Undo step, and ``flPackage.deleteGlyph`` removes it
outside history, so Redo would put the temporary glyph back
(``flcommands.cpp:914,919``). That path is a native
milestone candidate, not shipped behaviour. The cost: an existing glyph in
a font without any plain component is refused.

Prototype filter: a clone copies the builder state
(attached flag, attach anchor, component variation;
``flcompositeshapesbuilder.cpp:79-93``) and the shape style (excluded,
content lock, non-spacing, boolean operation, opacity;
``flshape.cpp:1906-1934,2213``). An attached clone gets its offset
overwritten at the next layer update (``fllayer.cpp:1493-1535``). So a
prototype qualifies only when every one of these reads as the default
through Python; ``_qualifies`` holds the rules:

- the bound ``flShape`` members (``pyflshape.cpp:438-443``): ``excluded``
  is the bool ``False``, ``opacity`` is 1.0 (``contentLocked`` is not read: it
  is True for every component on FontLab 9.0.9808, 504 of 504 in plum, A2
  report 18, so it cannot tell a user lock; the VFJ ``locked`` key below does);
- the fontpr ``get_glyph`` VFJ of its glyph (``mcptools_source.cpp:58-79``,
  a bound Python call; no ``flShape`` member reads these fields): the
  layer's ``elements`` match the layer shapes one to one; the element of
  the prototype has no ``locked``, ``nonSpacing``, ``booleanOperation``,
  ``opacity`` or ``excluded`` key with a non-default value, and its
  ``component`` holds only ``glyphName``, ``layerName`` and
  ``attached: false`` (no ``attachAnchor``, no ``off2026Variation``;
  tags of ``bin_types.cpp:383,535-545``; writers ``flshape.cpp:826-831``,
  ``flcompositeshapesbuilder.cpp:1141-1170``).

Anything that cannot be read, or reads otherwise, disqualifies the shape.
No qualifying prototype gives the ``NO_PROTOTYPE`` kept row.

Not measured natively: that a clone of a component is detached (own
``shapeData``, reference count 1), that setting ``componentGlyph``,
``componentLayer`` and ``transform`` on the detached clone re-targets it,
and the Undo/Redo/save/reopen result. ``build_components`` has no
auto-glyph consent: the edit runs in the caller's commit, whose
``history.refusal`` policy refuses auto layers and bases of auto
composites. Offline tests prove the call order and the refusals only.

This module imports only the standard library and stdlib-only App modules
at load time; PythonQt, fontpr and ``scripting`` load when
``build_components`` runs.

How to use (a script)::

    import fly.ap.components.creation as component_creation
    import fly.ap.core.history.glyphs as history

    facts = history.scan_auto_facts(package)
    wanted = [component_creation.NewComponent("A", master) for master in package.masters]
    shapes = component_creation.build_components(package, "a", wanted, facts)
    target = package.findName("a")
    layers = [target.findLayer(m) for m in package.masters]

    def mutate():
        for layer, shape in zip(layers, shapes, strict=True):
            component_creation.add_component(layer, shape)

    history.commit("Unicase", layers, [target], mutate, operation="geometry", facts=facts)
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import fontlabapp.components.writer as component_writer  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native
from fontlabapp import _native

#: Refusal text when the font has no plain component to copy.
NO_PROTOTYPE = (
    "the font has no plain, unattached component that is safe to copy, and no component "
    "constructor is measured on this FontLab build. Add one plain component in FontLab, "
    "then run this again"
)
#: Largest offset difference that still counts as the planned offset.
EPSILON = 1e-6
#: Keys that a qualifying prototype's VFJ ``component`` dict may hold.
COMPONENT_KEYS = frozenset({"glyphName", "layerName", "attached"})
#: Element-level VFJ keys whose presence (with a non-default value) disqualifies a prototype.
STYLE_DEFAULTS = {
    "locked": False,
    "nonSpacing": False,
    "booleanOperation": None,
    "excluded": False,
    "opacity": 1.0,
}


@dataclass(frozen=True)
class NewComponent:
    """One component to make: base glyph name, layer (master) name, offset x and y."""

    base: str
    layer: str
    x: float = 0.0
    y: float = 0.0


def _refuse(package: Any, target: str, wanted: Sequence[NewComponent]) -> None:
    """Raise ``ValueError`` for a bad item; the text names the target glyph."""
    for item in wanted:
        if not item.base or not item.layer:
            raise ValueError(
                f"{target}: kept; a component needs a base glyph and a layer."
            )
        if not all(
            isinstance(v, (int, float)) and math.isfinite(v) for v in (item.x, item.y)
        ):
            raise ValueError(
                f"{target} · {item.layer}: kept; the offset must be finite numbers."
            )
        glyph = package.findName(item.base)
        layer = None if glyph is None or glyph.isNull else glyph.findLayer(item.layer)
        if layer is None or layer.isNull:
            raise ValueError(
                f"{target} · {item.layer}: kept; no base glyph {item.base} with that layer."
            )


def _vfj_element(element: Any, shape: Any) -> bool:
    """True when the VFJ ``element`` of a component shape holds only default state."""
    if not isinstance(element, dict):
        return False
    component = element.get("component")
    if not isinstance(component, dict) or set(component) - COMPONENT_KEYS:
        return False
    if component.get("attached", False) is not False:
        return False
    if str(component.get("glyphName", "")) != str(shape.shapeData.componentGlyph):
        return False
    return all(
        key not in element or element[key] == default
        for key, default in STYLE_DEFAULTS.items()
    )


def _glyph_data(package: Any, glyph: Any) -> dict[str, Any]:
    """Read one glyph VFJ; return an empty dict when it cannot be read."""
    import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - lazy: cold import stays stdlib-only

    try:
        data = _native("fontpr").call(
            "get_glyph", font_id=scripting.font_id(package), glyph_name=str(glyph.name)
        )
    except Exception:  # noqa: BLE001 - unreadable: the shape does not qualify
        return {}
    data = data.get("glyph", data) if isinstance(data, dict) else {}
    return data if isinstance(data, dict) else {}


def _elements(data: dict[str, Any], layer: Any) -> list[Any] | None:
    """Return the layer elements from an already fetched glyph VFJ."""
    for entry in data.get("layers", None) or ():
        if isinstance(entry, dict) and str(entry.get("name")) == str(layer.name):
            elements = entry.get("elements", None) or []
            return list(elements) if isinstance(elements, (list, tuple)) else None
    return None


def _qualifies(shape: Any, element: Any) -> bool:
    """True when ``shape`` is a plain, unattached, default-style component (module text)."""
    try:
        # Native contentLocked reads True for every component on FontLab 9.0.9808
        # (A2 report 18, 504/504 in plum); the VFJ "locked" key is the lock source.
        style = (shape.excluded, float(shape.opacity))
    except Exception:  # noqa: BLE001 - unreadable member: does not qualify
        return False
    if style[0] is not False or style[1] != 1.0:
        return False
    return component_writer.plain_move(shape) and _vfj_element(element, shape)


def prototype(package: Any, facts: history.AutoFacts) -> Any | None:
    """Return the first component that qualifies as a prototype (module text), or None.

    Only the component users in ``facts.users`` are read, in name order, and
    only their non-auto layers. The VFJ elements must match the layer shapes
    one to one (count, and the base of each component), else the layer is
    skipped. Fetch each glyph VFJ at most once per call, across all layers.
    """
    users = sorted({name for names in facts.users.values() for name in names})
    for name in users:
        glyph = package.findName(name)
        data: dict[str, Any] | None = None
        for layer in glyph.layers if glyph is not None else ():
            if layer.autoLayer or not component_writer.components(layer):
                continue
            shapes = list(layer.shapes)
            if data is None:
                data = _glyph_data(package, glyph)
            elements = _elements(data, layer)
            if elements is None or len(elements) != len(shapes):
                continue
            for shape, element in zip(shapes, elements, strict=True):
                if shape.isComponent and _qualifies(shape, element):
                    return shape
    return None


def _retarget(copy: Any, item: NewComponent, qt: Any) -> None:
    """Point a detached clone at the base glyph, layer and offset of ``item``."""
    copy.shapeData.componentGlyph = item.base
    copy.shapeData.componentLayer = item.layer
    copy.transform = qt.QtGui.QTransform(
        1.0, 0.0, 0.0, 1.0, float(item.x), float(item.y)
    )
    copy.name = ""
    copy.shapeData.note = ""
    copy.selected = False
    # A clone serializes as VFJ "locked": true even when the prototype is unlocked
    # (A2 report 26). The setter clears that flag; the getter reads True regardless
    # on 9.0.9809, so verify through the glyph VFJ, not contentLocked.
    copy.contentLocked = False


def _one(source: Any, item: NewComponent, qt: Any) -> Any:
    """Return one detached, re-targeted clone of ``source``; RuntimeError when not detached."""
    copy = source.clone()
    if (
        copy is None
        or copy.id == source.id
        or copy.shapeData.id == source.shapeData.id
        or int(copy.shapeData.referenceCount) != 1
    ):
        raise RuntimeError(f"FontLab did not detach the component copy for {item.base}")
    _retarget(copy, item, qt)
    t = copy.transform
    if (
        str(copy.shapeData.componentGlyph) != item.base
        or str(copy.shapeData.componentLayer) != item.layer
        or abs(float(t.dx()) - float(item.x)) > EPSILON
        or abs(float(t.dy()) - float(item.y)) > EPSILON
    ):
        raise RuntimeError(
            f"FontLab did not re-target the component copy to {item.base} · {item.layer}"
        )
    return copy


def build_components(
    package: Any,
    target: str,
    wanted: Sequence[NewComponent],
    facts: history.AutoFacts,
    *,
    cache: dict[str, Any] | None = None,
) -> tuple[Any, ...]:
    """Return one detached plain component per item of ``wanted``; call it BEFORE ``history.commit``.

    ``target``: the existing glyph that will receive them (for the texts).
    ``facts``: a fresh ``history.scan_auto_facts(package)``. Every refusal
    raises ``ValueError("<target>: kept; ...")`` before any change. A
    native failure while cloning raises ``RuntimeError`` that says nothing
    was added to the font (the clones are detached). Nothing wanted returns
    ``()`` with no native call. Pass one empty ``cache`` dict per Apply to
    reuse the prototype across targets in the same package. Discard the
    cache after Apply; a later edit can change the prototype. A missing
    prototype is cached too.
    """
    if not wanted:
        return ()
    _refuse(package, target, wanted)
    if cache is None:
        source = prototype(package, facts)
    else:
        if "prototype" not in cache:
            cache["prototype"] = prototype(package, facts)
        source = cache["prototype"]
    if source is None:
        raise ValueError(f"{target}: kept; {NO_PROTOTYPE}.")
    qt = _native("PythonQt")
    try:
        return tuple(_one(source, item, qt) for item in wanted)
    except Exception as error:  # nothing is in the font yet: no Undo advice
        raise RuntimeError(
            f"{target}: kept; {error}. Nothing was added to the font."
        ) from error


def add_component(layer: Any, shape: Any) -> Any:
    """Add one shape from ``build_components`` to ``layer``; call it INSIDE ``mutate``.

    Return the shape that the layer holds now (``flLayer.addShape`` returns
    it; a ``None`` answer returns ``shape``). Raise ``RuntimeError`` unless
    the layer holds exactly one more component of the same base afterwards.
    """
    base = str(shape.shapeData.componentGlyph)

    def count() -> int:
        return sum(
            1
            for s in layer.shapes
            if s.isComponent and str(s.shapeData.componentGlyph) == base
        )

    before = count()
    added = layer.addShape(shape)
    if count() != before + 1:
        raise RuntimeError(f"FontLab did not add the component {base} to {layer.name}.")
    return shape if added is None else added


__all__ = [
    "COMPONENT_KEYS",
    "EPSILON",
    "NO_PROTOTYPE",
    "STYLE_DEFAULTS",
    "NewComponent",
    "add_component",
    "build_components",
    "prototype",
]
