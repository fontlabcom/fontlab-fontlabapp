# this_file: src/fontlabapp/glyphs/case_coverage/cleanup.py
# SPDX-License-Identifier: Apache-2.0
"""Bound proof restoration; retain incomplete work and fence subsequent proofs."""

from collections.abc import Callable
from time import monotonic
from typing import Any
from fontlabapp.glyphs.case_coverage.model import checkpoint

PENDING: list["CleanupIncomplete"] = []


class CleanupIncomplete(RuntimeError):
    """Retain exact remaining native handles; callers must not claim success."""

    def __init__(
        self, pending: dict, context: tuple, context_pending: bool, errors: list
    ) -> None:
        """Retain explicit choices or failed cleanup state for the owned caller."""
        super().__init__(
            "Case Coverage cleanup is incomplete; proof work is fenced. "
            f"{len(pending)} shape states remain; context pending={context_pending}. "
            "Recover the retained cleanup under a new bounded deadline before retrying. "
            + (
                f"First error: {errors[0]}; {len(errors)} retained errors."
                if errors
                else ""
            )
        )
        self.pending_states, self.context, self.context_pending, self.errors = (
            pending,
            context,
            context_pending,
            errors,
        )


def restore(
    states: dict,
    workspace: Any,
    previous: Any,
    original: Any,
    tool: Any,
    check: Callable,
    *,
    panel: Any = None,
    context_pending: bool = True,
) -> None:
    """Stop setters at the cleanup deadline and retain every unfinished identity.

    Cancellation starts recovery, but the final cleanup deadline is never
    disabled. A synchronous native setter can overrun; check again immediately
    on return, retain the remainder and fence further proof actions.
    """
    # No setter runs before the first budget check; a failed check is retained below.
    pending = dict(states)
    errors = []
    context = (workspace, previous, original, tool, panel)
    try:
        check()
        if context_pending:
            try:
                tool.call("set_active_font", font_id=original.fg_id)
                check()
                if previous is not None:
                    workspace.setActiveCanvas(previous)
                    check()
                    if workspace.getActiveCanvas().id != previous.id:
                        raise ValueError(
                            "The original proof canvas could not be restored."
                        )
                workspace.activeFontPanel = panel
                check()
                context_pending = False
            except TimeoutError:
                raise
            except Exception as error:
                errors.append(error)
        for identity, (shape, active) in states.items():
            check()
            try:
                if shape.active != active:
                    shape.active = active
                pending.pop(identity)
            except Exception as error:
                errors.append(error)
            check()
    except TimeoutError as error:
        errors.append(error)
    if pending or context_pending or errors:
        error = CleanupIncomplete(pending, context, context_pending, errors)
        PENDING.append(error)
        raise error


def recover(*, deadline: float) -> None:
    """Explicitly retry retained cleanup; leave a replacement fence on failure."""
    check = lambda: checkpoint(deadline, monotonic, lambda: False)
    check()
    for old in tuple(PENDING):
        check()
        workspace, previous, original, tool, panel = old.context
        PENDING.remove(old)
        restore(
            old.pending_states,
            workspace,
            previous,
            original,
            tool,
            check,
            panel=panel,
            context_pending=old.context_pending,
        )
