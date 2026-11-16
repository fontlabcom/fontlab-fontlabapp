# this_file: src/fontlabapp/anchors/crossfont/transaction.py
# SPDX-License-Identifier: Apache-2.0
"""Stage native anchor clones and notify actual destination owners exactly once.

The original uses flPinPoint.clone. Retain that maintained native operation,
verify all exposed clone fields before transforms, and never rebuild raw hidden
mark state from effective getters. Full-font native history/reopen is a gate.
"""

from dataclasses import replace
from typing import Any

from fontlabapp.anchors.copy.model import APPEARANCE
from fontlabapp.anchors.duplicates.capture import check
from fontlabapp.anchors.crossfont.model import TITLE, Edit, Options, copy_layer
from fontlabapp.anchors.crossfont.capture import Snapshot, pin_record
from fontlabapp.anchors.crossfont.names import insertion_name
from fontlabapp.guides.inspect.model import affected_auto_layers


class PartialWriteError(RuntimeError):
    """An attempted write was finalized; native Undo/history needs inspection."""

    def __init__(self, attempted: int, errors: list[BaseException]) -> None:
        """Retain attempted edits and every error from finalizing native history."""
        self.attempted = attempted
        self.errors = tuple(str(e) for e in errors)
        super().__init__(
            f"Copy failed after {attempted} attempted changes; inspect Edit > Undo. "
            + "; ".join(self.errors)
        )


def pending(native: Any) -> None:
    """Never clear or conceal unrelated process-global queued native updates."""
    if tuple(native.flGlyph.updatedFgGlyphs()):
        raise ValueError(
            "Pending native glyph updates must settle before copying anchors."
        )


def clone_pin(
    source: Any,
    edit: Any,
    layer_source: Any,
    options: Options,
    native: Any,
    qt: Any,
    deadline: float,
) -> Any:
    """A detached full native clone; fail pre-history on rounding or metadata loss."""
    from fontlabapp.anchors.crossfont.capture import pin_record

    check(deadline)
    original = pin_record(source, deadline)
    clone = native.flPinPoint(source.clone())
    actual = pin_record(clone, deadline)
    if (
        int(clone.id) == int(source.id)
        or replace(actual, identity=original.identity) != original
    ):
        raise ValueError(
            "Native anchor clone changed identity, coordinates or exposed metadata."
        )
    clone.name = edit.pin.name
    if (options.relative and int(layer_source.width)) or (
        options.italic and options.angle > 0
    ):
        clone.point = qt.QtCore.QPointF(edit.pin.x, edit.pin.y)
    actual = pin_record(clone, deadline)
    # Both cloudEnabled and markEnabled mask canonical caret names. Native
    # clones retain raw bits; their exact post-name getters are staged below,
    # never written back into those raw bits from effective getters.
    if (actual.name, actual.x, actual.y, actual.metadata[:2], actual.metadata[4:]) != (
        edit.pin.name,
        edit.pin.x,
        edit.pin.y,
        edit.pin.metadata[:2],
        edit.pin.metadata[4:],
    ):
        raise ValueError(
            "Native transform rounded coordinates or changed retained anchor metadata."
        )
    if actual.name == original.name and actual.metadata != edit.pin.metadata:
        raise ValueError(
            "An unchanged-name transform changed retained anchor metadata."
        )
    return clone


