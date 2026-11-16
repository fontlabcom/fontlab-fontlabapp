# this_file: src/fontlabapp/studios/vertical_metrics/zones.py
# SPDX-License-Identifier: Apache-2.0
"""Zones tab: Alignment Zones (Metrics) and Suggest Zones From Overshoots (Guides).

Refresh captures every master's zones (``metrics.zones.native.capture``) into
one ``metrics.zones.model.Editor``. The zone table shows the staged zones of
the chosen master (Kind, Position, Width, Name; double-click to edit); "Add
top zone", "Add bottom zone", "Remove selected" and "Suggest from o / O"
stage edits as in Alignment Zones, and edits of other masters are kept when
you switch. "Suggest from overshoots" measures H, O, x and o (outline
geometry, never the cached box, fl#8575) in the current or every master and
stages the original suggestions (``suggestions``/``merge``: replace the zone
of the same kind at the same position, else the one of the same name, else
add; a replaced zone keeps its name, tags and lock), listed with the zone
each one replaces. The pending list names every master with a change.

"Set zones" writes the staged plan of every changed master through the
original route-A writer (``metrics.zones.native``, ``commit_masters``) as ONE
``Vertical Metrics: set zones of <masters>`` Undo step. It refuses first when
H, O, x or o changed since the overshoot preview, then the writer refuses
row errors (``RowRefusal``), a call off the GUI thread or without the Font
window, and a font that changed since Refresh. Those refusals leave the font
and the stages as they were. Any other failure can leave masters partly
written: the tab locks until the app is reopened, as the originals did.
The serializer route (``zone_capture``/``zone_prepare``/``zone_write_plan``)
stays held (fl#8554) and is not used.
"""

from __future__ import (
    annotations,
)  # the verbatim annotations name lazily loaded classes

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from typing import TYPE_CHECKING, Any, NamedTuple

from PythonQt import QtGui

from .._kerning import Tool
from .._kerning_ui import Panel, button, combo, get, label, row
from . import _shared
from ._shared import MasterTable

RULES = (
    ("baseline", "H", "O", False),
    ("x-height", "x", "o", True),
    ("caps", "H", "O", True),
)
GLYPHS = ("H", "O", "x", "o")
LOCKED = "Zones may be partly written; check every master and reopen this tool."
CHANGED = "H, O, x or o changed since the preview; press Refresh."


class Suggestion(NamedTuple):
    """One measured zone: its name, kind, position and outward width."""

    name: str
    top: bool
    position: int
    width: int


# The checker sees stand-ins; at run time the names resolve to the reused backends,
# so the package imports no App internals.
if TYPE_CHECKING:

    class Zone(Any): ...

    class Zones(Any): ...

    class alignment_zones:  # noqa: N801 - the original's module name
        Extent = Any
        extent: Any

else:

    def Zone(*args: Any, **kwargs: Any) -> Any:  # noqa: N802 - the original's class name
        """``metrics.zones.data.Zone`` (through the backends, so the package imports no App internals)."""
        return _shared.backends().zone_data.Zone(*args, **kwargs)

    def Zones(*args: Any, **kwargs: Any) -> Any:  # noqa: N802 - the original's class name
        """``metrics.zones.data.Zones``."""
        return _shared.backends().zone_data.Zones(*args, **kwargs)


class Modules:
    """The verbatim Suggest functions read these module names; each resolves to the reused backend."""

    def __init__(self, attribute: str) -> None:
        self.attribute = attribute

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        return getattr(getattr(_shared.backends(), self.attribute), name)


if not TYPE_CHECKING:
    alignment_zones = Modules("zones")
outline_extent = Modules("extent")
zone_rows = Modules("zone_rows")


def overshoot_zone(flat: float, curved: float, top: bool) -> tuple[int, int]:
    """Return ``(position, width)``: the flat edge and the overshoot beyond it."""
    width = curved - flat if top else flat - curved
    return round(flat), max(0, round(width))


