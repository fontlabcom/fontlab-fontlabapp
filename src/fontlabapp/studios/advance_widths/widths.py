# this_file: src/fontlabapp/studios/advance_widths/widths.py
# SPDX-License-Identifier: Apache-2.0
"""Advance Widths plans, dry-run snapshots and the one write path. Qt-free.

What: the Scriptmix constants and planners of Round Advances, Scale
Advances, Tabular Width and Zero-Width Marks (copied unchanged), the layer
survey of ``fontlabapp.metrics.panel.model`` and ``apply``: it writes exactly
the entries a tab showed, refuses with "press Refresh" when a planned layer
changed after the dry run, and commits every layer through one
``AppShell.history`` call labelled ``"Advance Widths: <action> <subject>"``
(Issue 235 §1.3/§1.4). ``shift_and_set`` moves the outline and sets the
advance of each explicit layer, as the originals did.
Used by the tabs of ``fontlabapp.studios.advance_widths``.
"""

import math
import unicodedata
from collections.abc import Iterable
from typing import Any

from fontlabapp.core.scripting import advance_widths_backends

_backends = advance_widths_backends()
metrics_panel = _backends.panel

APP = "Advance Widths"
#: Shown when a planned layer changed between the dry run and Apply.
STALE = "Advance widths changed since the dry run; press Refresh."
#: Every partly-applied message ends with this hint (as Anchor Studio).
ROUNDING_NOTE = "Check Preferences > Rounding."

# Round Advances
STEP_DEFAULT = 10
#: Scriptmix TODO:76: the step now starts at 1; 2 to 100 behave as before.
STEP_MIN, STEP_MAX = 1, 100
DIRECTIONS = [("Nearest", "nearest"), ("Up", "up"), ("Down", "down")]
SOURCES = ["Selected glyphs", "All glyphs in the font"]

# Scale Advances
PERCENT_DEFAULT = 100.0

# Tabular Width
FIGURES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
]  # fmt: skip
CURRENCY = [
    "dollar", "cent", "sterling", "yen", "Euro", "euro", "currency", "franc", "lira",
    "rupee", "won",
]  # fmt: skip
SETS = [
    ("Figures (zero to nine)", FIGURES),
    ("Figures and currency signs", FIGURES + CURRENCY),
    ("Selected glyphs", None),
]
WIDTH_MODES = [("Widest in set, per master", "widest"), ("Fixed width", "fixed")]
FIXED_DEFAULT = 500

# Zero-Width Marks
PLACEMENTS = [
    ("Keep outline in place", "keep"),
    ("Hang left by the old width", "hang"),
    ("Centre ink on the origin", "centre"),
]
MARK_CATEGORIES = {"Mn", "Me"}
MAX_CODE_POINT = 0x10FFFF


def rounded(width: float, step: int, direction: str) -> int:
    """Return width as a multiple of step. A half goes up for "nearest"."""
    if direction == "up":
        return int(math.ceil(width / step) * step)
    if direction == "down":
        return int(math.floor(width / step) * step)
    return int(math.floor(width / step + 0.5) * step)


def round_planner(step: int, direction: str) -> metrics_panel.Planner:
    """Return the planner. It changes the advance only, never the outline."""

    def plan(layer: Any, master: str) -> metrics_panel.LayerPlan:
        width = layer.advanceWidth
        new = rounded(width, step, direction)
        return metrics_panel.make_plan(
            layer, 0, new, (f"{width:g}", str(new), f"{new - width:+g}")
        )

    return plan


def scaled(width: float, percent: float) -> tuple[int, int]:
    """Return the new width and the outline shift for a scale in percent.

    The shift is half of the width change, cut toward zero. The right
    sidebearing takes the odd unit.
    """
    new_width = metrics_panel.unit(width * percent / 100.0)
    return new_width, int((new_width - metrics_panel.unit(width)) / 2)


def scale_planner(percent: float) -> metrics_panel.Planner:
    """Return the planner for one percentage."""

    def plan(layer: Any, master: str) -> metrics_panel.LayerPlan:
        width = layer.advanceWidth
        new_width, dx = scaled(width, percent)
        return metrics_panel.make_plan(
            layer, dx, new_width, (f"{width:g}", str(new_width), f"{dx:+d}")
        )

    return plan


