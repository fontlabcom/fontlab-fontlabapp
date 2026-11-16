# this_file: src/fontlabapp/studios/spacing_studio/model.py
# SPDX-License-Identifier: Apache-2.0
"""Spacing Studio arithmetic: sidebearing plans, offsets, comparisons and base-first order.

What: Qt-free functions over whole font units. ``Metrics`` is one layer's
measured state; each rule (``tuned``, ``equalized``, ``centred``, ``copied``,
``synced``, ``italic``) returns the new left and right sidebearings (and
width) that ``make_plan`` turns into a ``Plan``: the outline shift ``dx`` and
the new advance. ``order_plans`` puts bases before composites per master and
removes the plan of any composite whose base moves in the same step, so no
outline is moved twice (App TODO:37, Scriptmix TODO:74).
Why: The maths of the nine absorbed Scriptmix metrics scripts and the Layer
Metric Comparison example, kept testable without FontLab.
Used by ``fontlabapp.studios.spacing_studio.session`` and ``.tabs``.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from math import floor
from typing import Any, NamedTuple

LIMIT = 2000
OFFSET_LIMIT = 100
EMPTY_NOTE = "empty (no outline)"
NEGATIVE_NOTE = "negative width (skipped)"
MISSING_NOTE = "no layer in this master"
AUTO_LAYER_NOTE = "auto layer (skipped)"
AUTO_GLYPH_NOTE = "glyph has auto layers (skipped)"
LINK_NOTE = "metrics link or expression (skipped)"
OPERATIONS = (("Add", "add"), ("Set to", "set"), ("Scale %", "scale"))
EQUALIZE_RULES = (
    ("Average of both (keep width)", "average"),
    ("Both = LSB", "lsb"),
    ("Both = RSB", "rsb"),
    ("Both = the smaller", "min"),
    ("Both = the larger", "max"),
)
WIDTH_MODES = (("Keep current width", "keep"), ("Set width to", "set"), ("Change width by", "add"))
WIDTH_DEFAULT = 500
COPY_MODES = (
    ("LSB and RSB", "both"),
    ("LSB only", "lsb"),
    ("RSB only", "rsb"),
    ("Advance width (centred)", "width"),
)
SYNC_RULES = (("Proportional to ink width", True), ("Same values", False))
ITALIC_MODES = (("Add to italic sidebearings", "add"), ("Set italic sidebearings to", "set"))
MEASURES = ("Advance", "Width", "Height", "Left", "Right")
COMPARE_MODES = ("Difference", "Percent")
DEFAULT_STRINGS = "HHOHOOH nnonoon"


def unit(value: float) -> int:
    """Round half up to a whole font unit, as the Metrics panels do."""
    return int(floor(value + 0.5))


class Metrics(NamedTuple):
    """One layer: whole-unit sidebearings, its advance and its ink extent."""

    lsb: int
    rsb: int
    width: float
    left: float
    right: float

    @property
    def ink(self) -> int:
        return unit(self.right) - unit(self.left)


class Plan(NamedTuple):
    """Move the outline by ``dx`` and set the advance to ``width``."""

    dx: int
    width: float
    lsb: int
    rsb: int
    changed: bool


def measure(edges: tuple[float, float] | None, width: float) -> Metrics | None:
    """``Metrics`` from ink ``edges`` (left, right) and the advance; None when empty."""
    if edges is None:
        return None
    left, right = edges
    return Metrics(unit(left), unit(width - right), width, left, right)


def make_plan(before: Metrics, lsb: int, rsb: int, width: float | None = None) -> Plan | str:
    """The ``Plan`` that gives ``before`` the sidebearings ``lsb``/``rsb``; a note when impossible."""
    new_width = lsb + before.ink + rsb if width is None else width
    if new_width < 0:
        return NEGATIVE_NOTE
    if lsb == before.lsb and rsb == before.rsb and width is None:
        new_width = before.width  # keep a fractional advance that nothing changes
    dx = lsb - before.lsb
    return Plan(dx, new_width, lsb, rsb, bool(dx) or new_width != before.width)


def tuned(current: int, mode: str, value: float) -> int:
    """Sidebearings Tuner: add ``value``, set to it, or scale by ``value`` percent."""
    if mode == "set":
        return int(value)
    if mode == "add":
        return current + int(value)
    if mode == "scale":
        return unit(current * value / 100)
    raise ValueError(f"Unknown operation {mode!r}.")


def tune(before: Metrics, mode: str, lsb: float | None, rsb: float | None) -> Plan | str:
    """Apply ``tuned`` to each side given; None keeps that side."""
    new_lsb = before.lsb if lsb is None else tuned(before.lsb, mode, lsb)
    new_rsb = before.rsb if rsb is None else tuned(before.rsb, mode, rsb)
    return make_plan(before, new_lsb, new_rsb)


def equalized(lsb: int, rsb: int, rule: str) -> tuple[int, int]:
    """Equalize Sidebearings: both sides from one rule."""
    if rule == "average":
        left = (lsb + rsb) // 2
        return left, lsb + rsb - left
    side = {"lsb": lsb, "rsb": rsb, "min": min(lsb, rsb), "max": max(lsb, rsb)}.get(rule)
    if side is None:
        raise ValueError(f"Unknown rule {rule!r}.")
    return side, side


def equalize(before: Metrics, rule: str) -> Plan | str:
    return make_plan(before, *equalized(before.lsb, before.rsb, rule))


def centred(before: Metrics, mode: str, value: float) -> Plan | str:
    """Centre In Advance: centre the ink in the kept, set or changed advance."""
    old = unit(before.width)
    new_width = {"keep": old, "set": int(value), "add": old + int(value)}[mode]
    ink = before.ink
    if new_width < 0:
        return NEGATIVE_NOTE
    new_lsb = (new_width - ink) // 2
    return make_plan(before, new_lsb, new_width - ink - new_lsb, new_width)


def copied(before: Metrics, reference: tuple[int, int, float], mode: str, offset: int) -> Plan | str:
    """Copy Metrics From Reference: ``reference`` is (lsb, rsb, width) of the same master."""
    ref_lsb, ref_rsb, ref_width = reference
    if mode == "width":
        new_width = unit(ref_width) + offset
        change = new_width - unit(before.width)
        left = int(change / 2)
        return make_plan(before, before.lsb + left, before.rsb + change - left, new_width)
    lsb = ref_lsb + offset if mode in ("both", "lsb") else before.lsb
    rsb = ref_rsb + offset if mode in ("both", "rsb") else before.rsb
    return make_plan(before, lsb, rsb)


def synced(before: Metrics, reference: Metrics, proportional: bool) -> Plan | str:
    """Sync Sidebearings: the reference master's sidebearings, scaled by ink width when proportional."""
    ink = reference.right - reference.left
    factor = (before.right - before.left) / ink if proportional and ink > 0 else 1
    lsb = reference.left
    rsb = reference.width - reference.right
    return make_plan(before, unit(lsb * factor), unit(rsb * factor))


