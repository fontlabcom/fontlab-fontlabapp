# this_file: src/fontlabapp/studios/component_studio/_shared.py
# SPDX-License-Identifier: Apache-2.0
"""Component Studio shared pieces: reused backends, the planned-layer tab and one labelled Apply.

The originals' panels (``components.panel`` ``ComponentPanel``) planned with
``components.writer.collect`` over explicit layers and wrote with
``components.writer.apply_work``. Their plans, refusals and texts are kept.
Only the write moves: ``prepare`` before history, ``write`` plus ``settle``
inside ``AppShell.history`` (with the removed components retained, fl#7641),
the original editor's read-back after it, as one
``Component Studio: <action> <subject>`` Undo step over exactly the planned
layers. Apply plans again from live data and refuses when the plan differs
from the one on screen. As in the originals, a glyph that owns auto layers
or is a base of one is refused outright (no opt-in: no original has one).
"""

from collections.abc import Iterable
from typing import Any

from PythonQt import QtGui

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native
from fontlabapp.core.scripting import component_studio_backends

from .._kerning import NO_FONT, Tool
from .._kerning_ui import Panel, button, combo, get, row
from .._kerning_ui import label as text_label

APP = "Component Studio"
STALE = "The glyphs changed since the dry run; press Reload selection."
MAX_ROWS = 400
SHOWN_NAMES = 8


def backends() -> Any:
    """``core.scripting.component_studio_backends()`` (tests replace it)."""
    return component_studio_backends()


class Modules:
    """A module name the verbatim originals read; resolves to one reused backend."""

    def __init__(self, attribute: str) -> None:
        self.attribute = attribute

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        return getattr(getattr(backends(), self.attribute), name)


def subject(names: Iterable[str]) -> str:
    """Undo-label subject: the glyph name, or ``"N glyphs"`` for several."""
    unique = list(dict.fromkeys(names))
    return unique[0] if len(unique) == 1 else f"{len(unique)} glyphs"


def label(action: str, names: Iterable[str]) -> str:
    """``Component Studio: <action> <subject>``."""
    return f"{APP}: {action} {subject(names)}"


def plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def find_glyphs(package: Any, names: Iterable[str]) -> list[Any]:
    """The existing glyphs of ``names`` in ``package``, in order (the originals' scan)."""
    found = (package.findName(name) for name in names)
    return [glyph for glyph in found if glyph is not None]


def fingerprint(plan: Any) -> tuple:
    """What the table shows and what Apply writes, comparable between two plans."""
    rows = tuple((text, c.name, c.old, c.new, c.problem) for text, c in plan.rows)
    work = tuple((g.name, str(layer.name), len(edits)) for g, layer, edits in plan.work)
    return rows, work


def write(tool: Tool, title: str, work: list, editor: Any) -> dict | None:
    """Write ``work`` with ``editor`` as ONE ``tool.shell.history`` step titled ``title``.

    The original ``apply_work`` steps: ``prepare`` before history, ``write``
    and ``settle`` per layer inside it, ``retain`` the removed native
    objects, the editor's ``check`` as read-back. None when refused (the
    status line says why); a read-back gap is reported with the shared
    ``unstored_error`` text.
    """
    settle = backends().components.settle
    glyphs = list({glyph.name: glyph for glyph, _, _ in work}.values())
    layers = [layer for _, layer, _ in work]
    prepared = [(layer, editor.prepare(layer, edits)) for _, layer, edits in work]
    retain = [item for _, steps in prepared for item in editor.retain(steps)]

    def mutate() -> None:
        for layer, steps in prepared:
            editor.write(layer, steps)
            settle(layer)

    committed = tool.shell.history(title, glyphs, mutate, layers=layers, retain=retain,
                                   read_back=lambda: editor.check(prepared))  # fmt: skip
    if committed is None:
        return None
    return {
        "edits": sum(len(edits) for _, _, edits in work),
        "layers": len(work),
        "pending_note": committed.pending_note,
        "mismatches": list(committed.mismatches),
    }


