# this_file: src/fontlabapp/core/signals/callbacks.py
# SPDX-License-Identifier: MIT
"""Keep owned callbacks quiet during nested programmatic UI changes.

Controls check their ``_quiet`` flag before reporting user callbacks. Use
``with quiet_callbacks(control):`` around a programmatic update. Restore the
incoming flag after every exit, so inner updates cannot release outer scopes.
Other Qt signal receivers continue to run. No widget, binding or host is loaded.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol


class CallbackOwner(Protocol):
    """Python control wrapper with an existing callback suppression flag."""

    _quiet: bool


@contextmanager
def quiet_callbacks(owner: CallbackOwner) -> Iterator[None]:
    """Suppress this owner's callbacks until the scope exits.

    The owner must expose a writable ``_quiet`` boolean. This is intended for
    Python wrappers on their UI thread, including reentrant signal handlers.
    It neither blocks Qt signals nor changes connections, targets or ownership.
    Exceptions propagate after the prior flag is restored; data changes made
    inside the scope are not rolled back. Missing owner state refuses on entry.
    """
    previous = owner._quiet
    owner._quiet = True
    try:
        yield
    finally:
        owner._quiet = previous
