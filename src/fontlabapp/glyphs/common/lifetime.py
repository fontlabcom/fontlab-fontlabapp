# this_file: src/fontlabapp/glyphs/common/lifetime.py
# SPDX-License-Identifier: Apache-2.0
"""Keep exact Common Glyphs panel owners and every failed cleanup receipt.

Registry state survives reloads with the shared owned-window registry. Failed
owners fence creation until explicit bounded recovery; no silent retry/reset.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
import sys
from time import monotonic
from typing import Any
from fontlabapp.glyphs.common.model import checkpoint

KEY = "masters_common_glyphs"
FAILED = "common_glyphs_failed"


@dataclass
class Held:
    """One still-owned panel and original errors in occurrence order."""

    owner: Any
    errors: list[BaseException] = field(default_factory=list)


def windows() -> dict:
    """Reuse the application script registry without touching another key."""
    return sys.__dict__.setdefault("_fontlab_samples", {})


def current() -> Any:
    """Return only this tool's active owner, if any."""
    return windows().get(KEY)


def pending() -> dict[int, Held]:
    """Read retained failed owners without implicitly retrying cleanup."""
    return windows().get(FAILED, {})


def retain(owner: Any, error: BaseException) -> None:
    """Retain an owner and append the exact exception even after a timeout."""
    records = windows().setdefault(FAILED, {})
    records.setdefault(id(owner), Held(owner)).errors.append(error)


def release(owner: Any) -> None:
    """Release only this verified retired identity, preserving all other owners."""
    records = pending()
    records.pop(id(owner), None)
    if not records:
        windows().pop(FAILED, None)
    if current() is owner:
        windows().pop(KEY)


def require_clear() -> None:
    """Refuse capture/allocation while a previous cleanup remains incomplete."""
    if pending():
        raise RuntimeError(
            "Common Glyphs cleanup is incomplete; explicitly recover retained owners before opening another panel."
        )


def recover(
    *, deadline: float, cancelled: Callable = lambda: False
) -> tuple[Held, ...]:
    """Retry retained owners under one deadline and return original receipts.

    Failed/untouched owners remain retained. Aggregate failures expose any
    successful earlier receipts through ``recovered`` without discarding errors.
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
        except Exception as error:
            record.errors.append(error)
            errors.append(error)
            if isinstance(error, (TimeoutError, InterruptedError)):
                break
        else:
            release(record.owner)
            done.append(record)
    if errors:
        failure = ExceptionGroup("Common Glyphs cleanup recovery failed.", errors)
        failure.recovered = tuple(done)
        raise failure
    return tuple(done)