def italic(
    before: Metrics, edges: tuple[float, float], mode: str, lsb: float | None, rsb: float | None
) -> Plan | str:
    """Italic Sidebearings: change the de-slanted (italic) sidebearings ``edges`` describe."""
    width = before.width
    ilsb, irsb = edges[0], width - edges[1]
    new_ilsb = ilsb if lsb is None else (ilsb + lsb if mode == "add" else lsb)
    new_irsb = irsb if rsb is None else (irsb + rsb if mode == "add" else rsb)
    dx = unit(new_ilsb - ilsb)
    new_width = unit(width + dx + (new_irsb - irsb))
    if new_width < 0:
        return NEGATIVE_NOTE
    lsb_after = before.lsb + dx
    return Plan(dx, new_width, lsb_after, unit(new_width - before.right - dx), bool(dx) or new_width != width)


def offset_rows(rows: Iterable[tuple[str, Metrics | None]], offset: int) -> list[tuple[str, str, str, str]]:
    """Sidebearing Offset Preview: (name, new LSB, new RSB, advance); the advance never changes."""
    if not isinstance(offset, int) or isinstance(offset, bool) or abs(offset) > OFFSET_LIMIT:
        raise ValueError(f"Offset must be an integer from -{OFFSET_LIMIT} to {OFFSET_LIMIT}.")
    result = []
    for name, metrics in rows:
        if metrics is None:
            result.append((name, "", "", ""))
        else:
            result.append((name, str(metrics.lsb + offset), str(metrics.rsb - offset), f"{metrics.width:g}"))
    return result


