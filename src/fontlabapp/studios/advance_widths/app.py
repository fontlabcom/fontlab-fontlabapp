# this_file: src/fontlabapp/studios/advance_widths/app.py
# SPDX-License-Identifier: Apache-2.0
"""Advance Widths window assembly: shell, shared ``Tool`` state and the read-only TMetrics preview."""

from typing import Any

from .. import _kerning_app
from . import APP, register_tabs


def tool_for(shell: Any) -> Any:
    """The ``Tool`` of ``shell``, created on first use."""
    return _kerning_app.tool_for(shell, APP)


def show(parent: Any = None, *, package: Any = None, font: Any = None, preview: Any = None) -> Any:
    """Open Advance Widths for the current font; return the shell.

    ``package``/``font`` are getters and ``preview`` a factory ``(shell, tool)``
    (tests inject them); by default the live package, Fontport font and an
    embedded control-less read-only TMetrics are used.
    """
    shell = _kerning_app.show(APP, register_tabs, parent=parent, package=package, font=font, preview=preview)
    from .._kerning_ui import get

    for view in shell.kerning_tool.views:
        panel = view.__self__
        if hasattr(panel, "apply_button"):
            shell.set_actions(panel.widget, refresh=panel.refresh, preview=panel.refresh,
                              apply=panel.apply,
                              ready=lambda panel=panel: bool(get(panel.apply_button.isEnabled)))
    return shell


__all__ = ["show", "tool_for"]
