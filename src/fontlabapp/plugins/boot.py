# this_file: src/fontlabapp/plugins/boot.py
"""One-call FontLab startup and explicit teardown."""

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from . import menu, registry
from .backend import select_backend
from .filters.host import FilterHost
from .general_plugins.host import GeneralHost
from .kinds import Services
from .reporters_panel import ReportersPanel
from .palettes.host import PaletteHost
from .tools.host import ToolHost


@dataclass
class _State:
    """Keep every Qt owner alive until uninstall has detached its signals."""

    config_dir: Path | None
    reporters: registry.Registry
    painters: Any
    menus: Any
    filters: FilterHost
    palettes: PaletteHost
    tools: ToolHost
    generals: GeneralHost
    reporters_panel: ReportersPanel
    extensions_dir: Path | None


_state: _State | None = None


def _error(error: Exception, source: object) -> None:
    """Log host errors without raising through native Qt callbacks."""
    try:
        print(f"fontlabapp.plugins {type(source).__name__}: {error}")
    except Exception:  # noqa: BLE001, S110 - native callback boundary
        pass


def _runtime() -> tuple[Any, Any, Any]:
    """Import PythonQt, FontLab and owned menus only inside FontLab."""
    qt = import_module("PythonQt")
    fontlab = import_module("fontlab")
    menus_cls = import_module("fontlabapp.qt.menus").OwnedMenus
    return qt, fontlab, menus_cls


def install(config_dir: str | Path | None = None, extensions_dir: str | Path | None = None) -> None:
    """Idempotently restore every plugin kind and its owned native hooks."""
    global _state
    path = None if config_dir is None else Path(config_dir)
    requested_path = path
    if _state is not None:
        if path != _state.config_dir or (extensions_dir is not None and Path(extensions_dir) != _state.extensions_dir):
            raise ValueError(
                "fontlabapp.plugins is already installed with another config directory"
            )
        return
    qt, fontlab, menus_cls = _runtime()
    if extensions_dir is None and hasattr(fontlab, "flPreferences"):
        value = fontlab.flPreferences().dataPathDefault
        value = value() if callable(value) else value
        if not value:
            raise RuntimeError("FontLab did not report its user data folder")
        user_data = Path(str(value)).expanduser().resolve()
        extensions_dir = user_data / "Extensions"
        if path is None:
            path = user_data / "Data"
    reporters = registry.configure(path, error_sink=_error, extensions_dir=extensions_dir)
    painters = select_backend(qt, fontlab, _error)
    menus = None
    filters = None
    palettes = None
    tools = None
    generals = None
    reporters_panel = None
    try:
        menus = menus_cls(qt, fontlab, error_sink=_error, owned_title="Plugmix")
        reporters.attach(painters, qt, _error)
        filters = FilterHost(Services(qt, fontlab, menus, painters, _error), reporters)
        filters.install()
        palettes = PaletteHost(
            Services(qt, fontlab, menus, painters, _error), reporters
        )
        panels_menu = menus.menu(menus.add_menu("Window", "Panels"))
        palettes.install(panels_menu)
        tools = ToolHost(Services(qt, fontlab, menus, painters, _error), reporters)
        tools.install()
        generals = GeneralHost(
            Services(qt, fontlab, menus, painters, _error), reporters, palettes
        )
        generals.install()
        reporters_panel = ReportersPanel(Services(qt, fontlab, menus, painters, _error), reporters)
        reporters_panel.install(panels_menu)
        menu.install(menus, reporters)  # last, so View > Reporters ends View
    except Exception:
        try:
            if reporters_panel is not None:
                reporters_panel.close()
            reporters.detach()
        finally:
            reporters.listeners.clear()
            try:
                try:
                    try:
                        if generals is not None:
                            generals.close()
                    finally:
                        try:
                            if tools is not None:
                                tools.close()
                        finally:
                            try:
                                if palettes is not None:
                                    palettes.close()
                            finally:
                                if filters is not None:
                                    filters.close()
                finally:
                    if menus is not None:
                        menus.close()
            finally:
                painters.close()
        raise
    _state = _State(
        requested_path, reporters, painters, menus, filters, palettes, tools, generals,
        reporters_panel, None if extensions_dir is None else Path(extensions_dir)
    )


def uninstall() -> None:
    """Remove actions and overlays while preserving saved enable choices."""
    global _state
    if _state is None:
        return
    state = _state
    # Palettes refuse cleanly and retry; close them before the Reporters panel
    # so a palette refusal cannot leave a retained state without its panel.
    if state.palettes.close() is False:
        return
    if getattr(state, "reporters_panel", None) is not None and state.reporters_panel.close() is False:
        return
    _state = None
    state.reporters.listeners.clear()
    try:
        try:
            try:
                try:
                    state.generals.close()
                finally:
                    state.tools.close()
            finally:
                state.filters.close()
        finally:
            state.menus.close()
    finally:
        try:
            state.reporters.detach()
        finally:
            state.painters.close()


def show_reporters() -> None:
    """Show the retained Reporters panel after idempotent core startup."""
    if _state is None:
        install()
    _state.reporters_panel.show()
