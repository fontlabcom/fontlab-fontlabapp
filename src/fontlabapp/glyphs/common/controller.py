# this_file: src/fontlabapp/glyphs/common/controller.py
# SPDX-License-Identifier: Apache-2.0
"""Lazy complete-report launch; the full all-font label writer remains held."""

from collections.abc import Callable
from time import monotonic
from typing import Any
from fontlabapp import _native
from fontlabapp.glyphs.common.model import checkpoint
from fontlabapp.glyphs.common.capture import capture
import fontlabapp.glyphs.common.lifetime as lifetime
from fontlabapp.glyphs.common.lifetime import recover
from fontlabapp.glyphs.common.ui import panel_type

__all__ = ["show", "recover"]


def show(metadata: Callable, *, copy_sink: Callable | None = None) -> Any:
    """Capture first; replace only this owned panel with bounded failure cleanup.

    No current font is needed. A no-font/stale/metadata refusal allocates no new
    widget and never clears Output. A failed owner fences subsequent launches.
    """
    lifetime.require_clear()
    deadline = monotonic() + 3
    check = lambda: checkpoint(deadline - 0.5, monotonic)
    refresh = lambda **options: capture(metadata, **options)
    report = refresh(deadline=deadline - 0.5)
    check()
    old = lifetime.current()
    if old is not None:
        try:
            old.recover_owned(deadline)
            check()
        except Exception as error:
            lifetime.retain(old, error)
            raise
        lifetime.release(old)
    binding = _native("PythonQt")
    parent = _native("fontlab").MainWindow()
    check()
    panel = panel_type(binding.QtGui, qt=binding)(
        parent, report, refresh, deadline=deadline, copy_sink=copy_sink
    )
    lifetime.windows()[lifetime.KEY] = panel
    try:
        check()
        panel.setWindowFlags(
            panel.windowFlags() | binding.QtCore.Qt.WindowStaysOnTopHint
        )
        check()
        panel.show()
        check()
        panel.raise_()
        check()
    except Exception as error:
        try:
            checkpoint(deadline, monotonic)
            panel.recover_owned(deadline)
            checkpoint(deadline, monotonic)
        except Exception as cleanup:
            failure = ExceptionGroup(
                "Common Glyphs display and cleanup failed.", [error, cleanup]
            )
            lifetime.retain(panel, failure)
            raise failure
        lifetime.release(panel)
        raise
    return panel
