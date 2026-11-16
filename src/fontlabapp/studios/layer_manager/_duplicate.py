# this_file: src/fontlabapp/studios/layer_manager/_duplicate.py
# SPDX-License-Identifier: Apache-2.0
"""Backups tab, Back up mode: the Scriptmix "Duplicate Current Layer" (Scripts/Masters/).

Clone master layers of the selected glyphs into "<master> backup <suffix>"
layers. The backup naming is the App's shared rule
(``masters.inspect.model.backup_master``/``backup_layer_name``, custom
suffixes, legacy ``@`` and overlapping names, exact-case prefixes,
casefolded master names refused), reused, not copied. The table lists
each new backup, special layers kept and the existing backups (the
original panel's inventory). Back up writes every clone as ONE
``Layer Manager: back up <subject>`` Undo step through
``AppShell.history`` with no target layers (the original's
layer-creating ``layers=[]`` route); the new layers are not master and
not automatic layers (``isMasterLayer``/``autoLayer`` stay False).
"""

from collections.abc import Collection, Sequence
from datetime import datetime
from typing import Any

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native

from .._kerning_ui import combo, get, line_edit, row
from ._shared import (
    Modules,
    PlanTab,
    append_note,
    commit,
    ident,
    label as undo_label,
    result_dict,
)

masters_api = Modules("masters")
contour_copy = Modules("contour_copy")

TITLE = "Duplicate Current Layer"
DEADLINE_SECONDS = 2.0
KEY = "masters_duplicate_current_layer"


def backup_master(name: str, masters: Sequence[str]) -> str | None:
    """Resolve backup layers through the shared App rule."""

    return masters_api.backup_master(name, masters)


def backup_name(
    base: str, taken: Collection[str], stamp: str, masters: Sequence[str]
) -> str:
    """Return the shared unique plain backup name, or raise ValueError."""

    return masters_api.backup_layer_name(base, taken, stamp, masters)


def backups_of(glyph: Any, masters: Sequence[str]) -> list[str]:
    """Inventory plain space-prefixed and old @ backups, excluding special layers."""
    return [
        str(layer.name)
        for layer in glyph.layers
        if not layer.isMaskLayer
        and not layer.isService
        and not layer.autoLayer
        and backup_master(str(layer.name), masters) is not None
    ]


def plan_rows(
    package: Any, names: Sequence[str], masters: Sequence[str], suffix: str, facts: Any
) -> list[Any]:
    """The original ``BackupPanel.plan_rows``: (glyph, layer or None, name, note) per row."""
    rows = []
    for name in names:
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            continue
        taken = {str(layer.name) for layer in glyph.layers}
        reason = history.refusal(facts, name, "geometry")
        for master in masters:
            layer = glyph.findLayer(master)
            if layer is None or layer.isNull:
                continue
            new = backup_name(master, taken, suffix, list(package.masters))
            taken.add(new)
            note = reason or (
                "special layer, kept"
                if layer.autoLayer or layer.isMaskLayer or layer.isService
                else ""
            )
            rows.append((glyph, layer, new, note))
        rows.extend(
            (glyph, None, old, "Existing backup")
            for old in backups_of(glyph, package.masters)
        )
    return rows


