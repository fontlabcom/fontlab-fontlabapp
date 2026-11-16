# this_file: src/fontlabapp/studios/derived_glyphs/unicase.py
# SPDX-License-Identifier: Apache-2.0
"""Unicase tab: ``Scripts/Components/Make Lower Unicase.py`` in host mode.

Every uppercase cell whose character has a separate single-character
lowercase shows that lowercase as plain components on every master:
contours, components and anchors are replaced, widths and kerning-class
memberships follow the lowercase. Canonical round-trip lowercase first,
then Unicode and glyph-name order; later mappings stay. Missing capitals
are never created; auto targets and bases of auto glyphs are kept (no
opt-in, as in the original). Press Preview, then Apply; Apply asks for
confirmation and refuses a plan that changed after Preview or during the
question. The writer is the shared component-set writer (``_component_sets``,
``replace_contours=True``); ``survey``, ``mappings`` and ``plan_key`` below
are the original's, verbatim. Credit: Pedro Arilla's idea, after Georg
Seifert's "Make lower-unicase font" (no source code copied).
"""

from typing import Any

import fontlabapp.core.edit_guards as edit_guards

from .._kerning_ui import button
from . import _shared
from ._component_sets import Pair, component_rows, write_components
from ._shared import PlanPanel, label

catalog = _shared.Modules("catalog")
glyph_copies = _shared.Modules("copies")
TITLE = "Make Lower Unicase"


def survey(package: Any) -> list[glyph_copies.Row]:
    """Choose canonical round-trip sources first, then Unicode and glyph-name order.

    For each existing uppercase glyph, the first source wins. Later candidates
    are kept rows. Missing uppercase glyphs and multi-character case mappings
    are kept too; this tool never guesses a capital glyph name.
    """
    records = catalog.capture().rows
    owners: dict[int, list[str]] = {}
    sources = []
    for name, codes, _ in records:
        for text in str(codes).split():
            code = int(text.removeprefix("U+"), 16)
            owners.setdefault(code, []).append(str(name))
            char = chr(code)
            if char.islower() and char.isalpha():
                sources.append((char.upper().lower() != char, code, str(name)))
    rows, chosen = [], set()
    for _, code, source in sorted(set(sources)):
        upper = chr(code).upper()
        if len(upper) != 1:
            rows.append(
                glyph_copies.Row(source, "", note="kept: multi-character uppercase")
            )
            continue
        if upper == chr(code):
            rows.append(
                glyph_copies.Row(source, source, note="kept: no separate uppercase")
            )
            continue
        targets = sorted(owners.get(ord(upper), []))
        if not targets:
            rows.append(
                glyph_copies.Row(source, "", note="kept: no existing uppercase glyph")
            )
            continue
        target = targets[0]
        if target == source or target in chosen:
            rows.append(
                glyph_copies.Row(
                    source, target, note="kept: earlier source has priority"
                )
            )
            continue
        chosen.add(target)
        rows.append(glyph_copies.Row(source, target))
    return rows


def mappings(package: Any) -> list[Pair]:
    """Return only the ready pairs from the ordered, fully listed case survey."""
    return [(row.target, row.source) for row in survey(package) if not row.note]


def plan_key(package: Any, rows: list[glyph_copies.Row]) -> tuple:
    """Bind Preview and confirmation to the font, rows and target shape identities."""
    return (
        int(package.id),
        tuple(str(m) for m in package.masters),
        tuple(
            (
                row.source,
                row.target,
                row.note,
                tuple(
                    (
                        str(layer.name),
                        tuple(int(shape.id) for shape in layer.shapes),
                        len(layer.anchors),
                    )
                    for layer in package.findName(row.target).layers
                )
                if row.target and package.findName(row.target) is not None
                else (),
            )
            for row in rows
        ),
    )


def apply_pairs(
    package: Any,
    pairs: list[Pair],
    *,
    title: str = TITLE,
    replace_contours: bool = True,
    clear_anchors: bool = True,
    allow_rebuild: bool = False,
    unicodes: dict[str, tuple[int, ...]] | None = None,
    kept: list[str] | None = None,
    report: list[str] | None = None,
    disclosure: dict[str, Any] | None = None,
) -> int:
    """The original's ``apply_pairs``: the shared writer with its Unicase defaults."""
    return write_components(
        package, pairs, title=title, replace_contours=replace_contours, clear_anchors=clear_anchors,
        allow_rebuild=allow_rebuild, unicodes=unicodes, kept=kept, report=report, disclosure=disclosure,
    )  # fmt: skip