def suggestions(extents: Mapping[str, alignment_zones.Extent]) -> list[Suggestion]:
    """Return the zones that the extents of H, O, x and o support, in rule order.

    ``extents`` maps a glyph name to its ``(bottom, top)`` or ``None``. A rule
    whose flat or round glyph is ``None`` or absent gives no zone.
    """
    found = []
    for name, flat, curved, top in RULES:
        pair = extents.get(flat), extents.get(curved)
        if None in pair:
            continue
        edge = 1 if top else 0
        position, width = overshoot_zone(pair[0][edge], pair[1][edge], top)
        found.append(Suggestion(name, top, position, width))
    return found


def missing(extents: Mapping[str, alignment_zones.Extent]) -> list[str]:
    """Return the rule names that ``suggestions`` skips for ``extents``."""
    return [
        name
        for name, flat, curved, _top in RULES
        if extents.get(flat) is None or extents.get(curved) is None
    ]


def _at(position: int) -> Callable[[Zone], bool]:
    """Return a test for a zone whose rounded position is ``position``."""
    return lambda zone: round(zone.position) == position


def _named(name: str) -> Callable[[Zone], bool]:
    """Return a test for a zone called ``name``."""
    return lambda zone: zone.name == name


def merge(
    zones: Zones, proposed: Sequence[Suggestion]
) -> tuple[Zones, list[Zone | None]]:
    """Return ``zones`` with ``proposed`` merged in, and the zone each one replaced.

    A suggestion replaces the zone of its kind at the same position, else the
    one with the same name, else it is added. A replaced zone keeps its name
    and, so, its source identity (tags and lock). A zone is replaced once.
    """
    kinds = {True: list(zones.top), False: list(zones.bottom)}
    replaced: list[Zone | None] = []
    for item in proposed:
        pool = kinds[item.top]
        old = next(
            (
                z
                for test in (_at(item.position), _named(item.name))
                for z in pool
                if test(z)
            ),
            None,
        )
        new = Zone(item.position, item.width, item.name)
        if old is not None:
            pool.remove(old)
            new = replace(new, name=old.name or item.name)
            if new.name == old.name:
                new = replace(new, origin=old.origin)
        pool.append(new)
        replaced.append(old)
    return Zones(tuple(kinds[True]), tuple(kinds[False])), replaced


def measure(
    package: Any, master: str, unreadable: dict[str, str] | None = None
) -> dict[str, alignment_zones.Extent]:
    """Return the vertical extent of each of ``GLYPHS`` in ``master``; reads only.

    The extent comes from the outline nodes, not from FontLab's cached
    ``boundingBox``, which can be stale after a node move (fl#8575). A glyph
    whose outline cannot be read gets ``None``; its reason goes into
    ``unreadable`` (glyph name to message) when that dict is given.
    """
    found = {}
    for name in GLYPHS:
        glyph = package.findName(name)
        absent = glyph is None or getattr(glyph, "isNull", False)
        layer = None if absent else glyph.findLayer(master)
        if layer is None or layer.isNull:
            found[name] = None
            continue
        try:
            span = outline_extent.vertical_extent(layer)
        except ValueError as error:
            found[name] = None
            if unreadable is not None:
                unreadable[name] = str(error)
            continue
        found[name] = (
            None if span is None else alignment_zones.extent(span[0], span[1] - span[0])
        )
    return found


def stage(editor: Any, master: str, zones: Zones) -> Any:
    """Return ``editor`` with ``zones`` staged for ``master``."""
    return editor.stage(master, zone_rows.rows(zones), origins=zone_rows.origins(zones))


def preview_row(master: str, item: Suggestion, old: Zone | None) -> list:
    """Return one table row: master, zone, position, signed width and the replaced zone."""
    width = f"+{item.width}" if item.top else f"-{item.width}"
    if old is None:
        return [master, item.name, item.position, width, "nothing: added"]
    label = old.name or "no name"
    return [
        master,
        item.name,
        item.position,
        width,
        f"{label} at {round(old.position)}, width {round(old.width)}",
    ]


def unchanged(error: ValueError, found: Any) -> bool:
    """True for an Apply refusal that left the font as it was (``metrics.zones.ui._unchanged``)."""
    history = found.font_history
    if isinstance(error, (found.zone_native.RowRefusal, history.RolledBackError)):
        return True
    return type(error) is ValueError and str(error) in (
        history.THREAD_TEXT,
        history.WINDOW_TEXT,
    )


