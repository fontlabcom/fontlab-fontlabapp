# this_file: src/fontlabapp/anchors/edit.py
# SPDX-License-Identifier: Apache-2.0
"""Source-candidate point transactions; full native editor acceptance is pending.

Enroll the actual transitive component closure before mutation. Automatic layers
are initialized but never notified. The UTC ordering has native evidence for one
owned dependency experiment, not for every graph this source candidate accepts.
"""

import math
from dataclasses import dataclass
from numbers import Real
from typing import Any

from fontlabapp import _native
from fontlabapp.anchors.copy.model import ORIGIN_ERROR, layer_of
from fontlabapp.guides.inspect.model import dependency_values


def finite(value: Any) -> float:
    """Reject coercible strings, booleans and nonfinite native coordinates."""
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
        or not math.isfinite(value)
    ):
        raise ValueError("Anchor coordinates and settings must be finite numbers.")
    return value


def raw_point(pin: Any) -> tuple[float, float]:
    """Read exact coordinates, retaining the original untouched axis."""
    return finite(pin.point.x()), finite(pin.point.y())


def _pin_values(pin: Any) -> tuple:
    return (
        pin.id,
        pin.name,
        raw_point(pin),
        pin.appearance,
        pin.anchor,
        pin.expressionX,
        pin.expressionY,
        pin.style,
        pin.cloudEnabled,
        pin.markEnabled,
    )


def _layer_values(layer: Any) -> tuple:
    box = layer.boundingBox
    return (
        layer.id,
        bool(layer.autoLayer),
        finite(layer.advanceWidth),
        tuple(finite(v()) for v in (box.x, box.y, box.width, box.height)),
        tuple(_pin_values(pin) for pin in layer.anchors),
        str(layer.recipe),
        tuple(
            (
                shape.id,
                shape.shapeData.componentGlyph,
                tuple(
                    finite(getattr(shape.transform, key)())
                    for key in ("m11", "m12", "m21", "m22", "dx", "dy")
                ),
            )
            for shape in layer.shapes
            if shape.isComponent
        ),
    )


def source_values(package: Any, names: list[str], masters: list[str]) -> tuple:
    """Freeze native identities, raw pins, bounds, widths, recipes and dependencies."""
    rows = []
    for name in names:
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            raise ValueError("Glyph source changed; reopen this tool.")
        rows.append(
            (
                name,
                glyph.id,
                tuple(
                    (
                        master,
                        None
                        if (layer := layer_of(glyph, master)) is None
                        else _layer_values(layer),
                    )
                    for master in masters
                ),
                tuple(_layer_values(layer) for layer in glyph.layers),
                glyph.activeLayer.id,
            )
        )
    return (
        package.id,
        package.master,
        tuple(package.masters),
        dependency_values(package),
        tuple(rows),
    )


def _affected(targets: set[str], records: tuple) -> set[str]:
    """Resolve a finite component closure, refusing missing bases and cycles."""
    names = {name for name, _, _ in records}
    if targets - names:
        raise ValueError("Glyph source changed; reopen this tool.")
    edges = {name: set() for name in names}
    for name, auto, bases in records:
        if set(bases) - names or (auto and not bases):
            raise ValueError("Unverified or missing component dependency.")
        edges[name].update(bases)
    affected = set(targets)
    while (
        found := {name for name, bases in edges.items() if bases & affected} - affected
    ):
        affected.update(found)
    pending, done = set(), set()

    def visit(name: str) -> None:
        if name in pending:
            raise ValueError("Unverified cyclic component dependency.")
        if name in done:
            return
        pending.add(name)
        for base in edges[name] & affected:
            visit(base)
        pending.remove(name)
        done.add(name)

    for name in affected:
        visit(name)
    return affected


