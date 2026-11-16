# this_file: src/fontlabapp/masters/text/sender.py
# SPDX-License-Identifier: Apache-2.0
"""Own one private-slot sender; retain failed disconnect/delete for recovery.

Unlike native_tabs.text_tab_sender, failed disconnect never deletes the emitter,
and body/cleanup exceptions remain aggregated. Existing consumers are unchanged.
The native connection signature is the same source-verified QString slot.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Pending:
    """Exact owned emitter/connection plus completed cleanup stages and failures."""

    emitter: Any
    connection: tuple
    connected: bool = False
    deleted: bool = False
    errors: list = field(default_factory=list)


PENDING: list[Pending] = []


def _release(item: Pending, check: Callable) -> None:
    """Check before/after each native cleanup primitive; retain unfinished work."""
    try:
        check()
        if item.connected:
            if item.emitter.disconnect(*item.connection) is False:
                raise RuntimeError("Comparison sender disconnection failed.")
            item.connected = False
            check()
        if not item.deleted:
            check()
            item.emitter.deleteLater()
            item.deleted = True
            check()
    except BaseException as error:
        item.errors.append(error)
        if not any(old is item for old in PENDING):
            PENDING.append(item)
        raise RuntimeError(
            "Comparison sender cleanup is incomplete; retained emitter fences new proofs."
        ) from error


def recover(*, check: Callable) -> None:
    """Explicit bounded retry; cancellation/deadline preserves all remaining handles."""
    check()
    for item in tuple(PENDING):
        check()
        _release(item, check)
        PENDING.remove(item)
        check()


@contextmanager
def sender(
    gui: Any, receiver: Any, check: Callable, cleanup: Callable
) -> Iterator[Any]:
    """Stage bootstrap before connect and preserve every action/cleanup failure."""
    check()
    if PENDING:
        raise ValueError(
            "Previous comparison sender cleanup is incomplete; recover it before retrying."
        )
    emitter = gui.QLineEdit()
    owned = Pending(
        emitter, ("textChanged(QString)", receiver, "doCreateTextBlock(QString)")
    )
    errors = []
    try:
        check()
        emitter.setText("fontlabapp-master-comparison-bootstrap")
        check()
        owned.connected = bool(emitter.connect(*owned.connection))
        check()
        if not owned.connected:
            raise RuntimeError("Comparison sender connection failed.")
        yield emitter
    except BaseException as error:
        errors.append(error)
    try:
        _release(owned, cleanup)
    except BaseException as error:
        errors.append(error)
    if len(errors) > 1:
        raise BaseExceptionGroup("Comparison body and sender cleanup failed.", errors)
    if errors:
        raise errors[0]
