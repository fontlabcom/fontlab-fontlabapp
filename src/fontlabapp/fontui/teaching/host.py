# this_file: src/fontlabapp/fontui/teaching/host.py
# SPDX-License-Identifier: Apache-2.0
"""Embed retained teaching panels without replacing their close protocols."""
from types import SimpleNamespace
from typing import Any

from PythonQt import QtCore

import fontlabapp.fontui as fontui
from fontlabapp.core.scripting import current_package
from fontlabapp.contours.nodes.coordinates import current_glyph
from fontlabapp.fontui.appshell import AppShell
from fontlabapp.fontui.lifecycle import Owned

OPEN: list[Any] = []


class TeachingShell(AppShell):
    """Keep failed owners reachable until every child acknowledges Close."""

    def close(self) -> None:
        super().close()
        if self in OPEN:
            OPEN.remove(self)


class PanelOwner(Owned):
    """Use the panel's original closeEvent; a refusal retains it for retry."""

    def __init__(self, parent: Any, panel: Any):
        super().__init__(parent)
        self.panel, self.panel_dead = panel, False
        panel.setParent(self.widget, QtCore.Qt.Widget)
        self.layout.addWidget(panel)
        self.connect(panel.destroyed, lambda *args: self._panel_destroyed(), closing=True)
        self._panel_connection = self.connections[-1]

    def _panel_destroyed(self) -> None:
        self.panel_dead = True
        self.connections[:] = [pair for pair in self.connections if pair is not self._panel_connection]

    def close(self) -> None:
        if not self._child_closed:
            if not self.panel_dead and self.panel.close() is False:
                raise RuntimeError("Teaching panel refused Close; retry after completing its task")
            self._child_closed = True
        super().close()


def create(title: str, preview: str | None = None, parent: Any = None,
           package: Any = None) -> TeachingShell:
    """Create an owned shell; callers construct all panels before showing it."""
    shell = TeachingShell(title, preview, parent=parent, package=package)
    OPEN.append(shell)
    shell.set_about(
        f"{title}\nChoose a named tab to explore its complete PythonQt profile.\n"
        "Source: https://github.com/fontlabcom/fontlab-python-examples\n"
        "Shared UI: https://github.com/fontlabcom/fontlab-fontlabapp\n"
        "Credits and original licences are retained in each source module and NOTICE."
    )
    return shell


def embed(shell: Any, title: str, panel: Any) -> PanelOwner:
    """Adopt one already constructed panel without opening another window."""
    return shell.add_tab(SimpleNamespace(title=title, build=lambda app: PanelOwner(app.tabs, panel)))


def finish(shell: Any) -> Any:
    """Show the completed shell, retaining it for the native menu lifetime."""
    shell.show()
    return shell


def bind_preview(shell: Any, font: Any, name: str | None = None,
                 layer: str | None = None) -> Any:
    """Bind a read-only preview to the captured font and layer."""
    if shell.preview_kind is None or font is None:
        return None
    options = dict(layer=layer, controls=False, read_only=True, hint_check=shell.hint_check)
    if shell.preview_kind == "tglyph":
        preview = fontui.glyph_view(font, shell.widget, name=name, **options)
    else:
        preview = fontui.metrics_preview(font, shell.widget, text="/" + name if name else None, **options)
    return shell.set_preview(preview)


def current_target() -> tuple[Any, str | None, str | None, tuple[Any, ...]]:
    """Resolve the active glyph through its actual package, including its layer."""
    package = current_package()
    glyph = current_glyph(package) if package is not None else None
    active = glyph.activeLayer if glyph is not None else None
    name = str(glyph.name) if glyph is not None else None
    layer = str(active.name) if active is not None else (
        str(package.defaultMaster) if package is not None else None
    )
    key = (package.id if package is not None else None, name,
           active.id if active is not None else None)
    return package, name, layer, key


def bind_current_preview(shell: Any) -> Any:
    """Capture the active font, glyph and exact layer; never retarget implicitly."""
    package, name, layer, key = current_target()
    font = fontui.current_font()
    shell._package = lambda: package
    preview = bind_preview(shell, font, name, layer)
    shell.preview_context = key
    return preview


def require_current_preview(shell: Any) -> None:
    """Refuse an action whose current target no longer matches the visible proof."""
    if getattr(shell, "preview_context", None) != current_target()[3]:
        raise ValueError("Font, glyph or layer changed. Refresh the preview before applying changes.")


def refresh_current_preview(shell: Any) -> Any:
    """Explicit Refresh replaces a captured proof only after its owner closes."""
    old = shell.preview
    if old is not None:
        old.close()
        if not old._close_complete:
            raise RuntimeError("Preview Close incomplete; retry Refresh")
        shell.preview_layout.removeWidget(old.widget)
        shell.children.remove(old)
        shell.preview = None
    shell.preview_context = None
    return bind_current_preview(shell)
