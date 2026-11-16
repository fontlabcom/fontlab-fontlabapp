# this_file: src/fontlabapp/studios/interpolation_doctor/model.py
# SPDX-License-Identifier: Apache-2.0
"""Interpolation Doctor findings: compatibility, counts, literal reports and the blend.

What: pure readers over explicit FontLab layers (``flGlyph.findLayer`` or
``flGlyph.layers``; never ``fgGlyph``) that rebuild the findings of ten
Scriptmix scripts: Masters > Compatibility Check (``signature``/``check``),
Anchors > Compatibility Report (``anchor_sets``), Components > Compatibility
(``component_lists``/``odd_masters``), Contours > Node Statistics
(``layer_counts``/``odd_cells``), Reports > Master Node Compatibility Report
(``node_report``), Reports > Why You Not Compatible (``why_report``), Reports >
Point Counter (``point_report``), Reports > Point Counter (Master Layers)
(``master_point_report``), Masters > Interpolation Preview
(``outline``/``problem``/``blend``) and Contours > Make Compatible
(``compatible_plan``). Report text is the originals' literal output.
Why: studios may not import ``fontlabapp.masters``/``contours``, so the
small readers are restated here with the same counter definitions.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from itertools import zip_longest
from typing import Any, NamedTuple

import fontlabapp.core.sharing as sharing

from .._contours import spans
from ..transform_studio.geometry import apply
from ..transform_studio.native import matrix_of

ASPECTS = ("contours", "anchors", "components")
MISSING_LAYER = "missing layer"
Point = tuple[float, float, bool]
Outline = list[list[Point]]


# Shared readers ------------------------------------------------------------------
def master_layers(glyph: Any, masters: Sequence[str]) -> dict[str, Any]:
    """{master: layer} for the masters where the glyph has a real layer."""
    found = {}
    for master in masters:
        layer = glyph.findLayer(master)
        if layer is not None and not getattr(layer, "isNull", False):
            found[master] = layer
    return found


def own_contours(layer: Any) -> list[Any]:
    """The contours of the layer's own (non-component) shapes, in order."""
    return [contour for shape in layer.shapes if not shape.isComponent for contour in shape.contours]


def node_points(contour: Any) -> list[Point]:
    return [(float(node.x), float(node.y), bool(node.isOn())) for node in contour.nodes()]


def component_name(shape: Any) -> str:
    """The component's base glyph name; the shape name when the data has none."""
    base = getattr(getattr(shape, "shapeData", None), "componentGlyph", None)
    return str(shape.name) if base is None else str(base)


def node_kinds(contour: Any) -> list[str]:
    """Scriptmix ``_records.nodes``: line, curve, qcurve or offcurve per node, start node first."""
    raw = list(contour.nodes())
    closed, tt = bool(contour.closed), bool(contour.isTT)
    kinds = []
    for index, node in enumerate(raw):
        previous = raw[index - 1] if index or closed else None
        if not node.isOn():
            kinds.append("offcurve")
        elif previous is not None and (previous.isOff() or previous.isCurve()):
            kinds.append("curve" if previous.isCurve() and not tt else "qcurve")
        else:
            kinds.append("line")
    return kinds[1:] + kinds[:1] if closed and kinds else kinds


def stored_foreground(glyph: Any) -> list[Any]:
    """Point Counter: every layer that is not mask or service, in stored order."""
    return [layer for layer in glyph.layers if not layer.isMaskLayer and not layer.isService]


def stored_masters(glyph: Any) -> list[Any]:
    """Point Counter (Master Layers): the native master layers, in stored order."""
    return [layer for layer in glyph.layers if layer.isMasterLayer]


def report_masters(glyph: Any, masters: Sequence[str]) -> list[Any]:
    """Master Node Compatibility Report: every font master in order; a missing one refuses."""
    found = master_layers(glyph, masters)
    if len(found) < len(masters):
        raise ValueError("A selected glyph is missing a valid master layer.")
    return [found[m] for m in masters]


def foreground_layers(glyph: Any, masters: Sequence[str]) -> list[Any]:
    """Not mask, not service; master layers first in font master order, then the rest in stored order."""
    layers = [layer for layer in glyph.layers if not layer.isMaskLayer and not layer.isService]
    order = {name: index for index, name in enumerate(masters)}
    first = sorted((layer for layer in layers if str(layer.name) in order), key=lambda layer: order[str(layer.name)])
    return first + [layer for layer in layers if str(layer.name) not in order]


def most_common(values: Sequence[Any]) -> Any:
    """Scriptmix ``max(set(values), key=values.count)`` with a stable tie-break (first seen)."""
    return max(dict.fromkeys(values), key=list(values).count)


