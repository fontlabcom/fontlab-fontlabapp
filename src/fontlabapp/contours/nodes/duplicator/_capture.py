# this_file: src/fontlabapp/contours/nodes/duplicator/_capture.py
# SPDX-License-Identifier: Apache-2.0
"""Read explicit native node facts, identity owners and automatic dependencies.

No shape clone, pen getter, fgGlyph getter, UpdateAll or selection writer occurs.
See native source pin inventory in the private verification receipt. Bindings are
source-calibrated; installed FontLab history/reopen preservation remains a gate.
"""

from dataclasses import dataclass, field
from math import isfinite
from time import monotonic
from typing import Any

from fontlabapp import _native
from fontlabapp.masters.layers.selection import capture as selected_layers
from fontlabapp.contours.nodes.duplicator.model import Layer, Node, Path, Source
from fontlabapp.qt.safe import qt_list

# NodeImpl::clone omits/normalizes some of these explicitly named properties.
PROPERTIES = (
    "thickness",
    "proportion",
    "contrast",
    "angle",
    "ink_trap",
    "inktrap_group",
    "hoi_point_id",
    "inktrap_role",
    "corner_tension",
    "corner_smooth",
)
TYPE, FIRST, SELECTED = 7, 16, 32


def check(deadline: float) -> None:
    """Bound Python work; native calls are checked immediately after returning."""
    if monotonic() >= deadline:
        raise TimeoutError("Node duplication exceeded its action deadline.")


