# this_file: src/fontlabapp/plugins/reporters_panel.py
"""Owned Reporters panel reflecting the same registry as View > Reporters."""

from importlib import import_module
from typing import Any

from fontlabapp.qt.properties import value

from .kinds import guarded
from .palettes.ui import PaletteUI


class ReportersPanel:
    """Own checkbox signals and a reusable, nonmodal App dock."""

    def __init__(self, services: Any, registry: Any) -> None:
        self.services, self.registry = services, registry
        self.owned = self.ui = None
        self.checks: dict[str, Any] = {}
        self.action = None
        self._syncing = False

    def install(self, panels: Any = None) -> None:
        """Expose the core panel in Window > Panels without opening it."""
        menus = self.services.menus
        if panels is None:
            panels = menus.menu(menus.add_menu("Window", "Panels"))
        self.action = menus.add_action(
            panels, "Reporters", lambda: guarded(self, self.services.sink, self.show)
        )

    def show(self) -> None:
        """Build once and show; every checkbox controls its reporter."""
        if self.owned is not None:
            self.owned.widget.show()
            return

        def build(content):
            self.ui = PaletteUI(self.services.qt, content, self, self.services.sink, None)
            self._build_grid(content)
            self._add_rows()

        try:
            self.owned = import_module("fontlabapp.qt.widgets").create_panel(
                self.services.menus.main_window(), "Reporters", build, "right"
            )
            self.registry.listeners.append(self.sync)
            guarded(self, self.services.sink, self._fit)
        except Exception:
            if self.ui is not None:
                self.ui.close()
            self.ui = None
            self.checks.clear()
            raise

    def _fit(self) -> None:
        """Fit initially without retiring a usable panel if screen access fails.

        Widen to as many ``_reflow`` cells as fit (at most 3) plus the panel's real chrome:
        everything around the scroll viewport, and the vertical scroll bar if not yet shown.
        Sizing is best effort: a geometry attribute missing on this binding or host (getter
        or property) is skipped quietly. Without screen geometry there is no fit at all;
        without a chrome or cell measurement, that part uses its default.
        """

        def measured(read, default):
            try:
                return read()
            except AttributeError:
                return default

        widget = self.owned.widget
        available = measured(lambda: self._available_geometry(widget), None)
        screen = measured(lambda: (value(available, "width"), value(available, "height")), None)
        if screen is None:
            return
        limit, height = int(screen[0] * 0.85), min(480, int(screen[1] * 0.7))
        checks = list(self.checks.values())
        cell = measured(lambda: self._cell(checks), 180) if checks else 180
        chrome = measured(
            lambda: max(0, value(widget, "width") - value(self.scroll.viewport(), "width")), 0
        )
        bar = measured(self.scroll.verticalScrollBar, None)
        if not measured(lambda: bar.isVisible(), True):
            chrome += measured(lambda: value(value(bar, "sizeHint"), "width"), 0)
        columns = next((count for count in (3, 2) if count * cell + chrome <= limit), 1)
        widget.resize(min(limit, columns * cell + chrome), height)

    def _available_geometry(self, widget: Any) -> Any:
        """Qt 6 ``screen()``, else the Qt 5 desktop: FontLab 9's QDockWidget has no ``screen``.

        Qt 6 returns no screen before the window is placed; it has no ``desktop()``, so use the
        primary screen then.
        """
        gui = self.services.qt.QtGui
        try:
            screen = value(widget, "screen")
        except AttributeError:
            return gui.QApplication.desktop().availableGeometry(widget)
        if screen is None:
            screen = getattr(gui, "QGuiApplication", gui.QApplication).primaryScreen()
        return value(screen, "availableGeometry")

    @staticmethod
    def _cell(checks: list[Any]) -> int:
        """One column's width, shared by the initial fit and every reflow."""
        return max(value(value(check, "sizeHint"), "width") for check in checks) + 12

    def _build_grid(self, content: Any) -> None:
        """Keep long labels intact; narrow docks scroll instead of growing tall."""
        gui, owner = self.services.qt.QtGui, self

        class Grid(gui.QWidget):
            def resizeEvent(self, event):
                gui.QWidget.resizeEvent(self, event)
                guarded(owner, owner.services.sink, owner._reflow)

        self.scroll = gui.QScrollArea(content)
        self.scroll.setFrameShape(gui.QFrame.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.grid_widget = Grid(self.scroll)
        self.grid = gui.QGridLayout(self.grid_widget)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSizeConstraint(gui.QLayout.SetMinimumSize)
        self.grid.setSpacing(4)
        self.scroll.setWidget(self.grid_widget)
        self.ui.layout.addWidget(self.scroll)

    def _reflow(self) -> None:
        if self.ui is None or not self.checks:
            return
        checks = list(self.checks.values())
        cell = self._cell(checks)
        width = value(self.scroll.viewport(), "width")
        columns = min(3, max(1, width // cell))
        for check in checks:
            self.grid.removeWidget(check)
        rows = (len(checks) + columns - 1) // columns
        for index, check in enumerate(checks):
            self.grid.addWidget(check, index % rows, index // rows)
        self.grid_widget.setMinimumWidth(cell)
        self.scroll.setMinimumWidth(cell + 24)
        height = max(value(value(check, "sizeHint"), "height") for check in checks)
        self.scroll.setMaximumHeight(min(480, rows * (height + 4) + 16))

    def _add_rows(self) -> None:
        """Append newly discovered reporters without replacing owned controls."""
        for name, cls in sorted(self.registry.available("reporter").items()):
            if name in self.checks:
                continue
            widget = self.ui.checkbox(cls.title.removeprefix("Show "), name in self.registry.enabled())
            self.ui.layout.removeWidget(widget)
            self.checks[name] = widget
            callback = lambda *args, name=name: guarded(self, self.services.sink, lambda: self._toggle(name))
            widget.toggled.connect(callback)
            self.ui.connections.append((widget.toggled, callback))
        self._reflow()

    def _toggle(self, name: str) -> None:
        if not self._syncing:
            try:
                self.registry.toggle(name)
            finally:
                self.sync()

    def sync(self) -> None:
        """Avoid recursively dispatching toggles while reflecting saved state."""
        self._syncing = True
        try:
            self._add_rows()
            enabled = self.registry.enabled()
            for name, widget in self.checks.items():
                widget.setChecked(name in enabled)
        finally:
            self._syncing = False

    def close(self) -> bool:
        """Keep ownership on close refusal; otherwise disconnect all controls."""
        if self.owned is not None:
            if self.owned.close() is False:
                return False
            self.registry.listeners.remove(self.sync)
            self.ui.close()
            self.owned = self.ui = None
            self.checks.clear()
        if self.action is not None:
            self.services.menus.remove(self.action)
            self.action = None
        return True