# Masters > Compatibility Check --------------------------------------------------
def signature(layer: Any) -> tuple:
    contours = tuple("".join("o" if node.isOn() else "h" for node in c.nodes()) for c in own_contours(layer))
    anchors = tuple(sorted(str(anchor.name) for anchor in layer.anchors))
    components = tuple(component_name(shape) for shape in layer.shapes if shape.isComponent)
    return contours, anchors, components


def summary(sig: tuple) -> tuple[int, int, int, int]:
    """(contours, nodes, anchors, components) of a signature."""
    contours, anchors, components = sig
    return len(contours), sum(len(c) for c in contours), len(anchors), len(components)


def check(glyph: Any, masters: Sequence[str]) -> tuple[dict[str, tuple | None], bool, list[str]]:
    """({master: signature or None for auto}, compatible, problems) across the present masters."""
    sigs = {m: None if layer.autoLayer else signature(layer) for m, layer in master_layers(glyph, masters).items()}
    compared = [sig for sig in sigs.values() if sig is not None]
    problems = [aspect for i, aspect in enumerate(ASPECTS) if len({sig[i] for sig in compared}) > 1]
    if len(sigs) < len(masters):
        problems.append(MISSING_LAYER)
    return sigs, not problems, problems


# Anchors and components ----------------------------------------------------------
def anchor_sets(glyph: Any, masters: Sequence[str]) -> dict[str, list[str] | None] | None:
    """{master: sorted anchor names, None for auto}, or None when no master carries anchors."""
    sets, has_anchors = {}, False
    for master, layer in master_layers(glyph, masters).items():
        names = sorted(str(anchor.name) for anchor in layer.anchors)
        has_anchors |= bool(names)
        sets[master] = None if layer.autoLayer else names
    return sets if has_anchors else None


def anchors_differ(sets: Mapping[str, list[str] | None]) -> bool:
    return len({tuple(names) for names in sets.values() if names is not None}) > 1


def component_lists(glyph: Any, masters: Sequence[str]) -> dict[str, list[str]] | None:
    """{master: component base names in order}, or None when no master has components."""
    lists = {m: [component_name(s) for s in layer.shapes if s.isComponent]
             for m, layer in master_layers(glyph, masters).items()}  # fmt: skip
    return lists if any(lists.values()) else None


def odd_masters(lists: Mapping[str, list[str]], masters: Sequence[str]) -> list[str]:
    """Masters whose list differs from the first present master's."""
    present = [m for m in masters if m in lists]
    return [m for m in present if lists[m] != lists[present[0]]]


# Contours > Node Statistics --------------------------------------------------------
def layer_counts(layer: Any) -> tuple[int, int] | None:
    """(own contours, nodes) drawn in the layer; None for an auto layer."""
    if layer.autoLayer:
        return None
    contours = own_contours(layer)
    return len(contours), sum(int(c.nodesCount) for c in contours)


def node_cells(glyph: Any, masters: Sequence[str]) -> dict[str, tuple[int, int] | None]:
    return {m: layer_counts(layer) for m, layer in master_layers(glyph, masters).items()}


def counts_differ(cells: Mapping[str, Any]) -> bool:
    return len({v for v in cells.values() if v is not None}) > 1


def odd_cells(cells: Mapping[str, Any]) -> list[str]:
    """Masters whose counts differ from the most common value (auto layers never odd)."""
    values = [v for v in cells.values() if v is not None]
    if len(set(values)) < 2:
        return []
    common = most_common(values)
    return [m for m, v in cells.items() if v is not None and v != common]


def cell_text(value: tuple[int, int] | None) -> str:
    return "auto" if value is None else f"{value[0]} / {value[1]}"


# Reports > Master Node Compatibility Report ----------------------------------------
def paths(layer: Any) -> list[list[str]]:
    return [node_kinds(contour) for contour in own_contours(layer)]


def first_difference(reference: Sequence[str], tested: Sequence[str]) -> tuple[int, str | None, str | None] | None:
    for index, (left, right) in enumerate(zip_longest(reference, tested)):
        if left != right:
            return index, left, right
    return None


def _counts(path: Sequence[str]) -> tuple[int, int]:
    off = path.count("offcurve")
    return len(path) - off, off


def _master_lines(name: str, found: Sequence[Sequence[str]]) -> list[str]:
    lines = [f"\n    ⭕️ Master: {name}", f"     • Paths: {len(found)}"]
    for path in found:
        on, off = _counts(path)
        curves = path.count("curve") + path.count("qcurve")
        lines += [f"     • Nodes: {on} (Lines: {path.count('line')} · Curves: {curves})", f"     • Handles: {off}",
                  f"     • Total Points: {len(path)}"]  # fmt: skip
    return lines


