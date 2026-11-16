# this_file: src/fontlabapp/metrics/panel/model.py
# SPDX-License-Identifier: Apache-2.0
"""Shared plan, write and panel parts of the Metrics scripts (advance edits).

What: the Metrics scripts (Round Advances, Scale Advances, Tabular Width,
Centre In Advance, Italic Sidebearings, Zero-Width Marks) share one model.
A planner turns one layer into a ``LayerPlan`` (outline shift ``dx`` and new
advance ``width``) or a skip text. ``survey`` plans every target layer,
``commit`` writes all pending plans as ONE Undo step and reads them back, and
the non-modal ``MetricsPanel`` (from ``panel_type()``) shows a live preview.

How: ``commit`` uses ``fontlabapp.core.history.glyphs.commit`` with the ``"geometry"``
policy. Auto layers are listed and never edited. A glyph that owns an auto
layer is listed and skipped as a whole. Layers with a metrics link or
expression are listed and skipped. A base of auto composites is refused until
the user ticks ``ALLOW_AUTO_LABEL`` for exactly the glyphs that change now.
``shift_and_set`` moves the outline in place (``applyTransform``), never
through a clone, because ``flShape.clone()`` drops raw node flags and notes
(FontLab issues 8516 and 8538).

Why: each script then holds only its constants, its planner and a small
``build()``. This module imports only the standard library at load time.
PythonQt and FontLab load inside the functions; ``panel_type()`` loads the
Qt panel class. Offline tests do not prove native Undo/Redo/reopen.

How to use (a script)::

    from fly.ap.metrics.panel.model import LayerPlan, make_plan, panel_type

    class RoundAdvances(panel_type()):
        TITLE, KEY, HEADERS, ACCENT = "Round Advances", "metrics_round", ("Width",), (1,)

        def build(self): ...
        def subtitle_hint(self): return "Rounds advances."
        def planner(self, package, glyphs): return lambda layer, master: make_plan(...)
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fontlabapp.core.history.glyphs import AutoFacts

from fontlabapp import _native

#: Table rows shown. Larger plans still apply in full.
MAX_ROWS = 400
#: Glyph names shown in the subtitle.
MAX_NAMES = 8
#: Auto composites named in the rebuild note, and mismatches in the status.
NOTE_LIMIT = 5
#: Label of the tick box that lets bases of auto composites through.
ALLOW_AUTO_LABEL = "Edit bases of auto glyphs anyway"
#: Units. The outline edge may differ by rounding after the write.
READ_BACK_TOLERANCE = 0.5
#: Layer fields that hold a sidebearing or width link or expression.
LINK_FIELDS = ("metricsLeft", "metricsRight", "metricsWidth")
#: Skip note of an auto layer.
AUTO_LAYER_NOTE = "auto layer (skipped)"
#: Skip note of a manual layer in a glyph that owns an auto layer.
AUTO_GLYPH_NOTE = "glyph has auto layers (skipped)"
#: Skip note of a layer with a metrics link or expression.
LINK_NOTE = "metrics link or expression (skipped)"
#: Skip note of a glyph without a layer in the master.
MISSING_NOTE = "no layer in this master"


@dataclass(frozen=True)
class LayerPlan:
    """One planned layer edit.

    ``dx``: units to move the outline sideways. ``width``: new advance width in
    units. ``cells``: preview texts that follow the glyph label. ``changed``:
    False for a no-op. Build it with ``make_plan``.
    """

    dx: int
    width: int
    cells: tuple[str, ...]
    changed: bool


#: A planner takes (layer, master name) and returns a LayerPlan, or a short
#: text that says why it skips the layer.
Planner = Callable[[Any, str], LayerPlan | str]


@dataclass
class Entry:
    """One glyph/master layer with its plan, or with its skip note.

    ``layer`` is None when the glyph has no layer in ``master``. ``plan`` is
    None for every skipped layer; ``note`` then says why.
    """

    glyph: Any
    master: str
    layer: Any
    plan: LayerPlan | None
    note: str


def unit(value: float) -> int:
    """Round half up to a whole unit. Python ``round()`` rounds half to even."""
    return math.floor(value + 0.5)


def make_plan(layer: Any, dx: int, width: int, cells: tuple[str, ...]) -> LayerPlan:
    """Build a plan. It is a no-op when the outline and the advance stay as they are."""
    return LayerPlan(dx, width, cells, bool(dx) or width != layer.advanceWidth)


def ink_edges(layer: Any) -> tuple[float, float] | None:
    """Return the left and right edge of the layer outline, or None for an empty layer."""
    box = layer.boundingBox
    if box.width() <= 0 and box.height() <= 0:
        return None
    return box.x(), box.x() + box.width()


def master_layers(glyph: Any, masters: list[str]) -> dict[str, Any]:
    """Map master name to layer for the masters that this glyph has."""
    found: dict[str, Any] = {}
    for master in masters:
        layer = glyph.findLayer(master)
        if layer is not None and not layer.isNull:
            found[master] = layer
    return found


def has_metrics_link(layer: Any) -> bool:
    """Return True when a sidebearing or the width holds a link or an expression."""
    return any(str(getattr(layer, field)) for field in LINK_FIELDS)


def _owns_auto(glyph: Any) -> bool:
    """Return True when any layer of the glyph is an auto layer."""
    return any(layer.autoLayer for layer in glyph.layers)


def survey(
    glyphs: list[Any], masters: list[str], planner: Planner, *, facts: AutoFacts | None = None,
) -> list[Entry]:
    """Plan every glyph/master layer. Skipped layers are listed with a note.

    Skip, in this order: a missing layer (``MISSING_NOTE``); an auto layer
    (``AUTO_LAYER_NOTE``); any other layer of a glyph that owns an auto layer
    (``AUTO_GLYPH_NOTE``; the geometry policy refuses such glyphs); a layer
    with a metrics link (``LINK_NOTE``); a layer the planner skips (its text).
    A manual composite is also skipped when its base moves in this plan.
    Pass the existing whole-font component ``facts`` to follow unselected
    intermediate glyphs. Without facts, only selected layers supply edges.
    """
    entries: list[Entry] = []
    for glyph in glyphs:
        owner = _owns_auto(glyph)
        for master in masters:
            layer = glyph.findLayer(master)
            if layer is None or layer.isNull:
                entries.append(Entry(glyph, master, None, None, MISSING_NOTE))
            elif layer.autoLayer:
                entries.append(Entry(glyph, master, layer, None, AUTO_LAYER_NOTE))
            elif owner:
                entries.append(Entry(glyph, master, layer, None, AUTO_GLYPH_NOTE))
            elif has_metrics_link(layer):
                entries.append(Entry(glyph, master, layer, None, LINK_NOTE))
            else:
                result = planner(layer, master)
                if isinstance(result, str):
                    entries.append(Entry(glyph, master, layer, None, result))
                else:
                    entries.append(Entry(glyph, master, layer, result, ""))
    # Follow component users even when an intermediate glyph is not selected.
    users: dict[str, set[str]] = {}
    if facts is not None:
        users = {base: set(names) for base, names in facts.users.items()}
    else:
        for entry in entries:
            if entry.layer is not None:
                for shape in entry.layer.shapes:
                    if shape.isComponent:
                        users.setdefault(str(shape.shapeData.componentGlyph), set()).add(str(entry.glyph.name))
    moving = {(str(e.glyph.name), e.master) for e in entries if e.plan and e.plan.dx}
    affected: dict[tuple[str, str], str] = {}
    for base, master in sorted(moving):
        seen, todo = {base}, [base]
        while todo:
            for name in sorted(users.get(todo.pop(), ())):
                if name not in seen:
                    seen.add(name)
                    todo.append(name)
                    affected.setdefault((name, master), base)
    for index, entry in enumerate(entries):
        base = affected.get((str(entry.glyph.name), entry.master))
        if entry.plan is not None and base is not None:
            entries[index] = Entry(
                entry.glyph, entry.master, entry.layer, None,
                f"{entry.glyph.name}: skipped; its base {base} moves in this step",
            )
    return entries


def pending(entries: list[Entry]) -> list[Entry]:
    """Return the entries that change the font."""
    return [e for e in entries if e.plan is not None and e.plan.changed]


def shift_and_set(layer: Any, dx: int, width: int, *, qtgui: Any = None) -> None:
    """Move the outline by ``dx`` units in place, anchors included, then set the advance.

    Use ``layer.applyTransform``, then ``changed()`` and ``update()``; never a
    shape clone. ``update()`` returning False raises ``RuntimeError``.
    ``qtgui`` is PythonQt's QtGui (default: the native one).
    """
    if dx:
        gui = _native("PythonQt").QtGui if qtgui is None else qtgui
        layer.applyTransform(gui.QTransform(1, 0, 0, 1, dx, 0))
        layer.changed()
        if layer.update() is False:
            raise RuntimeError("FontLab could not update the layer geometry.")
    layer.advanceWidth = width


def read_back(entry: Entry, before: tuple[float, float] | None) -> list[str]:
    """Compare the written layer with its plan. Return one text per mismatch.

    ``before`` holds the ink edges from before the write (``ink_edges``). The
    left edge may differ by ``READ_BACK_TOLERANCE`` units.
    """
    label = f"{entry.glyph.name} · {entry.master}"
    layer, plan = entry.layer, entry.plan
    found = []
    if layer.advanceWidth != plan.width:
        found.append(f"{label}: advance {layer.advanceWidth:g}, planned {plan.width}")
    after = ink_edges(layer)
    if before is not None and after is not None:
        want = before[0] + plan.dx
        if abs(after[0] - want) > READ_BACK_TOLERANCE:
            found.append(f"{label}: ink edge {after[0]:g}, planned {want:g}")
    return found


def auto_skipped(entries: list[Entry]) -> int:
    """Count the layers skipped because of auto layers."""
    return sum(1 for e in entries if e.note in (AUTO_LAYER_NOTE, AUTO_GLYPH_NOTE))


def commit(
    title: str,
    entries: list[Entry],
    *,
    facts: Any,
    allow_bases: bool = False,
    native: Any = None,
    stamp: Any = None,
    qtgui: Any = None,
) -> dict[str, Any]:
    """Apply all pending plans as ONE Undo step. Report what the font now holds.

    ``facts``: fresh ``history.AutoFacts`` of the font. ``allow_bases``: the
    user ticked ``ALLOW_AUTO_LABEL`` for these glyphs. The write goes through
    ``fontlabapp.core.history.glyphs.commit`` with ``operation="geometry"``: refusals
    first, then init history, ``shift_and_set`` per layer, stamp, one notify
    of the layers and their glyphs, stamp, read-back.

    Return ``{"layers", "glyphs", "auto_skipped", "mismatches"}``. Nothing to
    change returns zeros and makes no history call. A refusal raises
    ``ValueError``; a failure after history started raises
    ``history.PartialWriteError``.
    """
    from fontlabapp.core.history.glyphs import commit as one_step

    todo = pending(entries)
    skipped = auto_skipped(entries)
    if not todo:
        return {"layers": 0, "glyphs": 0, "auto_skipped": skipped, "mismatches": []}
    owners = list({e.glyph.name: e.glyph for e in todo}.values())
    edges = [ink_edges(e.layer) for e in todo]

    def mutate() -> None:
        for entry in todo:
            shift_and_set(entry.layer, entry.plan.dx, entry.plan.width, qtgui=qtgui)

    def check() -> list[str]:
        return [text for e, b in zip(todo, edges) for text in read_back(e, b)]

    result = one_step(
        title,
        [e.layer for e in todo],
        owners,
        mutate,
        operation="geometry",
        facts=facts,
        allow_bases=allow_bases,
        read_back=check,
        native=native,
        stamp=stamp,
    )
    return {"pending_note": result.pending_note, 
        "layers": len(todo),
        "glyphs": len(owners),
        "auto_skipped": skipped,
        "mismatches": list(result.mismatches),
        "pending_updates": result.pending_updates,
    }


def auto_dependants(facts: Any, names: Iterable[str]) -> list[str]:
    """Return the sorted auto glyphs that FontLab rebuilds when ``names`` change.

    ``facts`` is a ``history.AutoFacts``. Chains through manual composites
    count. Glyphs in ``names`` are never listed.
    """
    wanted = set(names)
    found: set[str] = set()
    for name in wanted:
        found.update(facts.dependants(name))
    return sorted(found - wanted)


def rebuild_note(found: list[str]) -> str:
    """Warn that FontLab rebuilds auto composites when it is told about their bases.

    Name at most ``NOTE_LIMIT`` glyphs. An empty list gives ``""``.
    """
    if not found:
        return ""
    shown = ", ".join(found[:NOTE_LIMIT])
    if len(found) > NOTE_LIMIT:
        shown += f" +{len(found) - NOTE_LIMIT} more"
    return (
        f"FontLab rebuilds auto glyphs {shown}; their anchors and locks may change "
        "and Undo does not restore them"
    )


def muted(widget: Any) -> str:
    """Return a dimmed text colour (``#AARRGGBB``) from the widget palette."""
    gui = _native("PythonQt").QtGui
    color = gui.QColor(widget.palette.color(gui.QPalette.WindowText))
    color.setAlpha(150)
    return color.name(gui.QColor.HexArgb)


def make_table(headers: list[str]) -> Any:
    """Return a read-only preview ``QTableWidget`` with a stretched layout.

    The first column fits its contents; the other columns stretch. No edit, no
    selection, alternating rows, no grid, no horizontal scroll bar.
    """
    qt = _native("PythonQt")
    gui, core = qt.QtGui, qt.QtCore
    table = gui.QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(gui.QAbstractItemView.NoEditTriggers)
    table.setSelectionMode(gui.QAbstractItemView.NoSelection)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    header = table.horizontalHeader()
    header.setSectionResizeMode(gui.QHeaderView.Stretch)
    header.setSectionResizeMode(0, gui.QHeaderView.ResizeToContents)
    table.setHorizontalScrollBarPolicy(core.Qt.ScrollBarAlwaysOff)
    table.setMinimumHeight(220)
    return table


def panel_type() -> type:
    """Return the ``MetricsPanel`` base class (a PythonQt ``QDialog``).

    The class loads PythonQt, so call this inside FontLab only. Subclass it and
    set ``TITLE``, ``KEY``, ``HEADERS`` and ``ACCENT``. Fill in the hooks
    ``build``, ``subtitle_hint`` and ``planner``; optionally override
    ``target_glyphs``, ``empty_message`` and ``sync_controls``. See
    ``fontlabapp.metrics.panel.ui.MetricsPanel`` for the full contract.
    """
    from fontlabapp.metrics.panel.ui import MetricsPanel

    return MetricsPanel


__all__ = [
    "ALLOW_AUTO_LABEL",
    "AUTO_GLYPH_NOTE",
    "AUTO_LAYER_NOTE",
    "LINK_FIELDS",
    "LINK_NOTE",
    "MAX_NAMES",
    "MAX_ROWS",
    "MISSING_NOTE",
    "NOTE_LIMIT",
    "READ_BACK_TOLERANCE",
    "Entry",
    "LayerPlan",
    "Planner",
    "auto_dependants",
    "auto_skipped",
    "commit",
    "has_metrics_link",
    "ink_edges",
    "make_plan",
    "make_table",
    "master_layers",
    "muted",
    "panel_type",
    "pending",
    "read_back",
    "rebuild_note",
    "shift_and_set",
    "survey",
    "unit",
]
