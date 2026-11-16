# this_file: src/fontlabapp/core/signals/deferred.py
"""Coalesce ordered targets for one persistent zero-delay Qt timer.

The caller injects its Qt namespace and target processor. This module imports
no binding and knows no font, host, foreign-object or disposal policy. Use the
queue only in the timer's thread. Retain it for the process lifetime: its one
signal connection and parentless timer deliberately remain connected, including
while the timeout callback runs. This avoids teardown inside native dispatch.
"""

from collections.abc import Callable
from typing import Any, Generic, TypeVar

Target = TypeVar('Target')


class DeferredBatch(Generic[Target]):
    """Own one single-shot timer and an equality-coalesced target queue.

    Every schedule restarts the zero timer, including duplicate targets. A
    timeout detaches the current queue before processing it in insertion order.
    Work scheduled during processing belongs to a fresh batch; nested event
    loops can dispatch that batch immediately. The caller must retain any
    dispatch-depth refusal and error sink it needs. Processor failures propagate
    unchanged and abandon the unattempted detached tail, matching the donor.
    """

    def __init__(self, qt: Any, process: Callable[[Target], Any]) -> None:
        self.pending: list[Target] = []
        self._process = process
        self.timer = qt.QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(0)
        self.timer.timeout.connect(self._run)

    def schedule(self, target: Target) -> None:
        """Retain the first equal target, then start or restart the timer."""
        if target not in self.pending:
            self.pending.append(target)
        self.timer.start()

    def _run(self) -> None:
        """Detach one batch and call its processor without changing errors."""
        pending, self.pending = self.pending, []
        for target in pending:
            self._process(target)