def _difference_lines(reference: Sequence, found: Sequence, master: str) -> list[str]:
    lines = []
    for number, (left, right) in enumerate(zip_longest(reference, found), 1):
        prefix = f"  ⚠️ Incompatibility in master '{master}':"
        if left is None or right is None:
            side = "reference" if left is None else "tested"
            lines.append(f"{prefix} Path #{number} → Path missing in {side} master.")
            continue
        difference = first_difference(left, right)
        if difference is None:
            continue
        index, expected, actual = difference
        lines += [prefix, f"     • Path #{number} mismatch → Expected {_counts(left)}, Found {_counts(right)}",
                  f"     • First difference at node #{index + 1}: Expected {expected.upper() if expected else '—'}, "
                  f"Found {actual.upper() if actual else '—'}"]  # fmt: skip
    return lines


def node_report(groups: Sequence[tuple[str, Sequence[tuple[str, Sequence[Sequence[str]]]]]]) -> str:
    """Literal Scriptmix text for (glyph, [(master, paths), ...]) groups; every master versus the first."""
    if not groups:
        raise ValueError("No glyph selected.")
    lines: list[str] = []
    for name, layers in groups:
        if not layers:
            raise ValueError("A glyph has no master layers.")
        lines.append(f"🔠 Glyph: {name}")
        for master, found in layers:
            lines += _master_lines(master, found)
        differences = [line for master, found in layers[1:] for line in _difference_lines(layers[0][1], found, master)]
        lines += differences
        lines += ["", "-" * 100]
        lines.append("  ⚠️ Masters are not compatible with the reference master." if differences
                     else "  ✅ All masters are fully compatible with the reference master.")  # fmt: skip
    return "\n".join(lines)


# Reports > Why You Not Compatible ---------------------------------------------------
class Layer(NamedTuple):
    name: str
    paths: tuple[tuple[str, ...], ...]
    anchors: frozenset[str]
    components: frozenset[str]


def why_layer(layer: Any) -> Layer:
    return Layer(str(layer.name), tuple(tuple(path) for path in paths(layer)),
                 frozenset(str(a.name) for a in layer.anchors),
                 frozenset(component_name(s) for s in layer.shapes if s.isComponent))  # fmt: skip


def _differences(left: Layer, right: Layer) -> list[tuple[str, Any, Any]]:
    found: list[tuple[str, Any, Any]] = []
    if len(left.paths) != len(right.paths):
        found.append(("path counts", len(left.paths), len(right.paths)))
    else:
        for i, (a, b) in enumerate(zip(left.paths, right.paths), 1):
            if len(a) != len(b):
                found.append((f"path {i}, node count", len(a), len(b)))
                continue
            found += [(f"path {i}, node {j} node types", x, y) for j, (x, y) in enumerate(zip(a, b), 1) if x != y]
    for label, a, b in (("anchors", left.anchors, right.anchors), ("components", left.components, right.components)):
        if a != b:
            found.append((label, ", ".join(sorted(a)), ", ".join(sorted(b))))
    return found


def why_report(groups: Sequence[tuple[str, Sequence[Layer]]]) -> str:
    """Literal Scriptmix text: adjacent foreground layers compared in order."""
    out = []
    for name, layers in groups:
        if not layers:
            raise ValueError("A glyph has no reportable foreground layer.")
        pairs = [(a, b, _differences(a, b)) for a, b in zip(layers, layers[1:])]
        found = any(diff for _, _, diff in pairs)
        text = f"{name} is {'not compatible' if found else 'compatible'}\n"
        for a, b, diff in pairs:
            for kind, prev, cur in diff:
                text += f"{kind} differ:\n  {a.name} has {prev}\n  {b.name} has {cur}\n"
        out.append(text + "\n\n")
    return "".join(out)


# Reports > Point Counter and Point Counter (Master Layers) --------------------------
class Counts(NamedTuple):
    lines: int
    curves: int
    handles: int
    paths: int

    @property
    def points(self) -> int:
        return self.lines + self.curves + self.handles


def counts(layer: Any) -> Counts:
    """Scriptmix point counter: handles are off/curve nodes; an on node after a handle is a curve."""
    lines = curves = handles = number = 0
    for contour in own_contours(layer):
        number += 1
        nodes = list(contour.nodes())
        control = [bool(n.isOff() or n.isCurve()) for n in nodes]
        handles += sum(control)
        bent = sum(1 for i, c in enumerate(control) if not c and (i > 0 or contour.closed) and control[i - 1])
        curves += bent
        lines += len(nodes) - sum(control) - bent
    return Counts(lines, curves, handles, number)


def point_report(groups: Sequence[tuple[str, Sequence[tuple[str, Counts]]]]) -> str:
    """Literal Scriptmix Point Counter text; "? " marks a count new to the previous two layers."""
    text = ""
    for name, layers in groups:
        text += f"---------- {name} ----------\n"
        previous: tuple[int, ...] = ()
        for layer, c in layers:
            marker = "? " if previous and c.points not in previous else ""
            text += f"{marker}{c.points} points - {c.lines} lines, {c.curves} curves, {c.handles} offcurves, " \
                    f"{c.paths} paths - {layer}\n"  # fmt: skip
            previous = (*previous[-1:], c.points)
        text += "\n"
    return text