def scalar(value: Any) -> Any:
    """Keep explicit scalar node properties without coercing absent to zero."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and isfinite(value):
        return value
    raise ValueError("A node property cannot be preserved as a finite scalar.")


def node_record(node: Any, kind: str) -> Node:
    """Capture local exact coordinates, raw connection flags and copy fields."""
    x, y = float(node.position.x()), float(node.position.y())
    if not isfinite(x) or not isfinite(y):
        raise ValueError("Node coordinates must be finite.")
    return Node(
        int(node.id),
        x,
        y,
        kind,
        int(node.nodeState) & ~(TYPE | FIRST | SELECTED),
        str(node.name),
        tuple((key, scalar(node.getProperty(key))) for key in PROPERTIES)
        + (("__smartAngleR", scalar(node.smartAngleR)),),
    )


def read_layer(layer: Any, glyph: Any, deadline: float) -> tuple[Layer, tuple, dict]:
    """Read own contours in shape/path order; components retain their owners."""
    paths, handles, metadata = [], {}, []
    for shape in layer.shapes:
        check(deadline)
        data = shape.shapeData
        metadata.append(
            (
                int(shape.id),
                int(data.id),
                str(data.name),
                str(data.note),
                bool(shape.isComponent),
                bool(shape.isComposite),
            )
        )
        if shape.isComponent:
            continue
        if shape.isComposite:
            raise ValueError("Nested composite paths need a verified own-path mapping.")
        builder = data.builder
        if builder is not None and not builder.isNull:
            raise ValueError("Generated paths cannot be edited as stored nodes.")
        for contour in shape.contours:
            check(deadline)
            nodes = tuple(contour.nodes())
            records = []
            for i, node in enumerate(nodes):
                state = int(node.nodeState)
                previous = nodes[i - 1] if i or contour.closed else None
                kind = (
                    "off"
                    if state & 6
                    else "curve"
                    if previous is not None and int(previous.nodeState) & 4
                    else "qcurve"
                    if previous is not None and int(previous.nodeState) & 2
                    else "line"
                )
                records.append(node_record(node, kind))
                if int(node.id) in handles:
                    raise ValueError("A source node has more than one own path owner.")
                handles[int(node.id)] = node
            path = Path(int(contour.id), tuple(records), bool(contour.closed))
            paths.append(path)
            handles[("path", len(paths) - 1)] = contour
    facts = (
        int(layer.id),
        str(layer.name),
        str(layer.note),
        bool(layer.autoLayer),
        bool(layer.isMaskLayer),
        bool(layer.isService),
        tuple(metadata),
        tuple(
            (int(n.id), int(n.nodeState))
            for p in paths
            for n in (handles[r.key] for r in p.nodes)
        ),
        int(glyph.currentHistoryState()),
    )
    return (
        Layer(
            int(layer.id),
            int(glyph.id),
            tuple(paths),
            not (layer.isMaskLayer or layer.isService),
        ),
        facts,
        handles,
    )


def dependency_facts(package: Any, native: Any, deadline: float) -> tuple:
    """Use canonical FontGate glyphs; detect cross-owner sharing and auto chains."""
    workspace = native.flWorkspace.instance()
    registered = {int(native.flPackage(p).id) for p in workspace.packages()}
    if int(package.id) not in registered or int(workspace.currentPackage.id) != int(
        package.id
    ):
        raise ValueError("Source font is no longer the registered current package.")
    font = native.CurrentFont()
    if font is None or int(font.id) != int(package.fgId):
        raise ValueError("Current FontGate source does not match the package.")
    rows = []
    for record in font.glyphs:
        check(deadline)
        glyph = package.findName(record.name)
        if glyph is None:
            raise ValueError("A canonical glyph disappeared during capture.")
        for layer in glyph.layers:
            check(deadline)
            shapes = []
            for shape in layer.shapes:
                check(deadline)
                shapes.append(
                    (
                        int(shape.shapeData.id),
                        str(shape.shapeData.componentGlyph)
                        if shape.isComponent
                        else "",
                        tuple(
                            (int(c.id), tuple(int(n.id) for n in c.nodes()))
                            for c in shape.contours
                        )
                        if not shape.isComponent
                        else (),
                    )
                )
            rows.append(
                (str(glyph.name), int(layer.id), bool(layer.autoLayer), tuple(shapes))
            )
    check(deadline)
    return tuple(rows)


def guard_dependencies(rows: tuple, targets: set[int], names: set[str]) -> None:
    """Refuse actual automatic dependants and shared native owners, not repeats."""
    uses, automatic, owners = {}, set(), {}
    for name, layer, auto, shapes in rows:
        if auto:
            automatic.add(name)
        for data, base, paths in shapes:
            if base:
                uses.setdefault(base, set()).add(name)
            ids = [("shape", data)] + [("path", p) for p, _ in paths]
            ids += [("node", n) for _, nodes in paths for n in nodes]
            for key in ids:
                owners.setdefault(key, set()).add(layer)
    pending, seen = set(names), set()
    while pending:
        name = pending.pop()
        if name not in seen:
            seen.add(name)
            pending.update(uses.get(name, set()) - seen)
    if seen & automatic:
        raise ValueError(
            "Automatic target/dependant layers cannot safely share this edit."
        )
    if any(len(layers) > 1 and layers & targets for layers in owners.values()):
        raise ValueError(
            "A target shares native shape/contour/node data with another layer."
        )


@dataclass(frozen=True)
class Capture:
    """Immutable facts plus retained owner handles, never equality by wrapper."""

    source: Source
    context: tuple
    metadata: tuple
    dependencies: tuple
    selection_facts: tuple
    bound: dict = field(compare=False, repr=False)
    native_nodes: dict = field(compare=False, repr=False)
    retained: Any = field(compare=False, repr=False)


def capture(
    mode: str, deadline: float, native: Any = None, provider: Any = None
) -> Capture:
    """Capture all needed source/target layers and ordered first-layer selection."""
    native = native or _native("fontlab")
    selected = (provider or selected_layers)(deadline)
    if not selected.occurrences:
        raise ValueError("Select a glyph layer before duplicating nodes.")
    first = selected.occurrences[0]
    package = first.package
    bound = {} if mode == "all" else {int(first.layer.id): (first.glyph, first.layer)}
    if mode == "all":
        for occurrence in selected.occurrences:
            if int(occurrence.package.id) != int(package.id):
                raise ValueError("Selected occurrences cross fonts.")
            for layer in occurrence.glyph.layers:
                check(deadline)
                if not layer.isMaskLayer and not layer.isService:
                    bound.setdefault(int(layer.id), (occurrence.glyph, layer))
    for o in selected.occurrences if mode == "all" else (first,):
        bound.setdefault(int(o.layer.id), (o.glyph, o.layer))
    layers, metadata, handles = [], [], {}
    for key, (glyph, layer) in bound.items():
        row, facts, nodes = read_layer(layer, glyph, deadline)
        layers.append(row)
        metadata.append(facts)
        handles[key] = nodes
    first_row = next(l for l in layers if l.key == int(first.layer.id))
    by_node = {
        n.key: (p, n.key) for p, path in enumerate(first_row.paths) for n in path.nodes
    }
    if selected.context[2] == "editor":
        canvas = selected.carriers[0]
        ordered = tuple(qt_list(canvas.selectedNodes))
        selection = tuple(
            by_node[int(info.node.id)]
            for info in ordered
            if int(info.node.id) in by_node
        )
        any_selection = bool(selection) or bool(qt_list(canvas.selection))
    else:
        selection = tuple(
            by_node[n.key]
            for p in first_row.paths
            for n in p.nodes
            if int(handles[first_row.key][n.key].nodeState) & SELECTED
        )
        any_selection = bool(selection) or any(s.selected for s in first.layer.shapes)
    # All-layer targets need not include a selected auxiliary mask source itself.
    occurrence_keys = tuple(int(o.layer.id) for o in selected.occurrences)
    source = Source(
        tuple(layers),
        occurrence_keys if mode == "all" else (int(first.layer.id),),
        selection,
        any_selection,
    )
    dependencies = dependency_facts(package, native, deadline)
    selection_facts = tuple(
        (o.package_id, o.glyph_id, o.layer_id, o.block_id, o.index)
        for o in selected.occurrences
    )
    check(deadline)
    return Capture(
        source,
        selected.context,
        tuple(metadata),
        dependencies,
        selection_facts,
        bound,
        handles,
        selected,
    )
