# this_file: src/fontlabapp/studios/layer_manager/cleanup.py
# SPDX-License-Identifier: Apache-2.0
"""Clean-up tab: the Scriptmix "Layer Cleanup" (Scripts/Masters/) and "Empty Layers" (Scripts/Cleanup/).

Mode "Delete ticked" (Layer Cleanup): list the extra layers (masks,
backups, alternates, others) of the selected glyphs; nothing is ticked at
first; the "Tick" buttons tick every free row of a kind, or none; "Tick
row" toggles the chosen row (the shared GlyphTable has no tick boxes, so
the "Ticked" column shows the ticks; disclosed). Shown, locked and
refused layers are listed as kept and cannot be ticked. "Delete Ticked"
plans again and refuses ticks that no longer match ("The layers changed.
Check the table and tick again."). Mode "Empty layers" (Empty Layers):
list the extra layers that hold no data, then delete them. The planning
is the originals', verbatim. Each delete is ONE ``Layer Manager: ...``
Undo step through ``AppShell.history`` on the originals' carrier layers;
the components of deleted layers are retained (fl#7641); layers go by the
originals' ``glyph.removeLayer`` route.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native

from .._kerning_ui import button
from ._empty import EmptyPanel
from ._modes import ModesPanel
from ._shared import (
    Modules,
    PlanTab,
    append_note,
    commit,
    hline,
    label as undo_label,
    result_dict,
)

masters_api = Modules("masters")


def associated_master(name: str, masters: Sequence[str]) -> str | None:
    """The App's FontLab layer-to-master rule (the original imported it in ``kind``)."""
    return masters_api.associated_master(name, masters)


TITLE = "Layer Cleanup"
KEY = "masters_layer_cleanup"
KINDS = ("mask", "backup", "alternate", "other")
TEMP_PREFIX = "|temp|"
MAX_NAMES = 8  # glyph names shown in the subtitle


@dataclass(frozen=True)
class Entry:
    """One extra layer. ``note`` is empty when the layer may be deleted."""

    glyph: Any
    layer: Any
    name: str
    kind: str
    contours: int
    note: str = ""


def backup_master(name: str, masters: Sequence[str]) -> str | None:
    """Resolve backup layers through the shared App rule."""

    return masters_api.backup_master(name, masters)


def kind(layer: Any, masters: Sequence[str]) -> str | None:
    """Return the kind of an extra layer, or None for a layer that is never listed."""
    name = str(layer.name)
    if layer.isMaskLayer:
        return "mask"
    if layer.isService or layer.isImgLayer or name.startswith(TEMP_PREFIX):
        return None
    if name.lower() in {str(m).lower() for m in masters}:
        return None
    if backup_master(name, masters) is not None:
        return "backup"
    if associated_master(name, masters) is not None:
        return "alternate"
    return "other"


def _contours(layer: Any) -> int:
    """Return the number of contours in the non-component shapes of ``layer``."""
    return sum(len(s.contours) for s in layer.shapes if not s.isComponent)


def survey(
    package: Any, names: Sequence[str], masters: Sequence[str], facts: Any
) -> list[Entry]:
    """List the extra layers of ``names`` in glyph order. Change nothing.

    Notes, in this order: a glyph the geometry policy refuses, a locked
    layer, the shown layer.
    """

    entries: list[Entry] = []
    for name in names:
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            continue
        reason = history.refusal(facts, str(glyph.name), "geometry")
        active = glyph.updateActiveLayer(False)
        shown = int(active.id) if active is not None and not active.isNull else None
        for layer in glyph.layers:
            what = kind(layer, masters)
            if what is None:
                continue
            note = ""
            if reason:
                note = f"{reason} (kept)"
            elif layer.isLocked:
                note = "locked layer (kept)"
            elif int(layer.id) == shown:
                note = "shown layer (kept)"
            entries.append(
                Entry(glyph, layer, str(layer.name), what, _contours(layer), note)
            )
    return entries


def undo_layers(glyph: Any, doomed: set[int], masters: Sequence[str]) -> list[Any]:
    """Return the surviving body layers that carry the Undo step of a deletion.

    FontLab records an Undo step only for a list of layers plus their glyph;
    a glyph alone adds no step. Take the body layer of each deleted mask;
    else the first master layer that stays. ``doomed`` holds layer ids.
    Raise ValueError when no such layer is left.
    """
    found = []
    for layer in glyph.layers:
        if int(layer.id) in doomed or layer.isMaskLayer or layer.autoLayer:
            continue
        mask = layer.getMaskLayer(False)
        if mask is not None and not mask.isNull and int(mask.id) in doomed:
            found.append(layer)
    if not found:
        for master in masters:
            layer = glyph.findLayer(master)
            if (
                layer is not None
                and not layer.isNull
                and int(layer.id) not in doomed
                and not layer.autoLayer
            ):
                found.append(layer)
                break
    if not found:
        raise ValueError(f"'{glyph.name}' has no layer left to record the Undo step.")
    return found


def plural(count: int, word: str) -> str:
    """Return "1 layer" or "2 layers"."""
    return f"{count} {word}{'' if count == 1 else 's'}"


