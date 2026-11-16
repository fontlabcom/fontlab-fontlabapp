# this_file: src/fontlabapp/contours/angularizzle/session.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
"""Bound original Angularizzle Process/Cancel state to detached layer snapshots.

The native adapter stages complete copies, validates source/context and retains
diagnosed recovery state on late failures. This module supplies no native writer.
"""

from dataclasses import dataclass, replace
from itertools import pairwise
from time import monotonic
from typing import Protocol

from fontlabapp.contours.angularizzle.model import (
    Path,
    Segment,
    _check_deadline,
    angularize,
    line_nodes,
)

ACTION_SECONDS = 2.0


@dataclass(frozen=True)
class LayerSnapshot:
    """A bound target's detached geometry and source color index."""

    key: str
    paths: tuple[Path, ...]
    color: int | None


@dataclass(frozen=True)
class Capture:
    """Opening context and ordered target records, including duplicate targets."""

    context: str
    layers: tuple[LayerSnapshot, ...]
    inputs: tuple[LayerSnapshot, ...] | None = None


class Backend(Protocol):
    """Native ownership, whole-plan staging, history and diagnosed write edge.

    A post-mutation failure must retain a recoverable history state, diagnose
    any incomplete rollback and poison the writer. Do not promise atomicity
    through native setters whose exact restoration is not exposed.
    """

    def capture(self, deadline: float) -> Capture: ...

    def check(self, source: Capture, *, selection: bool, deadline: float) -> None: ...

    def apply(
        self,
        source: Capture,
        before: tuple[LayerSnapshot, ...],
        after: tuple[LayerSnapshot, ...],
        *,
        restore: bool,
        deadline: float,
    ) -> None: ...


def parse_plane(text: str) -> int:
    """Accept original decimal integer input above4; diagnose source crashes."""
    if not isinstance(text, str) or not text.isdecimal():
        raise ValueError("Minimum plane must be a decimal integer above4.")
    value = int(text)
    if value <= 4:
        raise ValueError("Minimum plane must be a decimal integer above4.")
    return value


def _path(points: tuple, deadline: float) -> Path:
    """Translate original line-node output, retaining an explicit empty path."""
    segments = []
    for a, b in pairwise((*points, *points[:1])):
        _check_deadline(deadline)
        segments.append(Segment((a, b)))
    return Path(tuple(segments))


def _plan(
    layer: LayerSnapshot, plane: int, detail: bool, deadline: float
) -> LayerSnapshot:
    """Source replaces all paths only when at least one closed path is sampled."""
    generated = angularize(layer.paths, plane, keep_detail=detail, deadline=deadline)
    paths = tuple(_path(line_nodes(path), deadline) for path in generated)
    return replace(layer, paths=paths if generated else layer.paths, color=8)


class Session:
    """Single Process previews restart opening paths; batch Process then closes.

    Target choice is the native adapter's explicit source contract. Repeated
    batch records process the previous result, exactly like the source loop.
    Cancel restores paths only, retaining the last color8. Window Close keeps
    processed data; parent destruction must not trigger a hidden native edit.
    """

    def __init__(self, backend: Backend) -> None:
        self.backend = backend
        self.closed = False
        self.processed = False
        deadline = monotonic() + ACTION_SECONDS
        self.source = backend.capture(deadline)
        _check_deadline(deadline)
        if not self.source.layers:
            raise ValueError("Select glyph layers before opening Angularizzle.")
        if self.source.inputs is not None and len(self.source.inputs) != len(
            self.source.layers
        ):
            raise ValueError(
                "Every selected input must have one bound first-layer target."
            )
        self.current: dict[str, LayerSnapshot] = {}
        for layer in self.source.layers:
            if layer.key in self.current and layer != self.current[layer.key]:
                raise ValueError("One bound target has conflicting opening snapshots.")
            self.current[layer.key] = layer
        self.batch = len(self.source.layers) > 1

    def process(self, text: str, keep_detail: bool) -> bool:
        """Compute every record before native apply; failed work stays open."""
        if self.closed:
            return False
        plane = parse_plane(text)
        deadline = monotonic() + ACTION_SECONDS
        self.backend.check(self.source, selection=True, deadline=deadline)
        draft = dict(self.current)
        for opening in self.source.layers:
            original = (
                draft[opening.key]
                if self.batch
                else replace(
                    opening, paths=(self.source.inputs or self.source.layers)[0].paths
                )
            )
            draft[opening.key] = _plan(original, plane, keep_detail, deadline)
        self.backend.check(self.source, selection=True, deadline=deadline)
        _check_deadline(deadline)
        self.backend.apply(
            self.source,
            tuple(self.current.values()),
            tuple(draft.values()),
            restore=False,
            deadline=deadline,
        )
        self.current, self.processed = draft, True
        self.closed = self.batch
        return True

    def cancel(self) -> bool:
        """Restore bound originals, preserving source color behavior, then close."""
        if self.closed:
            return False
        if self.processed:
            deadline = monotonic() + ACTION_SECONDS
            self.backend.check(self.source, selection=False, deadline=deadline)
            originals = {
                row.key: replace(row, color=self.current[row.key].color)
                for row in self.source.layers
            }
            _check_deadline(deadline)
            self.backend.apply(
                self.source,
                tuple(self.current.values()),
                tuple(originals.values()),
                restore=True,
                deadline=deadline,
            )
            self.current = originals
        self.closed = True
        return True

    def close(self) -> None:
        """Fence retained actions without mutating fonts during native teardown."""
        self.closed = True
