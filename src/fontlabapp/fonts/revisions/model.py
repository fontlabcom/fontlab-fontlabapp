# this_file: src/fontlabapp/fonts/revisions/model.py
# SPDX-License-Identifier: Apache-2.0
"""Read-only comparison of named revision fields, never complete font equality.

All records contain immutable plain data. Native packages are promoted only from
the registered workspace list; font_id is fgId, not the distinct flObject id.
No master activation, glyph FontGate getter, history or persistence API is used.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Any

from fontlabapp import _native

# Proteus/common/model/flnode.h: Selected, Preview, ReadyToEdit and HotSpot.
# Retain all other raw flags, including First, Smooth, G2, Hobby and unknown bits.
TRANSIENT_NODE_FLAGS = 0x0020 | 0x0040 | 0x0080 | 0x0800
MATRIX_FIELDS = ("m11", "m12", "m21", "m22", "dx", "dy", "m13", "m23", "m33")


@dataclass(frozen=True)
class FontChoice:
    font_id: int
    package_id: int
    label: str
    masters: tuple[str, ...]
    path: str


@dataclass(frozen=True)
class GlyphRecord:
    name: str
    glyph_id: int
    layer_id: int | None
    state: str
    advance: float | None
    geometry: tuple
    anchors: tuple
    components: tuple | None
    raw_node_states: tuple


@dataclass(frozen=True)
class RevisionSnapshot:
    font: FontChoice
    master: str
    master_present: bool
    glyphs: tuple[GlyphRecord, ...]
    workspace_domain: tuple[FontChoice, ...]
    include_components: bool


@dataclass(frozen=True)
class Difference:
    glyph: str
    fields: tuple[str, ...]
    left: Any
    right: Any


def _number(value: Any) -> float:
    value = float(value)
    if not isfinite(value):
        raise ValueError("Revision source contains a non-finite numeric value")
    return value


def _matrix(transform: Any) -> tuple[float, ...]:
    return tuple(_number(getattr(transform, key)()) for key in MATRIX_FIELDS)


def _packages(workspace: Any) -> tuple:
    native = _native("fontlab")
    packages = tuple(native.flPackage(item) for item in workspace.packages())
    choices = []
    for package in packages:
        if package is None or package.isNull:
            raise ValueError("Open font registration changed")
        if int(package.fgId) <= 0:
            raise ValueError("Open font has no registered FontGate backing")
        masters = tuple(str(master) for master in package.masters)
        if len(masters) != len(set(masters)):
            raise ValueError("Open font has duplicate master names")
        choices.append(FontChoice(int(package.fgId), int(package.id), str(package.title_name()), masters, str(package.path)))
    if len(choices) != len({choice.font_id for choice in choices}):
        raise ValueError("Open fonts have duplicate FontGate IDs")
    return packages, tuple(choices)


def font_choices(workspace: Any) -> tuple[FontChoice, ...]:
    """List explicitly registered fonts in workspace order, with master domains."""
    return _packages(workspace)[1]


def _geometry(layer: Any, include_components: bool) -> tuple:
    shapes, components, raw_states = [], [], []
    for index, shape in enumerate(layer.shapes):
        matrix = _matrix(shape.transform)
        contours = []
        if shape.isComponent:
            if include_components:
                components.append((index, str(shape.shapeData.componentGlyph), str(shape.shapeData.componentLayer), matrix))
        else:
            for contour in shape.contours:
                nodes = []
                states = []
                for node in contour.nodes():
                    raw = int(node.nodeState)
                    # pygate binds nodeType as string-valued Python ``type``.
                    nodes.append((_number(node.x), _number(node.y), str(node.type), raw & ~TRANSIENT_NODE_FLAGS))
                    states.append(raw)
                contours.append((bool(contour.closed), bool(contour.isTT), tuple(nodes)))
                raw_states.append((index, tuple(states)))
        shapes.append((bool(shape.isComponent), matrix, tuple(contours)))
    geometry = (_matrix(layer.transform), tuple(shapes))
    return geometry, tuple(components) if include_components else None, tuple(raw_states)


def _glyph(package: Any, name: str, master: str, present: bool, components: bool) -> GlyphRecord:
    glyph = package.findName(name)
    if glyph is None or glyph.isNull or str(glyph.name) != name:
        raise ValueError("Glyph membership changed during revision capture")
    layer = glyph.findLayer(master) if present else None
    state = "missing_master" if not present else "missing_layer"
    if layer is None or layer.isNull:
        return GlyphRecord(name, int(glyph.id), None, state, None, (), (), () if components else None, ())
    geometry, bases, raw = _geometry(layer, components)
    anchors = tuple((str(anchor.name), _number(anchor.point.x()), _number(anchor.point.y())) for anchor in layer.anchors)
    return GlyphRecord(name, int(glyph.id), int(layer.id), "present", _number(layer.advanceWidth), geometry, anchors, bases, raw)


def _capture(workspace: Any, font_id: int, master: str, components: bool) -> RevisionSnapshot:
    packages, domain = _packages(workspace)
    found = next(((package, choice) for package, choice in zip(packages, domain, strict=True) if choice.font_id == font_id), None)
    if found is None:
        raise ValueError("Chosen font is no longer open")
    package, choice = found
    # fgPackage is safe here only because this package came from registration.
    names = tuple(str(glyph.name) for glyph in package.fgPackage.glyphs)
    if len(names) != len(set(names)):
        raise ValueError("Font has duplicate glyph names")
    present = master in choice.masters
    records = tuple(_glyph(package, name, master, present, components) for name in names)
    return RevisionSnapshot(choice, master, present, records, domain, components)


def capture(workspace: Any, font_id: int, master: str, *, components: bool = True) -> RevisionSnapshot:
    """Capture the explicit font/master twice; refuse an unstable or invalid read.

    Includes all glyphs in font order, missing layers, raw ordered local contours,
    node types/state, closure/quadratic topology, full layer/shape 3×3 transforms,
    ordered anchor names/coordinates and optional component base/layer/transforms.
    Raw state includes selection; geometry excludes only four transient flags.
    """
    if not isinstance(master, str) or not master:
        raise ValueError("Choose an explicit nonempty master name")
    result = _capture(workspace, font_id, master, components)
    if result != _capture(workspace, font_id, master, components):
        raise ValueError("Revision source changed during capture; refresh choices")
    return result


def validate(workspace: Any, snapshot: RevisionSnapshot) -> None:
    """Reject any captured source/domain change, including raw selection flags."""
    try:
        current = capture(workspace, snapshot.font.font_id, snapshot.master, components=snapshot.include_components)
    except (ValueError, RuntimeError, AttributeError, TypeError) as error:
        raise ValueError("Revision snapshot is stale or unreadable; refresh") from error
    if current != snapshot:
        raise ValueError("Revision snapshot is stale; refresh")


def compare(left: RevisionSnapshot, right: RevisionSnapshot) -> tuple[Difference, ...]:
    """Compare only the named fields; raw_node_state includes transient selection."""
    if left.include_components != right.include_components:
        raise ValueError("Revision snapshots use different component scope")
    result = []
    if left.master_present != right.master_present:
        result.append(Difference("", ("master_presence",), left.master_present, right.master_present))
    left_names = tuple(glyph.name for glyph in left.glyphs)
    right_names = tuple(glyph.name for glyph in right.glyphs)
    if left_names != right_names:
        result.append(Difference("", ("glyph_order",), left_names, right_names))
    a, b = {g.name: g for g in left.glyphs}, {g.name: g for g in right.glyphs}
    for name in dict.fromkeys(left_names + right_names):
        before, after = a.get(name), b.get(name)
        if before is None or after is None:
            result.append(Difference(name, ("glyph_presence",), before, after))
            continue
        fields = tuple(field for field in ("state", "advance", "geometry", "anchors", "components") if getattr(before, field) != getattr(after, field))
        if before.raw_node_states != after.raw_node_states:
            fields += ("raw_node_state",)
        if fields:
            result.append(Difference(name, fields, before, after))
    return tuple(result)