def delete_layers(
    tool: Any, entries: Sequence[Entry], masters: Sequence[str], title: str = TITLE
) -> dict | None:
    """The original ``delete_layers`` through ``tool.shell.history``: ONE Undo step; None when refused."""
    kept = [f"{e.glyph.name}/{e.name}: {e.note}" for e in entries if e.note]
    if kept:
        raise ValueError("Refused: " + "; ".join(kept[:3]))
    if not entries:
        return {
            "pending_updates": (),
            "pending_note": "",
            "layers": 0,
            "glyphs": 0,
            "deleted": [],
            "mismatches": [],
        }
    glyphs = list({str(e.glyph.name): e.glyph for e in entries}.values())
    doomed = {int(e.layer.id) for e in entries}
    carriers = [
        layer for glyph in glyphs for layer in undo_layers(glyph, doomed, masters)
    ]
    retain = [
        item
        for e in entries
        for shape in e.layer.shapes
        for item in history.component_history(shape)
    ]
    labels = [f"{e.glyph.name}/{e.name}" for e in entries]

    def mutate() -> None:
        for entry in entries:
            entry.glyph.removeLayer(entry.layer)

    def read_back() -> list[str]:
        return [
            f"{e.glyph.name}: layer '{e.name}' is still there"
            for e in entries
            if int(e.layer.id) in {int(x.id) for x in e.glyph.layers}
        ]

    done = commit(
        tool, title, carriers, glyphs, mutate, read_back=read_back, retain=retain
    )
    if done is None:
        return None
    return result_dict(done, layers=len(entries), glyphs=len(glyphs), deleted=labels)


class TickPanel(PlanTab):
    """Layer Cleanup: the kind Tick buttons, Tick row, the kept rows and Delete Ticked."""

    ACTION = "Delete Ticked"
    HEADERS = ("Glyph", "Layer", "Kind", "Contours", "Ticked")
    STALE_TICKS = "The layers changed. Check the table and tick again."

    def build_controls(self, form: Any) -> None:
        self.ticks: set[tuple[int, int]] = set()
        self.chosen: tuple[str, str] | None = None
        line = hline(form)
        line.addWidget(text_widget(self.widget, "Tick"))
        self.kind_buttons = {k: button(self.widget, line, f"all {k}s", self.contain(lambda k=k: self.tick_kind(k)))
                             for k in KINDS}  # fmt: skip
        self.none_button = button(
            self.widget, line, "none", self.contain(lambda: self.tick_kind(None))
        )
        self.row_button = button(
            self.widget, line, "Tick row", self.contain(self.tick_row)
        )

    def plan(self) -> list[Entry]:
        package = self.bound()
        if not self.names:
            raise ValueError(
                "Select glyphs in the Font window. Then press Use selection."
            )
        return survey(
            package,
            self.names,
            [str(m) for m in package.masters],
            history.scan_auto_facts(package),
        )

    @staticmethod
    def ident(entry: Entry) -> tuple[int, int]:
        return int(entry.glyph.id), int(entry.layer.id)

    def rows(self, items: list[Entry]) -> list[tuple]:
        return [(str(e.glyph.name), e.name, (e.name, e.kind, e.note or e.contours,
                 "yes" if self.ident(e) in self.ticks else "")) for e in items]  # fmt: skip

    def key(self, items: list[Entry]) -> Any:
        return tuple((self.ident(e), e.name, e.kind, e.contours, e.note) for e in items)

    def ticked(self) -> list[Entry]:
        return [e for e in self.items if self.ident(e) in self.ticks]

    def ready_items(self, items: list[Entry]) -> bool:
        return bool(self.ticked())

    def summary(self, items: list[Entry]) -> str:
        return f"{plural(len(items), 'extra layer')} · {len(self.ticked())} ticked for deletion"

    def redraw(self) -> None:
        super().redraw()
        live = {self.ident(e) for e in self.items if not e.note}
        self.ticks &= live

    def show_ticks(self) -> None:
        self.grid.set_rows(self.rows(self.items))
        if self.chosen:
            self.grid.select(*self.chosen)
        self.apply_button.setEnabled(self.ready_items(self.items))
        self.status.setText(self.summary(self.items))

    def tick_kind(self, kind_name: str | None) -> None:
        """The original's Tick buttons: tick every free row of one kind and clear the rest."""
        self.ticks = {
            self.ident(e) for e in self.items if not e.note and e.kind == kind_name
        }
        self.show_ticks()

    def tick_row(self) -> None:
        """Toggle the chosen row; a kept row cannot be ticked."""
        found = [e for e in self.items if self.chosen == (str(e.glyph.name), e.name)]
        if not found or found[0].note:
            return
        self.ticks ^= {self.ident(found[0])}
        self.show_ticks()

    def row_chosen(self, name: str, layer: Any) -> None:
        self.chosen = (name, layer) if name else None
        super().row_chosen(name, layer)

    def checked(self) -> list[Entry]:
        """Match the ticks against a fresh plan; refuse when the layers changed."""
        wanted = set(self.ticks)
        fresh = self.plan()
        found = [e for e in fresh if self.ident(e) in wanted]
        if len(found) != len(wanted) or any(e.note for e in found):
            self.redraw()
            raise ValueError(self.STALE_TICKS)
        return found

    def write(self, items: list[Entry]) -> str | None:
        package = self.bound()
        result = delete_layers(self.tool, items, [str(m) for m in package.masters],
                               undo_label("delete layers", [e.glyph.name for e in items]))  # fmt: skip
        if result is None:
            return None
        self.ticks.clear()
        text = f"Deleted {plural(len(result['deleted']), 'layer')} from {plural(result['glyphs'], 'glyph')}"
        if result["mismatches"]:
            text += " · did not read back as planned: " + "; ".join(
                result["mismatches"][:5]
            )
        return append_note(text, result)


def text_widget(owner: Any, value: str) -> Any:
    from PythonQt import QtGui

    return QtGui.QLabel(value, owner)


class CleanupPanel(ModesPanel):
    MODES = (("Delete ticked", TickPanel), ("Empty layers", EmptyPanel))


__all__ = [
    "KINDS",
    "TITLE",
    "CleanupPanel",
    "Entry",
    "TickPanel",
    "delete_layers",
    "kind",
    "survey",
    "undo_layers",
]
