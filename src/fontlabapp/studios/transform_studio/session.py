# this_file: src/fontlabapp/studios/transform_studio/session.py
# SPDX-License-Identifier: Apache-2.0
"""Studio state shared by Transform Studio and Align & Nudge: reads, plans, ghost and one-step writes.

What: ``Studio`` keeps the glyph list, the preview master and the last plan.
``plan`` reads each named glyph's explicit layer on the chosen masters
(``flGlyph.findLayer``; never ``fgGlyph``), snapshots it with
``native.snapshot`` and runs ``planner(name, master, snapshot)``. Missing,
auto, planner-noted and hinted layers are skipped with a note; hinted layers
are written only when the user ticks "Edit hinted layers anyway" or runs
"Remove PostScript hints" (``fontui.remove_hints``). ``ghost`` simulates the
plan for the preview glyph and draws it with ``preview.set_overlay``.
``apply`` writes every pending layer through ``AppShell.history`` as one
``"<App>: <action> <subject>"`` Undo step on those explicit layers, then reads
every layer back with ``geometry.verify``; a difference is reported as
"Partly applied", never as success.
Why: Contract §1.3/§1.4. Read-only paths (``plan``, ``ghost``) never open
history. ``APP`` is a class attribute so ``fontlabapp.studios.align_nudge``
reuses this class with its own name and labels.
"""

from collections.abc import Callable, Sequence
from typing import Any, NamedTuple

import fontlabapp.fontui as fontui
from fontlabapp.core import sharing
from fontlabapp.studios._kerning_ui import get

from . import APP, geometry, native
from .geometry import Change

NO_FONT = "Open a font first."
NO_GLYPHS = "Choose glyphs first: type names or use the font selection."
MISSING_NOTE = "no layer in this master"
AUTO_NOTE = "auto layer, skipped"
HINT_NOTE = " Tick Edit hinted layers anyway or use Remove PostScript hints first."
ROUNDING_NOTE = "Check Preferences > Rounding."
ERRORS = (ValueError, KeyError, TypeError, IndexError, RuntimeError, ZeroDivisionError)
Planner = Callable[[str, str, geometry.Layer], "list[Change] | str"]


class Row(NamedTuple):
    """One glyph layer of a plan: its snapshot, its changes and a skip note."""

    glyph: str
    master: str
    snap: geometry.Layer | None
    changes: tuple[Change, ...]
    note: str

    @property
    def steps(self) -> tuple:
        return tuple(
            step for change in self.changes if change.edit for step in change.edit
        )

    @property
    def blocked(self) -> bool:
        return any(change.problem for change in self.changes)


def _selection() -> list[str]:
    from fontlabapp.core.scripting import names_selected_names

    return names_selected_names()


def _metrics(package: Any, master: str) -> Any:
    import fontlab

    return fontlab.FontMetrics(package, master)


