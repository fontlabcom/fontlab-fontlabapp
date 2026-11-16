# this_file: src/fontlabapp/core/signals/scope.py
# SPDX-License-Identifier: Apache-2.0
"""Own exact signal pairs, fencing callbacks and retaining failed Close retries."""

from collections.abc import Callable
from typing import Any


class Scope:
    """A panel/editor owns this scope; it never disconnects another listener.

    False binding returns are failures; None-returning bindings remain valid.
    Close retry buttons drain last, after every other signal is disconnected.
    Failed records stay owned. A destroyed emitter needs reference release only.
    """

    def __init__(self, report: Callable[[Exception], None]) -> None:
        self.report = report
        self.records: list[tuple[Any, Callable, bool]] = []
        self.closed = self.dead = False
        self.error = ""

    def _report(self, error: Exception) -> None:
        self.error = str(error)
        try:
            self.report(error)
        except Exception as failure:  # noqa: BLE001 - reporting cannot escape Qt
            self.error += "; reporting failed: " + str(failure)

    def connect(
        self,
        signal: Any,
        call: Callable,
        *,
        closing: bool = False,
        retry: bool = False,
    ) -> None:
        if self.closed:
            raise RuntimeError("The owned signal scope is closed.")

        def guarded(*args: Any) -> None:
            if self.dead or (self.closed and not closing):
                return
            try:
                call(*args)
            except Exception as error:  # noqa: BLE001 - owned Qt callback boundary
                self._report(error)

        if signal.connect(guarded) is False:
            raise RuntimeError("Qt refused the owned signal connection.")
        self.records.append((signal, guarded, retry))

    def finish(self, *, destroyed: bool = False) -> bool:
        """Fence work, drain non-retry pairs first and refuse deletion on failure."""
        self.closed = True
        if destroyed:
            self.records.clear()
        for retry in (False, True):
            failed = []
            for signal, slot, last in reversed(self.records):
                if last != retry:
                    failed.append((signal, slot, last))
                    continue
                try:
                    if signal.disconnect(slot) is False:
                        raise RuntimeError("Qt refused the owned signal disconnection.")
                except Exception as error:  # noqa: BLE001 - preserve the failed owner
                    failed.append((signal, slot, last))
                    self._report(error)
            self.records[:] = reversed(failed)
            if any(last == retry for _, _, last in self.records):
                return False
        self.dead = True
        self.report = lambda error: None
        return True
