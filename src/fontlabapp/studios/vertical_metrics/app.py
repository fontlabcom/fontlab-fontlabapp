# this_file: src/fontlabapp/studios/vertical_metrics/app.py
# SPDX-License-Identifier: Apache-2.0
"""Vertical Metrics & Zones window assembly: shell, shared ``Tool`` state and the read-only TMetrics preview."""

from typing import Any

from .. import _kerning_app
from . import APP, register_tabs


def tool_for(shell: Any) -> Any:
    """The ``Tool`` of ``shell``, created on first use."""
    return _kerning_app.tool_for(shell, APP)


def show(
    parent: Any = None, *, package: Any = None, font: Any = None, preview: Any = None
) -> Any:
    """Open Vertical Metrics & Zones for the current font; return the shell.

    ``package``/``font`` are getters and ``preview`` a factory ``(shell, tool)``
    (tests inject them); by default the live package, Fontport font and an
    embedded control-less read-only TMetrics are used.
    """
    return configure(_kerning_app.show(
        APP, register_tabs, parent=parent, package=package, font=font, preview=preview
    ))


def show_font_metrics(parent: Any = None, *, package: Any = None, font: Any = None, preview: Any = None) -> Any:
    """Open the Font Info metrics table and whole-font calculation routes."""
    return configure(_kerning_app.show(APP, register_tabs, parent=parent, package=package, font=font,
                             preview=preview, title="Font Metrics", tab_titles=("Metrics table", "Calculate")))


def show_vertical_metrics(parent: Any = None, *, package: Any = None, font: Any = None, preview: Any = None) -> Any:
    """Open alignment zones and the vertical-metrics diagram."""
    return configure(_kerning_app.show(APP, register_tabs, parent=parent, package=package, font=font,
                             preview=preview, title="Vertical Metrics", tab_titles=("Zones", "Diagram")))


def configure(shell: Any) -> Any:
    """Keep editable metric drafts until explicit Apply or Discard preview."""
    from PythonQt import QtGui

    from .._kerning_ui import get
    from ..spacing_studio.staged import buttons
    from ._shared import MasterTable

    tool = shell.kerning_tool
    for view in tool.views:
        panel = view.__self__
        if not hasattr(panel, "apply_button"):
            continue
        preview = panel.edited if hasattr(panel, "values") else panel.refresh
        if hasattr(panel, "show_plan") and not hasattr(panel, "values"):
            preview = panel.show_plan
        shell.set_actions(panel.widget, refresh=panel.refresh, preview=preview,
                          apply=lambda panel=panel: apply_current(panel),
                          ready=lambda panel=panel: bool(get(panel.apply_button.isEnabled)),
                          dirty=lambda panel=panel: dirty(panel))
        for field in vars(panel).values():
            if isinstance(field, MasterTable):
                shell.connect(field.view.itemChanged, lambda *args: shell._update_actions())
            elif isinstance(field, QtGui.QComboBox):
                shell.connect(field.currentIndexChanged, lambda *args: shell._update_actions())
            elif isinstance(field, QtGui.QSpinBox):
                shell.connect(field.valueChanged, lambda *args: shell._update_actions())
            elif isinstance(field, QtGui.QCheckBox):
                shell.connect(field.toggled, lambda *args: shell._update_actions())
        for button in buttons(panel.layout):
            if button is panel.apply_button:
                button.clicked.disconnect()
                shell.connect(button.clicked, lambda *args, panel=panel: apply_current(panel))
            elif get(button.text) == "Refresh":
                button.clicked.disconnect()
                shell.connect(button.clicked, lambda *args: shell._run_action("refresh"))
            shell.connect(button.clicked, lambda *args: shell._update_actions())
        discard = QtGui.QPushButton("Discard preview", panel.widget)
        panel.layout.addWidget(discard)
        shell.connect(discard.clicked, lambda *args, panel=panel: panel.run(panel.refresh))
    return shell


def apply_current(panel: Any) -> Any:
    def apply() -> Any:
        panel.tool.shell.package()
        return panel.apply()
    return panel.run(apply)


def dirty(panel: Any) -> bool:
    """An invalid cell is still a draft even though it has no valid change list."""
    from .._kerning_ui import get

    if hasattr(panel, "values"):
        return any(panel.grid.cell(row, col + 1) != f"{number:g}"
                   for row, (_, values) in enumerate(panel.values) for col, number in enumerate(values))
    return bool(get(panel.apply_button.isEnabled))


__all__ = ["show", "show_font_metrics", "show_vertical_metrics", "tool_for"]