def _dependants(
    package: Any, targets: set[str], records: tuple, target_masters: dict[str, set[str]]
) -> list[Any]:
    """Enroll resolved users; refuse recipes on edited or notification-active layers.

    This source-candidate graph is not native acceptance of arbitrary automatic
    recomputation. Native notification resolves each glyph's active layer when
    its master argument is empty (flhistorycontroller/update_components). Other
    inactive masters remain frozen and initialized, without vetoing this edit.
    """
    affected = _affected(targets, records)
    masters = set().union(*target_masters.values())
    result = []
    for name in sorted(affected):
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            raise ValueError("Dependency source changed; reopen this tool.")
        active = glyph.activeLayer
        if (
            active is None
            or active.isNull
            or active.id not in {layer.id for layer in glyph.layers}
        ):
            raise ValueError("Dependency active layer changed; reopen this tool.")
        scoped = [
            layer_of(glyph, master) for master in target_masters.get(name, masters)
        ] + [active]
        for layer in scoped:
            if layer is None:
                raise ValueError("Missing affected dependency master layer.")
            if layer.recipe:
                raise ValueError("Unverified explicit automatic-layer recipe.")
        if name not in targets:
            result.append(glyph)
    return result


@dataclass
class PreparedPointMoves:
    """Preconstructed native values bound to an unchanged source and dependency graph."""

    package: Any
    work: list
    dependants: list
    names: list[str]
    masters: list[str]
    snapshot: tuple
    consumed: bool = False


def prepare_point_moves(package: Any, jobs: list) -> PreparedPointMoves:
    """Prepare (glyph, master, [(existing_native_pin, (raw_x, raw_y))]) jobs.

    Validate the whole batch before constructing any point or opening history.
    Pins retain identity and every native attribute; no additions or removals.
    """
    masters = list(package.masters)
    work, seen, target_masters = [], set(), {}
    for glyph, master, moves in jobs:
        if master not in masters:
            raise ValueError("Masters changed; reopen this tool.")
        live = package.findName(glyph.name)
        if live is None or live.isNull or live.id != glyph.id:
            raise ValueError("Glyph source changed; reopen this tool.")
        layer = layer_of(live, master)
        if layer is None or layer.autoLayer:
            raise ValueError("Missing or automatic anchor target layer.")
        pins = {pin.id: pin for pin in layer.anchors}
        edits = []
        for pin, point in moves:
            if len(point) != 2 or pin.id not in pins or pins[pin.id].name != pin.name:
                raise ValueError("Anchor source changed; reopen this tool.")
            if pin.id in seen:
                raise ValueError("Duplicate anchor move in batch.")
            seen.add(pin.id)
            old, point = raw_point(pin), tuple(finite(v) for v in point)
            if point == old:
                continue
            if point == (0, 0):
                raise ValueError(ORIGIN_ERROR)
            edits.append((pins[pin.id], old, point))
        if edits:
            work.append((live, master, layer, edits))
            target_masters.setdefault(live.name, set()).add(master)
    dependants = (
        _dependants(
            package,
            {g.name for g, _, _, _ in work},
            dependency_values(package),
            target_masters,
        )
        if work
        else []
    )
    names = list(
        dict.fromkeys([g.name for g, _, _, _ in work] + [g.name for g in dependants])
    )
    snapshot = source_values(package, names, masters) if work else ()
    if work:
        constructor = _native("PythonQt").QtCore.QPointF
        work = [
            (
                g,
                m,
                layer,
                [(pin, old, constructor(*point)) for pin, old, point in edits],
            )
            for g, m, layer, edits in work
        ]
    return PreparedPointMoves(package, work, dependants, names, masters, snapshot)


