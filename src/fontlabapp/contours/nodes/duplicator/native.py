# this_file: src/fontlabapp/contours/nodes/duplicator/native.py
# SPDX-License-Identifier: Apache-2.0
"""Immediate native edit boundary for all three complete source policies.

Bounded twice-read source checks precede detached staging and one native history
operation. Exact whole-font Apply/Undo/Redo/save/reopen and selection-order native
qualification remain required; standalone tests are not that proof.
"""

from time import monotonic
from typing import Any

from fontlabapp import _native
from fontlabapp.contours.nodes.duplicator._capture import (
    capture,
    check,
    guard_dependencies,
    read_layer,
)
from fontlabapp.contours.nodes.duplicator._write import (
    WriteError,
    publish,
    representable,
    stage,
    verify,
)
from fontlabapp.contours.nodes.duplicator.model import Mode, plan
from fontlabapp.core.edit_guards import (
    pending_note,
    pending_updates,
    require_history_scope,
)


def execute(
    mode: Mode,
    *,
    native: Any = None,
    qt: Any = None,
    provider: Any = None,
    deadline: float | None = None,
    report: bool = True,
    expected: Any = None,
) -> dict:
    """Duplicate immediately; publish a complete result only after verification."""
    if mode not in ("current", "all", "handles"):
        raise ValueError("Unknown Node Duplicator profile.")
    deadline = monotonic() + 3 if deadline is None else deadline
    native, qt = native or _native("fontlab"), qt or _native("PythonQt")
    queued = pending_updates(native)
    before = capture(mode, deadline, native, provider)
    if expected is not None and before != expected:
        raise ValueError("Node duplication preview changed; preview again.")
    result = plan(before.source, mode)
    layer_names = {row[0]: row[1] for row in before.metadata}
    glyph_names = {row[1]: row[0] for row in before.dependencies}
    skipped_labels = tuple((glyph_names[layer], layer_names[layer], path, node)
                           for _, layer, path, node in result.skipped)
    check(deadline)
    changed = {o.layer for o in result.operations}
    names = {str(before.bound[k][0].name) for k in changed}
    guard_dependencies(before.dependencies, changed, names)
    representable(before, result)
    if result.operations:
        owners = {int(before.bound[key][0].id): before.bound[key][0] for key in changed}
        require_history_scope(list(owners.values()), native=native)
        check(deadline)
    staged = stage(before, result, native, qt, deadline)
    if capture(mode, deadline, native, provider) != before:
        raise ValueError(
            "Node duplication source, selection or context changed before history."
        )
    if result.operations:
        attached = publish(before, result, staged, native, qt, deadline)
        try:
            for row in result.layers:
                check(deadline)
                glyph, layer = before.bound[row.key]
                _, facts, _ = read_layer(layer, glyph, deadline)
                previous = next(f for f in before.metadata if f[0] == row.key)
                if facts[:7] != previous[:7]:
                    raise ValueError("Captured layer or shape metadata changed during insertion.")
                for p, path in enumerate(row.paths):
                    check(deadline)
                    contour = before.native_nodes[row.key][("path", p)]
                    actual = tuple(contour.nodes())
                    expected_ids = tuple(
                        int(staged[n.key].id) if n.key in staged else n.key
                        for n in path.nodes
                    )
                    if (
                        tuple(int(n.id) for n in actual) != expected_ids
                        or bool(contour.closed) != path.closed
                    ):
                        raise ValueError(
                            "Native post-write topology differs from the complete plan."
                        )
                    for node, expected in zip(actual, path.nodes, strict=True):
                        check(deadline)
                        if expected.key in staged:
                            verify(node, expected)
                        else:
                            old = before.native_nodes[row.key][expected.key]
                            # Old handles alias actual: immutable records, not wrapper
                            # self-comparison, establish retained raw geometry/metadata.
                            from fontlabapp.contours.nodes.duplicator._capture import (
                                node_record,
                            )

                            raw = dict(
                                before.metadata[
                                    next(
                                        i
                                        for i, m in enumerate(before.metadata)
                                        if m[0] == row.key
                                    )
                                ][7]
                            )
                            if (
                                int(old.nodeState) != raw[expected.key]
                                or node_record(old, expected.kind) != expected
                            ):
                                raise ValueError(
                                    "An original node changed during insertion."
                                )
            check(deadline)
        except BaseException as error:
            raise WriteError((error,), pending_nodes=attached, history_finalized=True) from error
    outcome = {
        "profile": mode,
        "inserted": result.inserted,
        "skipped": result.skipped,
        "skipped_labels": skipped_labels,
        "no_selection_message": result.no_selection_message,
        "native_acceptance": False,
        "pending_updates": queued,
        "pending_note": pending_note(queued),
    }
    if report and (result.no_selection_message or result.skipped or queued):
        from fontlabapp.contours.nodes.duplicator.ui import show_result

        show_result(outcome)
    return outcome


# Public entry point for the newly exposed original actions. Older rescued
# adapters lack this name, so those menu files cannot silently use stale guards.
duplicate_selected_nodes = execute