def prepare(
    facts: Snapshot, options: Options, native: Any, qt: Any, deadline: float
) -> tuple:
    """Resolve all collisions and construct every incoming pin before history."""
    jobs = []
    for name, left, right, source, target in facts.layers:
        check(deadline)
        if source is None or target is None:
            continue
        result = copy_layer(
            source.pins,
            target.pins,
            source.width,
            target.width,
            options,
            normalize_insertion=lambda n, existing: insertion_name(
                n, existing, native, qt, deadline
            ),
        )
        if not result.edits:
            continue
        if target.automatic:
            raise ValueError(
                "Automatic destination layers cannot safely receive copied anchors."
            )
        if any(
            pin.metadata[0] == 0 and APPEARANCE.get(pin.name.lower(), 0)
            for pin in (*target.pins, *result.pins)
        ):
            raise ValueError(
                "A named default-appearance anchor cannot preserve its exact appearance through native Undo/Redo; no copy was started."
            )
        src_layer = facts.handles[source.identity][1]
        by_id = {int(p.id): p for p in src_layer.anchors}
        clones = {
            e.identity: clone_pin(
                by_id[e.source], e, source, options, native, qt, deadline
            )
            for e in result.edits
            if e.action == "add"
        }
        # Resolve exact name-derived flags on detached full clones, rather than
        # guessing hidden raw bits from a caret's masked effective getters.
        by_id.update({int(p.id): p for p in facts.handles[target.identity][1].anchors})
        original_names = {p.identity: p.name for p in (*source.pins, *target.pins)}
        expected = []
        for pin in result.pins:
            if pin.identity in clones:
                staged = clones[pin.identity]
            elif pin.name != original_names[pin.identity]:
                staged = clone_pin(
                    by_id[pin.identity],
                    Edit("rename", pin.identity, pin),
                    None,
                    Options(),
                    native,
                    qt,
                    deadline,
                )
            else:
                expected.append(pin)
                continue
            expected.append(
                replace(pin, metadata=pin_record(staged, deadline).metadata)
            )
        result = replace(result, pins=tuple(expected))
        jobs.append((name, target.identity, result, clones))
    blocked = affected_auto_layers(facts.dependencies, {name for name, _, _, _ in jobs})
    if blocked:
        raise ValueError(
            "Automatic destination dependants cannot safely undo this copy: "
            + ", ".join(blocked)
        )
    # A native pin/layer must have exactly one captured owner, except the same
    # source/destination layer deliberately used twice by a same-font copy.
    owners = {}
    for name, left, right, source, target in facts.layers:
        for master, layer in ((left, source), (right, target)):
            if layer is None:
                continue
            for p in layer.pins:
                owners.setdefault(p.identity, set()).add((layer.identity, name, master))
    if any(len(v) > 1 for v in owners.values()):
        raise ValueError("A captured anchor has ambiguous layer ownership.")
    return tuple(jobs)


def publish(
    facts: Snapshot,
    jobs: tuple,
    native: Any,
    qt: Any,
    deadline: float,
    title: str = TITLE,
) -> dict:
    """Identity-based ordered operations, one actual-destination history boundary.

    ``title`` names the Undo step (default: the Copy Anchors Between Fonts title).
    """
    layers = [facts.handles[key][1] for _, key, _, _ in jobs]
    glyphs = list(
        {
            int(facts.handles[key][0].id): facts.handles[key][0]
            for _, key, _, _ in jobs
        }.values()
    )
    objects = layers + glyphs
    for obj in objects:
        check(deadline)
        obj.checkInitHistoryState(0)
    stamp = qt.QtCore.QDateTime.currentDateTimeUtc()
    attempted = 0
    errors = []
    try:
        for _, key, result, clones in jobs:
            layer = facts.handles[key][1]
            refs = {int(p.id): p for p in layer.anchors}
            refs.update(clones)
            for edit in result.edits:
                check(deadline)
                attempted += 1
                if edit.action == "remove":
                    layer.removeAnchor(refs[edit.identity])
                    if any(
                        int(p.id) == int(refs[edit.identity].id) for p in layer.anchors
                    ):
                        raise RuntimeError(
                            "Destination anchor removal was not applied."
                        )
                elif edit.action == "rename":
                    refs[edit.identity].name = edit.pin.name
                    if str(refs[edit.identity].name) != edit.pin.name:
                        raise RuntimeError("Destination anchor rename was not applied.")
                else:
                    layer.addAnchor(refs[edit.identity])
            expected = tuple(int(refs[p.identity].id) for p in result.pins)
            if tuple(int(p.id) for p in layer.anchors) != expected:
                raise RuntimeError(
                    "Destination anchor order/identity differs from the full plan."
                )
    except BaseException as error:  # noqa: BLE001 - finalize partial native changes and interruption
        errors.append(error)
    if attempted:
        for glyph in glyphs:
            try:
                glyph.lastModified = stamp
            except BaseException as error:  # noqa: BLE001 - finalize all attempted native history
                errors.append(error)
        try:
            native.flItems().notifyChangesApplied(title, objects)
        except BaseException as error:  # noqa: BLE001 - retain failed native notification
            errors.append(error)
        finally:
            for glyph in glyphs:
                try:
                    glyph.lastModified = stamp
                except BaseException as error:  # noqa: BLE001 - retain failed final stamp
                    errors.append(error)
    if errors:
        raise PartialWriteError(attempted, errors) from errors[0]
    return {
        "anchors": sum(result.copied for _, _, result, _ in jobs),
        "layers": len(jobs),
        "skipped": facts.skipped,
        "zero_advance": tuple(
            (name, p) for name, _, result, _ in jobs for p in result.zero_advance
        ),
    }
