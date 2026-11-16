# this_file: src/fontlabapp/contours/angularizzle/_native_write.py
# SPDX-License-Identifier: Apache-2.0
"""Stage own-contour copies before history; keep untouched native shapes attached.

There is no public resetMark binding for inherited marks. Late failures restore
geometry where possible and retain diagnosed history; they are never atomic-success.
"""

from typing import Any

import fontlabapp.core.edit_guards as edit_guards

from fontlabapp.contours.angularizzle._native_records import clone_shape, number
from fontlabapp.contours.angularizzle.model import _check_deadline


class NativeAdapterError(RuntimeError):
    """A failed native boundary, possibly retaining recoverable history state."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.errors: tuple = ()
        self.geometry_recovery_attempted = False


def build_contour(
    path: Any, transform: Any, native: Any, qt: Any, deadline: float
) -> Any:
    if not path.closed or len(path.segments) < 3:
        raise ValueError(
            "Angularizzle cannot represent an empty/collapsed output contour."
        )
    points = []
    for index, segment in enumerate(path.segments):
        _check_deadline(deadline)
        if (
            segment.move
            or len(segment.points) != 2
            or segment.points[1]
            != path.segments[(index + 1) % len(path.segments)].points[0]
        ):
            raise ValueError(
                "Angularizzle output must be one continuous closed line contour."
            )
        points.append(segment.points[0])
    inverse = transform.inverted()
    nodes = []
    for x, y in points:
        _check_deadline(deadline)
        local = inverse.map(qt.QtCore.QPointF(number(x), number(y)))
        node = native.flNode(local, nodeType="on")
        nodes.append(node)
    contour = native.flContour(nodes, closed=True)
    if len(contour.nodes()) != len(nodes):
        raise ValueError("Angularizzle native constructor changed output node count.")
    return contour


def prepare(
    bound: Any,
    before: Any,
    after: Any,
    inputs: Any,
    restore: bool,
    native: Any,
    qt: Any,
    deadline: float,
) -> tuple:
    """Keep each output on its original owner, refusing ambiguous cross-layer groups."""
    if before.paths == after.paths:
        return ()
    own = [
        (i, s)
        for i, s in enumerate(bound.layer.shapes)
        if not s.isComponent and s.contours
    ]
    if restore:
        if not bound.originals:
            return tuple((i, shape, None) for i, shape in reversed(own))
        return tuple(
            (i, bound.layer.shapes[i], clone_shape(shape, deadline))
            for i, shape in bound.originals
        )
    if not own:
        shape = native.flShape()
        for path in after.paths:
            shape.addContour(
                build_contour(path, shape.transform, native, qt, deadline), True
            )
        if len(shape.contours) != len(after.paths):
            raise ValueError("Angularizzle native shape rejected an output contour.")
        return ((len(bound.layer.shapes), None, shape),)
    if len(own) == 1:
        owners = [own[0][0]] * len(after.paths)
    else:
        if inputs.key != before.key:
            raise ValueError(
                "Angularizzle cross-layer multi-shape correspondence is ambiguous."
            )
        owners = [
            owner
            for path, owner in zip(inputs.paths, bound.owners, strict=True)
            if path.closed and any(not s.move and s.points for s in path.segments)
        ]
        if len(owners) != len(after.paths):
            raise ValueError("Angularizzle output lost original own-shape provenance.")
    grouped = {index: [] for index, _ in own}
    for path, owner in zip(after.paths, owners, strict=True):
        _check_deadline(deadline)
        grouped[owner].append(path)
    result = []
    for index, shape in own:
        _check_deadline(deadline)
        clone = clone_shape(shape, deadline)
        for contour in tuple(clone.contours):
            clone.removeContour(contour)
        for path in grouped[index]:
            contour = build_contour(path, clone.transform, native, qt, deadline)
            clone.addContour(contour, True)
        if len(clone.contours) != len(grouped[index]):
            raise ValueError("Angularizzle native shape rejected an output contour.")
        result.append((index, shape, clone))
    return tuple(result)


def swap(
    layer: Any,
    replacements: tuple,
    *,
    rollback: bool = False,
    deadline: float | None = None,
) -> None:
    """Replace only selected own shapes at their original layer indices."""
    for index, old, new in replacements:
        _check_deadline(deadline)
        desired = old if rollback else new
        current = layer.shapes[index] if index < len(layer.shapes) else None
        if (
            current is not None
            and desired is not None
            and int(current.id) == int(desired.id)
        ):
            continue
        # Failed insertion may leave an empty slot, with the next untouched shape
        # now at index. Never remove that component or unrelated shape.
        other = new if rollback else old
        if (
            current is not None
            and other is not None
            and int(current.id) == int(other.id)
        ):
            layer.removeShape(current)
            _check_deadline(deadline)
        if desired is None:
            continue
        inserted = layer.insertShape(index, desired)
        _check_deadline(deadline)
        if inserted is not None and int(inserted.id) != int(desired.id):
            raise RuntimeError("Angularizzle attachment changed native shape identity.")


def publish(jobs: tuple, native: Any, qt: Any, deadline: float) -> None:
    """One prepared history operation; diagnose all late failures without global Undo."""
    layers = [bound.layer for bound, _, _, _ in jobs]
    glyphs = {int(bound.glyph.id): bound.glyph for bound, _, _, _ in jobs}
    edit_guards.require_history_scope(list(glyphs.values()), native=native)
    items = layers + list(glyphs.values())
    for item in items:
        _check_deadline(deadline)
        item.checkInitHistoryState(0)
    _check_deadline(deadline)
    stamp = qt.QtCore.QDateTime.currentDateTimeUtc()
    attempted, errors = [], []
    recovery_attempted = False
    try:
        for bound, replacements, _, _ in jobs:
            _check_deadline(deadline)
            attempted.append((bound, replacements))
            swap(bound.layer, replacements, deadline=deadline)
        for bound, _, color, _ in jobs:
            _check_deadline(deadline)
            bound.layer.mark = color
        for bound, _, _, _ in jobs:
            for item in (bound.layer, bound.glyph):
                _check_deadline(deadline)
                item.changed()
                if item.update() is False:
                    raise RuntimeError("Angularizzle native cache update failed.")
        _check_deadline(deadline)
    except BaseException as error:  # noqa: BLE001 - recover even interrupted native edits
        errors.append(error)
        recovery_attempted = bool(attempted)
        # Recovery deliberately has no expired action deadline: stop further
        # planned writes, restore only attached geometry, then expose history.
        for bound, replacements in reversed(attempted):
            try:
                swap(bound.layer, tuple(reversed(replacements)), rollback=True)
                bound.layer.changed()
                if bound.layer.update() is False:
                    raise RuntimeError("Angularizzle recovery cache update failed.")
            except BaseException as recovery:  # noqa: BLE001 - retain recovery failure alongside cause
                errors.append(recovery)
    finally:
        for glyph in glyphs.values():
            try:
                glyph.lastModified = stamp
            except BaseException as error:  # noqa: BLE001 - notification must still be attempted
                errors.append(error)
        try:
            native.flItems().notifyChangesApplied("Angularizzle", items, True)
            native.UpdateAll()
        except BaseException as error:  # noqa: BLE001 - recover even interrupted native edits
            errors.append(error)
        finally:
            for glyph in glyphs.values():
                try:
                    glyph.lastModified = stamp
                except BaseException as error:  # noqa: BLE001 - retain final observer/stamp failure
                    errors.append(error)
    if errors:
        failure = NativeAdapterError(
            "Angularizzle native write failed; geometry/color/history may retain changes. Review the retained error and recovery state before reopening or using native Undo."
        )
        failure.errors = tuple(errors)
        failure.geometry_recovery_attempted = recovery_attempted
        raise failure from errors[0]
