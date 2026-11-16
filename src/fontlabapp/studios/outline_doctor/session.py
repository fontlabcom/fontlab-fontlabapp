# this_file: src/fontlabapp/studios/outline_doctor/session.py
# SPDX-License-Identifier: Apache-2.0
"""Outline Doctor session: scan, plan, ghost and fix through the check registry.

What: ``Doctor`` reuses the Transform Studio session for fonts, masters,
glyph lookup and hint removal, and adds ``scan`` (read-only: never opens a
history step), ``plan`` (with the compatibility guard of the Scriptmix
outline panel), ``ghost`` (the planned after-outline over the TGlyph
preview, with the affected points highlighted) and ``fix`` (one
``AppShell.history`` step named ``"Outline Doctor: <action> <subject>"`` on
the explicit layers, then the check's own read-back).
Why: every ``checks.Check`` runs through the same guarded path. Layers with
PostScript hints are refused unless the caller opts in.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Any, NamedTuple

import fontlabapp.core.outline as outline
import fontlabapp.core.sharing as sharing
import fontlabapp.fontui as fontui

from ..transform_studio.geometry import Overlay, OverlayContour, OverlayPoint, apply, subject
from ..transform_studio.native import matrix_of
from ..transform_studio.session import AUTO_NOTE, ERRORS, HINT_NOTE, MISSING_NOTE, ROUNDING_NOTE, Studio
from . import APP
from .model import Check, Context, Issue, held_back

ALL_GLYPHS_NOTE = "whole font"


class Row(NamedTuple):
    """One glyph layer: its live layer (None when skipped), issues and skip note."""

    glyph: str
    master: str
    layer: Any
    issues: tuple[Issue, ...]
    note: str = ""

    @property
    def edits(self) -> list[Any]:
        return [issue.edit for issue in self.issues if issue.edit is not None]

    @property
    def problem(self) -> str:
        return next((issue.problem for issue in self.issues if issue.problem and issue.edit is None
                     and issue.problem != "gap"), "")  # fmt: skip


class Doctor(Studio):
    """The Outline Doctor session (see the module docstring)."""

    APP = APP

    def __init__(self, shell: Any, *, measures: Callable[[Any], Callable[[str], tuple]] | None = None,
                 **kwargs: Any) -> None:  # fmt: skip
        super().__init__(shell, **kwargs)
        self._measures = measures or _font_measures

    # Reading -------------------------------------------------------------------
    def font_glyphs(self) -> list[str]:
        return [str(glyph.name) for glyph in self.package().glyphs]

    def scan(self, check: Check, options: Mapping[str, Any] | None = None, names: Sequence[str] | None = None, *,
             all_masters: bool = False, whole_font: bool = False) -> list[Row]:  # fmt: skip
        """Run ``check`` as a read-only report: no history step, no writes."""
        chosen = self.font_glyphs() if whole_font else self._names(names)
        rows = self._rows(check, options, chosen, self.targets(all_masters), allow_hinted=True)
        self.rows = rows
        found = sum(len(row.issues) for row in rows)
        where = ALL_GLYPHS_NOTE if whole_font else subject(chosen)
        self.say(f"{self.APP}: {check.title} found {found} item(s) in {where}; nothing written.")
        return rows

    def plan(self, check: Check, options: Mapping[str, Any] | None = None, names: Sequence[str] | None = None, *,
             all_masters: bool = False, compatible: bool = True, allow_hinted: bool = False) -> list[Row]:  # fmt: skip
        """Plan ``check`` (read-only). Structural fixes with ``compatible`` plan every master."""
        chosen, targets = self._names(names), self.targets(all_masters)
        guard = check.structural and compatible
        rows = self._rows(check, options, chosen, list(self.masters) if guard else targets, allow_hinted=allow_hinted)
        if guard:
            rows = self._guard(rows, targets)
        self.rows = [row for row in rows if row.master in targets]
        return self.rows

    @sharing.sharing_operation()  # one component-user count per scan or plan pass
    def _rows(self, check: Check, options: Mapping[str, Any] | None, names: Sequence[str], masters: Sequence[str],
              *, allow_hinted: bool) -> list[Row]:  # fmt: skip
        values = {**check.defaults(), **(options or {})}
        measures = self._measures(self.package()) if check.key == "near_miss" else None
        rows = []
        for name in names:
            self.native_glyph(name)
            reference = self.layer(name, self.master) if self.master else None
            for master in masters:
                layer = self.layer(name, master)
                if layer is None:
                    rows.append(Row(name, master, None, (), MISSING_NOTE))
                    continue
                if layer.autoLayer:
                    rows.append(Row(name, master, None, (), AUTO_NOTE))
                    continue
                try:
                    issues = tuple(check.plan(layer, values, Context(name, master, reference, measures)))
                except ERRORS as error:
                    rows.append(Row(name, master, layer, (), f"skipped: {error}"))
                    continue
                note = ""
                if any(i.edit is not None for i in issues) and not allow_hinted:
                    hinted = fontui.layer_is_hinted(layer)
                    note = hinted.text() + HINT_NOTE if hinted else ""
                rows.append(Row(name, master, layer, issues, note))
        return rows

    @staticmethod
    def _guard(rows: list[Row], targets: Sequence[str]) -> list[Row]:
        """Hold back a glyph's edit when its masters would stop matching."""
        result = []
        for name in dict.fromkeys(row.glyph for row in rows):
            mine = [row for row in rows if row.glyph == name]
            reason = held_back({row.master: list(row.issues) for row in mine if row.layer is not None}, targets)
            for row in mine:
                if reason:
                    row = row._replace(issues=tuple(i._replace(new=reason, edit=None, after=())
                                                    if i.edit is not None else i for i in row.issues))  # fmt: skip
                result.append(row)
        return result

    # Preview -------------------------------------------------------------------
    def ghost(self, rows: Sequence[Row], glyph: str | None = None, master: str | None = None) -> Overlay | None:
        """Draw the planned after-outline of one row over the preview and highlight its points."""
        wanted = [r for r in rows if r.layer is not None and (glyph is None or r.glyph == glyph)
                  and r.master == (master or self.master)]  # fmt: skip
        row = next((r for r in wanted if any(i.after or i.marks for i in r.issues)), None)
        if row is None or self.preview is None:
            return None
        changes = dict(entry for issue in row.issues for entry in issue.after)
        overlay = after_overlay(row.layer, changes) if changes else None
        self.preview.set_overlay(overlay)
        marks = tuple(mark for issue in row.issues for mark in issue.marks)
        if marks and hasattr(self.preview, "highlight"):
            self.preview.highlight(points=marks)
        return overlay

    # Writing -------------------------------------------------------------------
    def fix(self, check: Check, options: Mapping[str, Any] | None = None, names: Sequence[str] | None = None, *,
            all_masters: bool = False, compatible: bool = True, allow_hinted: bool = False,
            allow_bases: bool = False) -> bool:  # fmt: skip
        """Apply ``check`` to the planned layers as one Undo step; False when refused.

        ``allow_bases`` (only for checks whose original offered it) lets the
        AppShell edit bases of automatic composites; otherwise it refuses them.
        """
        app = self.APP
        if check.report:
            self.say(f"{app}: {check.title} only reports; nothing to apply.")
            return False
        try:
            rows = self.plan(check, options, names, all_masters=all_masters, compatible=compatible,
                             allow_hinted=allow_hinted)  # fmt: skip
        except ERRORS as error:
            self.say(f"{app}: {error}")
            return False
        blocked = next((row for row in rows if row.problem), None)
        if blocked is not None:
            self.say(f"{app}: refused. {blocked.glyph} ({blocked.master}): {blocked.problem}")
            return False
        pending = [row for row in rows if row.edits and not row.note]
        skipped = sorted({f"{row.glyph} ({row.master}): {row.note}" for row in rows if row.note})
        if not pending:
            self.say(f"{app}: no change." + (" Skipped: " + "; ".join(skipped) if skipped else ""))
            return False
        values = {**check.defaults(), **(options or {})}
        write, verify = check.write, check.verify
        assert write is not None and verify is not None  # fixes always register both
        label = f"{app}: {check.action} {subject([row.glyph for row in pending])}"
        layers = [row.layer for row in pending]
        glyphs = list({row.glyph: self.native_glyph(row.glyph) for row in pending}.values())

        @sharing.sharing_operation()  # one component-user count per apply pass
        def mutate() -> None:
            for row in pending:
                write(row.layer, row.edits, values)

        def read_back() -> list[str]:
            return [text for row in pending for text in verify(row.layer, row.edits)]

        try:
            committed = self.shell.history(label, glyphs, mutate, layers=layers, read_back=read_back,
                                           allow_bases=bool(allow_bases and check.bases))  # fmt: skip
        except ERRORS as error:
            self.say(f"{app}: {error} Native changes may remain; use Edit > Undo.")
            return False
        if committed is None:
            return False
        mismatches = tuple(getattr(committed, "mismatches", ()) or ())
        if mismatches:
            self.say(f"Partly applied: {label}. " + "; ".join(mismatches)
                     + f". Native changes may remain; use Edit > Undo. {ROUNDING_NOTE}")  # fmt: skip
        else:
            advice = list(dict.fromkeys(
                text for row in pending if check.advise for text in check.advise(row.layer, row.edits)))  # fmt: skip
            self.say(f"{label}." + (" Skipped: " + "; ".join(skipped) if skipped else "")
                     + (" · " + "; ".join(advice) if advice else ""))  # fmt: skip
        if self.preview is not None:
            self.preview.set_overlay(None)
            self.preview.refresh()
        self._refresh()
        return not mismatches


def after_overlay(layer: Any, changes: Mapping[tuple[int, int], Any]) -> Overlay:
    """The layer's own outline in glyph space with planned contours replaced or removed."""
    drawn = []
    for position, shape in enumerate(layer.shapes):
        if shape.isComponent:
            continue
        matrix = matrix_of(shape.transform)
        for index, contour in enumerate(shape.contours):
            if (position, index) in changes:
                points = changes[(position, index)]
                if points is None:
                    continue
            else:
                points = [(*apply(matrix, float(n.x), float(n.y)), bool(n.isOn())) for n in contour.nodes()]
            drawn.append(OverlayContour(tuple(OverlayPoint(x, y, "line" if on else None, False)
                                              for x, y, on in points), bool(contour.closed)))  # fmt: skip
    return Overlay(tuple(drawn))


def _font_measures(package: Any) -> Callable[[str], tuple]:
    """Per-master (metrics, horizontal stems, vertical stems) read once from fontpr."""
    data = outline.font_info(package)
    return lambda master: outline.master_measures(data, master)