def measure_value(metrics: Metrics | None, height: float | None, which: str) -> float | None:
    """One Layer Metric Comparison measurement; None when an empty layer has no such value."""
    if which == "Advance":
        return None if metrics is None else metrics.width
    if metrics is None:
        return None
    return {
        "Width": metrics.right - metrics.left,
        "Height": height,
        "Left": metrics.left,
        "Right": metrics.width - metrics.right,
    }[which]


def compared(value: float | None, reference: float | None, mode: str) -> str:
    """Signed difference or percentage of ``reference``; blank when undefined (never substituted)."""
    if value is None or reference is None:
        return ""
    if mode == "Percent":
        return "" if reference == 0 else f"{value / reference * 100:.1f}%"
    return f"{value - reference:+g}"


def subject(names: Sequence[str]) -> str:
    """Undo-label subject: the glyph name, or ``"N glyphs"`` for several."""
    unique = list(dict.fromkeys(names))
    return unique[0] if len(unique) == 1 else f"{len(unique)} glyphs"


def order_plans(
    entries: Sequence[tuple[str, str, Plan | None, str]], users: Mapping[str, Iterable[str]]
) -> list[tuple[str, str, Plan | None, str]]:
    """Bases before composites per master; drop the plan of a composite whose base moves.

    ``entries`` are ``(glyph, master, plan or None, note)``; ``users`` maps a
    base to the glyphs that use it as a component (followed through chains).
    A composite inherits its base's outline shift, so shifting it too would
    move that component twice: it is kept unchanged with a note instead.
    """
    moving = {(g, m) for g, m, plan, _note in entries if plan is not None and plan.dx}
    affected: dict[tuple[str, str], str] = {}
    for base, master in sorted(moving):
        seen, todo = {base}, [base]
        while todo:
            for name in sorted(users.get(todo.pop(), ())):
                if name not in seen:
                    seen.add(name)
                    todo.append(name)
                    affected.setdefault((name, master), base)
    result = []
    for glyph, master, plan, note in entries:
        base = affected.get((glyph, master))
        if plan is not None and base is not None:
            result.append((glyph, master, None, f"{glyph}: skipped; its base {base} moves in this step"))
        else:
            result.append((glyph, master, plan, note))
    depth = _depths(users)
    # Stable depth ordering keeps captured glyph/master order for independent rows.
    return sorted(result, key=lambda e: depth.get(e[0], 0))


def _depths(users: Mapping[str, Iterable[str]]) -> dict[str, int]:
    """Component depth: 0 for a glyph used by nobody's base chain, base < its users."""
    depth: dict[str, int] = {}
    todo = [(base, 0) for base in users]
    while todo:
        name, level = todo.pop()
        if depth.get(name, -1) >= level or level > len(users) + 1:
            continue
        depth[name] = level
        todo.extend((user, level + 1) for user in users.get(name, ()))
    return depth


Planner = Callable[[str, Metrics, Any, str], "Plan | str"]

__all__ = [
    "COMPARE_MODES",
    "COPY_MODES",
    "DEFAULT_STRINGS",
    "EQUALIZE_RULES",
    "ITALIC_MODES",
    "MEASURES",
    "OPERATIONS",
    "SYNC_RULES",
    "WIDTH_MODES",
    "Metrics",
    "Plan",
    "centred",
    "compared",
    "copied",
    "equalize",
    "equalized",
    "italic",
    "make_plan",
    "measure",
    "measure_value",
    "offset_rows",
    "order_plans",
    "subject",
    "synced",
    "tune",
    "tuned",
    "unit",
]
