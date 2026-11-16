# this_file: src/fontlabapp/kerning/symmetry/model.py
# SPDX-License-Identifier: Apache-2.0
"""Independent Science Gothic symmetry planning; original source is not copied.

Keep every configured occurrence, original class priority and sequential writes.
A requested zero deletes an explicit pair, matching FontGate's native setter.
"""

from collections.abc import Callable
from dataclasses import dataclass
from itertools import combinations
from math import isfinite

from fontlabapp.kerning.batch import KerningSnapshot
from fontlabapp.kerning.identity import Pair

# Preserve the original seven named targets followed by its 21 single characters.
TOKENS = ("/a.sc", "/v.sc", "/w.sc", "/y.sc", "/t.sc", "/x.sc", "/o.sc") + tuple(
    "AVWYUX80TOovwx:!*|`.-"
)

TITLE, KEY = "Kerning Symmetry", "kerning-symmetry"


@dataclass(frozen=True)
class Mismatch:
    """One original comparison, including intermediate alias-dependent values."""

    glyphs: tuple[str, str]
    forward: Pair
    reverse: Pair
    before: tuple[float | None, float | None]
    value: float

    @property
    def warning(self) -> bool:
        """The original WARN means one explicit direction was absent."""
        return None in self.before


@dataclass(frozen=True)
class MasterPlan:
    """Ordered original diagnostics and net changes for one included master."""

    name: str
    comparisons: int
    mismatches: tuple[Mismatch, ...]
    changes: tuple[tuple[Pair, float | None], ...]
    ambiguities: tuple[tuple[str, str, tuple[str, ...]], ...]


@dataclass(frozen=True)
class Plan:
    """Whole batch tied to the exact prior explicit pairs/classes/masters."""

    before: KerningSnapshot
    masters: tuple[MasterPlan, ...]
    skipped: tuple[str, ...]

    @property
    def edits(self) -> dict:
        """Produce native typed identities or the original legacy plan representation."""
        return {master.name: dict(master.changes) for master in self.masters}


def symmetric_value(one: float | None, two: float | None) -> float | None:
    """Retain absence, numeric-min versus mean, and Python ties-even fives."""
    for value in (one, two):
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
        ):
            raise ValueError("Symmetry needs finite numeric kerning values.")
    if one is None or two is None:
        return two if one is None else one
    target = min(one, two) if abs(abs(one) - abs(two)) <= 10 else (one + two) / 2
    return float(5 * round(target / 5))


def _resolve(
    groups: dict, names: tuple[str, ...], *, typed: bool
) -> tuple[dict, tuple]:
    """Prioritize side-specific classes; retain their captured native order."""
    modes = {mode for _, mode in groups.values()}
    if not {"KernLeft", "KernRight"} <= modes:
        raise ValueError(
            "Original symmetry requires KernLeft and KernRight class categories."
        )
    resolved, ambiguous = {}, []
    for name in dict.fromkeys(names):
        for side in ("KernLeft", "KernRight"):
            specific = tuple(
                key
                for key, (members, mode) in groups.items()
                if mode == side and name in members
            )
            both = tuple(
                key
                for key, (members, mode) in groups.items()
                if mode == "KernBothSide" and name in members
            )
            choices = specific or both
            if typed:
                resolved[name, side] = (
                    (choices[0], "groupMode") if choices else (name, "glyphMode")
                )
            else:
                resolved[name, side] = "@" + choices[0] if choices else name
            if len(choices) > 1:
                ambiguous.append((name, side, choices))
    return resolved, tuple(ambiguous)


def _master(
    name: str,
    groups: dict,
    pairs: dict,
    names: tuple[str, ...],
    check: Callable[[], None],
    *,
    typed: bool,
) -> MasterPlan:
    """Simulate the original order so aliased pairs see earlier operations."""
    resolved, ambiguous = _resolve(groups, names, typed=typed)
    values, mismatches, count = dict(pairs), [], 0
    for left, right in combinations(names, 2):
        check()
        count += 1
        forward = resolved[left, "KernLeft"], resolved[right, "KernRight"]
        reverse = resolved[right, "KernLeft"], resolved[left, "KernRight"]
        before = values.get(forward), values.get(reverse)
        if before[0] == before[1]:
            continue
        value = symmetric_value(*before)
        mismatches.append(Mismatch((left, right), forward, reverse, before, value))
        for key in (forward, reverse):
            if value == 0:
                values.pop(key, None)
            else:
                values[key] = value
    keys = dict.fromkeys((*pairs, *values))
    changes = tuple(
        (key, values.get(key))
        for key in keys
        if (key in pairs) != (key in values) or pairs.get(key) != values.get(key)
    )
    return MasterPlan(name, count, tuple(mismatches), changes, ambiguous)


def plan(
    before: KerningSnapshot,
    names: tuple[str, ...],
    *,
    check: Callable[[], None] = lambda: None,
) -> Plan:
    """Plan all 378 comparisons per original non-# / non-Ctr master before writes."""
    if len(names) != len(TOKENS):
        raise ValueError("All 28 configured target occurrences are required.")
    masters, skipped = [], []
    for master in before.masters:
        check()
        if "#" in master or "Ctr" in master:
            skipped.append(master)
        else:
            masters.append(
                _master(
                    master,
                    before.groups[master],
                    before.pairs[master],
                    names,
                    check,
                    typed=before.typed,
                )
            )
    return Plan(before, tuple(masters), tuple(skipped))


def show():
    """Run the complete write and show owned diagnostics through Fly/App."""
    from fontlabapp.kerning.symmetry.native import show as show_native

    return show_native()
