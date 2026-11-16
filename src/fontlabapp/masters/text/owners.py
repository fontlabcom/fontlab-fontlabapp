# this_file: src/fontlabapp/masters/text/owners.py
# SPDX-License-Identifier: Apache-2.0
"""Retain every failed panel owner and fence creation until bounded recovery.

The registry lives with the existing owned-window registry, surviving module
reloads. Recovery returns the original error receipts; it never replaces an
unresolved owner, implicitly retries cleanup or clears failures to permit launch.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
import sys
from time import monotonic
from typing import Any
from fontlabapp.masters.text.model import checkpoint

KEY = "master_text_failed"


@dataclass
class Held:
    owner: Any
    errors: list[BaseException] = field(default_factory=list)


def pending() -> dict[int, Held]:
    """Keep old scalar owners too; never overwrite a previous candidate's handle."""
    windows = sys.__dict__.setdefault("_fontlab_samples", {})
    raw = windows.get(KEY)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raw = {id(raw): Held(raw)}
        windows[KEY] = raw
    return raw


def retain(owner: Any, error: BaseException) -> Held:
    """Retain in constant time even after the cleanup deadline has expired."""
    owners = pending()
    record = owners.setdefault(id(owner), Held(owner))
    record.errors.append(error)
    sys.__dict__.setdefault("_fontlab_samples", {})[KEY] = owners
    return record


def release(owner: Any) -> None:
    """Remove only this confirmed retired identity, preserving all other owners."""
    owners = pending()
    owners.pop(id(owner), None)
    if not owners:
        sys.__dict__.get("_fontlab_samples", {}).pop(KEY, None)
    windows = sys.__dict__.get("_fontlab_samples", {})
    if windows.get("masters_text_comparison") is owner:
        windows.pop("masters_text_comparison")


def require_clear() -> None:
    """Fail before native capture/allocation while any owner remains unresolved."""
    if pending():
        raise RuntimeError(
            "Master Text Comparison cleanup is incomplete; explicitly recover retained owners before opening another panel."
        )


def recover(
    *, deadline: float, cancelled: Callable = lambda: False
) -> tuple[Held, ...]:
    """Retry only retained cleanup under ONE caller deadline, returning receipts.

    A failed recovery retains that owner and every error. Aggregate exceptions
    also expose recovered receipts for any earlier successful items in the batch.
    Native primitives cannot be preempted; owners check before/after each stage.
    """
    check = lambda: checkpoint(deadline, monotonic, cancelled)
    check()
    records = tuple(pending().values())
    check()
    done, errors = [], []
    for record in records:
        try:
            check()
            record.owner.recover_owned(deadline, cancelled=cancelled)
            check()
        except BaseException as error:
            record.errors.append(error)
            errors.append(error)
            if isinstance(error, (TimeoutError, InterruptedError)):
                break
        else:
            release(record.owner)
            done.append(record)
    if errors:
        failure = BaseExceptionGroup(
            "Comparison owner cleanup recovery failed.", errors
        )
        failure.recovered = tuple(done)
        raise failure
    return tuple(done)
