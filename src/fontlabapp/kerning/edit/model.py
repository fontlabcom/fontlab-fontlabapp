# this_file: src/fontlabapp/kerning/edit/model.py
# SPDX-License-Identifier: Apache-2.0
"""Plan the five menu editors without native writes or optional dependencies.

Native @class notation and explicit zero presence are retained. Scale/copy/snap
round halves away from zero; the original Pair Editor rounds typed cells with
Python's integer round. Writers validate every resulting whole-unit value.
"""

import math
from collections.abc import Iterable, Mapping
from typing import Any

from fontlabapp.core.scripting import kerning_class_lists, kerning_pairs

Pair = tuple[str, str]
Pairs = dict[Pair, float]
Edits = dict[str, dict[Pair, int | None]]
Changes = dict[str, dict[Pair, tuple[float, int | None]]]
Cell = tuple[Pair, str]
MIN_VALUE, MAX_VALUE = -(2**31), 2**31 - 1


def _pairs(package: Any, master: str) -> Pairs:
    """Reject unknown named masters before asking the native accessor for a view."""
    if master not in tuple(package.masters):
        raise ValueError(f"Unknown kerning master: {master}")
    return kerning_pairs(package, master)


def whole_value(value: float) -> int:
    """Require finite signed32 whole units, including exact native history values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Kerning needs a finite whole-unit number")  # noqa: TRY004 - one numeric input boundary
    if not math.isfinite(value) or value != int(value):
        raise ValueError(
            "Native kerning history cannot preserve fractional/nonfinite values"
        )
    if not MIN_VALUE <= value <= MAX_VALUE:
        raise ValueError("Kerning needs signed 32-bit whole-unit values")
    return int(value)


def scaled(value: float, percent: float) -> int:
    """Multiply by percent, with exact original halves-away rounding and bounds."""
    exact = value * percent / 100.0
    if not math.isfinite(exact):
        raise ValueError("Scale must produce a finite kerning value")
    return whole_value(int(math.copysign(math.floor(abs(exact) + 0.5), exact)))


def round_to(value: float, step: float) -> int:
    """Snap to a positive whole-unit step, with halves away from zero."""
    if whole_value(step) <= 0 or not math.isfinite(value):
        raise ValueError("Rounding step must be positive and value finite")
    return whole_value(
        int(math.copysign(math.floor(abs(value) / step + 0.5) * step, value))
    )


def copy_plan(
    source: Mapping[Pair, float],
    target: Mapping[Pair, float],
    mode: str,
    percent: float,
) -> dict[Pair, int | None]:
    """Stage replace, missing-only or matching-only edits without conflating zero/absence."""
    if mode not in {"replace", "missing", "matching"}:
        raise ValueError(f"Unknown copy mode: {mode}")
    edits = {}
    for pair, old in source.items():
        value = scaled(old, percent)
        if (mode == "missing" and pair in target) or (
            mode == "matching" and pair not in target
        ):
            continue
        if pair not in target or target[pair] != value:
            edits[pair] = value
    if mode == "replace":
        edits.update({pair: None for pair in target if pair not in source})
    return edits


def summary(
    target: Mapping[Pair, float], edits: Mapping[Pair, int | None]
) -> tuple[int, int, int]:
    """Count added/changed/deleted explicit pairs in one target's preview."""
    added = sum(
        value is not None and pair not in target for pair, value in edits.items()
    )
    removed = sum(value is None and pair in target for pair, value in edits.items())
    return added, len(edits) - added - removed, removed


def copy_run(
    package: Any,
    source_master: str,
    targets: list[str],
    mode: str,
    percent: float,
    *,
    expected: Any = None,
    undo_name: str,
) -> dict[str, tuple[int, int, int]]:
    """Build every target before the one multi-master native write; return preview counts."""
    from fontlabapp.kerning.batch import write_kerning

    source = _pairs(package, source_master)
    targets_values = {master: _pairs(package, master) for master in targets}
    edits = {
        master: copy_plan(source, target, mode, percent)
        for master, target in targets_values.items()
    }
    write_kerning(package, edits, undo_name, expected=expected)
    return {
        master: summary(targets_values[master], changes)
        for master, changes in edits.items()
    }


def _value_plan(
    package: Any,
    masters: Iterable[str],
    parameter: float,
    drop_zero: bool,
    *,
    snap: bool,
) -> Changes:
    """Build whole per-master previews; scale keeps existing zero pairs as the original does."""
    return plan_values({master: _pairs(package, master) for master in masters}, parameter, drop_zero, snap=snap)


