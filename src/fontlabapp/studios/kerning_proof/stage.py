# this_file: src/fontlabapp/studios/kerning_proof/stage.py
# SPDX-License-Identifier: Apache-2.0
"""Preview and apply the original complete symmetry plan without re-planning writes."""

from collections.abc import Callable
from time import monotonic
from typing import Any

from fontlabapp.core.scripting import kerning_tool_backends

native = kerning_tool_backends().symmetry
model = kerning_tool_backends().symmetry_model


def deadline_check() -> Callable[[], None]:
    """Bound each capture/planning operation with the existing 2.5-second budget."""
    end = monotonic() + 2.5

    def check() -> None:
        if monotonic() >= end:
            raise TimeoutError("Kerning symmetry deadline reached before writing; preview again.")

    return check


class SymmetryStage:
    """An accepted plan retains ordered glyph/class identities until Apply."""

    def __init__(self, package: Callable[[], Any]) -> None:
        self.package = package
        self.before: Any = None
        self.result: Any = None

    def target(self) -> Any:
        package = self.package()
        if package is None:
            raise ValueError("Open a font before previewing Kerning Symmetry.")
        return package

    def preview(self) -> dict:
        """Discard an older plan before capture, so a failed preview cannot enable Apply."""
        self.before, self.result = None, None
        check = deadline_check()
        package = self.target()
        before = native.capture(package, check)
        result = model.plan(before.kerning, tuple(name for _, _, name in before.bindings), check=check)
        if native.capture(package, check) != before:
            raise ValueError("Font targets, kerning or class order changed; preview again.")
        self.before, self.result = before, result
        report = native.describe(result, False)
        report['result'] = 'Preview only; no kerning written.'
        return report

    def ready(self) -> bool:
        return self.result is not None and any(self.result.edits.values())

    def apply(self) -> dict:
        """Refuse stale input and preserve the shared writer's partial-failure diagnostic."""
        if self.result is None:
            raise ValueError("Preview Changes before applying symmetry.")
        before, result = self.before, self.result
        self.before, self.result = None, None
        check = deadline_check()
        package = self.target()
        if native.capture(package, check) != before:
            raise ValueError("Font targets, kerning or class order changed; preview again.")
        check()
        applied = native.write_kerning(package, result.edits, model.TITLE, expected=before.kerning)
        return native.describe(result, applied)
