# this_file: src/fontlabapp/fontui/open_fonts_overview.py
# SPDX-License-Identifier: Apache-2.0
"""Open-font chooser with the selected font's current native master metrics."""

from math import isfinite
from typing import Any

from .tabular_audit import TabularAudit, _HANDLES

__all__ = ("show",)


class OpenFontsOverview(TabularAudit):
    """Reuse the open-font browser and its retryable ownership from the audit."""

    def __init__(self, qt: Any, world: Any) -> None:
        super().__init__(qt, world)
        self._generation = 0

    def build(self, content: Any) -> None:
        from . import _construct
        from .fonts import FontBrowser

        gui = self.qt.QtGui
        layout = gui.QVBoxLayout(content)
        self.comparison, self.status = gui.QLabel(content), gui.QLabel(content)
        self.refresh_button = gui.QPushButton("Refresh open fonts and metrics", content)
        for widget in (self.refresh_button, self.comparison, self.status):
            layout.addWidget(widget)
        self.scope.connect(content.finished, self._finished, closing=True)
        self.scope.connect(content.destroyed, self._destroyed, closing=True)
        self.browser = _construct(FontBrowser, self.world.AllFonts(), content, None, False)
        glyphs = self.browser.browser
        glyphs.on_selection = self.selected
        layout.addWidget(self.browser.widget)
        self.scope.connect(self.refresh_button.clicked, lambda *args: self.refresh())
        glyphs.selection_changed()

    def selected(self, font: Any, names: tuple[str, ...]) -> None:
        from fontlabapp import _native
        from fontlabapp.masters.inspect.model import METRICS, location_text

        if self._closing:
            return
        self._generation += 1
        generation = self._generation
        self._clear("Reading current master")
        self._busy += 1
        try:
            if font is not self.browser.state.selected:
                raise ValueError("Selection belongs to another font")
            if font is None:
                self.status.setText("Choose an available font")
                return
            if not any(font is current for current in self.world.AllFonts()):
                raise ValueError("Selected font is no longer open; refresh")
            font._check()
            backend = font._backend
            package = backend._package()
            if package.fgId != backend.font_id:
                raise ValueError("The registered font identity changed")
            master = package.master
            identity = package.id, tuple(package.masters)
            if not master or master not in package.masters:
                raise ValueError("Current master is unavailable")
            metrics = _native("fontlab").FontMetrics(package, master)
            values = tuple((label, float(getattr(metrics, field))) for label, field in METRICS)
            if not all(isfinite(value) for _, value in values):
                raise ValueError("Current master metrics must be finite")
            location = location_text(package, master)
            font._check()
            current = backend._package()
            if (font._backend is not backend or (current.id, tuple(current.masters)) != identity
                    or current.master != master):
                raise ValueError("Font or current master changed during inspection; refresh")
            if not self._closing and generation == self._generation:
                self.report = (master, location, values)
                self.comparison.setText("\n".join(
                    [f"Current master: {master}", f"Location: {location}",
                     *(f"{label}: {value:g}" for label, value in values)]))
                self.status.setText("Stored current-master metrics; no master switching")
        except Exception as error:
            if not self._closing and generation == self._generation:
                self._clear(str(error))
                self.browser.browser.preview.set_glyph(None)
        finally:
            self._busy -= 1

    def refresh(self) -> None:
        """Re-enumerate documents without invalidating borrowed font caches."""
        if self._closing:
            return
        self._clear("Refreshing open fonts")
        self._busy += 1
        try:
            fonts = self.world.AllFonts()
            if not self._closing:
                self.browser.refresh(fonts)
        except Exception as error:
            if not self._closing:
                self._clear(str(error))
        finally:
            self._busy -= 1


def show(font: Any, parent: Any = None) -> OpenFontsOverview:
    """Borrow an open-font world (``AllFonts``), without changing its current font."""
    from fontlabapp import _native
    from fontlabapp.qt.safe import main_window
    from fontlabapp.qt.widgets import OwnedWidget, create_dialog
    from .lifecycle import Owned

    qt = _native("PythonQt")
    owner = OpenFontsOverview(qt, font)
    _HANDLES.append(owner)
    try:
        host = parent if parent is not None else main_window(_native("fontlab"), qt)
        owner.owned = create_dialog(host, "Open Fonts and Master Overview", owner.build)
    except BaseException as error:
        owner.problems.append(error)
        pending = [error]
        while pending:
            failure = pending.pop()
            failed = getattr(failure, "owner", None)
            if isinstance(failed, OwnedWidget):
                owner.owned = failed
            elif isinstance(failed, Owned):
                owner._failed_owners.append(failed)
            if isinstance(failure, BaseExceptionGroup):
                pending.extend(failure.exceptions)
        try:
            complete = owner.release()
        except BaseException as cleanup:
            owner.problems.append(cleanup)
            error.add_note("Overview cleanup interrupted; owner retained")
        else:
            if not complete:
                error.add_note("Overview cleanup incomplete; owner retained")
        raise
    return owner
