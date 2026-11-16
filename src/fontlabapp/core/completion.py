# this_file: src/fontlabapp/core/completion.py
"""Route native dialog completion through each script panel's full Close path.

Own terminal signal records separately from control callbacks. Qt removes a dying
emitter's own signals before destruction callbacks; do not disconnect them there.
This module imports no host and never edits a font or invokes application exec().
"""

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(eq=False)
class Completion:
    """Keep an owned panel's completion callbacks and tombstone outside Qt."""

    dialog: Any
    key: str
    hooks: list[tuple[Any, Callable[..., Any]]] = field(default_factory=list)
    on_destroyed: list[Callable[[], None]] = field(default_factory=list)
    closed: bool = False
    finishing: bool = False
    error: str = ""
    errors: list[str] = field(default_factory=list)

    def complete(self) -> None:
        """Use virtual Close so subclass timers, painters and source cleanup run."""
        if self.closed or self.finishing:
            return
        self.finishing = True
        try:
            dialog = self.dialog
            accepted = dialog.close()
            if not self.closed and accepted is not False:
                # Escape can already be inside Qt's native Close dispatcher.
                # Invoke the Python close handler explicitly in that case.
                from fontlabapp import _native

                event = _native("PythonQt").QtGui.QCloseEvent()
                type(dialog).closeEvent(dialog, event)
                accepted = event.isAccepted()
            if not self.closed and accepted is False:
                dialog.show()
        except Exception as error:  # noqa: BLE001 - contain native signal errors
            self.error = repr(error)
        finally:
            self.finishing = False

    def stop(self) -> None:
        """Disconnect the still-live emitter before normal owned deletion."""
        if self.closed:
            return
        self.closed = True
        self.dialog = None
        for signal, callback in reversed(self.hooks):
            try:
                signal.disconnect(callback)
            except Exception as error:  # noqa: BLE001 - attempt all owned disconnections
                self.errors.append(repr(error))
        self.hooks.clear()
        self.on_destroyed.clear()

    def destroyed(self) -> None:
        """Drop dead-emitter records, then run explicit caller destruction hooks."""
        if self.closed:
            return
        dialog, self.dialog = self.dialog, None
        self.closed = True
        self.hooks.clear()
        callbacks, self.on_destroyed = self.on_destroyed, []
        for callback in callbacks:
            try:
                callback()
            except Exception as error:  # noqa: BLE001 - do not escape QObject destruction
                self.errors.append(repr(error))
        windows = getattr(sys, "_fontlab_samples", {})
        if windows.get(self.key) is dialog:
            windows.pop(self.key)


def install(dialog: Any, key: str) -> Completion:
    """Connect plain functions, never native-slot/bound-method mixtures."""
    owner = Completion(dialog, key)
    for signal, callback in (
        (dialog.finished, lambda *args: owner.complete()),
        (dialog.destroyed, lambda *args: owner.destroyed()),
    ):
        signal.connect(callback)
        owner.hooks.append((signal, callback))
    return owner


def stop(dialog: Any) -> None:
    """Retain close_script_dialog compatibility for callers without this owner."""
    owner = getattr(dialog, "_completion_lifetime", None)
    if owner is not None:
        owner.stop()
