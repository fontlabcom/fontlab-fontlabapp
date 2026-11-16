# this_file: src/fontlabapp/contours/nodes/duplicator/model.py
# SPDX-License-Identifier: Apache-2.0
"""Three literal Node Duplicator policies, independent of either editor's API.

Keep per-occurrence replay, numeric target indices and selected-object identity
separate. The all-layer original intentionally does not deduplicate parents or
recheck the indexed destination's type. Other profiles only copy selected
on-curves in the first selected layer. No original body is imported or executed.
"""

from collections.abc import Iterator
from dataclasses import dataclass, replace
from itertools import count
from typing import Literal

Mode = Literal["current", "all", "handles"]


@dataclass(frozen=True)
class Node:
    """Exact local geometry and copy metadata; selection is separate membership."""

    key: int
    x: float
    y: float
    kind: str
    flags: int
    name: str
    properties: tuple


@dataclass(frozen=True)
class Path:
    """One own path in source order, including empty/open/quadratic paths."""

    key: int
    nodes: tuple[Node, ...]
    closed: bool


@dataclass(frozen=True)
class Layer:
    """One foreground master or auxiliary layer in its parent's stored order."""

    key: int
    glyph: int
    paths: tuple[Path, ...]
    target: bool = True


@dataclass(frozen=True)
class Source:
    """Selected layer occurrences and first-layer ordered selected node identities."""

    layers: tuple[Layer, ...]
    occurrences: tuple[int, ...]
    selection: tuple[tuple[int, int], ...]
    any_selection: bool


@dataclass(frozen=True)
class Operation:
    """One exact insertion; source can refer to an earlier staged copy."""

    layer: int
    path: int
    index: int
    source: int | None
    node: Node


@dataclass(frozen=True)
class Result:
    """Complete predicted topology, ordered insertions and every source skip."""

    layers: tuple[Layer, ...]
    selection: tuple[tuple[int, int], ...]
    operations: tuple[Operation, ...]
    skipped: tuple[tuple[int, int, int, int], ...]
    no_selection_message: bool

    @property
    def inserted(self) -> int:
        """Count handles and endpoints, rather than silently counting only copies."""
        return len(self.operations)


def _selected(source: Source, first: Layer) -> list[tuple[int, int]]:
    """Filter handles without changing the original supplied selection order."""
    selected = []
    for path_index, key in source.selection:
        if not 0 <= path_index < len(first.paths):
            raise ValueError("Selected node owner is unreadable.")
        node = next((n for n in first.paths[path_index].nodes if n.key == key), None)
        if node is None:
            raise ValueError("Selected node identity is unreadable.")
        if node.kind != "off":
            selected.append((path_index, key))
    return selected


def _insert(
    layer: Layer, path_index: int, node_index: int, handles: bool, serial: Iterator[int]
) -> tuple[Layer, list[Operation]]:
    """Insert after the current target, retaining literal copy data and order."""
    path = layer.paths[path_index]
    original = path.nodes[node_index]
    added = []
    operations = []
    if handles:
        for offset in (1, 2):
            node = Node(next(serial), original.x, original.y, "off", 0, "", ())
            added.append(node)
            operations.append(
                Operation(layer.key, path_index, node_index + offset, None, node)
            )
    node = replace(original, key=next(serial), kind="curve" if handles else "line")
    added.append(node)
    operations.append(
        Operation(layer.key, path_index, node_index + len(added), original.key, node)
    )
    nodes = path.nodes[: node_index + 1] + tuple(added) + path.nodes[node_index + 1 :]
    paths = list(layer.paths)
    paths[path_index] = replace(path, nodes=nodes)
    return replace(layer, paths=tuple(paths)), operations


def _current(
    first: Layer, selected: list, handles: bool, serial: Iterator[int]
) -> tuple[Layer, list[Operation]]:
    """Resolve each original identity after prior insertions shift its index."""
    operations = []
    for path_index, key in selected if handles else reversed(selected):
        index = next(
            i for i, n in enumerate(first.paths[path_index].nodes) if n.key == key
        )
        first, added = _insert(first, path_index, index, handles, serial)
        operations.extend(added)
    return first, operations


def _every(
    source: Source, first: Layer, selected: list, layers: dict, serial: Iterator[int]
) -> tuple[list, list]:
    """Replay fixed source indices for every selected-parent occurrence, literally."""
    wanted = set(selected)
    indices = [
        (p, i)
        for p, path in enumerate(first.paths)
        for i, node in enumerate(path.nodes)
        if (p, node.key) in wanted
    ]
    operations = []
    skipped = []
    for occurrence in source.occurrences:
        glyph = next(layer.glyph for layer in source.layers if layer.key == occurrence)
        for original in source.layers:
            if original.glyph != glyph or not original.target:
                continue
            layer = layers[original.key]
            for path_index, node_index in reversed(indices):
                if path_index >= len(layer.paths) or node_index >= len(
                    layer.paths[path_index].nodes
                ):
                    skipped.append((glyph, layer.key, path_index, node_index))
                    continue
                layer, added = _insert(layer, path_index, node_index, False, serial)
                operations.extend(added)
            layers[layer.key] = layer
    return operations, skipped


def plan(source: Source, mode: Mode) -> Result:
    """Predict the complete original operation, including distinct no-op messages."""
    if mode not in ("current", "all", "handles"):
        raise ValueError("Unknown Node Duplicator profile.")
    if not source.occurrences:
        raise ValueError("Select a glyph layer before duplicating nodes.")
    layers = {layer.key: layer for layer in source.layers}
    if len(layers) != len(source.layers) or any(
        k not in layers for k in source.occurrences
    ):
        raise ValueError("Ambiguous layer occurrence.")
    first = layers[source.occurrences[0]]
    selected = _selected(source, first)
    serial = count(
        min(
            [0]
            + [
                n.key
                for layer in source.layers
                for path in layer.paths
                for n in path.nodes
            ]
        )
        - 1,
        -1,
    )
    skipped = []
    if mode == "all":
        operations, skipped = _every(source, first, selected, layers, serial)
    else:
        layers[first.key], operations = _current(
            first, selected, mode == "handles", serial
        )
    message = (
        not selected
        if mode == "all"
        else not source.any_selection
        if mode == "current"
        else False
    )
    return Result(
        tuple(layers[l.key] for l in source.layers),
        source.selection,
        tuple(operations),
        tuple(skipped),
        message,
    )


def run_current() -> dict:
    """Duplicate selected on-curves in the first selected layer, with LINE copies."""
    from fontlabapp.contours.nodes.duplicator.native import execute

    return execute("current")


def run_all_layers() -> dict:
    """Replay first-layer indices for every layer of every selected parent occurrence."""
    from fontlabapp.contours.nodes.duplicator.native import execute

    return execute("all")


def run_with_handles() -> dict:
    """Add coincident cubic handle pairs in the first layer only, in selection order."""
    from fontlabapp.contours.nodes.duplicator.native import execute

    return execute("handles")