class ZonesPanel(Panel):
    """Alignment Zones with Suggest Zones From Overshoots."""

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.master = combo(self.widget, [], _shared.keep(self, self.choose))
        row(self.widget, self.layout, "Master", self.master)
        self.grid = MasterTable(self.widget, self.layout, ["Kind", "Position", "Width", "Name"],
                                editable=(0, 1, 2, 3), changed=_shared.keep(self, self.store))  # fmt: skip
        edits = QtGui.QHBoxLayout()
        self.layout.addLayout(edits)
        button(
            self.widget,
            edits,
            "Add top zone",
            _shared.keep(self, lambda: self.add("Top")),
        )
        button(
            self.widget,
            edits,
            "Add bottom zone",
            _shared.keep(self, lambda: self.add("Bottom")),
        )
        self.remove_button = button(
            self.widget, edits, "Remove selected", _shared.keep(self, self.remove)
        )
        button(
            self.widget, edits, "Suggest from o / O", _shared.keep(self, self.suggest)
        )
        label(self.widget, self.layout, "Suggest Zones From Overshoots: each zone starts at the edge of H or x "
                                        "and covers the overshoot of O or o. Matching zones are replaced; all "
                                        "other zones are kept.")  # fmt: skip
        self.scope = combo(self.widget, ["Current master", "All masters"])
        row(self.widget, self.layout, "Masters", self.scope)
        button(
            self.widget,
            self.layout,
            "Suggest from overshoots",
            _shared.keep(self, self.overshoots),
        )
        self.suggested = MasterTable(
            self.widget,
            self.layout,
            ["Master", "Zone", "Position", "Width", "Replaces"],
        )
        self.status = label(self.widget, self.layout)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        button(self.widget, buttons, "Refresh", tool.reload)
        self.apply_button = button(
            self.widget, buttons, "Set zones", lambda: self.run(self.apply)
        )
        self.editor: Any = None
        self.current = ""
        self.measured: dict[str, dict] = {}
        self.locked = False

    # Reading -------------------------------------------------------------------
    def clear(self) -> None:
        self.editor, self.measured = None, {}
        self.grid.set_rows([])
        self.suggested.set_rows([])
        self.apply_button.setEnabled(False)

    def refresh(self) -> None:
        self.editor, self.measured = None, {}
        self.suggested.set_rows([])
        if self.locked:
            raise ValueError(LOCKED)
        tool = self.tool
        if tool.package is None:
            self.subtitle.setText("Open a font first.")
            self.clear()
            self.status.setText("")
            return
        found = _shared.backends()
        snapshot = found.zone_native.capture(tool.package.id)
        self.editor = found.zones.Editor(snapshot)
        names = [m.name for m in snapshot.masters]
        self.current = (
            self.current if self.current in names else snapshot.current_master
        )
        self.master.blockSignals(True)
        self.master.clear()
        for name in names:
            self.master.addItem(name)
        self.master.setCurrentIndex(names.index(self.current))
        self.master.blockSignals(False)
        self.subtitle.setText(f"{_shared.plural(len(names), 'master')}: stage zones per master, then Set zones "
                              "writes every changed master as one Undo step.")  # fmt: skip
        self.fill()

    def fill(self) -> None:
        rows = self.editor.rows(self.current)
        self.grid.set_rows([tuple(f"{v:g}" if isinstance(v, float | int) else v for v in r) for r in rows],
                           keys=[self.current] * len(rows))  # fmt: skip
        self.show_status()

    def show_status(self) -> None:
        pending = self.editor.pending() if self.editor is not None else ()
        count = len(self.editor.rows(self.current)) if self.editor is not None else 0
        note = " · unsaved: " + ", ".join(pending) if pending else ""
        self.status.setText(f"{self.current}: {_shared.plural(count, 'zone')}{note}")
        self.apply_button.setEnabled(bool(pending))
        self.remove_button.setEnabled(count > 0)

    def require(self) -> Any:
        if self.locked:
            raise ValueError(LOCKED)
        if self.editor is None:
            raise ValueError("Open a font first.")
        return self.editor

    # Staging (Alignment Zones) ---------------------------------------------------
    def texts(self) -> tuple[tuple[str, ...], ...]:
        return tuple(
            tuple(self.grid.cell(r, c) for c in range(4))
            for r in range(self.grid.count())
        )

    def store(self) -> None:
        """Stage the edited table; an invalid cell refuses and keeps the previous stage."""
        editor = self.require()
        try:
            self.editor = editor.stage(
                self.current, self.texts(), origins=editor.origins(self.current)
            )
        except ValueError:
            self.apply_button.setEnabled(False)
            raise
        self.show_status()

    def choose(self) -> None:
        self.require()
        self.current = get(self.master.currentText)
        self.fill()

    def add(self, kind: str) -> None:
        self.editor = self.require().add(self.current, kind)
        self.fill()

    def remove(self) -> None:
        self.editor = self.require().remove(self.current, self.grid.selected())
        self.fill()

    def suggest(self) -> None:
        """Alignment Zones' "Suggest from o / O": the native bounds of o and O in this master."""
        editor = self.require()
        lower, upper = _shared.backends().zone_native.bounds(
            editor.snapshot, self.current
        )
        self.editor = editor.suggest(self.current, lower, upper)
        self.fill()

    # Suggest Zones From Overshoots ---------------------------------------------------
    def chosen_masters(self) -> list[str]:
        editor = self.require()
        if get(self.scope.currentIndex):
            return [master.name for master in editor.snapshot.masters]
        return [editor.snapshot.current_master]

    def overshoots(self) -> None:
        """Measure the four glyphs and stage the merged suggestions; list each with the zone it replaces."""
        editor = self.require()
        rows, skipped, measured = [], [], {}
        for master in self.chosen_masters():
            unreadable: dict[str, str] = {}
            extents = measure(self.tool.package, master, unreadable)
            measured[master] = extents
            skipped += [
                f"{name} in {master} ({reason})" for name, reason in unreadable.items()
            ]
            proposed = suggestions(extents)
            zones, replaced = merge(editor.zones(master), proposed)
            editor = stage(editor, master, zones)
            rows += [
                preview_row(master, *pair)
                for pair in zip(proposed, replaced, strict=True)
            ]
            skipped += [f"{name} in {master}" for name in missing(extents)]
        self.editor = editor
        self.measured.update(measured)
        self.suggested.set_rows([tuple(r) for r in rows])
        self.fill()
        note = f" · not measured: {', '.join(skipped)}" if skipped else ""
        same = "" if editor.pending() or not rows else " · the zones already match"
        self.tool.say(f"{_shared.plural(len(rows), 'suggested zone')}{same}{note}")

    # Writing ---------------------------------------------------------------------
    def apply(self) -> None:
        editor = self.require()
        package = self.tool.package
        if any(measure(package, m) != e for m, e in self.measured.items()):
            raise ValueError(CHANGED)
        changes = editor.plan()
        if not changes:
            raise ValueError("Nothing to change.")
        found = _shared.backends()
        title = _shared.label("set zones", [c.master for c in changes])
        backend = found.zone_native.backend(package.id, title=title)
        try:
            after = backend.apply(editor.snapshot, changes)
        except ValueError as error:
            if not unchanged(error, found):
                self.locked = True
            raise
        except BaseException:  # PartialWriteError, a read-back gap, an interrupt
            self.locked = True
            raise
        try:
            found.zone_editor.check_result(editor.snapshot, changes, after)
        except Exception:
            self.locked = True
            raise
        zones = sum(len(c.after.top) + len(c.after.bottom) for c in changes)
        self.measured = {}
        self.tool.reload()
        self.tool.say(
            f"{title}. Wrote {_shared.plural(zones, 'zone')} in {_shared.plural(len(changes), 'master')}"
        )


__all__ = ["GLYPHS", "RULES", "Suggestion", "ZonesPanel", "measure", "merge", "missing", "overshoot_zone",
           "preview_row", "stage", "suggestions"]  # fmt: skip
