# this_file: src/fontlabapp/proof/reports/model.py
# SPDX-License-Identifier: Apache-2.0
"""Format detached JSON snapshots; load the owned native report UI only on show."""

from collections.abc import Callable
import json
from time import monotonic
from typing import Any


def _check(deadline: float | None, clock: Callable, cancelled: Callable) -> None:
    """Keep optional report budgets/cancellation independent of a native binding."""
    if cancelled():
        raise InterruptedError("Report preparation was cancelled.")
    if deadline is not None and clock() >= deadline:
        raise TimeoutError(
            "Report preparation exceeded its deadline; no partial report was published."
        )


def format_report(
    report: Any,
    *,
    deadline: float | None = None,
    clock: Callable = monotonic,
    cancelled: Callable = lambda: False,
) -> str:
    """Serialize complete Unicode JSON; optional budgets check every encoder chunk.

    Default text is unchanged. Scalar formatting and final join are synchronous
    operations checked on return. Never truncate rows or publish partial JSON.
    """
    check = lambda: _check(deadline, clock, cancelled)
    check()
    chunks = []
    encoder = json.JSONEncoder(ensure_ascii=False, indent=2, allow_nan=False)
    for chunk in encoder.iterencode(report):
        check()
        chunks.append(chunk)
    check()
    text = "".join(chunks)
    check()
    return text


def show_report(
    report: Any,
    *,
    title: str = "Report",
    key: str = "json-report",
    deadline: float | None = None,
    clock: Callable = monotonic,
    cancelled: Callable = lambda: False,
) -> Any:
    """Show one read-only nonmodal snapshot; replace only the same owned key.

    Complete serialization precedes UI creation. Check before/after the native
    show call, which cannot be preempted. Overrun raises; an already opened
    complete report can remain. No active font/Output/preference API is touched.
    Existing callers retain their unbudgeted defaults and exact JSON text.
    """
    text = format_report(report, deadline=deadline, clock=clock, cancelled=cancelled)
    from fontlabapp.proof.reports.ui import show

    _check(deadline, clock, cancelled)
    window = show(text, title, key)
    _check(deadline, clock, cancelled)
    return window
