# this_file: src/fontlabapp/masters/background/transaction.py
# SPDX-License-Identifier: Apache-2.0
"""One scoped background history operation, explicit recovery and paint restore.

No global Undo, preference writer, Output operation, event pump or UpdateAll.
Native full-font/cache/history/reopen qualification remains pending.
"""

from typing import Any

from fontlabapp.contours.angularizzle._native_write import swap
from fontlabapp.masters.background.records import check
from fontlabapp.qt.properties import value


class BackgroundWriteError(RuntimeError):
    """Failed native boundary; inspect retained errors before any further edit."""

    def __init__(self, errors: list, attempted: bool):
        super().__init__(
            "Background edit failed; recovery/history may retain changes. Reopen only after reviewing the retained errors and native history."
        )
        self.errors = tuple(errors)
        self.geometry_recovery_attempted = attempted


def _recover(job: Any) -> None:
    target = job.target
    if job.created is not None:
        target.glyph.removeLayer(job.created)
    elif target.mask is not None:
        swap(target.mask, tuple(reversed(job.attempted)), rollback=True)
        if job.replace:
            target.mask.clearAnchors()
            for anchor in job.anchors:
                target.mask.addAnchor(anchor)
            target.mask.removeGuides(True, True)
            target.mask.appendGuidelines(list(job.guides))
        target.mask.changed()
        if target.mask.update() is False:
            raise RuntimeError("Background recovery cache update failed.")
    target.foreground.isVisible = target.visible
    target.glyph.activeLayer = target.active


def _write(job: Any, deadline: float) -> Any:
    target = job.target
    mask = target.mask
    if mask is None:
        try:
            mask = target.foreground.getMaskLayer(True)
        finally:
            # Even a setter that creates then raises must be recovered.
            current = target.foreground.getMaskLayer(False)
            if current is not None and current.isValid:
                job.created = current
            target.foreground.isVisible = target.visible
            target.glyph.activeLayer = target.active
        if mask is None or not mask.isValid:
            raise RuntimeError("FontLab could not create the required background.")
    check(deadline)
    if job.replace:
        mask.clearAnchors()
        mask.removeGuides(True, True)
    for replacement in job.replacements:
        # Include a setter that changes state before raising, but never undo
        # later entries whose original shapes are still attached.
        job.attempted.append(replacement)
        swap(mask, (replacement,), deadline=deadline)
    mask.changed()
    if mask.update() is False:
        raise RuntimeError("Background cache update failed.")
    return mask


def publish(jobs: tuple, native: Any, qt: Any, deadline: float, label: str) -> None:
    """Keep original component history objects and one final layer/glyph batch."""
    glyphs = {int(j.target.glyph.id): j.target.glyph for j in jobs}
    history = []
    for job in jobs:
        for _index, shape, _new in job.replacements:
            if shape is None:
                continue
            if shape.isComponent:
                data = shape.shapeData
                history.extend((shape, data))
                if data.builder is not None:
                    history.append(data.builder)
    for item in [j.target.mask for j in jobs if j.target.mask is not None] + list(
        glyphs.values()
    ):
        check(deadline)
        item.checkInitHistoryState(0)
    window = native.MainWindow()
    previous = bool(value(window, "updatesEnabled"))
    stamp = qt.QtCore.QDateTime.currentDateTimeUtc()
    errors = []
    attempted = []
    masks = []
    try:
        window.setUpdatesEnabled(False)
        for job in jobs:
            check(deadline)
            job.attempted = []
            attempted.append(job)
            masks.append(_write(job, deadline))
        check(deadline)
    except BaseException as error:  # noqa: BLE001 - retain interruption and recovery errors
        errors.append(error)
        for job in reversed(attempted):
            try:
                _recover(job)
            except BaseException as recovery:  # noqa: BLE001 - retain recovery failure alongside cause
                errors.append(recovery)
    finally:
        for glyph in glyphs.values():
            try:
                glyph.lastModified = stamp
            except BaseException as error:  # noqa: BLE001 - retain interruption and recovery errors
                errors.append(error)
        try:
            current = [j.target.mask for j in jobs if j.target.mask is not None]
            current.extend(
                j.created
                for j in jobs
                if j.created is not None and j.created in j.target.glyph.layers
            )
            native.flItems().notifyChangesApplied(
                label, history + current + list(glyphs.values()), True
            )
        except BaseException as error:  # noqa: BLE001 - retain interruption and recovery errors
            errors.append(error)
        finally:
            for glyph in glyphs.values():
                try:
                    glyph.lastModified = stamp
                except BaseException as error:  # noqa: BLE001 - retain interruption and recovery errors
                    errors.append(error)
            try:
                window.setUpdatesEnabled(previous)
            except BaseException as error:  # noqa: BLE001 - retain interruption and recovery errors
                errors.append(error)
    if errors:
        raise BackgroundWriteError(errors, bool(attempted)) from errors[0]
