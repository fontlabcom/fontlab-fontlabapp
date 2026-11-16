# this_file: src/fontlabapp/studios/align_nudge/session.py
# SPDX-License-Identifier: Apache-2.0
"""Align & Nudge studio state: the Transform Studio ``Studio`` under its own name.

Why: reads, plans, ghost preview, hinted-layer opt-in and the one-step
``AppShell.history`` write are identical; only the window name, and so every
Undo label (``"Align & Nudge: <action> <subject>"``), differs.
"""

from fontlabapp.studios.transform_studio.session import Row
from fontlabapp.studios.transform_studio.session import Studio as _Base

from . import APP


class Studio(_Base):
    """Shared state of one Align & Nudge window."""

    APP = APP


__all__ = ["Row", "Studio"]