class ComponentPanel(Panel):
    """The originals' component panel as a tab: controls, the dry-run table, Reload selection and Apply.

    Subclasses set ``ACTION``/``DONE``/``HEADERS`` (the original's) and
    ``UNDO`` (the Undo label's action) and fill in the hooks.
    """

    ACTION = "Apply"
    DONE = "Changed"
    RELOAD = "Reload selection"
    UNDO = ""
    HEADERS: tuple[str, ...] = ("Glyph · master", "Component", "Becomes")
    #: The original's master scope default: 0 current master, 1 all masters.
    SCOPE = 0

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.ready = False  # option slots fire while the controls are built
        self.scope: Any = None
        self.scoped = False
        self.package: Any = None
        self.package_id: Any = None
        self.current_master = ""
        self.glyphs: list[Any] = []
        self.facts = history.auto_facts(())
        form = QtGui.QVBoxLayout()
        self.layout.addLayout(form)
        self.form = form
        self.build_controls(form)
        columns = ["Glyph", "Master", *self.HEADERS[1:]]
        self.grid = self.table(columns, self.row_chosen)
        self.count = text_label(self.widget, self.layout)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        self.add_buttons(buttons)
        button(self.widget, buttons, self.RELOAD, self.reloaded)
        self.apply_button = button(self.widget, buttons, self.ACTION, self.apply)
        self.apply_button.setEnabled(False)
        self.plan = backends().components.Plan()
        self.problem = ""
        self.shown: tuple = ((), ())
        self.last_result: dict = {}
        self.ready = True

    # controls ----------------------------------------------------------------
    def scope_box(
        self, layout: Any, *, plain: bool = False, title: str = "Masters"
    ) -> Any:
        """The originals' Masters combo: "Current master (M)" / "All masters (N)"."""
        box = combo(self.widget, [], self.contain(self.replan))
        row(self.widget, layout, title, box)
        self.scope = box
        return box

    def relabel(self) -> None:
        """Keep the scope combo in step with the font; the first fill takes the original's default."""
        box = self.scope
        if box is None:
            return
        index = get(box.currentIndex) if self.scoped else self.SCOPE
        box.blockSignals(True)
        box.clear()
        box.addItem(f"Current master ({self.tool.current})")
        box.addItem(f"All masters ({len(self.tool.masters)})")
        box.setCurrentIndex(max(index, 0))
        box.blockSignals(False)
        self.scoped = True

    def chosen_masters(self) -> list[str]:
        """Masters in scope: the scope combo picks the current master or all."""
        if self.scope is not None and get(self.scope.currentIndex) == 0:
            return [self.current_master] if self.current_master else []
        return list(self.tool.masters)

    # hooks -------------------------------------------------------------------
    def build_controls(self, form: Any) -> None:  # pragma: no cover - overridden
        pass

    def add_buttons(self, buttons: Any) -> None:
        pass

    def reloaded(self) -> None:
        """The Reload selection button: re-read the font and every tab."""
        self.tool.reload()

    def glyph_names(self) -> list[str]:
        """Glyphs the tab works on: the Font window selection."""
        return self.tool.selected_names()

    def on_reload(self) -> None:
        """Refresh control contents that depend on the font."""

    def planner(self) -> Any:  # pragma: no cover - overridden
        raise NotImplementedError

    def editor(self) -> Any:  # pragma: no cover - overridden
        raise NotImplementedError

    def make_plan(self, package: Any, glyphs: list[Any], facts: Any) -> tuple[Any, str]:
        """The original panel's plan: ``collect``, blocked rows first, then ``require_safe``."""
        writer = backends().components
        plan, problem = writer.Plan(), ""
        try:
            plan = writer.collect(glyphs, self.chosen_masters(), self.planner())
        except ValueError as error:
            problem = str(error)
        if plan.problems:
            problem = plan.problems[0]
        if plan.work:
            plan.rows[:0] = writer.blocked_rows(plan.work, facts)
            if not problem:
                try:
                    writer.require_safe(plan.work, facts)
                except ValueError as error:
                    problem = str(error)
        return plan, problem

    def final_plan(self, package: Any, glyphs: list[Any], facts: Any, plan: Any) -> Any:
        """The plan Apply writes; the live plan by default."""
        return plan

    def summary(self, plan: Any) -> str:
        """Status line when Apply is possible, or when nothing is to do."""
        if not plan.rows:
            return "No components to change on the selected glyphs"
        return f"{plural(plan.edits, 'component change')} on {plural(len(plan.work), 'layer')}"

    def done_text(self, result: dict, plan: Any) -> str:
        """The original panel's status after a write."""
        skipped = len(plan.skipped)
        note = f" · {plural(skipped, 'auto layer')} skipped" if skipped else ""
        queued = result.get("pending_note", "")
        note += f" · {queued}" if queued else ""
        return f"{self.DONE} {plural(result['edits'], 'component')} on {plural(result['layers'], 'layer')}{note}"

    def title(self, plan: Any) -> str:
        return label(self.UNDO, (glyph.name for glyph, _, _ in plan.work))

    # read --------------------------------------------------------------------
    def intro(self) -> str:
        """Subtitle text. Names the glyphs, or says what is missing."""
        if self.package is None:
            return NO_FONT
        if not self.glyphs:
            return "Select glyphs in the Font window, then press Reload selection."
        count = len(self.glyphs)
        names = ", ".join(g.name for g in self.glyphs[:SHOWN_NAMES]) + (
            " …" if count > SHOWN_NAMES else ""
        )
        return f"{count} glyph{'s' if count != 1 else ''}: {names}"

    def clear(self) -> None:
        self.plan = backends().components.Plan()
        self.problem = ""
        self.shown = ((), ())
        self.grid.set_rows([])
        self.count.setText("")
        self.apply_button.setEnabled(False)

    def refresh(self) -> None:
        """Reload selection: read font, selection and the auto-composite map again, then plan."""
        if not self.ready:
            return
        self.clear()
        tool = self.tool
        self.package = tool.package
        self.package_id = self.package.id if self.package is not None else None
        self.current_master = tool.current
        self.relabel()
        self.glyphs, self.facts = [], history.auto_facts(())
        if self.package is not None:
            self.glyphs = find_glyphs(self.package, self.glyph_names())
            self.facts = history.scan_auto_facts(self.package)
        self.on_reload()
        self.replan()

    def replan(self) -> None:
        """Recompute the plan from the controls; fill the table; enable Apply only when it is safe."""
        if not self.ready:
            return
        self.subtitle.setText(self.intro())
        plan, problem = backends().components.Plan(), ""
        if self.package is not None and self.glyphs:
            plan, problem = self.make_plan(self.package, self.glyphs, self.facts)
        self.plan, self.problem, self.shown = plan, problem, fingerprint(plan)
        self.fill(plan)
        self.apply_button.setEnabled(bool(plan.work) and not problem)
        self.count.setText(problem or self.status_text(plan))

    def status_text(self, plan: Any) -> str:
        text = self.summary(plan)
        if len(plan.rows) > MAX_ROWS:
            text += f" · table shows the first {MAX_ROWS}"
        return text

    def cells(self, change: Any) -> tuple[str, ...]:
        """Row texts after glyph and master: 3 original columns (component, result) or 4 (with current)."""
        last = change.problem or change.new
        if len(self.HEADERS) == 3:
            return (change.name, last)
        return (change.name, change.old, last)

    def fill(self, plan: Any) -> None:
        rows = []
        for text, change in plan.rows[:MAX_ROWS]:
            name, _, master = text.partition(" · ")
            rows.append((name, master or None, self.cells(change)))
        self.grid.set_rows(rows)

    def row_chosen(self, name: str, master: Any) -> None:
        """Load the row's glyph on its master in the TGlyph preview."""
        if self.tool.preview is not None and name:
            self.tool.preview.load(name, master or None)

    # write -------------------------------------------------------------------
    def live_glyphs(self) -> tuple[Any, list[Any]]:
        """Re-resolve the bound font and the scanned glyphs. ValueError when stale (the originals' texts)."""
        package = self.tool.shell.package()
        if package is None or package.id != self.package_id:
            raise ValueError("The font changed; press Reload selection.")
        if str(package.master) != self.current_master:
            raise ValueError("Master changed; Reload selection.")
        glyphs = [package.findName(glyph.name) for glyph in self.glyphs]
        if any(glyph is None or glyph.isNull for glyph in glyphs):
            raise ValueError("Glyphs changed; Reload selection.")
        return package, glyphs

    def live_plan(self) -> tuple[Any, Any, Any]:
        """Plan again from live data; refuse a refused, empty or changed plan before any write."""
        package, glyphs = self.live_glyphs()
        facts = history.scan_auto_facts(package)
        plan, problem = self.make_plan(package, glyphs, facts)
        if problem:
            raise ValueError(problem)
        if fingerprint(plan) != self.shown:
            raise ValueError(STALE)
        if not plan.work:
            raise ValueError("Nothing to change.")
        return package, facts, self.final_plan(package, glyphs, facts, plan)

    def apply(self) -> bool:
        """Write the shown plan as one Undo step, then re-read every tab."""

        def run() -> bool:
            _, _, plan = self.live_plan()
            title = self.title(plan)
            result = write(self.tool, title, plan.work, self.editor())
            if result is None:
                status = get(self.tool.shell.status.text)
                self.tool.reload()
                self.tool.say(status)
                return False
            self.last_result = result
            if result["mismatches"]:
                text = f"{title}. {history.unstored_error(result['mismatches'])}"
            else:
                text = f"{title}. {self.done_text(result, plan)}"
            self.after_apply()
            self.tool.say(text)
            return True

        return bool(self.run(run))

    def after_apply(self) -> None:
        """Show the new state of the font."""
        self.tool.reload()


__all__ = [
    "APP", "MAX_ROWS", "STALE", "ComponentPanel", "Modules", "backends", "find_glyphs",
    "fingerprint", "label", "plural", "subject", "write",
]  # fmt: skip
