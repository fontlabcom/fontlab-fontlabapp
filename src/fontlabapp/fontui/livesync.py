# this_file: src/fontlabapp/fontui/livesync.py
# SPDX-License-Identifier: Apache-2.0
"""Echo suppression for windows that write to the font they follow.

What: ``Echo`` remembers the fingerprint a window produced after its own
successful write. When the follow callback later fires, ``Echo.stale(current)``
says whether the window must refresh: False only while the font still matches
that recorded fingerprint, so the window's own write does not reset it. Any
other fingerprint is an external change: the token is dropped and every later
call refreshes until the next own write records a new token.
Use: ``fontlabapp.fontui.tmetrics`` records after each LSB/RSB/width/kerning
write and checks in its follow callback.
Why: Qt-free so the rule is unit-tested without FontLab; fingerprints come
from ``fontlabapp.fontui.tmetrics_model.fingerprint``.
"""

__all__ = ["Echo"]


class Echo:
    """One-token echo filter over opaque fingerprint strings."""

    def __init__(self) -> None:
        self.token: str | None = None

    def record(self, fingerprint: str) -> None:
        """Remember ``fingerprint`` as the state the window's own write produced."""
        self.token = fingerprint

    def clear(self) -> None:
        """Forget the token; the next check refreshes."""
        self.token = None

    def stale(self, fingerprint: str) -> bool:
        """Return True when ``fingerprint`` is not the window's own echo.

        A match keeps the token (FontLab may report one write several times);
        a mismatch drops it, so a later return to that state still refreshes.
        """
        if self.token is not None and fingerprint == self.token:
            return False
        self.token = None
        return True
