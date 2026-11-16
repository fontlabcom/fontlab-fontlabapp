# this_file: src/fontlabapp/studios/derived_glyphs/_shared.py
# SPDX-License-Identifier: Apache-2.0
"""Pieces every Derived Glyphs tab shares: backends, the Undo title and the plan panel.

``PlanPanel`` is the host-mode form of the originals' ``SelectionPanel`` /
``CopiesPanel``: controls, a sortable ``GlyphTable`` dry run, the rebuild
consent where the original has one, a status line and one explicit Apply
button. A row choice shows the source (and the target, when it exists) in
the read-only TMetrics preview. Nothing is written on open, on a control
change or on a row choice. Apply scans the font again, re-plans, refuses a
plan that differs from the list on screen (``STALE``), then runs the
original's App writer with ``label(action, names)`` as its title.
"""

from collections.abc import Iterable
from typing import Any

from PythonQt import QtCore, QtGui

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native
from fontlabapp.core.scripting import derived_glyphs_backends

from .._kerning import ERRORS, NO_FONT
from .._kerning_ui import Panel, button, check, label as text_label

APP = "Derived Glyphs"
STALE = "The font changed since the list was made; check the list again."
MAX_ROWS = 500
SHOWN_NAMES = 8


def backends() -> Any:
    """The reused App backends (tests replace this)."""
    return derived_glyphs_backends()


class Modules:
    """A module name the verbatim originals read; resolves to one reused backend."""

    def __init__(self, attribute: str) -> None:
        self.attribute = attribute

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        return getattr(getattr(backends(), self.attribute), name)


class Qt:
    """``fly.qt`` as the originals read it: ``qt.QtGui`` and ``qt.QtCore``."""

    QtCore, QtGui = QtCore, QtGui


def subject(names: Iterable[str]) -> str:
    """Undo-title subject: the glyph name, or ``"N glyphs"`` for several."""
    unique = list(dict.fromkeys(names))
    return unique[0] if len(unique) == 1 else f"{len(unique)} glyphs"


def label(action: str, names: Iterable[str]) -> str:
    """``"Derived Glyphs: <action> <subject>"``."""
    return f"{APP}: {action} {subject(names)}"


def plural(count: int, word: str) -> str:
    """'1 glyph', '2 glyphs'."""
    return f"{count} {word}{'' if count == 1 else 's'}"


def result_note(text: str, result: dict[str, Any]) -> str:
    """The originals' result tail: first five read-back mismatches, then the pending note."""
    if result.get("mismatches"):
        text += " · did not read back as planned: " + "; ".join(
            result["mismatches"][:5]
        )
    note = result.get("pending_note", "")
    return f"{text} · {note}" if note and note not in text else text


