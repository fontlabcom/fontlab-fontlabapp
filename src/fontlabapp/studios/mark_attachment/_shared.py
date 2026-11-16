# this_file: src/fontlabapp/studios/mark_attachment/_shared.py
# SPDX-License-Identifier: Apache-2.0
"""Mark Attachment shared pieces: reused backends, the dry run, one labelled Apply and the planned-layer tab base.

The originals' plans (``components.writer`` / ``anchors.writer`` ``collect``
over explicit layers) are kept. Their apply step is replaced by
``AppShell.history`` over exactly the planned layers: ``prepare`` before
history, ``write`` inside it and the original read-back after it, one
``Mark Attachment: <action> <subject>`` Undo step. Auto layers are skipped,
and, as in the originals, a glyph that owns auto layers or is a base of
one is refused outright (``blocked_rows`` and ``require_safe``).
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from PythonQt import QtGui

from fontlabapp.core.scripting import mark_attachment_backends

from .._kerning import NO_FONT, Tool
from .._kerning_ui import Panel, button, get
from .._kerning_ui import label as text_label

APP = "Mark Attachment"
STALE = "The glyphs changed since the dry run; press Refresh."
ROUNDING_NOTE = "Check Preferences > Rounding."
MAX_ROWS = 400
SHOWN_NAMES = 8
COLUMNS = ["Glyph", "Master", "Item", "Current", "New"]


def backends() -> Any:
    """``core.scripting.mark_attachment_backends()`` (tests replace it)."""
    return mark_attachment_backends()


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
    """``Mark Attachment: <action> <subject>``."""
    return f"{APP}: {action} {subject(names)}"


def plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def find_glyphs(package: Any, names: Iterable[str]) -> list[Any]:
    """The existing glyphs of ``names`` in ``package``, in order."""
    found = (package.findName(name) for name in names)
    return [glyph for glyph in found if glyph is not None and not glyph.isNull]


@dataclass
class Dry:
    """One dry run: exactly the ``work`` Apply writes, the shown rows and why Apply is off."""

    work: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    problem: str = ""
    shown: tuple = ()

    @property
    def edits(self) -> int:
        return sum(len(edits) for _, _, edits in self.work)


def dry_run(
    writer: Any,
    package: Any,
    glyphs: list[Any],
    masters: list[str],
    planner: Callable[..., Any],
) -> Dry:
    """Plan once with ``writer.collect`` (the original's plan) and decide whether Apply may run."""
    history = backends().history
    plan = writer.collect(glyphs, masters, planner)
    facts = history.scan_auto_facts(package)
    problem = plan.problems[0] if plan.problems else ""
    if plan.work:  # the originals' refresh: blocked rows first, then require_safe
        plan.rows[:0] = writer.blocked_rows(plan.work, facts)
        if not problem:
            try:
                writer.require_safe(plan.work, facts)
            except ValueError as error:
                problem = str(error)
    rows = []
    for text, change in plan.rows:
        name, _, master = text.partition(" · ")
        rows.append(
            (
                name,
                master or None,
                (change.name, change.old, change.problem or change.new),
            )
        )
    shown = (
        tuple((g.name, str(layer.name), tuple(edits)) for g, layer, edits in plan.work),
        tuple(map(str, rows)),
    )
    return Dry(
        plan.work,
        rows,
        plan.skipped,
        problem,
        shown,
    )


def apply(
    tool: Tool, action: str, dry: Dry, replan: Callable[[], Dry | None], edit: Any
) -> bool:
    """Write exactly the edits of ``dry`` as one named Undo step through ``tool.shell.history``.

    ``edit`` has ``prepare(layer, edits)``, ``write(layer, steps)`` and
    ``check(prepared, before)`` (the original writer's read-back). A live plan
    that differs from ``dry`` raises ``ValueError(STALE)`` before any write.
    Return True when FontLab committed; a refusal stays in the status line.
    """
    if not dry.work:
        raise ValueError("Nothing to change.")
    if dry.problem:
        raise ValueError(dry.problem)
    live = replan() if tool.package is not None else None
    if live is None or live.shown != dry.shown or live.problem:
        raise ValueError(STALE)
    work = live.work
    title = label(action, (glyph.name for glyph, _, _ in work))
    glyphs = list({glyph.name: glyph for glyph, _, _ in work}.values())
    layers = [layer for _, layer, _ in work]
    before = edit.before(work)
    prepared = [(layer, edit.prepare(layer, edits)) for _, layer, edits in work]

    def mutate() -> None:
        for layer, steps in prepared:
            edit.write(layer, steps)

    committed = tool.shell.history(title, glyphs, mutate, layers=layers,
                                   read_back=lambda: edit.check(work, prepared, before))  # fmt: skip
    if committed is None:
        return False
    if committed.mismatches:
        tool.say(
            f"Partly applied: {title}. "
            + "; ".join(committed.mismatches)
            + f". {ROUNDING_NOTE}"
        )
        return True
    note = f" · {plural(len(dry.skipped), 'auto layer')} skipped" if dry.skipped else ""
    note += f" · {committed.pending_note}" if committed.pending_note else ""
    tool.say(
        f"{title}. {edit.done} {plural(live.edits, edit.noun)} on {plural(len(work), 'layer')}{note}"
    )
    return True


class MoveEdit:
    """Align By Anchor's component offsets: ``components.writer.MoveEditor`` steps and read-back."""

    done, noun = "Moved", "component"

    def __init__(self) -> None:
        self.editor = backends().components.MoveEditor()

    def before(self, work: list) -> None:
        return None

    def prepare(self, layer: Any, edits: list) -> Any:
        return self.editor.prepare(layer, edits)

    def write(self, layer: Any, steps: Any) -> None:
        self.editor.write(layer, steps)
        backends().components.settle(layer)

    def check(self, work: list, prepared: list, before: Any) -> list[str]:
        return self.editor.check(prepared)


class AnchorEdit:
    """Add Anchors' new pins: ``anchors.writer`` prepare/write and ``unstored`` read-back."""

    done, noun = "Added", "anchor"

    def before(self, work: list) -> list:
        writer = backends().anchors
        return [writer.anchor_points(layer) for _, layer, _ in work]

    def prepare(self, layer: Any, edits: list) -> Any:
        return backends().anchors.prepare(layer, edits)

    def write(self, layer: Any, steps: Any) -> None:
        backends().anchors.write(layer, steps)

    def check(self, work: list, prepared: list, before: list) -> list[str]:
        return backends().anchors.unstored(work, before)


class PlanPanel(Panel):
    """A planned layer edit: subclasses set ``ACTION``/``UNDO``/``WRITER`` and the hooks."""

    ACTION = "Apply"
    UNDO = ""
    #: ``backends()`` attribute of the original's writer: "components" or "anchors".
    WRITER = ""

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.ready = False  # option slots fire while the controls are built
        form = QtGui.QVBoxLayout()
        self.layout.addLayout(form)
        self.form = form
        self.build_controls(form)
        self.grid = self.table(list(COLUMNS), self.row_chosen)
        self.count = text_label(self.widget, self.layout)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        self.add_buttons(buttons)
        button(self.widget, buttons, "Refresh", tool.reload)
        self.apply_button = button(self.widget, buttons, self.ACTION, self.apply)
        self.dry = Dry()
        self.glyphs: list[Any] = []
        self.ready = True

    # hooks -------------------------------------------------------------------
    def build_controls(self, form: Any) -> None:  # pragma: no cover - overridden
        pass

    def add_buttons(self, buttons: Any) -> None:
        pass

    def planner(
        self, glyphs: list[Any], masters: list[str]
    ) -> Callable[..., list[Any]]:  # pragma: no cover
        raise NotImplementedError

    def masters(self) -> list[str]:
        return [self.tool.current] if self.tool.current else []

    def editor(self) -> Any:  # pragma: no cover - overridden
        raise NotImplementedError

    def summary(self) -> str:
        dry = self.dry
        return f"{plural(dry.edits, 'change')} on {plural(len(dry.work), 'layer')}"

    # plan --------------------------------------------------------------------
    def clear(self) -> None:
        self.dry = Dry()
        self.glyphs = []
        self.grid.set_rows([])
        self.count.setText("")
        self.apply_button.setEnabled(False)

    def plan(self) -> Dry | None:
        tool = self.tool
        if tool.package is None:
            self.subtitle.setText(NO_FONT)
            return None
        glyphs = find_glyphs(tool.package, tool.selected_names())
        if not glyphs:
            self.subtitle.setText(
                "Select glyphs in the Font window, then press Refresh."
            )
            return None
        masters = self.masters()
        planner = self.planner(glyphs, masters)
        self.glyphs = glyphs
        return dry_run(
            getattr(backends(), self.WRITER), tool.package, glyphs, masters, planner
        )

    def intro(self) -> str:
        count = len(self.glyphs)
        names = ", ".join(g.name for g in self.glyphs[:SHOWN_NAMES]) + (
            " …" if count > SHOWN_NAMES else ""
        )
        return f"{plural(count, 'glyph')}: {names}"

    def refresh(self) -> None:
        if not self.ready:
            return
        self.clear()
        dry = self.plan()
        if dry is None:
            return
        self.dry = dry
        self.subtitle.setText(self.intro())
        self.grid.set_rows(dry.rows[:MAX_ROWS])
        self.sync()

    def sync(self, *args: Any) -> None:
        """Enable Apply only for a non-empty plan that is not refused; say why in the count line."""
        dry = self.dry
        self.apply_button.setEnabled(bool(dry.work) and not dry.problem)
        text = self.summary() if dry.work else "Nothing to change"
        if dry.skipped:
            text += f" · {plural(len(dry.skipped), 'auto layer')} skipped"
        if len(dry.rows) > MAX_ROWS:
            text += f" · table shows the first {MAX_ROWS}"
        if dry.problem:
            text = f"Refused. {dry.problem}"
        self.count.setText(text)

    def row_chosen(self, name: str, master: Any) -> None:
        """Show the row's glyph on its master in the TMetrics preview."""
        preview = self.tool.preview
        if preview is not None and name:
            preview.set_text(f"/{name}")
            if master:
                preview.set_layer(master)

    def apply(self) -> bool:
        """Write the shown plan as one Undo step, then re-read every tab."""
        dry = self.dry

        def write() -> bool:
            done = apply(self.tool, self.UNDO, dry, self.plan, self.editor())
            status = self.tool.status if done else get(self.tool.shell.status.text)
            self.tool.reload()
            self.tool.say(status)
            return done

        return bool(self.run(write))


__all__ = [
    "APP", "COLUMNS", "MAX_ROWS", "STALE", "AnchorEdit", "Dry", "Modules", "MoveEdit",
    "PlanPanel", "apply", "backends", "dry_run", "find_glyphs", "label", "plural", "subject",
]  # fmt: skip
