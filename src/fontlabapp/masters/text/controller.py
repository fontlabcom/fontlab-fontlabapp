# this_file: src/fontlabapp/masters/text/controller.py
# SPDX-License-Identifier: Apache-2.0
"""Lazy shared launch boundary for the complete Master Text Comparison workflow."""

from pathlib import Path
from time import monotonic
from typing import Any
from fontlabapp import _native
from fontlabapp.masters.text.model import checkpoint
from fontlabapp.masters.text.capture import read
from fontlabapp.masters.text.ui import panel_type
from fontlabapp.masters.text.proof import open_proof
from fontlabapp.masters.text.owners import require_clear, recover
from fontlabapp.core.scripting import show_script_dialog

__all__ = ["show", "recover"]


def show(*, settings: Any = None, directory: Path | None = None) -> Any:
    """Bind the panel to the actual opening font, not the next current font.

    The original relative local preset lookup uses the opening working directory;
    callers/tests can inject another explicit local directory and owned settings.
    No font raises before allocating any owned panel or native sender.
    """
    require_clear()
    deadline = monotonic() + 3.0
    check = lambda: checkpoint(deadline - 0.5, monotonic, lambda: False)
    opening = read(deadline - 0.5, check=check)
    binding = _native("PythonQt")
    check()
    kind = panel_type(binding.QtCore, binding.QtGui)
    return show_script_dialog(
        lambda parent: kind(
            parent,
            opening,
            open_proof,
            settings=settings,
            directory=directory,
            deadline=deadline,
        ),
        "masters_text_comparison",
    )
