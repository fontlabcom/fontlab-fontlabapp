# this_file: src/fontlabapp/studios/layer_manager/_restore.py
# SPDX-License-Identifier: Apache-2.0
"""Backups tab, Restore mode: the Scriptmix "Restore Backup Layer" (Scripts/Masters/).

Copy a chosen backup layer back into the master layer it belongs to
(contours replaced by repaired clones, same-named anchors moved, advance
width set), for every selected glyph; optionally delete the backup and
its mask. The planning is the original's, verbatim, with the App's shared
backup rule (``masters.inspect.model.backup_master``). A shown or locked
backup is kept and counted. The components of deleted layers are read
before the edit and retained (fl#7641). Restore plans again, refuses a
plan that differs from the list, and writes ONE
``Layer Manager: restore backup <subject>`` Undo step through
``AppShell.history``; layer deletion keeps the original's
``glyph.removeLayer`` route inside that step.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native

from .._kerning_ui import check, combo, get, row
from ._shared import (
    Modules,
    PlanTab,
    Qt,
    append_note,
    commit,
    ident,
    label as undo_label,
    result_dict,
)

masters_api = Modules("masters")
contour_copy = Modules("contour_copy")
qt = Qt

TITLE = "Restore Backup Layer"
KEY = "masters_restore_backup"
LINK_FIELDS = ("metricsLeft", "metricsRight", "metricsWidth")
TEMP_PREFIX = "|temp|"
MAX_NAMES = 8  # glyph names shown in the subtitle
NO_BACKUP = "No backup layers in these glyphs. Make some with Duplicate Current Layer."

Move = tuple[str, float, float]


@dataclass(frozen=True)
class Job:
    """One glyph: its backup layer, its master layer and the plan.

    ``note`` is empty for a glyph that will be restored; else it says why
    the glyph is skipped. ``mask`` is the mask layer of the backup, or None.
    """

    glyph: Any
    backup: Any
    master: str
    target: Any
    mask: Any
    contours_now: int
    contours_after: int
    width_now: float
    width_after: float
    moves: tuple[Move, ...] = ()
    missing: tuple[str, ...] = ()
    note: str = ""


def backup_master(name: str, masters: Sequence[str]) -> str | None:
    """Resolve backup layers through the shared App rule."""

    return masters_api.backup_master(name, masters)


def _valid(layer: Any) -> bool:
    """True for a real native layer object."""
    return layer is not None and not layer.isNull


def backup_names(glyphs: Sequence[Any], masters: Sequence[str]) -> list[str]:
    """Return the sorted unique backup layer names of ``glyphs``."""
    found = {
        str(layer.name)
        for glyph in glyphs
        for layer in glyph.layers
        if not layer.isMaskLayer
        and not layer.isService
        and not layer.autoLayer
        and backup_master(str(layer.name), masters)
    }
    return sorted(found)


def outline_shapes(layer: Any) -> list[Any]:
    """Return the non-component shapes of ``layer`` that hold contours."""
    return [s for s in layer.shapes if not s.isComponent and len(s.contours)]


def contours_in(layer: Any) -> int:
    """Return the number of contours in the non-component shapes of ``layer``."""
    return sum(len(s.contours) for s in layer.shapes if not s.isComponent)


def clone_shape(shape: Any) -> Any:
    """Return a repaired clone of ``shape``. Raise RuntimeError on a lost contour."""

    copy = shape.clone()
    if len(copy.contours) != len(shape.contours):
        raise RuntimeError("FontLab clone changed the contour count of a shape.")
    contour_copy.restore_shape(shape, copy)
    return copy


def replace_outline(source: Any, target: Any) -> None:
    """Remove the non-component shapes of ``target``; add clones of the source outline."""
    for shape in [s for s in target.shapes if not s.isComponent]:
        target.removeShape(shape)
    for shape in outline_shapes(source):
        target.addShape(clone_shape(shape))


def _point(pin: Any) -> tuple[float, float]:
    """Stored anchor position, unrounded."""
    return float(pin.point.x()), float(pin.point.y())


def plan_anchors(
    source: Any, target: Any
) -> tuple[tuple[Move, ...], tuple[str, ...], str]:
    """Return (moves, missing names, problem) for same-named anchors."""
    for layer in (source, target):
        names = [str(pin.name) for pin in layer.anchors]
        twice = sorted({n for n in names if names.count(n) > 1})
        if twice:
            return (), (), f"several anchors named {', '.join(twice)} (skipped)"
    own = {str(pin.name): _point(pin) for pin in target.anchors}
    moves, missing = [], []
    for pin in source.anchors:
        name, where = str(pin.name), _point(pin)
        if name not in own:
            missing.append(name)
        elif own[name] != where:
            if where == (0.0, 0.0):
                return (
                    (),
                    (),
                    f"anchor {name} would move to 0, 0; FontLab cannot redo it (fl#8527)",
                )
            moves.append((name, *where))
    return tuple(moves), tuple(missing), ""


def has_metrics_link(layer: Any) -> bool:
    """True when a sidebearing or the width holds a link or an expression."""
    return any(str(getattr(layer, field)) for field in LINK_FIELDS)


def _plan(glyph: Any, backup: Any, masters: Sequence[str], reason: str) -> Job:
    """Plan one glyph. ``reason`` is the geometry refusal of the glyph, or ""."""
    master = backup_master(str(backup.name), masters) or ""
    target = glyph.findLayer(master) if master else None
    mask = backup.getMaskLayer(False)
    mask = mask if _valid(mask) else None
    if not _valid(target):
        return Job(
            glyph, backup, master, None, mask, 0, 0, 0, 0, note="no master layer"
        )
    now, width = contours_in(target), target.advanceWidth
    note = ""
    if target.autoLayer:
        note = "auto layer (skipped)"
    elif reason:
        note = f"{reason} (skipped)"
    elif target.isLocked:
        note = "locked layer (skipped)"
    elif has_metrics_link(target):
        note = "metrics link or expression (skipped)"
    elif not outline_shapes(backup):
        note = "backup has no outline (skipped)"
    if not note:
        moves, missing, note = plan_anchors(backup, target)
    if note:
        return Job(
            glyph, backup, master, target, mask, now, now, width, width, note=note
        )
    return Job(
        glyph,
        backup,
        master,
        target,
        mask,
        now,
        contours_in(backup),
        width,
        backup.advanceWidth,
        moves,
        missing,
    )


def survey(package: Any, names: Sequence[str], chosen: str, facts: Any) -> list[Job]:
    """Plan the restore of backup ``chosen`` for every glyph in ``names``. Change nothing."""

    masters = [str(m) for m in package.masters]
    jobs: list[Job] = []
    for name in names:
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            continue
        backup = next(
            (x for x in glyph.layers if str(x.name) == chosen and not x.isMaskLayer),
            None,
        )
        if backup is None:
            jobs.append(
                Job(
                    glyph,
                    None,
                    "",
                    None,
                    None,
                    0,
                    0,
                    0,
                    0,
                    note="no layer with this name",
                )
            )
            continue
        jobs.append(
            _plan(
                glyph,
                backup,
                masters,
                history.refusal(facts, str(glyph.name), "geometry"),
            )
        )
    return jobs


def restore(
    tool: Any, jobs: Sequence[Job], delete: bool, title: str = TITLE
) -> dict[str, Any] | None:
    """Restore the planned jobs as ONE Undo step; optionally delete the backups (the original's ``restore``).

    The original's plan of deletions, retained component history, mutate
    and read-back, verbatim; the step goes through ``tool.shell.history``
    titled ``title`` (None when refused).
    """
    todo = [j for j in jobs if not j.note]
    if not todo:
        return {
            "pending_updates": (),
            "pending_note": "",
            "layers": 0,
            "glyphs": 0,
            "deleted": 0,
            "kept": 0,
            "mismatches": [],
        }
    glyphs = list({str(j.glyph.name): j.glyph for j in todo}.values())
    doomed: list[
        tuple[Any, Any, str]
    ] = []  # (glyph, layer, name): backup, then its mask
    kept = 0
    for job in todo if delete else ():
        active = job.glyph.updateActiveLayer(False)
        shown = _valid(active) and int(active.id) == int(job.backup.id)
        locked = job.backup.isLocked or (job.mask is not None and job.mask.isLocked)
        if shown or locked:
            kept += 1
            continue
        doomed.append((job.glyph, job.backup, str(job.backup.name)))
        if job.mask is not None:
            doomed.append((job.glyph, job.mask, str(job.mask.name)))
    # Read before any removal: a builder read after detachment can be too late (fl#7641).
    retain = [
        obj
        for _, layer, _ in doomed
        for shape in layer.shapes
        for obj in history.component_history(shape)
    ]

    def mutate() -> None:
        for job in todo:
            replace_outline(job.backup, job.target)
            pins = {str(pin.name): pin for pin in job.target.anchors}
            for name, x, y in job.moves:
                pins[name].point = qt.QtCore.QPointF(x, y)
            if job.width_after != job.width_now:
                job.target.advanceWidth = job.width_after
            job.target.changed()
            if job.target.update() is False:
                raise RuntimeError(
                    f"FontLab could not update '{job.glyph.name}' in '{job.master}'."
                )
        for glyph, layer, _ in reversed(doomed):  # the mask first, then its backup
            glyph.removeLayer(layer)

    def read_back() -> list[str]:
        found = []
        for job in todo:
            label = f"{job.glyph.name} · {job.master}"
            if contours_in(job.target) != job.contours_after:
                found.append(
                    f"{label}: {contours_in(job.target)} contours, planned {job.contours_after}"
                )
            if job.target.advanceWidth != job.width_after:
                found.append(
                    f"{label}: width {job.target.advanceWidth:g}, planned {job.width_after:g}"
                )
        for glyph, layer, name in doomed:
            if int(layer.id) in {int(x.id) for x in glyph.layers}:
                found.append(f"{glyph.name}: layer '{name}' is still there")
        return found

    done = commit(
        tool,
        title,
        [j.target for j in todo],
        glyphs,
        mutate,
        read_back=read_back,
        retain=retain,
    )
    if done is None:
        return None
    return result_dict(
        done, layers=len(todo), glyphs=len(glyphs), deleted=len(doomed), kept=kept
    )


def plural(count: int, word: str) -> str:
    """Return "1 glyph" or "2 glyphs"."""
    return f"{count} {word}{'' if count == 1 else 's'}"


class RestorePanel(PlanTab):
    """Backup and "Delete the backup…", the per-glyph table, Use selection and Restore."""

    ACTION = "Restore"
    HEADERS = ("Glyph", "Into master", "Contours", "Width", "Note")
    STATUS_REFUSALS = (NO_BACKUP,)

    def build_controls(self, form: Any) -> None:
        self.backup = row(
            self.widget,
            form,
            "Backup",
            combo(self.widget, [], self.contain(self.redraw)),
        )
        self.delete_after = check(
            self.widget,
            form,
            "Delete the backup layer and its mask after restoring",
            False,
        )

    def bind(self) -> None:
        super().bind()
        self.fill_backups()

    def fill_backups(self) -> None:
        """List the backup names of the selected glyphs; keep the current choice."""
        package = self.tool.shell.package()
        if package is None:
            return
        glyphs = [
            g
            for g in (package.findName(n) for n in self.names)
            if g is not None and not g.isNull
        ]
        chosen = str(get(self.backup.currentText))
        names = backup_names(glyphs, [str(m) for m in package.masters])
        self.backup.blockSignals(True)
        self.backup.clear()
        for name in names:
            self.backup.addItem(name)
        if chosen in names:
            self.backup.setCurrentIndex(names.index(chosen))
        self.backup.blockSignals(False)

    def plan(self) -> list[Job]:
        package = self.bound()
        if not self.names:
            raise ValueError(
                "Select glyphs in the Font window. Then press Use selection."
            )
        if get(self.backup.count) == 0:
            raise ValueError(NO_BACKUP)
        return survey(
            package,
            self.names,
            str(get(self.backup.currentText)),
            history.scan_auto_facts(package),
        )

    def rows(self, items: list[Job]) -> list[tuple]:
        return [(str(j.glyph.name), j.master or None, ("", "", "", j.note) if j.note else
                 (j.master, f"{j.contours_now} → {j.contours_after}", f"{j.width_now:g} → {j.width_after:g}", ""))
                for j in items]  # fmt: skip

    def key(self, items: list[Job]) -> Any:
        return tuple(self.rows(items)), tuple(
            (ident(j.backup), ident(j.target), j.moves) for j in items
        )

    def ready_items(self, items: list[Job]) -> bool:
        return any(not j.note for j in items)

    def summary(self, items: list[Job]) -> str:
        todo = [j for j in items if not j.note]
        return (f"{plural(len(todo), 'glyph')} will get “{get(self.backup.currentText)}” back · cells read now → after"
                if todo else "Nothing to restore")  # fmt: skip

    def write(self, items: list[Job]) -> str | None:
        todo = [j for j in items if not j.note]
        result = restore(self.tool, items, bool(get(self.delete_after.isChecked)),
                         undo_label("restore backup", [j.glyph.name for j in todo]))  # fmt: skip
        if result is None:
            return None
        self.fill_backups()
        text = f"Restored {plural(result['layers'], 'master layer')} in {plural(result['glyphs'], 'glyph')}"
        if result["deleted"]:
            text += f" · deleted {plural(result['deleted'], 'layer')}"
        if result["kept"]:
            text += f" · kept {result['kept']} shown backup(s)"
        if result["mismatches"]:
            text += " · did not read back as planned: " + "; ".join(
                result["mismatches"][:5]
            )
        return append_note(text, result)


__all__ = [
    "NO_BACKUP",
    "TITLE",
    "Job",
    "RestorePanel",
    "backup_names",
    "restore",
    "survey",
]
