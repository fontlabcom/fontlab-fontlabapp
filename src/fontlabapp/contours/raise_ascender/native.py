# this_file: src/fontlabapp/contours/raise_ascender/native.py
# SPDX-License-Identifier: MIT AND Apache-2.0
"""Complete original target policies with explicit unsupported native boundaries.

Whole selection and first-parent ALL foreground layers remain the denominator.
Unknown associations, implicit editor slots, generated/hinted/automatic writers
are not silently omitted or claimed equivalent through refusal. Native history,
full metadata and save/reopen qualification remain required.
"""

from dataclasses import dataclass, field, replace
from threading import current_thread, main_thread
from time import monotonic
from typing import Any

from fontlabapp import _native
import fontlabapp.core.edit_guards as edit_guards
from fontlabapp.contours.raise_ascender._capture import (
    closure,
    dependencies,
    masters,
    selected,
)
from fontlabapp.contours.raise_ascender._geometry import prepare, read
from fontlabapp.contours.raise_ascender._write import run
from fontlabapp.contours.raise_ascender.model import (
    Layer,
    associated_master,
    check,
    plan,
)
from fontlabapp.core.scripting import current_package


@dataclass(frozen=True)
class Bound:
    """Compare captured facts while retaining exact native owners for attachment."""

    key: str
    name: str
    facts: tuple
    source: Layer
    glyph: Any = field(compare=False, repr=False)
    layer: Any = field(compare=False, repr=False)

@dataclass(frozen=True)
class Snapshot:
    """Entire target occurrence, named metrics and whole-font dependency fence."""

    context: tuple
    masters: tuple
    dependencies: tuple
    rows: tuple[Bound, ...]
    carriers: tuple = field(compare=False, repr=False)


class Backend:
    """Capture selection fresh per click while staying bound to the original font."""

    def __init__(self) -> None:
        package = current_package()
        self.identity = None if package is None else int(package.id)

    def capture(self, all_layers: bool, deadline: float) -> Snapshot:
        """Read full target order, geometry and source-master metrics twice."""
        if current_thread() is not main_thread():
            raise RuntimeError("Run Raise Ascender on the main UI thread.")
        first = self._read(all_layers, deadline)
        second = self._read(all_layers, deadline)
        check(deadline)
        if first != second:
            raise ValueError(
                "Font, selection, metrics or geometry changed during capture."
            )
        return second

    def _read(self, all_layers: bool, deadline: float) -> Snapshot:
        check(deadline)
        document, targets = selected(all_layers, deadline)
        package = document.package
        if int(package.id) != self.identity:
            raise ValueError(
                "The original font is no longer current; reopen Raise Ascender."
            )
        metrics = masters(package, deadline)
        mapping, rows = dict(metrics), []
        for glyph, layer in targets:
            check(deadline)
            if (
                int(layer.glyph.id) != int(glyph.id)
                or layer.isNull
                or not layer.isValid
            ):
                raise ValueError("Target layer owner or identity changed.")
            points, state, _ = read(layer, deadline)
            master = associated_master(str(layer.name), mapping)
            key = f"{int(glyph.id)}:{int(layer.id)}"
            facts = (
                int(glyph.id),
                int(layer.id),
                str(glyph.name),
                bool(layer.autoLayer),
                state,
            )
            rows.append(
                Bound(
                    key,
                    str(glyph.name),
                    facts,
                    Layer(key, None if master is None else mapping[master], points),
                    glyph,
                    layer,
                )
            )
        deps = dependencies(package, deadline)
        check(deadline)
        return Snapshot(document.context, metrics, deps, tuple(rows), document.carriers)

    def execute(
        self, amount: str, all_layers: bool, *, disclosure: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Stage the action and validate each sequential result.

        Return queue IDs and their date caveat with the counters. An optional
        disclosure mapping receives the caveat before history, including on
        failure; without a mapping, the caveat is printed for script callers.
        """
        pending = {"pending_updates": (), "pending_note": ""}
        edit_guards.disclose(pending, disclosure)
        deadline = monotonic() + 5
        before = self.capture(all_layers, deadline)
        steps = plan(tuple(row.source for row in before.rows), amount, deadline)
        touched = {
            row.name
            for row, step in zip(before.rows, steps, strict=True)
            if step.changed
        }
        affected = closure(before.dependencies, touched, deadline)
        for _, name, layers in before.dependencies:
            check(deadline)
            for _, _, auto, _ in layers:
                check(deadline)
                if auto and name in affected:
                    raise ValueError(
                        "Automatic dependants cannot yet preserve full native history; no partial action."
                    )
        if not touched:
            return {"occurrences": len(steps), "undo_steps": 0, "nodes": 0, **pending}
        native, qt = _native("fontlab"), _native("PythonQt")
        shapes, expected, work = {}, before, []
        for row, step in zip(before.rows, steps, strict=True):
            check(deadline)
            originals = shapes.get(row.key, tuple(row.layer.shapes))
            jobs, future = prepare(row.layer, step, originals, qt, deadline)
            shapes[row.key] = future
            points, state, _ = read(row.layer, deadline, future)
            facts = (*row.facts[:4], state)
            updated = tuple(
                replace(other, facts=facts, source=replace(other.source, points=points))
                if other.key == row.key
                else other
                for other in expected.rows
            )
            expected = replace(expected, rows=updated)
            dependants = self._dependants(row, before.dependencies, deadline)
            work.append(
                (row.glyph, row.layer, jobs, dependants, expected, step.changed)
            )
        if self.capture(all_layers, deadline) != before:
            raise ValueError("Source changed before history.")
        ids = edit_guards.pending_updates(native)
        pending = {"pending_updates": ids, "pending_note": edit_guards.pending_note(ids)}
        edit_guards.disclose(pending, disclosure)
        check(deadline)
        result = run(
            tuple(work),
            lambda expected: self.validate(expected, all_layers, deadline),
            native,
            qt,
            deadline,
        )
        return {**result, **pending}

    def validate(self, expected: Snapshot, all_layers: bool, deadline: float) -> None:
        """Refuse callback-driven geometry/selection/metric changes before later scopes."""
        if self.capture(all_layers, deadline) != expected:
            raise ValueError(
                "Native result or source changed; stop before later occurrences."
            )

    def _dependants(self, row: Bound, dependencies: tuple, deadline: float) -> tuple:
        """Enroll transitive normal component owners without notifying automatic layers."""
        affected, owners = closure(dependencies, {row.name}, deadline), []
        for identity, name, _ in dependencies:
            check(deadline)
            if name in affected and name != row.name:
                glyph = row.glyph.package.findName(name)
                if glyph is None or int(glyph.id) != identity:
                    raise ValueError("A component dependant identity changed.")
                owners.append(glyph)
        return tuple(owners)
