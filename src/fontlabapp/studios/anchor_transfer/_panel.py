# this_file: src/fontlabapp/studios/anchor_transfer/_panel.py
# SPDX-License-Identifier: Apache-2.0
"""The dry-run tab shared by From glyph, Between masters, From components and CSV import.

What: ``AnchorPanel`` plans once on Refresh (or when an option changes)
with ``transfer.dry_run``, lists exactly the anchor edits Apply will write
("Glyph", "Master", "Anchor", "Current", "New"; real glyph and master in
every row, so choosing a row loads it in the TGlyph preview), says why Apply
is off, and on Apply writes the shown plan through ``transfer.apply`` (one
``Anchor Transfer: <action> <subject>`` Undo step; a live plan that differs
from the dry run is refused with "press Refresh"). "Edit bases of auto
glyphs anyway" is off by default and resets whenever the refused glyph set
changes. Used by the tabs of ``fontlabapp.studios.anchor_transfer``.
"""

from collections.abc import Callable
from typing import Any

from PythonQt import QtGui

from .._kerning import Tool
from .._kerning_ui import Panel, button, check, get, label
from . import transfer

#: Rows shown in a table; the count line says when a plan has more.
MAX_ROWS = 400
SHOWN_NAMES = 8
COLUMNS = ["Glyph", "Master", "Anchor", "Current", "New"]


def show_glyph(tool: Tool, name: str, master: Any) -> None:
    """Load ``name`` on ``master`` in the TGlyph preview."""
    if tool.preview is not None and name:
        tool.preview.load(name, master or None)


class AnchorPanel(Panel):
    """A planned anchor edit; subclasses set ``ACTION``/``UNDO`` and fill in the hooks."""

    ACTION = "Apply"
    #: The Undo label's action ("copy anchors", ...).
    UNDO = ""

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.ready = False  # option slots fire while the controls are built
        form = QtGui.QVBoxLayout()
        self.layout.addLayout(form)
        self.build_controls(form)
        self.grid = self.table(list(COLUMNS), self.row_chosen)
        self.count = label(self.widget, self.layout)
        self.allow = check(self.widget, self.layout, transfer.ALLOW_AUTO_LABEL, False, self.sync)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        button(self.widget, buttons, "Refresh", tool.reload)
        self.apply_button = button(self.widget, buttons, self.ACTION, self.apply)
        self.dry = transfer.Dry()
        self.glyphs: list[Any] = []
        self.override_for: frozenset[str] = frozenset()
        self.ready = True

    # hooks -------------------------------------------------------------------
    def build_controls(self, form: Any) -> None:  # pragma: no cover - overridden
        pass

    def target_glyphs(self) -> list[Any]:
        """The Font window selection (the originals' default)."""
        return transfer.find_glyphs(self.tool.package, self.tool.selected_names())

    def masters(self) -> list[str]:  # pragma: no cover - overridden
        raise NotImplementedError

    def planner(self, glyphs: list[Any], masters: list[str]) -> Callable[..., list[Any]]:  # pragma: no cover
        raise NotImplementedError

    def empty_message(self) -> str:
        return "Select glyphs in the Font window, then press Refresh."

    def summary(self) -> str:
        """The count line for a plan with work; subclasses may name their source."""
        return f"{transfer.anchor_writer.plural(self.dry.anchors, 'anchor change')} on " \
               f"{transfer.anchor_writer.plural(len(self.dry.work), 'layer')}"  # fmt: skip

    # state -------------------------------------------------------------------
    def clear(self) -> None:
        self.dry, self.glyphs = transfer.Dry(), []
        self.grid.set_rows([])
        self.count.setText("")
        self.sync()

    def plan(self) -> transfer.Dry | None:
        """One dry run from the live font and the current options; None when there is nothing to plan."""
        tool = self.tool
        if tool.package is None:
            self.subtitle.setText("Open a font first.")
            return None
        glyphs = self.target_glyphs()
        if not glyphs:
            self.subtitle.setText(self.empty_message())
            return None
        masters = self.masters()
        planner = self.planner(glyphs, masters)
        self.glyphs = glyphs
        return transfer.dry_run(glyphs, masters, planner, transfer.auto_facts(tool.package))

    def intro(self) -> str:
        count = len(self.glyphs)
        names = ", ".join(g.name for g in self.glyphs[:SHOWN_NAMES]) + (" …" if count > SHOWN_NAMES else "")
        return f"{count} glyph{'s' if count != 1 else ''}: {names}"

    def refresh(self) -> None:
        if not self.ready:
            return
        self.clear()
        dry = self.plan()
        if dry is None:
            return
        self.dry = dry
        self.subtitle.setText(self.intro())
        if dry.bases != self.override_for:
            self.allow.setChecked(False)
            self.override_for = dry.bases
        self.grid.set_rows(dry.rows[:MAX_ROWS])
        self.sync()

    def sync(self) -> None:
        """Enable Apply only for a non-empty plan that is not refused; say why in the count line."""
        dry = self.dry
        blocked = bool(dry.bases) and not get(self.allow.isChecked)
        self.allow.setVisible(bool(dry.bases))
        self.apply_button.setEnabled(bool(dry.work) and not dry.problem and not blocked)
        if not dry.rows and not dry.problem:
            if self.glyphs:
                self.count.setText("Nothing to change")
            return
        text = self.summary() if dry.work else "Nothing to change"
        if dry.skipped:
            text += f" · {transfer.anchor_writer.plural(len(dry.skipped), 'auto layer')} skipped"
        if len(dry.rows) > MAX_ROWS:
            text += f" · table shows the first {MAX_ROWS}"
        if dry.problem:
            text = f"Refused. {dry.problem}"
        elif blocked:
            text = f'Refused. {dry.note}. Tick "{transfer.ALLOW_AUTO_LABEL}" to go on.'
        elif dry.note:
            text += f" · {dry.note}"
        self.count.setText(text)

    def row_chosen(self, name: str, master: Any) -> None:
        show_glyph(self.tool, name, master)

    def apply(self) -> bool:
        """Write the shown plan as one Undo step, then re-read every tab."""
        dry = self.dry
        allow = bool(get(self.allow.isChecked)) and self.override_for == dry.bases

        def write() -> bool:
            done = transfer.apply(self.tool, self.UNDO, dry, self.plan, allow_bases=allow)
            # A refusal is in the shell status line; keep it (or the result) after the re-read.
            status = self.tool.status if done else get(self.tool.shell.status.text)
            self.tool.reload()
            self.tool.say(status)
            return done

        return bool(self.run(write))


__all__ = ["COLUMNS", "MAX_ROWS", "AnchorPanel", "show_glyph"]
