# this_file: src/fontlabapp/contours/nodes/duplicator/_write.py
# SPDX-License-Identifier: Apache-2.0
"""Stage detached native nodes, then insert only those exact owned identities.

No shape copy can infer Smooth, lose shape notes or alter hidden pen data here.
Native insert rounds points, so restore the captured unrounded coordinates after
attachment. Failures retain explicit recovery/history diagnostics, never Undo.
"""

from typing import Any

from fontlabapp.contours.nodes.duplicator._capture import check, node_record
from fontlabapp.contours.nodes.duplicator._finish import notify, remove_owned
from fontlabapp.core.edit_guards import require_history_scope


class WriteError(RuntimeError):
    """A late native failure; history may remain even after owned-node removal."""

    def __init__(self, errors: tuple, *, pending_nodes: tuple = (), history_finalized: bool = False) -> None:
        super().__init__(
            "Node duplication failed; inspect native history before retrying. "
            + "; ".join(str(e) for e in errors)
        )
        self.errors = errors
        self.pending_nodes = pending_nodes
        self.history_finalized = history_finalized


def restore(node: Any, record: Any, qt: Any, *, fresh: bool = True) -> None:
    """Restore named copy fields without invoking node type's destructive setter."""
    node.position = qt.QtCore.QPointF(record.x, record.y)
    node.name = record.name
    for key, value in record.properties:
        if key == "__smartAngleR":
            node.smartAngleR = value
        elif value is not None:
            node.setProperty(key, value)
    # FontLab's Curve bit names a cubic CONTROL, unlike Glyphs' CURVE endpoint.
    state = record.flags | (4 if record.kind == "off" else 1)
    node.nodeState = state if fresh else record.flags


def verify(node: Any, record: Any) -> None:
    """Check materialized copy metadata and exact coordinates before publication."""
    actual = node_record(node, record.kind)

    def present(properties: tuple) -> tuple:
        return tuple(
            (k, v)
            for k, v in properties
            if v is not None and not (k == "__smartAngleR" and v == 0)
        )

    if (actual.x, actual.y, actual.flags, actual.name, present(actual.properties)) != (
        record.x,
        record.y,
        record.flags,
        record.name,
        present(record.properties),
    ):
        raise ValueError("Native node copy changed coordinates, raw flags or metadata.")
    if int(node.nodeState) & 7 != (4 if record.kind == "off" else 1):
        raise ValueError("Native node copy has the wrong control/endpoint type.")


def stage(capture: Any, result: Any, native: Any, qt: Any, deadline: float) -> dict:
    """Complete every clone before history; a prior inserted copy is a valid source."""
    originals = {
        key: node
        for nodes in capture.native_nodes.values()
        for key, node in nodes.items()
        if isinstance(key, int)
    }
    staged = {}
    identities = set(originals)
    for operation in result.operations:
        check(deadline)
        if operation.source is None:
            node = native.flNode(
                qt.QtCore.QPointF(operation.node.x, operation.node.y), nodeType="curve"
            )
        else:
            source = staged.get(operation.source, originals.get(operation.source))
            if source is None:
                raise ValueError("Planned copy source is no longer present.")
            # flNode(source) aliases; only actual clone() creates detached storage.
            node = native.flNode(source.clone())
        if int(node.id) in identities:
            raise ValueError("Native node clone reused an existing identity.")
        identities.add(int(node.id))
        restore(node, operation.node, qt)
        verify(node, operation.node)
        staged[operation.node.key] = node
    check(deadline)
    return staged


def representable(capture: Any, result: Any) -> None:
    """Keep known unsafe save/control scenarios explicit before opening history."""
    changed = {(o.layer, o.path) for o in result.operations}
    for layer in result.layers:
        for i, path in enumerate(layer.paths):
            if (layer.key, i) not in changed:
                continue
            before = next(l for l in capture.source.layers if l.key == layer.key).paths[
                i
            ]
            # A LINE after a destination control has no independent native endpoint
            # type. Do not claim source-engine equivalence for a malformed target.
            for o in result.operations:
                if o.layer == layer.key and o.path == i and o.source is not None:
                    source = next((n for n in before.nodes if n.key == o.source), None)
                    if (
                        o.node.kind == "line"
                        and source is not None
                        and source.kind == "off"
                    ):
                        raise ValueError(
                            "An indexed destination control forced to LINE needs a verified native segment mapping."
                        )
            # fl#8517: VFJ writer's final smooth cubic control reloads as On.
            if (
                path.closed
                and path.nodes
                and path.nodes[-1].kind == "off"
                and path.nodes[-1].flags & 8
            ):
                raise ValueError(
                    "Closed final Smooth control cannot safely save/reopen (FontLab #8517)."
                )
    changed_layers = {o.layer for o in result.operations}
    for key in changed_layers:
        _, layer = capture.bound[key]
        if (
            layer.autoLayer
            or layer.tthProgram
            or layer.ttData.hasHints()
            or any(g.isHint for g in layer.guidelines)
        ):
            raise ValueError(
                "Automatic or hinted target topology cannot safely change."
            )


def publish(
    capture: Any, result: Any, staged: dict, native: Any, qt: Any, deadline: float
) -> tuple:
    """One Undo notification; roll back only exact new nodes if attachment fails."""
    changed = list(dict.fromkeys(o.layer for o in result.operations))
    layers = [capture.bound[key][1] for key in changed]
    glyphs = {int(capture.bound[key][0].id): capture.bound[key][0] for key in changed}
    items = layers + list(glyphs.values())
    if not result.operations:
        return ()
    require_history_scope(list(glyphs.values()), native=native)
    check(deadline)
    stamp = qt.QtCore.QDateTime.currentDateTimeUtc()
    check(deadline)
    attempted, errors = [], []
    opened, finalized = False, False
    try:
        for item in items:
            check(deadline)
            opened = True  # A binding may initialize history, then raise.
            item.checkInitHistoryState(0)
            check(deadline)
        for operation in result.operations:
            check(deadline)
            contour = capture.native_nodes[operation.layer][("path", operation.path)]
            node = staged[operation.node.key]
            # Record before call: a binding may attach, then raise.
            attempted.append((contour, node))
            contour.insert(operation.index, node)
            check(deadline)
            restore(node, operation.node, qt)
            check(deadline)
            verify(node, operation.node)
            if int(contour.nodes()[operation.index].id) != int(node.id):
                raise ValueError(
                    "Native contour insertion changed node order/identity."
                )
        for key in changed:
            glyph, layer = capture.bound[key]
            check(deadline)
            layer.changed()
            check(deadline)
            if layer.update() is False:
                raise ValueError("Native layer cache update failed.")
            check(deadline)
        for glyph in glyphs.values():
            check(deadline)
            glyph.changed()
            check(deadline)
            if glyph.update() is False:
                raise ValueError("Native glyph cache update failed.")
            check(deadline)
    except BaseException as error:  # noqa: BLE001 - retain interruption while finishing owned cleanup/history
        errors.append(error)
        if attempted:
            remove_owned(attempted, layers, deadline, errors)
    finally:
        if opened:
            finalized = notify(list(glyphs.values()), items, stamp if attempted else None,
                               native, deadline, errors)
    if errors:
        raise WriteError(tuple(errors), pending_nodes=tuple(attempted), history_finalized=finalized) from errors[0]
    return tuple(attempted)