class Studio:
    """Shared state of one studio window; tabs subscribe with ``views``."""

    APP = APP

    def __init__(self, shell: Any, *, font: Callable[[], Any] | None = None,
                 selection: Callable[[], list[str]] | None = None,
                 metrics: Callable[[Any, str], Any] | None = None) -> None:  # fmt: skip
        self.shell = shell
        self._font = font or fontui.current_font
        self._selection = selection or _selection
        self._metrics = metrics or _metrics
        self.masters: list[str] = []
        self.current: str | None = None
        self.master: str | None = None
        self.glyphs: list[str] = []
        self.rows: list[Row] = []
        self.views: list[Callable[[], None]] = []
        self.preview: Any = None
        self.status = ""

    def say(self, text: str) -> None:
        self.status = text
        self.shell.set_status(text)

    # Reads -----------------------------------------------------------------
    def font(self) -> Any:
        return self._font()

    def reload(self) -> None:
        """Re-read the masters (no writes), then refresh every view."""
        package = self.shell.package()
        if package is None:
            self.masters, self.current = [], None
            self.say(NO_FONT)
        else:
            self.masters = [str(name) for name in package.masters]
            self.current = str(package.master)
        if self.master not in self.masters:
            self.master = self.current
        self._refresh()

    def choose_master(self, name: str | None) -> None:
        self.master = name
        self.show_glyph(self.glyphs[0] if self.glyphs else None)

    def show_glyph(self, name: str | None) -> None:
        """Load ``name`` on the chosen master in the TGlyph preview and clear the ghost (read-only)."""
        if self.preview is not None and name and self.master:
            self.preview.load(name, self.master)
            self.preview.set_overlay(None)

    def set_glyphs(self, names: Sequence[str]) -> None:
        self.glyphs = list(dict.fromkeys(n for n in names if n))

    def use_selection(self) -> list[str]:
        self.set_glyphs(self._selection())
        return self.glyphs

    def package(self) -> Any:
        package = self.shell.package()
        if package is None:
            raise ValueError(NO_FONT)
        return package

    def native_glyph(self, name: str) -> Any:
        glyph = self.package().findName(name)
        if glyph is None or getattr(glyph, "isNull", False):
            raise ValueError(f"Glyph {name} is not in the font.")
        return glyph

    def layer(self, name: str, master: str) -> Any:
        """The live layer of ``name`` on ``master``, or None."""
        layer = self.native_glyph(name).findLayer(master)
        return None if layer is None or getattr(layer, "isNull", False) else layer

    def targets(self, all_masters: bool) -> list[str]:
        if not self.masters or self.master is None:
            raise ValueError(NO_FONT)
        return list(self.masters) if all_masters else [self.master]

    def _names(self, names: Sequence[str] | None) -> list[str]:
        chosen = list(names) if names is not None else list(self.glyphs)
        if not chosen:
            raise ValueError(NO_GLYPHS)
        return chosen

    def x_height(self, master: str) -> float:
        return float(self._metrics(self.package(), master).xHeight)

    def italic_angle(self) -> float:
        """The current master's italic angle (``package.italicAngle_value``)."""
        return float(getattr(self.package(), "italicAngle_value", 0) or 0)

    def italic_angles(self, masters: Sequence[str]) -> dict[str, float]:
        """{master: italic angle}; switches the current master briefly and always restores it."""
        package = self.package()
        current, angles = package.master, {}
        try:
            for master in masters:
                if package.master != master:
                    package.setMaster(master)
                angles[master] = float(package.italicAngle_value)
        finally:
            if package.master != current:
                package.setMaster(current)
        return angles

    def snapshot(self, name: str, master: str) -> geometry.Layer | None:
        layer = self.layer(name, master)
        return None if layer is None else native.snapshot(layer)

    # Planning (read-only) ----------------------------------------------------
    @sharing.sharing_operation()  # one component-user count per planning pass
    def plan(self, planner: Planner, names: Sequence[str] | None = None, *, all_masters: bool = False,
             masters: Sequence[str] | None = None, allow_hinted: bool = False) -> list[Row]:  # fmt: skip
        """Plan ``planner(name, master, snapshot)`` for each glyph layer; skipped layers carry a note."""
        chosen = self._names(names)
        targets = list(masters) if masters is not None else self.targets(all_masters)
        rows = []
        for name in chosen:
            self.native_glyph(name)
            for master in targets:
                layer = self.layer(name, master)
                if layer is None:
                    rows.append(Row(name, master, None, (), MISSING_NOTE))
                    continue
                if layer.autoLayer:
                    rows.append(Row(name, master, None, (), AUTO_NOTE))
                    continue
                snap = native.snapshot(layer)
                result = planner(name, master, snap)
                if isinstance(result, str):
                    rows.append(Row(name, master, snap, (), result))
                    continue
                note = ""
                if any(change.edit for change in result) and not allow_hinted:
                    hinted = fontui.layer_is_hinted(layer)
                    note = hinted.text() + HINT_NOTE if hinted else ""
                rows.append(Row(name, master, snap, tuple(result), note))
        self.rows = rows
        return rows

    def ghost(self, rows: Sequence[Row]) -> geometry.Overlay | None:
        """Draw the planned outline of the previewed glyph on the preview master; None when there is none."""
        shown = self.glyphs[0] if self.glyphs else None
        for row in rows:
            if (
                row.glyph == shown
                and row.master == self.master
                and row.snap is not None
                and row.steps
            ):
                overlay = geometry.ghost(geometry.simulate(row.snap, row.steps))
                if self.preview is not None:
                    self.preview.set_overlay(overlay)
                return overlay
        if self.preview is not None:
            self.preview.set_overlay(None)
        return None

    # Writes ----------------------------------------------------------------
    def apply(self, action: str, planner: Planner, names: Sequence[str] | None = None, *, all_masters: bool = False,
              masters: Sequence[str] | None = None, allow_bases: bool = False, allow_hinted: bool = False) -> bool:  # fmt: skip
        """Plan, then write every changed layer as one ``"<App>: <action> <subject>"`` step."""
        app = self.APP
        try:
            rows = self.plan(
                planner,
                names,
                all_masters=all_masters,
                masters=masters,
                allow_hinted=allow_hinted,
            )
        except ERRORS as error:
            self.say(f"{app}: {error}")
            return False
        blocked = [row for row in rows if row.blocked]
        if blocked:
            first = next(
                change.problem for change in blocked[0].changes if change.problem
            )
            self.say(
                f"{app}: refused. {blocked[0].glyph} ({blocked[0].master}): {first}"
            )
            self._refresh()
            return False
        pending = [row for row in rows if row.steps and not row.note]
        skipped = [
            f"{row.glyph} ({row.master}): {row.note}"
            for row in rows
            if row.note and row.steps
        ]
        if not pending:
            self.say(
                f"{app}: no change."
                + (" Skipped: " + " ".join(skipped) if skipped else "")
            )
            self._refresh()
            return False
        label = f"{app}: {action} {geometry.subject([row.glyph for row in pending])}"
        try:
            layers = [self.layer(row.glyph, row.master) for row in pending]
            glyphs = list(
                {row.glyph: self.native_glyph(row.glyph) for row in pending}.values()
            )
            expected = [geometry.simulate(row.snap, row.steps) for row in pending]  # type: ignore[arg-type]
        except ERRORS as error:
            self.say(f"{app}: {error}")
            return False

        def mutate() -> None:
            for row, layer in zip(pending, layers):
                native.write(layer, row.steps)

        def read_back() -> list[str]:
            problems = []
            for row, layer, want in zip(pending, layers, expected):
                problems += geometry.verify(
                    f"{row.glyph} ({row.master})",
                    want,
                    native.snapshot(layer),
                    row.steps,
                )
            return problems

        committed = self.shell.history(
            label,
            glyphs,
            mutate,
            layers=layers,
            read_back=read_back,
            allow_bases=allow_bases,
        )
        if committed is None:
            self._refresh()
            return False
        mismatches = list(getattr(committed, "mismatches", ()) or ())
        if mismatches:
            self.say(
                f"Partly applied: {label}. "
                + "; ".join(mismatches)
                + f". Native changes may remain; use Edit > Undo. {ROUNDING_NOTE}"
            )
        elif skipped:
            self.say(f"{self.shell_status()} Skipped: " + " ".join(skipped))
        if self.preview is not None:
            self.preview.set_overlay(None)
            self.preview.refresh()
        self._refresh()
        return not mismatches

    def shell_status(self) -> str:
        status = getattr(self.shell, "status", None)
        return str(get(status.text)) if hasattr(status, "text") else self.status

    def _refresh(self) -> None:
        for view in list(self.views):
            view()

    def remove_hints(
        self, names: Sequence[str] | None = None, *, all_masters: bool = False
    ) -> int:
        """Remove PostScript hints from the chosen layers: one ``"<App>: remove hints <glyph>"`` step each."""
        app = self.APP
        try:
            chosen, targets = self._names(names), self.targets(all_masters)
            removed = 0
            for name in chosen:
                glyph = self.native_glyph(name)
                for master in targets:
                    layer = self.layer(name, master)
                    if layer is None or not fontui.layer_is_hinted(layer).ps_hints:
                        continue
                    state = fontui.remove_hints(
                        layer,
                        f"{app}: remove hints {name}",
                        glyph=glyph,
                        commit=self._commit,
                    )
                    removed += 0 if state.ps_hints else 1
        except ERRORS as error:
            self.say(f"{app}: {error}")
            return 0
        if not removed:
            self.say(f"{app}: no PostScript hints removed.")
        self._refresh()
        return removed

    def _commit(
        self,
        label: str,
        layers: list[Any],
        glyphs: list[Any],
        mutate: Any,
        read_back: Any,
    ) -> Any:
        return self.shell.history(
            label, glyphs, mutate, layers=layers, read_back=read_back
        )
