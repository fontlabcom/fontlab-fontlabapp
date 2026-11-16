# this_file: src/fontlabapp/studios/interpolation_doctor/session.py
# SPDX-License-Identifier: Apache-2.0
"""Interpolation Doctor session: read-only checks, counts, reports, the blend ghost and Make Compatible.

What: ``Doctor`` reuses the Transform Studio session (fonts, masters, glyph
lookup, hint removal) and adds the read-only readers of the Check, Node
counts and Preview tabs (they never open a history step) and
``make_compatible``: one ``AppShell.history`` step named
``"Interpolation Doctor: make compatible <subject>"`` over the explicit
layers, then the original read-back of node counts.
Why: the ten absorbed Scriptmix tools share one font, one master list and
one TGlyph preview here.
"""

from collections.abc import Callable, Sequence
from typing import Any, NamedTuple

import fontlabapp.core.sharing as sharing
import fontlabapp.fontui as fontui

from ..transform_studio.geometry import Overlay, OverlayContour, OverlayPoint, subject
from ..transform_studio.session import AUTO_NOTE, ERRORS, HINT_NOTE, MISSING_NOTE, ROUNDING_NOTE, Studio
from . import APP
from . import model as m

CHECKS = ("masters", "anchors", "components")
REPORTS = ("node", "why", "points", "master points")
ACTION = "make compatible"
ODD = " ≠"  # Scriptmix bold/red cell: differs from the other masters


class Fix(NamedTuple):
    """One planned Make Compatible layer: live layer (None when skipped), changes and note."""

    glyph: str
    master: str
    layer: Any
    changes: tuple[m.Change, ...]
    note: str = ""

    @property
    def edits(self) -> list[Any]:
        return [change.edit for change in self.changes if change.edit is not None]


class Found(NamedTuple):
    """A Check/Node counts result: table records, flagged glyphs and the status line."""

    records: list[tuple[str, str | None, tuple[str, ...]]]
    flagged: list[str]
    status: str
    marks: dict[tuple[str, str], tuple] = {}


def _select(package: Any, names: Sequence[str]) -> list[str]:
    from fontlabapp.core.scripting import select_glyphs

    return select_glyphs(names, package_id=int(package.id))


def _plural(count: int) -> str:
    return "s" if count != 1 else ""