def plan_values(pairs: Mapping[str, Pairs], parameter: float, drop_zero: bool, *, snap: bool) -> Changes:
    """Round (``snap``) or scale already-read ``{master: pairs}``, e.g. a kerning snapshot's pairs.

    The same rule as ``round_plan``/``scale_plan``; used by Kerning Batch so
    Apply writes exactly the plan built from the snapshot it shows.
    """
    todo = {}
    for master, values in pairs.items():
        items = {}
        for pair, old in values.items():
            new = round_to(old, parameter) if snap else scaled(old, parameter)
            if new == 0 and drop_zero and (snap or old != 0):
                items[pair] = old, None
            elif new != old:
                items[pair] = old, new
        todo[master] = items
    return todo


def scale_plan(
    package: Any, masters: list[str], percent: float, drop_zero: bool
) -> Changes:
    """Preview scaling with the original explicit-zero option semantics."""
    return _value_plan(package, masters, percent, drop_zero, snap=False)


def round_plan(package: Any, masters: list[str], step: int, drop_zero: bool) -> Changes:
    """Preview snapping, including existing zero deletion when requested."""
    return _value_plan(package, masters, step, drop_zero, snap=True)


def small_pairs(
    package: Any, masters: list[str], threshold: float
) -> dict[str, list[tuple[str, str, float]]]:
    """List strictly smaller magnitudes, ordered by magnitude then pair names."""
    if not math.isfinite(threshold) or threshold < 0:
        raise ValueError("Threshold must be finite and nonnegative")
    return small_values({master: _pairs(package, master) for master in masters}, threshold)


def small_values(
    pairs: Mapping[str, Pairs], threshold: float
) -> dict[str, list[tuple[str, str, float]]]:
    """``small_pairs`` over already-read ``{master: pairs}`` (a kerning snapshot's pairs)."""
    if not math.isfinite(threshold) or threshold < 0:
        raise ValueError("Threshold must be finite and nonnegative")
    return {
        master: sorted(
            [(a, b, value) for (a, b), value in values.items() if abs(value) < threshold],
            key=lambda row: (abs(row[2]), row[0], row[1]),
        )
        for master, values in pairs.items()
    }


def remove_run(
    package: Any,
    masters: list[str],
    threshold: float,
    *,
    expected: Any = None,
    undo_name: str,
) -> dict[str, int]:
    """Stage every small-pair deletion before one shared native write."""
    from fontlabapp.kerning.batch import write_kerning

    found = small_pairs(package, masters, threshold)
    write_kerning(
        package,
        {m: {(a, b): None for a, b, _ in rows} for m, rows in found.items()},
        undo_name,
        expected=expected,
    )
    return {master: len(rows) for master, rows in found.items()}


def class_sides(package: Any, master: str, glyph: str) -> tuple[str | None, str | None]:
    """Return the original first side-specific class for the selected glyph."""
    left, right, _ = kerning_class_lists(package, master)
    return next(iter(left.get(glyph, [])), None), next(iter(right.get(glyph, [])), None)


def involving(
    package: Any, masters: list[str], glyph: str
) -> dict[Pair, dict[str, float]]:
    """Collect explicit pairs involving the glyph or either original first-side class."""
    rows = {}
    for master in masters:
        left, right = class_sides(package, master, glyph)
        for pair, value in _pairs(package, master).items():
            if pair[0] in {glyph, left} or pair[1] in {glyph, right}:
                rows.setdefault(pair, {})[master] = value
    return rows


def parse_cell(text: str) -> int | None:
    """Parse blank as deletion and retain the original typed-cell integer rounding."""
    text = text.strip().replace("−", "-")
    if not text:
        return None
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("Kerning cell must be finite")
    return whole_value(round(value))


def stage_cell(
    staged: dict[Cell, int | None],
    errors: dict[Cell, str],
    key: Cell,
    text: str,
    old: float | None,
) -> bool:
    """Clear only the invalid cell's prior edit; preserve every other valid staged cell."""
    try:
        value = parse_cell(text)
    except ValueError:
        staged.pop(key, None)
        errors[key] = text
        return False
    errors.pop(key, None)
    if value == old:
        staged.pop(key, None)
    else:
        staged[key] = value
    return True


def native_side(name: str) -> tuple[str, bool]:
    """Retain original scripts' boolean explicit-key conversion interface."""
    return (name[1:], True) if name.startswith("@") else (name, False)


def write_kerning(package: Any, edits: Edits, undo_name: str) -> bool:
    """Provide the original programmatic writer interface through the safe batch."""
    from fontlabapp.kerning.batch import write_kerning as write_batch

    return write_batch(package, edits, undo_name)


def partner_exists(package: Any, masters: list[str], pair: Pair) -> bool:
    """Allow a new pair row if at least one master has its side-compatible names."""
    from fontlabapp.kerning.batch import validate_pair

    for master in masters:
        try:
            validate_pair(package, master, pair)
            return True
        except ValueError:
            continue
    return False