def duplicate(
    tool: Any, package: Any, jobs: Sequence[tuple[Any, Any, str]], title: str = TITLE
) -> dict[str, Any] | None:
    """Clone each layer, name the clone, add it to its glyph. ONE Undo step (the original's ``duplicate``).

    The original's checks, mutate and read-back, with ``package`` the bound
    font instead of ``current_package()``; the step goes through
    ``tool.shell.history`` with no target layers. None when refused.
    """
    if not jobs:
        return {"pending_updates": (), "pending_note": "", "layers": 0, "created": []}
    masters = tuple(str(master) for master in package.masters)
    for _, layer, name in jobs:
        base = masters_api.associated_master(str(layer.name), masters) or backup_master(
            str(layer.name), masters
        )
        if base is None or not name.startswith(base + " backup "):
            raise ValueError(f"Backup '{name}' must use <master> backup <suffix>.")
        if (
            "@" in name
            or "#" in name
            or "|temp|" in name
            or backup_master(name, masters) != base
        ):
            raise ValueError(
                f"Backup '{name}' does not resolve to its own master; choose another suffix."
            )
    active = [(glyph, glyph.updateActiveLayer(False)) for glyph, _, _ in jobs]

    def mutate() -> list[Any]:
        created = []
        for glyph, layer, name in jobs:
            clone = layer.clone()
            if len(clone.shapes) != len(layer.shapes):
                raise RuntimeError(
                    f"FontLab clone changed the shape count of '{glyph.name}'."
                )
            for old, new in zip(layer.shapes, clone.shapes, strict=True):
                contour_copy.restore_shape(old, new, keep_view_state=True)
            clone.name = name
            glyph.addLayer(clone)
            found = glyph.findLayer(name)
            if found is None or found.isNull:
                raise RuntimeError(f"FontLab did not add layer '{name}'.")
            glyph.bindDependencies()
            created.append(found)
        for glyph, shown in active:
            if shown is not None and not shown.isNull:
                shown.setActive()
        return created

    glyphs = list({int(glyph.id): glyph for glyph, _, _ in jobs}.values())

    def read_back() -> list[str]:
        missed = []
        for glyph, source, name in jobs:
            found = glyph.findLayer(name)
            if found is None or found.isNull or len(found.shapes) != len(source.shapes):
                missed.append(f"{glyph.name}: {name}")
        for glyph, shown in active:
            current = glyph.updateActiveLayer(False)
            if shown is not None and (current is None or current.id != shown.id):
                missed.append(f"{glyph.name}: active layer changed")
        return missed

    done = commit(tool, title, [], glyphs, mutate, read_back=read_back)
    if done is None:
        return None
    if done.mismatches:
        raise history.unstored_error(done.mismatches)
    return result_dict(done, layers=len(done.created), created=list(done.created))


SCOPES = ("Current master", "All masters")


class DuplicatePanel(PlanTab):
    """Master scope and Suffix, the backup table (with the existing backups), Use selection and Back up."""

    ACTION = "Back up"
    HEADERS = ("Glyph · master", "Backup layer", "Status")
    NO_FONT_TEXT = "Select a glyph first."
    CHANGED_TEXT = "The font changed. Run this script again."

    def build_controls(self, form: Any) -> None:
        self.scope_choice = row(
            self.widget,
            form,
            "Masters",
            combo(self.widget, list(SCOPES), self.contain(self.redraw)),
        )
        self.suffix = row(self.widget, form, "Suffix", line_edit(
            self.widget, masters_api.default_suffix(datetime.now().astimezone()), "", self.contain(self.redraw)))  # fmt: skip

    def masters(self, package: Any) -> list[str]:
        if get(self.scope_choice.currentIndex) == 1:
            return [str(m) for m in package.masters]
        return [str(package.master)]

    def plan(self) -> list[Any]:
        package = self.bound()
        if not self.names:
            raise ValueError("Select a glyph first.")
        return plan_rows(package, self.names, self.masters(package), str(get(self.suffix.text)),
                         history.scan_auto_facts(package))  # fmt: skip

    def rows(self, items: list[Any]) -> list[tuple]:
        return [(str(glyph.name), None if layer is None else str(layer.name),
                 (str(layer.name) if layer is not None else "", name, note or "New backup"))
                for glyph, layer, name, note in items]  # fmt: skip

    def key(self, items: list[Any]) -> Any:
        return tuple(self.rows(items)), tuple(ident(layer) for _, layer, _, _ in items)

    def ready_items(self, items: list[Any]) -> bool:
        return any(layer is not None and not note for _, layer, _, note in items)

    def summary(self, items: list[Any]) -> str:
        count = sum(layer is not None and not note for _, layer, _, note in items)
        return (
            f"{count} backup layer(s) will be created"
            if count
            else "Nothing to back up"
        )

    def write(self, items: list[Any]) -> str | None:
        jobs = [
            (g, layer, name)
            for g, layer, name, note in items
            if layer is not None and not note
        ]
        result = duplicate(
            self.tool,
            self.bound(),
            jobs,
            undo_label("back up", [g.name for g, _, _ in jobs]),
        )
        if result is None:
            return None
        return append_note(f"Created {result['layers']} backup layer(s)", result)


__all__ = [
    "TITLE",
    "DuplicatePanel",
    "backup_master",
    "backup_name",
    "backups_of",
    "duplicate",
    "plan_rows",
]