class Doctor(Studio):
    """The Interpolation Doctor session (see the module docstring)."""

    APP = APP

    def __init__(self, shell: Any, *, select: Callable[[Any, Sequence[str]], list[str]] | None = None,
                 **kwargs: Any) -> None:  # fmt: skip
        super().__init__(shell, **kwargs)
        self._select_names = select or _select
        self.fixes: list[Fix] = []

    # Reading -------------------------------------------------------------------
    def font_glyphs(self) -> list[str]:
        return [str(glyph.name) for glyph in self.package().glyphs]

    def scope(self, names: Sequence[str] | None, whole_font: bool) -> list[str]:
        return self.font_glyphs() if whole_font else self._names(names)

    def found_glyphs(self, names: Sequence[str]) -> list[Any]:
        """Native glyphs for ``names``; unknown names are skipped like the originals."""
        package = self.package()
        found = [package.findName(name) for name in names]
        return [g for g in found if g is not None and not getattr(g, "isNull", False)]

    def check(self, kind: str, names: Sequence[str] | None = None, *, whole_font: bool = False,
              only_bad: bool = False) -> Found:  # fmt: skip
        """One of ``CHECKS`` as a read-only table (no history step, no writes)."""
        if kind not in CHECKS:
            raise ValueError(f"Unknown check: {kind}")
        if not self.masters:
            raise ValueError("Open a font first.")
        glyphs = self.found_glyphs(self.scope(names, whole_font))
        found = getattr(self, f"_{kind}")(glyphs, only_bad)
        self.say(f"{self.APP}: {found.status}")
        return found

    def _masters(self, glyphs: Sequence[Any], _only_bad: bool) -> Found:
        records, failing, marks = [], [], {}
        for glyph in glyphs:
            name = str(glyph.name)
            sigs, ok, problems = m.check(glyph, self.masters)
            if not ok:
                failing.append(name)
            records.append((name, None, ("", "", "", "", "", "✓" if ok else "✗ " + ", ".join(problems))))
            values = {master: m.summary(sig) for master, sig in sigs.items() if sig is not None}
            for master, sig in sigs.items():
                if sig is None:
                    records.append((name, master, (master, "auto layer · not compared", "", "", "", "")))
                    continue
                cells = []
                for column, value in enumerate(m.summary(sig)):
                    others = [v[column] for other, v in values.items() if other != master]
                    odd = bool(others) and value != m.most_common(others)
                    cells.append(f"{value}{ODD if odd else ''}")
                records.append((name, master, (master, *cells, "")))
                marks[(name, master)] = first_mismatch(sigs, master)
        return Found(records, failing, f"{len(failing)} of {len(glyphs)} glyphs incompatible", marks)

    def _anchors(self, glyphs: Sequence[Any], only_bad: bool) -> Found:
        rows = [(str(g.name), sets) for g in glyphs if (sets := m.anchor_sets(g, self.masters)) is not None]
        bad = [name for name, sets in rows if m.anchors_differ(sets)]
        records = []
        for name, sets in sorted(rows, key=lambda row: row[0] not in bad):
            if only_bad and name not in bad:
                continue
            records.append((name, None, ("", "", "", "", "", "✗" if name in bad else "✓")))
            every = sorted({a for names in sets.values() if names for a in names})
            for master in self.masters:
                here = sets.get(master, [])
                if here is None:
                    records.append((name, master, (master, "", "", "auto", "", "")))
                    continue
                missing = [a for a in every if a not in here]
                note = "missing: " + ", ".join(missing) if missing else ""
                records.append((name, master, (master, "", "", f"{len(here)}: " + ", ".join(here), "", note)))
        status = (f"{len(bad)} glyph{_plural(len(bad))} with different anchors across masters" if bad
                  else "All masters carry the same anchor names")  # fmt: skip
        return Found(records, bad, status)

    def _components(self, glyphs: Sequence[Any], only_bad: bool) -> Found:
        rows = [(str(g.name), lists) for g in glyphs if (lists := m.component_lists(g, self.masters)) is not None]
        bad = [name for name, lists in rows if m.odd_masters(lists, self.masters)]
        records = []
        for name, lists in sorted(rows, key=lambda row: row[0] not in bad):
            if only_bad and name not in bad:
                continue
            odd = set(m.odd_masters(lists, self.masters))
            records.append((name, None, ("", "", "", "", "", "✗" if name in bad else "✓")))
            for master in self.masters:
                text = " + ".join(lists.get(master, [])) or "–"
                records.append((name, master, (master, "", "", "", text, "differs from the first master"
                                               if master in odd else "")))  # fmt: skip
        status = (f"{len(bad)} glyph{_plural(len(bad))} with incompatible components" if bad
                  else "All composites have the same components on every master")  # fmt: skip
        return Found(records, bad, status)

    def node_counts(self, names: Sequence[str] | None = None, *, whole_font: bool = False,
                    only_flagged: bool = False) -> Found:  # fmt: skip
        """Contours / nodes per glyph and master (Node Statistics); read-only."""
        if not self.masters:
            raise ValueError("Open a font first.")
        glyphs = self.found_glyphs(self.scope(names, whole_font))
        data = {str(g.name): m.node_cells(g, self.masters) for g in glyphs}
        flagged = [name for name, cells in data.items() if m.counts_differ(cells)]
        records = []
        for name, cells in data.items():
            if only_flagged and name not in flagged:
                continue
            odd = set(m.odd_cells(cells))
            for master in self.masters:
                text = m.cell_text(cells.get(master)) + (ODD if master in odd else "")
                records.append((name, master, (master, text, "✗ differ" if name in flagged else "✓")))
        status = f"{len(flagged)} of {len(data)} glyphs have masters that differ"
        self.say(f"{self.APP}: {status}")
        return Found(records, flagged, status)

    def report(self, kind: str, names: Sequence[str] | None = None) -> str:
        """One of ``REPORTS`` as the originals' literal text; read-only."""
        chosen = self._names(names)
        if kind == "node":
            groups = [(str(g.name), [(str(layer.name), m.paths(layer)) for layer in m.report_masters(g, self.masters)])
                      for g in self.found_glyphs(list(dict.fromkeys(chosen)))]  # fmt: skip
            return m.node_report(groups)
        glyphs = self.found_glyphs(chosen)
        if kind == "why":
            return m.why_report([(str(g.name), [m.why_layer(layer) for layer in m.foreground_layers(g, self.masters)])
                                 for g in glyphs])  # fmt: skip
        if kind == "points":
            return m.point_report([(str(g.name), [(str(layer.name), m.counts(layer))
                                                  for layer in m.stored_foreground(g)]) for g in glyphs])  # fmt: skip
        if kind == "master points":
            return m.master_point_report([(str(layer.name), m.counts(layer)) for g in glyphs
                                          for layer in m.stored_masters(g)])  # fmt: skip
        raise ValueError(f"Unknown report: {kind}")

    def select(self, names: Sequence[str], what: str) -> list[str]:
        """Select ``names`` in the Font window (the originals' select action); no history step."""
        if not names:
            raise ValueError(f"No {what} glyphs to select.")
        selected = self._select_names(self.package(), list(names))
        self.say(f"{self.APP}: Selected {len(selected)} {what} glyphs in the Font window")
        return selected

    # Preview -------------------------------------------------------------------
    def blend(self, name: str, first: str, second: str, percent: int, *, ghost_second: bool = False) -> Overlay | None:
        """Load ``first`` in TGlyph and draw the blend (or the second master) over it; read-only.

        The write master (``self.master``) is left alone: previewing never retargets the Fix tab.
        """
        glyph = self.native_glyph(name)
        layers = m.master_layers(glyph, self.masters)
        a_layer, b_layer = layers.get(first), layers.get(second)
        a = m.outline(a_layer) if a_layer is not None else []
        b = m.outline(b_layer) if b_layer is not None else []
        why = m.problem(a, b)
        overlay = None
        if why is None:
            drawn = b if ghost_second else m.blend(a, b, percent / 100.0)
            closed = _closed(b_layer if ghost_second else a_layer)
            overlay = to_overlay(drawn, closed)
            self.say(f"{name}: {percent} % from {first} to {second} · {sum(len(c) for c in a)} nodes")
        else:
            self.say(f"{name} cannot interpolate between these masters: {why}")
        if self.preview is not None:
            if a_layer is not None:
                self.preview.load(name, first)
            self.preview.set_overlay(overlay)
        return overlay

    def clear_overlay(self) -> None:
        if self.preview is not None:
            self.preview.set_overlay(None)

    # Make Compatible ---------------------------------------------------------
    @sharing.sharing_operation()  # one component-user count per planning pass
    def plan_compatible(self, names: Sequence[str] | None = None, *, all_masters: bool = True,
                        allow_hinted: bool = False) -> list[Fix]:  # fmt: skip
        """Plan Make Compatible on the chosen masters (read-only)."""
        chosen, targets = self._names(names), self.targets(all_masters)
        fixes = []
        for name in chosen:
            self.native_glyph(name)
            layers = {master: self.layer(name, master) for master in self.masters}
            for master in targets:
                layer = layers[master]
                if layer is None:
                    fixes.append(Fix(name, master, None, (), MISSING_NOTE))
                    continue
                if layer.autoLayer:
                    fixes.append(Fix(name, master, None, (), AUTO_NOTE))
                    continue
                try:
                    changes = tuple(m.glyph_changes(master, layers, self.masters, m.shape_notes))
                except ERRORS as error:
                    fixes.append(Fix(name, master, layer, (), f"skipped: {error}"))
                    continue
                note = ""
                if any(c.edit is not None for c in changes) and not allow_hinted:
                    hinted = fontui.layer_is_hinted(layer)
                    note = hinted.text() + HINT_NOTE if hinted else ""
                fixes.append(Fix(name, master, layer, changes, note))
        self.fixes = fixes
        return fixes

    def make_compatible(self, names: Sequence[str] | None = None, *, all_masters: bool = True,
                        allow_hinted: bool = False, allow_bases: bool = False) -> bool:  # fmt: skip
        """Promote lines to cubics on the planned layers as one Undo step; False when refused."""
        app = self.APP
        try:
            fixes = self.plan_compatible(names, all_masters=all_masters, allow_hinted=allow_hinted)
        except ERRORS as error:
            self.say(f"{app}: {error}")
            return False
        pending = [fix for fix in fixes if fix.edits and not fix.note]
        skipped = sorted({f"{fix.glyph} ({fix.master}): {fix.note}" for fix in fixes if fix.note})
        if not pending:
            self.say(f"{app}: no change." + (" Skipped: " + "; ".join(skipped) if skipped else ""))
            return False
        label = f"{app}: {ACTION} {subject([fix.glyph for fix in pending])}"
        layers = [fix.layer for fix in pending]
        glyphs = list({fix.glyph: self.native_glyph(fix.glyph) for fix in pending}.values())

        def mutate() -> None:
            for fix in pending:
                m.write_compatible(fix.edits)

        def read_back() -> list[str]:
            return [str(fix.layer.name) for fix in pending for contour, _ends, count in fix.edits
                    if int(contour.nodesCount) != count]  # fmt: skip

        try:
            committed = self.shell.history(label, glyphs, mutate, layers=layers, read_back=read_back,
                                           allow_bases=allow_bases)  # fmt: skip
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
            self.say(f"{label}." + (" Skipped: " + "; ".join(skipped) if skipped else ""))
        if self.preview is not None:
            self.preview.set_overlay(None)
            self.preview.refresh()
        self._refresh()
        return not mismatches


