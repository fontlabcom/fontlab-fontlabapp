# this_file: src/fontlabapp/studios/advance_widths/_layers.py
# SPDX-License-Identifier: Apache-2.0
"""The dry-run-then-Apply tab of Advance Widths (Round & scale, Tabular, Marks).

What: ``LayerPanel`` shows the master scope of the originals' metrics
panels, the tab's own controls and a ``GlyphTable`` of exactly the layers
Apply changes (real glyph and master per row, skip notes kept). Refresh
re-reads the selection, plans once and stores that snapshot; Apply writes
exactly the shown pending layers through ``widths.apply`` (refused as stale
when a layer changed in between). The "Edit bases of auto glyphs anyway"
tick is off by default, shown only with a rebuild note, and resets whenever
the planned glyph set changes. Used by the Advance Widths tab modules.
"""

from typing import Any

from PythonQt import QtGui

from .._kerning import Tool
from .._kerning_ui import Panel, button, check, get, label
from . import widths

MAX_ROWS = widths.metrics_panel.MAX_ROWS
SHOWN_NAMES = widths.metrics_panel.MAX_NAMES


def show_glyph(tool: Tool, name: str, master: Any) -> None:
    """Preview ``name`` on ``master`` in the read-only TMetrics."""
    if tool.preview is None or not name:
        return
    tool.preview.set_text(f"/{name}")
    if master:
        tool.preview.set_layer(master)


class LayerPanel(Panel):
    """A planned layer edit; subclasses set ``MODES`` and fill in the hooks."""

    ACTION = "Apply"
    #: (mode key, Undo action, column headers after "Glyph" and "Master").
    MODES: tuple[tuple[str, str, tuple[str, ...]], ...] = ()

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        form = QtGui.QVBoxLayout()
        self.layout.addLayout(form)
        self.scope = self.scope_box(form, plain=True)
        self.build_controls(form)
        self.grids = {key: self.table(["Glyph", "Master", *headers], self.row_chosen) for key, _, headers in self.MODES}
        self.count = label(self.widget, self.layout)
        self.allow = check(self.widget, self.layout, widths.metrics_panel.ALLOW_AUTO_LABEL, False, self.sync)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        button(self.widget, buttons, "Refresh", tool.reload)
        self.apply_button = button(self.widget, buttons, self.ACTION, self.apply)
        self.entries: list[Any] = []
        self.work: list[Any] = []
        self.shown: tuple = ()
        self.note = ""
        self.override_for: frozenset[str] = frozenset()
        self.show_mode()

    # hooks -------------------------------------------------------------------
    def build_controls(self, form: Any) -> None:  # pragma: no cover - overridden
        pass

    def mode(self) -> str:
        return self.MODES[0][0]

    def planner(self, glyphs: list[Any], masters: list[str]) -> Any:  # pragma: no cover - overridden
        raise NotImplementedError

    def hint(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    def target_glyphs(self) -> list[Any]:
        """The Font window selection (the originals' default glyph source)."""
        return widths.find_glyphs(self.tool.package, self.tool.selected_names())

    def empty_message(self) -> str:
        return "Select glyphs in the Font window, then press Refresh."

    # state -------------------------------------------------------------------
    def undo_action(self) -> str:
        return next(action for key, action, _ in self.MODES if key == self.mode())

    def show_mode(self) -> None:
        for key, grid in self.grids.items():
            grid.widget.setVisible(key == self.mode())

    def clear(self) -> None:
        self.entries, self.work, self.shown, self.note = [], [], (), ""
        for grid in self.grids.values():
            grid.set_rows([])
        self.count.setText("")
        self.sync()

    def refresh(self) -> None:
        tool = self.tool
        self.show_mode()
        self.clear()
        self.fill_scope(self.scope)
        if tool.package is None:
            self.subtitle.setText("Open a font first.")
            return
        glyphs = self.target_glyphs()
        if not glyphs:
            self.subtitle.setText(self.empty_message())
            return
        masters = tool.scope(get(self.scope.currentIndex) == 1)
        facts = widths.auto_facts(tool.package)
        self.entries = widths.survey(glyphs, masters, self.planner(glyphs, masters), facts)
        self.work = widths.pending(self.entries)
        self.shown = widths.fingerprint(self.work)
        names = frozenset(e.glyph.name for e in self.work)
        self.note = widths.rebuild_note(facts, names)
        if names != self.override_for:
            self.allow.setChecked(False)
            self.override_for = names
        listed = list(dict.fromkeys(g.name for g in glyphs))
        more = " …" if len(listed) > SHOWN_NAMES else ""
        self.subtitle.setText(f"{self.hint()} ({', '.join(listed[:SHOWN_NAMES])}{more})")
        width = len(self.MODES[0][2])
        shown = [e for e in self.entries if e.plan is None or e.plan.changed]
        rows = [(e.glyph.name, e.master, (e.master, *(e.plan.cells if e.plan else (e.note, *[""] * (width - 1)))))
                for e in shown[:MAX_ROWS]]  # fmt: skip
        self.grids[self.mode()].set_rows(rows)
        self.sync()

    def sync(self) -> None:
        """Enable Apply only for a non-empty plan that is not refused; say why in the count line."""
        blocked = bool(self.note) and not get(self.allow.isChecked)
        self.allow.setVisible(bool(self.note))
        self.apply_button.setEnabled(bool(self.work) and not blocked)
        if not self.entries:
            return
        text = f"{widths.plural(len(self.work), 'layer')} will change" if self.work else "Nothing to change"
        if len(self.entries) > MAX_ROWS:
            text += f" · table shows the first {MAX_ROWS}"
        if blocked:
            text = f'Refused. {self.note}. Tick "{widths.metrics_panel.ALLOW_AUTO_LABEL}" to go on.'
        elif self.note:
            text += f" · {self.note}"
        self.count.setText(text)

    def row_chosen(self, name: str, master: Any) -> None:
        show_glyph(self.tool, name, master)

    def apply(self) -> bool:
        """Write the shown plan as one Undo step, then re-read every tab."""
        work, shown = self.work, self.shown
        skipped = widths.metrics_panel.auto_skipped(self.entries)
        allow = bool(get(self.allow.isChecked)) and self.override_for == frozenset(e.glyph.name for e in work)

        def write() -> bool:
            done = widths.apply(self.tool, self.undo_action(), work, shown, allow_bases=allow)
            # A refusal is in the shell status line; keep it (or the result) after the re-read.
            status = self.tool.status if done else get(self.tool.shell.status.text)
            if done and allow and self.note:
                status += f" · {self.note}"
            if skipped:
                status += f" · {skipped} layers skipped (auto)"
            self.tool.reload()
            self.tool.say(status)
            return done

        return bool(self.run(write))


__all__ = ["LayerPanel", "show_glyph"]