def confirm(parent: Any, message: str) -> bool:
    """Ask Yes/No (default No) with the original's standard question box (tests replace this)."""
    qt = _shared.Qt
    box = qt.QtGui.QMessageBox
    answer = _shared.backends().dialogs.run_standard_message_box(
        qt, parent, TITLE, message, "Question",
        box.StandardButtons(box.Yes | box.No), box.No,
    )  # fmt: skip
    return answer == box.Yes


class UnicasePanel(PlanPanel):
    """Preview, dry run, Apply with confirmation."""

    ACTION = "Apply to uppercase"
    UNDO = "make unicase"
    HEADERS = ("Lowercase source", "Uppercase target", "Action")
    SELECTION = False

    def __init__(self, tool: Any) -> None:
        self.preview_key: Any = None
        self.last_result: dict[str, Any] = {}
        super().__init__(tool)

    def add_buttons(self, footer: Any) -> None:
        self.preview_button = button(
            self.widget, footer, "Preview", self.contain(self.preview)
        )

    def plan(self, package: Any, facts: Any) -> list[Any]:
        return component_rows(package, survey(package))

    def plan_key(self, package: Any, rows: list[Any]) -> Any:
        return plan_key(package, rows)

    def cells(self, row: Any) -> tuple[str, str | None, tuple[Any, ...]]:
        return (
            row.source,
            None,
            (row.target, row.note or f"replace on {len(self.masters)} masters"),
        )

    def intro(self) -> str:
        return (
            "Canonical round-trip lowercase first; then Unicode and glyph-name order. "
            "Later mappings stay. Replacing existing outlines is recorded as one Undo step."
        )

    def pending(self, todo: list[Any]) -> str:
        return f"{_shared.plural(len(todo), 'row')} ready"

    def can_apply(self, todo: list[Any]) -> bool:
        return (
            bool(todo) and self.preview_key is not None and self.key == self.preview_key
        )

    def preview(self) -> None:
        self.preview_key = None
        self.facts = None
        self.refresh()
        if any(not row.note for row in self.rows):
            self.preview_key = self.key
            self.apply_button.setEnabled(True)
            self.say("Preview ready. Apply asks for confirmation.")

    def apply(self) -> bool:
        try:
            package = self.live()
            rows = self.plan(package, None)
            if self.preview_key is None or plan_key(package, rows) != self.preview_key:
                self.preview_key = None
                self.apply_button.setEnabled(False)
                raise ValueError("The plan changed. Press Preview before Apply.")
            todo = [row for row in rows if not row.note]
            count = len(todo)
            message = (
                f'Replace uppercase drawings in "{package.name}"?\n{count} glyphs, '
                f"{count * len(package.masters)} layers.\n0 targets created; {count} targets replaced."
            )
            if not confirm(self.widget, message):
                return False
            package = self.live()
            rows = self.plan(package, None)
            if plan_key(package, rows) != self.preview_key:
                raise ValueError(
                    "The plan changed during confirmation. Press Preview again."
                )
            disclosure = {"pending_updates": (), "pending_note": ""}
            pairs = [(row.target, row.source) for row in rows if not row.note]
            changed = apply_pairs(
                package,
                pairs,
                title=label(self.UNDO, [t for t, _ in pairs]),
                disclosure=disclosure,
            )
        except _shared.ERRORS as error:
            self.preview_key = None
            self.apply_button.setEnabled(False)
            self.say(str(error))
            return False
        self.preview_key = None
        self.facts = None
        self.refresh()
        self.last_result = {"layers": changed, **disclosure}
        self.say(
            edit_guards.append_note(
                f"Changed {changed} master layers.", self.last_result
            )
        )
        return True


__all__ = ["UnicasePanel", "apply_pairs", "confirm", "mappings", "plan_key", "survey"]