def target_widths(
    glyphs: list[Any], masters: list[str], mode: str, fixed: int
) -> dict[str, int]:
    """Map master to the shared width: the widest advance of the group, or the fixed value."""
    if mode == "fixed":
        return dict.fromkeys(masters, fixed)
    widest: dict[str, int] = {}
    for glyph in glyphs:
        for master, layer in metrics_panel.master_layers(glyph, masters).items():
            widest[master] = max(
                widest.get(master, 0), metrics_panel.unit(layer.advanceWidth)
            )
    return widest


def tabular_planner(widths: dict[str, int]) -> metrics_panel.Planner:
    """Return the planner. widths maps master name to the shared width."""

    def plan(layer: Any, master: str) -> metrics_panel.LayerPlan | str:
        edges = metrics_panel.ink_edges(layer)
        if edges is None:
            return "empty (no outline)"
        new_width = widths[master]
        lsb = metrics_panel.unit(edges[0])
        new_lsb = (new_width - (metrics_panel.unit(edges[1]) - lsb)) // 2
        cells = (
            f"{metrics_panel.unit(layer.advanceWidth)}",
            f"{new_width}",
            f"{lsb}",
            f"{new_lsb}",
        )
        return metrics_panel.make_plan(layer, new_lsb - lsb, new_width, cells)

    return plan


def is_mark(glyph: Any, unicodes: Any = ()) -> bool:
    """True for a name that ends in "comb" or any code point of category Mn or Me.

    ``flGlyph`` has no Unicode binding; callers pass
    ``package.fgPackage[str(glyph.name)].unicodes`` (as App ``glyphs.identity.read``).
    """
    if glyph.name.split(".")[0].endswith("comb"):
        return True
    return any(
        0 <= int(code) <= MAX_CODE_POINT
        and unicodedata.category(chr(int(code))) in MARK_CATEGORIES
        for code in unicodes
    )


def glyph_unicodes(package: Any, glyph: Any) -> Any:
    """Return the glyph's code points from FontGate. Refuse a glyph FontGate lacks."""
    entry = package.fgPackage[str(glyph.name)]
    if entry is None:
        raise ValueError(
            f"Cannot read Unicode values for {glyph.name}: it has no FontGate glyph."
            " Clear Only combining marks, or save and reopen the font."
        )
    return entry.unicodes


def zero_planner(placement: str) -> metrics_panel.Planner:
    """Return the planner. The new advance is always 0."""

    def plan(layer: Any, master: str) -> metrics_panel.LayerPlan:
        width = metrics_panel.unit(layer.advanceWidth)
        dx = 0
        if placement == "hang":
            dx = -width
        elif placement == "centre":
            edges = metrics_panel.ink_edges(layer)
            if edges is not None:
                dx = -metrics_panel.unit((edges[0] + edges[1]) / 2)
        return metrics_panel.make_plan(layer, dx, 0, (f"{width}", "0", f"{dx:+d}"))

    return plan


def plural(count: int, word: str) -> str:
    """``"1 layer"`` or ``"2 layers"``."""
    return f"{count} {word}{'' if count == 1 else 's'}"


def subject(names: Iterable[str]) -> str:
    """Undo-label subject: the glyph name, or ``"N glyphs"`` for several."""
    unique = list(dict.fromkeys(names))
    return unique[0] if len(unique) == 1 else f"{len(unique)} glyphs"


def find_glyphs(package: Any, names: Iterable[str]) -> list[Any]:
    """The existing glyphs of ``names`` in ``package``, in order."""
    found = (package.findName(name) for name in names)
    return [glyph for glyph in found if glyph is not None and not glyph.isNull]


def auto_facts(package: Any) -> Any:
    """Whole-font auto-layer facts (``core.history.glyphs.scan_auto_facts``)."""
    return _backends.history.scan_auto_facts(package)


def survey(glyphs: list[Any], masters: list[str], planner: Any, facts: Any) -> list[Any]:
    """``metrics.panel.model.survey``: one ``Entry`` per glyph and master, with skip notes."""
    return metrics_panel.survey(glyphs, masters, planner, facts=facts)


def pending(entries: list[Any]) -> list[Any]:
    """The entries whose plan changes the layer."""
    return metrics_panel.pending(entries)


def rebuild_note(facts: Any, names: Iterable[str]) -> str:
    """FontLab's auto-glyph rebuild warning for ``names``, or ``""``."""
    found = metrics_panel.auto_dependants(facts, names)
    return metrics_panel.rebuild_note(found) if found else ""


