# this_file: src/fontlabapp/kerning/symmetry/native.py
# SPDX-License-Identifier: Apache-2.0
"""Capture exact configured glyphs/groups, then use the accepted batch writer.

No glyph/auto-layer notifications, Output writes or UI selection mutations.
Native full-font history/cache/save/reopen qualification remains separate.
"""

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import Any

from fontlabapp.kerning.batch import KerningSnapshot, snapshot_kerning, write_kerning
from fontlabapp.kerning.symmetry.model import KEY, TITLE, TOKENS, Plan, plan
from fontlabapp.core.scripting import current_package


@dataclass(frozen=True)
class Capture:
    """Ordered group identity is separate because dictionary equality ignores order."""

    kerning: KerningSnapshot
    bindings: tuple[tuple[str, int, str], ...]
    group_order: tuple


def capture(package: Any, check: Callable[[], None]) -> Capture:
    """Read explicit data and original asDict class order, without active-master edits."""
    check()
    before = snapshot_kerning(package, typed=True)
    bindings = []
    for token in TOKENS:
        check()
        glyph = (
            package.findName(token[1:])
            if token.startswith("/")
            else package.findUnicode(ord(token))
        )
        if glyph is None or glyph.isNull:
            raise ValueError(
                f"Missing required symmetry target: {token}. No targets were omitted."
            )
        name = glyph.name
        if not name:
            raise ValueError(f"Symmetry target needs a nonempty glyph name: {token}.")
        bindings.append((token, glyph.id, name))
    groups = {}
    for master in before.masters:
        check()
        groups[master] = {
            name: (tuple(members), mode)
            for name, (members, mode) in package.kerning(master).groups.asDict().items()
        }
    if groups != before.groups:
        raise ValueError("Kerning groups changed during capture; run again.")
    check()
    ordered = tuple(
        (master, tuple(values.items())) for master, values in groups.items()
    )
    facts = KerningSnapshot(
        before.package_id, before.masters, before.pairs, groups, typed=before.typed
    )
    return Capture(facts, tuple(bindings), ordered)


def describe(result: Plan, applied: bool) -> dict:
    """Retain all source mismatch/WARN rows, including superseded alias writes."""
    masters = []
    for master in result.masters:
        rows = [
            {
                "glyph_pair": list(row.glyphs),
                "forward": [
                    list(side) if isinstance(side, tuple) else side
                    for side in row.forward
                ],
                "reverse": [
                    list(side) if isinstance(side, tuple) else side
                    for side in row.reverse
                ],
                "before": list(row.before),
                "requested_value": row.value,
                "warning": row.warning,
                "operation": "delete both explicit keys"
                if row.value == 0
                else "set both directions",
            }
            for row in master.mismatches
        ]
        choices = [
            {
                "glyph": glyph,
                "side": side,
                "chosen_class": names[0],
                "competing_classes_in_native_order": list(names),
            }
            for glyph, side, names in master.ambiguities
        ]
        masters.append(
            {
                "master": master.name,
                "comparisons": master.comparisons,
                "mismatch_count": len(rows),
                "net_changed_keys": len(master.changes),
                "mismatches": rows,
                "class_ambiguities": choices,
            }
        )
    return {
        "applied": applied,
        "targets": list(TOKENS),
        "masters": masters,
        "skipped_masters": list(result.skipped),
        "zero_policy": "A requested zero deletes both explicit keys; equal existing zeros stay.",
        "result": "Kerning updated. Use Undo to restore."
        if applied
        else "No changes required.",
    }


def run(*, deadline: float | None = None) -> dict:
    """Execute the complete original operation with exact ordered stale-source refusal.

    Cooperative checks bound Python planning, not blocking native methods. The
    shared writer validates all masters/history/ranges before its first mutation.
    Its honest partial-failure exception is preserved for the owned diagnostic.
    """
    end = monotonic() + 2.5 if deadline is None else deadline

    def check() -> None:
        if monotonic() >= end:
            raise TimeoutError(
                "Kerning symmetry deadline reached before writing; run again."
            )

    package = current_package()
    if package is None:
        raise ValueError("Open a font before running Kerning Symmetry.")
    before = capture(package, check)
    result = plan(
        before.kerning, tuple(name for _, _, name in before.bindings), check=check
    )
    if capture(package, check) != before:
        raise ValueError(
            "Font targets, kerning or class order changed; run again before applying."
        )
    check()
    applied = write_kerning(package, result.edits, TITLE, expected=before.kerning)
    return describe(result, applied)


def show() -> Any:
    """Apply immediately, then replace only this tool's owned diagnostic panel."""
    from fontlabapp.proof.reports.model import show_report

    try:
        report = run()
    except Exception as error:  # noqa: BLE001 - native errors belong in the owned result
        report = {"error": str(error)}
    try:
        return show_report(report, title=TITLE, key=KEY)
    except Exception as error:
        if report.get("applied"):
            raise RuntimeError(
                f"Kerning was applied; use Undo to restore it. Result display failed: {error}"
            ) from error
        if report.get("error"):
            raise RuntimeError(
                f"{report['error']} Result display failed: {error}"
            ) from error
        raise
