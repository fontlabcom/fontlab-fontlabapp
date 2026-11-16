# this_file: src/fontlabapp/studios/kerning_batch/app.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Batch window assembly: shell, shared ``Tool`` state and the read-only TMetrics preview."""

from typing import Any

from .. import _kerning_app
from . import APP, register_tabs


def tool_for(shell: Any) -> Any:
    """The ``Tool`` of ``shell``, created on first use."""
    return _kerning_app.tool_for(shell, APP)


def show(parent: Any = None, *, package: Any = None, font: Any = None, preview: Any = None, consolidated: bool = False) -> Any:
    """Open Kerning Batch for the current font; return the shell.

    ``package``/``font`` are getters and ``preview`` a factory ``(shell, tool)``
    (tests inject them); by default the live package, Fontport font and an
    embedded control-less read-only TMetrics are used.
    """
    from . import TAB_TITLES

    shell = _kerning_app.show(APP, register_tabs, parent=parent, package=package, font=font, preview=preview,
                             tab_titles=TAB_TITLES[:-1] if consolidated else None)
    shell.set_about("Kerning Batch\nReview each planned pair before Apply; external kerning changes require a new preview.\n"
                    "Source: https://github.com/fontlabcom/fontlab-fontlabapp\n"
                    "Credits: FontLab App contributors; Science Gothic Cutoff: independent rewrite after "
                    "Vassil Kateliev / Karandash Type Foundry, source licence undeclared, no original body copied.\n"
                    "https://github.com/googlefonts/science-gothic")
    return shell


__all__ = ["show", "tool_for"]