def master_point_report(rows: Sequence[tuple[str, Counts]]) -> str:
    """Literal Scriptmix Point Counter (Master Layers) text, one block per master layer."""
    return "\n".join(f"Layer: {name}\nTotal: {c.points} Points - {c.handles} Handles, {c.lines + c.curves} Nodes, "
                     f"{c.paths} Paths\n" for name, c in rows)  # fmt: skip


# Masters > Interpolation Preview ------------------------------------------------
def outline(layer: Any) -> Outline:
    """Every shape's contours (components included) in layer coordinates."""
    found = []
    for shape in layer.shapes:
        matrix = matrix_of(getattr(shape, "transform", None))
        for contour in shape.contours:
            found.append([(*apply(matrix, x, y), on) for x, y, on in node_points(contour)])
    return found


def problem(a: Outline, b: Outline) -> str | None:
    """Why two outlines cannot interpolate; None when they can."""
    if len(a) != len(b):
        return f"{len(a)} vs {len(b)} contours"
    for i, (ca, cb) in enumerate(zip(a, b), 1):
        if [p[2] for p in ca] != [p[2] for p in cb]:
            return f"contour {i}: {len(ca)} vs {len(cb)} nodes or different node types"
    return None


def blend(a: Outline, b: Outline, t: float) -> Outline:
    return [[(pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t, pa[2]) for pa, pb in zip(ca, cb)]
            for ca, cb in zip(a, b)]  # fmt: skip


# Contours > Make Compatible ------------------------------------------------------
class Change(NamedTuple):
    item: str
    now: str
    after: str
    edit: tuple[Any, tuple[Any, ...], int] | None = None


SHAPE_NOTE = "Use own, unscaled outline shapes."
EPSILON = 1e-9


def shape_notes(layer: Any) -> list[str]:
    """Scriptmix ``outline_shapes`` notes: shared or scaled/rotated own outlines are kept whole."""
    notes = []
    for shape in layer.shapes:
        if shape.isComponent or not list(shape.contours):
            continue
        m11, m12, m21, m22, _dx, _dy = matrix_of(getattr(shape, "transform", None))
        if sharing.element_shared(shape, layer):
            notes.append("shared outline, kept")
        elif max(abs(m11 - 1), abs(m12), abs(m21), abs(m22 - 1)) > EPSILON:
            notes.append("scaled or rotated shape, kept")
    return notes


def editable_contours(layer: Any, notes: Callable[[Any], list[str]]) -> list[Any]:
    if notes(layer):
        raise ValueError(SHAPE_NOTE)
    return own_contours(layer)


def compatible_plan(master: str, layers: Mapping[str, Any], masters: Sequence[str],
                    notes: Callable[[Any], list[str]]) -> list[Change]:  # fmt: skip
    """Scriptmix ``plan_content``: lines of ``master`` that are cubic in any other master become cubic."""
    if any(layers.get(m) is None for m in masters):
        raise ValueError("Every declared master must have a layer.")
    groups = [editable_contours(layers[m], notes) for m in masters]
    if len({len(group) for group in groups}) > 1:
        raise ValueError("Master contour counts differ.")
    found = []
    for ci, aligned in enumerate(zip(*groups)):
        edges = [spans(contour) for contour in aligned]
        if len({len(edge) for edge in edges}) > 1:
            raise ValueError("Master segment counts differ.")
        current = edges[list(masters).index(master)]
        picked = [i for i, corr in enumerate(zip(*edges)) if len(current[i]) == 2 and any(len(e) == 4 for e in corr)]
        if picked:
            contour = aligned[list(masters).index(master)]
            found.append(Change(f"contour {ci + 1}", str(len(picked)), "line to cubic",
                                (contour, tuple(current[i][-1] for i in picked),
                                 int(contour.nodesCount) + 2 * len(picked))))  # fmt: skip
    return found


def glyph_changes(master: str, layers: Mapping[str, Any], masters: Sequence[str],
                  notes: Callable[[Any], list[str]]) -> list[Change]:  # fmt: skip
    """Check every master first; a structural problem keeps the glyph whole with one note row."""
    try:
        for other in masters:
            compatible_plan(other, layers, masters, notes)
        return compatible_plan(master, layers, masters, notes)
    except ValueError as error:
        return [Change("glyph", "", f"{str(error).rstrip('.,')}, kept")]


def write_compatible(edits: Iterable[tuple[Any, tuple[Any, ...], int]]) -> None:
    for _contour, endpoints, _count in edits:
        for endpoint in endpoints:
            if endpoint.convertToCurve(False) is False:
                raise RuntimeError("FontLab refused cubic conversion.")