def first_mismatch(sigs: dict[str, tuple | None], master: str) -> tuple:
    """TGlyph ``(contour, index)`` keys of the first contour of ``master`` that differs from the others."""
    mine = sigs.get(master)
    others = [sig[0] for other, sig in sigs.items() if other != master and sig is not None]
    if mine is None or not others:
        return ()
    common = m.most_common(others)
    for index, pattern in enumerate(mine[0]):
        if index >= len(common) or pattern != common[index]:
            return tuple((index, j) for j in range(len(pattern)))
    return ()


def _closed(layer: Any) -> list[bool]:
    if layer is None:  # no layer on the drawn master: nothing to draw, as in the original
        return []
    return [bool(contour.closed) for shape in layer.shapes for contour in shape.contours]


def to_overlay(contours: m.Outline, closed: Sequence[bool]) -> Overlay:
    return Overlay(tuple(OverlayContour(tuple(OverlayPoint(x, y, "line" if on else None, False) for x, y, on in c),
                                        closed[i] if i < len(closed) else True)
                         for i, c in enumerate(contours)))  # fmt: skip


class OverlayCloser:
    """Clears the ghost when the AppShell closes (``shell.children``)."""

    def __init__(self, studio: Doctor) -> None:
        self.studio = studio

    def close(self) -> None:
        try:
            self.studio.clear_overlay()
        except ERRORS:
            pass