def _finish(glyphs: list, items: list, title: str) -> None:
    errors = []
    stamp = None
    try:
        try:
            stamp = _native("PythonQt").QtCore.QDateTime.currentDateTimeUtc()
            for glyph in glyphs:
                try:
                    glyph.lastModified = stamp
                except Exception as error:  # noqa: BLE001 - native cleanup must continue
                    errors.append(error)
        except Exception as error:  # noqa: BLE001 - still record history after clock failure
            errors.append(error)
        try:
            _native("fontlab").flItems().notifyChangesApplied(title, items)
        except Exception as error:  # noqa: BLE001 - native cleanup must continue
            errors.append(error)
    finally:
        try:
            _native("fontlab").UpdateAll()
        except Exception as error:  # noqa: BLE001 - preserve earlier native failure
            errors.append(error)
        if stamp is not None:
            # Native window observers can stamp after history captures this value.
            for glyph in glyphs:
                try:
                    glyph.lastModified = stamp
                except Exception as error:  # noqa: BLE001 - finish every owned glyph
                    errors.append(error)
    if errors:
        for error in errors[1:]:
            errors[0].add_note(f"Additional cleanup failure: {error}")
        raise errors[0]


def _read_changes(
    attempted: list, error: Exception | None
) -> tuple[list, Exception | None]:
    """Keep ownership of attempted writes when a native read cannot prove no change."""
    changed = {}
    for glyph, layer, pin, old, point in attempted:
        try:
            actual, wanted = raw_point(pin), (point.x(), point.y())
        except Exception as failure:  # noqa: BLE001 - uncertain writes still need history
            if error is None:
                error = failure
            else:
                error.add_note(
                    f"Postwrite anchor read failure: {type(failure).__name__}: {failure}"
                )
            error.add_note(
                "Postwrite read leaves changes uncertain; conservatively recording attempted owned targets and their dependants."
            )
            changed[layer.id] = glyph, layer
            continue
        if actual != old:
            changed[layer.id] = glyph, layer
        if actual != wanted and error is None:
            error = RuntimeError(
                "FontLab did not retain the requested anchor point; check rounding or expressions."
            )
    return list(changed.values()), error


def apply_point_moves(prepared: PreparedPointMoves, title: str) -> dict[str, int]:
    """Apply once, then create one final history notification, including partial writes."""
    if prepared.consumed:
        raise ValueError("Anchor source changed; prepare a new operation.")
    if not prepared.work:
        return {"anchors": 0, "layers": 0}
    if (
        source_values(prepared.package, prepared.names, prepared.masters)
        != prepared.snapshot
    ):
        raise ValueError("Anchor source changed; reopen this tool.")
    prepared.consumed = True
    glyphs = (
        list({g.id: g for g, _, _, _ in prepared.work}.values()) + prepared.dependants
    )
    layers = list({layer.id: layer for _, _, layer, _ in prepared.work}.values())
    initialize = (
        layers
        + [g.activeLayer for g in glyphs]
        + [layer for g in prepared.dependants for layer in g.layers]
        + glyphs
    )
    for item in {item.id: item for item in initialize}.values():
        item.checkInitHistoryState(0)
    error, attempted = None, []
    try:
        for glyph, _, layer, edits in prepared.work:
            for pin, old, point in edits:
                attempted.append((glyph, layer, pin, old, point))
                pin.point = point
    except Exception as failure:  # noqa: BLE001 - finalize partial native writes
        error = failure
    changed, error = _read_changes(attempted, error)
    changed_names = {g.name for g, _ in changed}
    if not changed:
        if error is not None:
            raise error
        raise RuntimeError(
            "FontLab did not move the requested anchors; check rounding or expressions."
        )
    affected = _affected(changed_names, prepared.snapshot[3])
    glyphs = [g for g in glyphs if g.name in affected]
    items = list({layer.id: layer for _, layer in changed}.values()) + glyphs
    try:
        _finish(glyphs, items, title)
    except Exception as failure:
        if error is None:
            raise
        error.add_note(f"History/refresh failure after partial anchor write: {failure}")
    if error is not None:
        error.add_note(
            "A partial anchor edit may remain; use the named Edit > Undo step."
        )
        raise error
    return {
        "anchors": sum(len(edits) for _, _, _, edits in prepared.work),
        "layers": len(layers),
    }
