# this_file: src/fontlabapp/glyphs/case_coverage/targets.py
# SPDX-License-Identifier: Apache-2.0
"""Explicit FontLab proof targets; never invent an inactive per-font MRU order."""

from dataclasses import dataclass
from collections.abc import Callable
from fontlabapp.glyphs.case_coverage.capture import FontReport, Snapshot


@dataclass(frozen=True)
class Target:
    """Exact registered package, canvas and text-block identities."""

    package_id: int
    canvas_id: int
    block_id: int
    label: str


class TargetChoiceRequired(ValueError):
    """A nonmodal caller must ask for these exact ambiguous view choices."""

    def __init__(self, targets: dict[int, tuple[Target, ...]]) -> None:
        """Retain explicit choices or failed cleanup state for the owned caller."""
        super().__init__(
            "Choose the existing proof view for each font, then click Report again."
        )
        self.targets = targets
        self.snapshot: Snapshot | None = None


def choose(
    fonts: tuple[FontReport, ...],
    targets: tuple[Target, ...],
    active_block: int | None,
    reuse: bool,
    choices: dict[int, tuple[int, int]],
    *,
    check: Callable = lambda: None,
) -> dict[int, Target | None]:
    """Reuse active/unique targets, ask for ambiguous views, or explicitly create.

    FontLab exposes no per-font MRU getter. This source-verified adaptation
    preserves every reuse outcome via explicit selection instead of claiming
    equivalence to Glyphs' remembered current tab. Empty proof scopes do nothing.
    """
    result, required = {}, {}
    for font in fonts:
        check()
        if not font.report["proof"]:
            continue
        candidates = []
        for target in targets:
            check()
            if target.package_id == font.identity:
                candidates.append(target)
        selected = choices.get(font.identity)
        if not reuse or not candidates:
            result[font.identity] = None
        elif selected is not None:
            match = None
            for candidate in candidates:
                check()
                if (candidate.canvas_id, candidate.block_id) == selected:
                    match = candidate
                    break
            if match is None:
                raise ValueError(
                    "The selected proof view changed or closed; choose it again."
                )
            result[font.identity] = match
        else:
            active = None
            for candidate in candidates:
                check()
                if candidate.block_id == active_block:
                    active = candidate
                    break
            if active is not None or len(candidates) == 1:
                result[font.identity] = active or candidates[0]
            else:
                required[font.identity] = tuple(candidates)
    check()
    if required:
        raise TargetChoiceRequired(required)
    return result


class ProofFailure(RuntimeError):
    """Retain complete analysis while clearly separating failed proof delivery."""

    def __init__(self, snapshot: Snapshot, cause: Exception) -> None:
        """Keep all diagnostics and the exact proof failure for the owned caller."""
        super().__init__("Analysis is complete; proof delivery failed: " + str(cause))
        self.snapshot, self.cause = snapshot, cause