def width_report(glyphs: list[Any], masters: list[str]) -> list[tuple]:
    """Width Table rows: ``proof.inspectors.model.report`` (name, widths, progression)."""
    return _backends.inspectors.report(glyphs, masters)


def master_order(package: Any) -> list[str]:
    """Width Chart masters: ``masters.inspect.model.master_order`` (first-axis order)."""
    return _backends.masters.master_order(package)


def master_widths(glyph: Any, masters: list[str]) -> list[tuple[str, float | None]]:
    """Width Chart points: ``masters.inspect.model.widths``."""
    return _backends.masters.widths(glyph, masters)


def check_tabular() -> Any:
    """Check Tabular Widths: ``metrics.tabular_width.model.capture()`` (reads only)."""
    return _backends.tabular.capture()


def state(layer: Any) -> tuple:
    """What a planned layer looked like: its advance and ink edges."""
    return float(layer.advanceWidth), metrics_panel.ink_edges(layer)


def fingerprint(entries: list[Any]) -> tuple:
    """The dry-run snapshot of ``entries``: (glyph, master, advance, ink edges)."""
    return tuple((e.glyph.name, e.master, *state(e.layer)) for e in entries)


def live_fingerprint(package: Any, entries: list[Any]) -> tuple | None:
    """The same snapshot re-read from ``package`` by name; None when a glyph or layer is gone."""
    rows = []
    for entry in entries:
        glyph = package.findName(entry.glyph.name)
        layer = None if glyph is None or glyph.isNull else metrics_panel.master_layers(glyph, [entry.master]).get(entry.master)
        if layer is None:
            return None
        rows.append((entry.glyph.name, entry.master, *state(layer)))
    return tuple(rows)


def apply(tool: Any, action: str, work: list[Any], shown: tuple, *, allow_bases: bool = False) -> bool:
    """Write exactly ``work`` (the shown pending entries) as one named Undo step.

    ``shown`` is ``fingerprint(work)`` from the dry run; a different live
    state raises ``ValueError(STALE)`` before any write. Return True when
    FontLab committed; a refusal leaves the shell's status text and returns False.
    """
    if not work:
        raise ValueError("Nothing to change.")
    if tool.package is None or live_fingerprint(tool.package, work) != shown:
        raise ValueError(STALE)
    label = f"{APP}: {action} {subject(e.glyph.name for e in work)}"
    glyphs = list({e.glyph.name: e.glyph for e in work}.values())
    before = [metrics_panel.ink_edges(e.layer) for e in work]

    def mutate() -> None:
        for entry in work:
            metrics_panel.shift_and_set(entry.layer, entry.plan.dx, entry.plan.width)

    def read_back() -> list[str]:
        return [text for entry, old in zip(work, before, strict=True) for text in metrics_panel.read_back(entry, old)]

    committed = tool.shell.history(label, glyphs, mutate, layers=[e.layer for e in work],
                                   read_back=read_back, allow_bases=allow_bases)  # fmt: skip
    if committed is None:
        return False
    if committed.mismatches:
        tool.say(f"Partly applied: {label}. " + "; ".join(committed.mismatches) + f". {ROUNDING_NOTE}")
        return True
    note = f" · {committed.pending_note}" if committed.pending_note else ""
    tool.say(f"{label}. Changed {plural(len(work), 'layer')} in {plural(len(glyphs), 'glyph')}{note}")
    return True


__all__ = [
    "APP", "CURRENCY", "DIRECTIONS", "FIGURES", "FIXED_DEFAULT", "MARK_CATEGORIES", "MAX_CODE_POINT",
    "PERCENT_DEFAULT", "PLACEMENTS", "ROUNDING_NOTE", "SETS", "SOURCES", "STALE", "STEP_DEFAULT", "STEP_MAX",
    "STEP_MIN", "WIDTH_MODES", "apply", "auto_facts", "check_tabular", "find_glyphs", "fingerprint", "glyph_unicodes", "is_mark", "live_fingerprint", "master_order", "master_widths",
    "pending", "plural", "rebuild_note", "round_planner", "rounded", "scale_planner", "scaled", "state", "subject",
    "survey", "tabular_planner", "target_widths", "width_report", "zero_planner",
]
