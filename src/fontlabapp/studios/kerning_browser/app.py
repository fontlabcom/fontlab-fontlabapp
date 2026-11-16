# this_file: src/fontlabapp/studios/kerning_browser/app.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Browser window assembly: shell, shared ``Tool`` state and the read-only TMetrics preview."""

from typing import Any

from .. import _kerning_app
from . import APP, register_tabs


def tool_for(shell: Any) -> Any:
    """The ``Tool`` of ``shell``, created on first use."""
    return _kerning_app.tool_for(shell, APP)


def _show(parent: Any = None, *, package: Any = None, font: Any = None, preview: Any = None, consolidated: bool = False) -> Any:
    """Open Kerning Browser for the current font; return the shell.

    ``package``/``font`` are getters and ``preview`` a factory ``(shell, tool)``
    (tests inject them); by default the live package, Fontport font and an
    embedded control-less read-only TMetrics are used.
    """
    from fontlabapp.studios import TabSpec

    shell = _kerning_app.show(APP, register_tabs, parent=parent, package=package, font=font, preview=preview)
    shell.set_about("Kerning Browser\nInspect exact pairs, classes, masters, exceptions and persistence risks. "
                    "Ticked exceptions are removed only by their named Apply action.\n"
                    "Source: https://github.com/fontlabcom/fontlab-fontlabapp\n"
                    "Credits: FontLab App contributors; Simon Cozens, Kern Optimizer / Energy (MIT), "
                    "https://github.com/simoncozens/GlyphsScripts\n"
                    "Same Kerning Groups: independent rewrite after Reza Bohloul; source licence undeclared, "
                    "no original body copied. https://github.com/RezaBohloul/RezaBohloul")
    if consolidated:
        from .consolidated import GroupsPanel, PersistencePanel

        try:
            tool = tool_for(shell)
            for title, panel in (("Same groups", GroupsPanel), ("Persistence", PersistencePanel)):
                shell.add_tab(TabSpec(title, lambda owner, cls=panel: cls(tool).widget))
            _kerning_app.bind_actions(shell, tool)
            tool.reload()
        except BaseException:
            shell.close()
            raise
    return shell


def show(parent: Any = None, *, package: Any = None, font: Any = None, preview: Any = None, consolidated: bool = False) -> Any:
    """Open the Browser, retaining an existing consolidated owner on close refusal."""
    from .owner import open_owned

    def create() -> Any:
        return _show(parent, package=package, font=font, preview=preview, consolidated=consolidated)

    return open_owned(create) if consolidated else create()


__all__ = ["show", "tool_for"]