class PlanPanel(Panel):
    """Controls, dry-run table, optional consent, status, one Apply button."""

    ACTION = "Apply"
    UNDO = ""
    HEADERS: tuple[str, ...] = ("Source", "New glyph", "Action")
    CONSENT = ""
    SELECTION = True
    NOUN = "glyphs"

    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        self.ready = False
        self.package: Any = None
        self.names: list[str] | None = None
        self.facts: Any = None
        self.rows: list[Any] = []
        self.key: Any = None
        self.masters: list[str] = []
        self.form = QtGui.QVBoxLayout()
        self.layout.addLayout(self.form)
        self.build_controls(self.form)
        self.consent = (
            check(
                self.widget, self.form, self.CONSENT, False, self.contain(self.refresh)
            )
            if self.CONSENT
            else None
        )
        self.grid = self.table(list(self.HEADERS), self.row_chosen)
        self.status = text_label(self.widget, self.layout)
        footer = QtGui.QHBoxLayout()
        self.layout.addLayout(footer)
        if self.SELECTION:
            self.selection_button = button(
                self.widget, footer, "Use selection", self.contain(self.reselect)
            )
        self.add_buttons(footer)
        footer.addStretch(1)
        self.apply_button = button(
            self.widget, footer, self.ACTION, lambda: self.run(self.apply)
        )
        self.apply_button.setEnabled(False)
        self.ready = True

    # ------------------------------------------------------------ hooks
    def build_controls(self, form: Any) -> None:
        """Add the tab's controls to ``form``."""

    def add_buttons(self, footer: Any) -> None:
        """Add extra buttons before the stretch."""

    def plan(self, package: Any, facts: Any) -> list[Any]:
        """Return the original's rows for the live font (no writes)."""
        raise NotImplementedError

    def plan_key(self, package: Any, rows: list[Any]) -> Any:
        """What Apply compares with the list on screen."""
        return (
            package.id,
            tuple(package.masters),
            tuple(self.row_key(row) for row in rows),
        )

    def row_key(self, row: Any) -> Any:
        return (row.source, row.target, row.note, tuple(row.rebuild),
                tuple((str(m), round(float(x.advanceWidth), 3)) for m, x in row.layers))  # fmt: skip

    def is_ready(self, row: Any) -> bool:
        return not row.note

    def cells(self, row: Any) -> tuple[str, str | None, tuple[Any, ...]]:
        """``(glyph, layer, values)`` for one table row."""
        raise NotImplementedError

    def intro(self) -> str:
        names = self.names or []
        shown = ", ".join(names[:SHOWN_NAMES]) + (
            " …" if len(names) > SHOWN_NAMES else ""
        )
        return f"{plural(len(names), 'glyph')}: {shown}" if names else ""

    def pending(self, todo: list[Any]) -> str:
        return f"{plural(len(todo), 'glyph')} to create"

    def write(self, package: Any, rows: list[Any], facts: Any) -> dict[str, Any]:
        raise NotImplementedError

    def result_text(self, result: dict[str, Any]) -> str:
        return "Done"

    def subjects(self, rows: list[Any]) -> list[str]:
        return [row.target for row in rows if self.is_ready(row)]

    def consented(self) -> bool:
        return self.consent is not None and bool(self.consent.isChecked())

    # ------------------------------------------------------------ flow
    def live(self) -> Any:
        package = self.tool.shell.package()
        if package is None:
            raise ValueError(NO_FONT)
        if self.package is not None and package.id != self.package.id:
            raise ValueError("The font changed. Run this script again.")
        return package

    def reselect(self) -> None:
        """Use the Font-window selection; clear the consent, as the originals do."""
        self.names = self.tool.selected_names()
        if self.consent is not None:
            self.consent.blockSignals(True)
            self.consent.setChecked(False)
            self.consent.blockSignals(False)
        self.facts = None
        self.refresh()

    def refresh(self) -> None:
        if not self.ready:
            return
        package = self.tool.shell.package()
        if package is None:
            self.package = None
            self.failed(ValueError(NO_FONT))
            return
        if self.package is None or package.id != self.package.id:
            self.facts = None
            if self.SELECTION:
                self.names = self.tool.selected_names()
        self.package = package
        self.masters = [str(m) for m in package.masters]
        try:
            if self.facts is None:
                self.facts = history.scan_auto_facts(package)
            if self.SELECTION and not self.names:
                raise ValueError(
                    f"Select {self.NOUN} in the Font window. Then press Use selection."
                )
            self.rows = list(self.plan(package, self.facts))
            self.key = self.plan_key(package, self.rows)
        except ERRORS as error:
            self.rows, self.key = [], None
            self.grid.set_rows([])
            self.subtitle.setText(str(error))
            self.status.setText("")
            self.apply_button.setEnabled(False)
            return
        self.subtitle.setText(self.intro())
        self.grid.set_rows([self.cells(row) for row in self.rows[:MAX_ROWS]])
        todo = [row for row in self.rows if self.is_ready(row)]
        more = (
            f" (table shows the first {MAX_ROWS})" if len(self.rows) > MAX_ROWS else ""
        )
        self.status.setText(self.pending(todo) + more)
        self.apply_button.setEnabled(self.can_apply(todo))

    def can_apply(self, todo: list[Any]) -> bool:
        return bool(todo)

    def clear(self) -> None:
        self.rows, self.key = [], None
        self.grid.set_rows([])
        self.status.setText("")
        self.apply_button.setEnabled(False)

    def row_chosen(self, name: str, layer: Any = None) -> None:
        """Show the source and, when it exists already, the target in the preview."""
        preview = self.tool.preview
        if preview is None or self.package is None:
            return
        row = next((r for r in self.rows if self.row_name(r) == name), None)
        names = [name] + [n for n in self.preview_names(row) if n != name]
        preview.set_text(
            "".join(f"/{n}" for n in names if self.package.findName(n) is not None)
        )
        preview.set_layer(self.tool.current or None)

    def row_name(self, row: Any) -> str:
        return row.source

    def preview_names(self, row: Any) -> list[str]:
        return [row.target] if row is not None else []

    def checked_plan(self) -> tuple[Any, Any, list[Any]]:
        """Scan again and re-plan; refuse a plan that is not the one on screen."""
        package = self.live()
        facts = history.scan_auto_facts(package)
        rows = list(self.plan(package, facts))
        if self.key is None or self.plan_key(package, rows) != self.key:
            raise ValueError(STALE)
        return package, facts, rows

    def apply(self) -> bool:
        try:
            package, facts, rows = self.checked_plan()
            result = self.write(package, rows, facts)
        except ERRORS as error:
            self.facts = None
            self.refresh()
            self.say(str(error))
            return False
        self.facts = None
        self.refresh()
        self.say(result_note(self.result_text(result), result))
        return True

    def say(self, text: str) -> None:
        self.status.setText(text)
        self.tool.say(text)


__all__ = [
    "APP",
    "CopiesPanel",
    "MAX_ROWS",
    "Modules",
    "PlanPanel",
    "Qt",
    "STALE",
    "backends",
    "label",
    "plural",
    "result_note",
    "subject",
]


class CopiesPanel(PlanPanel):
    """Host-mode ``CopiesPanel``: one new glyph per selected source, created with Add Glyph.

    ``glyph_copies.create`` creates every planned glyph (each its own FontLab
    Add Glyph step), then fills all outlines as one more step titled
    ``label(UNDO, targets)``.
    """

    ACTION = "Create glyphs"
    HEADERS = ("Source", "New glyph", "Action")

    def __init__(self, tool: Any) -> None:
        self.CONSENT = backends().creation.REBUILD_LABEL
        super().__init__(tool)

    def survey(self, package: Any, facts: Any, allow_rebuild: bool) -> list[Any]:
        raise NotImplementedError

    def jobs(self, rows: list[Any]) -> list[Any]:
        raise NotImplementedError

    def plan(self, package: Any, facts: Any) -> list[Any]:
        return self.survey(package, facts, self.consented())

    def cells(self, row: Any) -> tuple[str, str | None, tuple[Any, ...]]:
        action = row.note or f"create on {len(self.masters)} masters"
        if row.rebuild and not row.note:
            action += " · " + backends().creation.rebuild_note(row.rebuild)
        return (row.source, None, (row.target, action))

    def write(self, package: Any, rows: list[Any], facts: Any) -> dict[str, Any]:
        title = label(self.UNDO, self.subjects(rows))
        return backends().copies.create(
            package, self.jobs(rows), title, facts, allow_rebuild=self.consented()
        )

    def result_text(self, result: dict[str, Any]) -> str:
        if not result["glyphs"]:
            return "Nothing to create"
        return f"Created {plural(result['glyphs'], 'glyph')} ({plural(result['layers'], 'master layer')})"
