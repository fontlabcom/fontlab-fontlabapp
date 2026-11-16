# this_file: src/fontlabapp/fontui/tabular_audit.py
# SPDX-License-Identifier: Apache-2.0
"""Read-only tabular advance audit over an explicit borrowed FontWorld."""

from datetime import datetime
from types import SimpleNamespace
from typing import Any

__all__ = ("show",)
_HANDLES = []


class TabularAudit:
    """Retain the chooser, linked report and retryable nested widget ownership."""

    def __init__(self, qt: Any, world: Any) -> None:
        from fontlabapp.core.signals.scope import Scope

        self.qt, self.world = qt, world
        self.browser = self.owned = self.report = None
        self.problems = []
        self._failed_owners = []
        self.scope = Scope(self.problems.append)
        self._released = self._closing = self._queued = False
        self._busy = 0
        self._stranded = None

    def build(self, content: Any) -> None:
        from . import font_browser

        gui = self.qt.QtGui
        layout = gui.QVBoxLayout(content)
        self.comparison, self.status = gui.QLabel(content), gui.QLabel(content)
        self.refresh_button = gui.QPushButton("Refresh open fonts", content)
        for widget in (self.refresh_button, self.comparison, self.status):
            layout.addWidget(widget)
        self.scope.connect(content.finished, self._finished, closing=True)
        self.scope.connect(content.destroyed, self._destroyed, closing=True)
        self.browser = font_browser(self.world.AllFonts(), parent=content)
        glyphs = self.browser.browser
        glyphs.on_selection = self.selected
        glyphs.glyph_list.setSelectionMode(gui.QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.browser.widget)
        self.scope.connect(self.refresh_button.clicked, lambda *args: self.refresh())
        glyphs.selection_changed()

    def _clear(self, reason: str) -> None:
        self.report = None
        self.comparison.setText("")
        self.status.setText(reason)

    def selected(self, font: Any, names: tuple[str, ...]) -> None:
        from fontlabapp.metrics.tabular_width.model import compare, render

        if self._closing:
            return
        self._clear("Reading selected advances")
        self._busy += 1
        try:
            if font is not self.browser.state.selected:
                raise ValueError("Selection belongs to another font")
            if font is None:
                self.status.setText("Choose an available font")
                return
            if not any(font is current for current in self.world.AllFonts()):
                raise ValueError("Selected font is no longer open; refresh")
            state = self.browser.browser.state
            if state.error:
                raise ValueError(state.error)
            if not names:
                self.status.setText("Select glyphs" if state.original else "Font has no glyphs")
                return
            values = tuple((name, float(font[name].width)) for name in names)
            report = compare(values, datetime.now().isoformat(timespec="seconds"))
            text = render(report)
            if not self._closing:
                self.report = report
                self.comparison.setText(text)
                self.status.setText(f"{len(report.rows)} selected glyphs; first row is the reference")
        except Exception as error:
            if not self._closing:
                self._clear(str(error))
                self.browser.browser.preview.set_glyph(None)
        finally:
            self._busy -= 1

    def refresh(self) -> None:
        if self._closing:
            return
        self._clear("Refreshing open fonts")
        self._busy += 1
        try:
            fonts = self.world.refresh()
            if not self._closing:
                self.browser.refresh(fonts)
        except Exception as error:
            if not self._closing:
                self._clear(str(error))
                self.browser.browser.preview.set_glyph(None)
        finally:
            self._busy -= 1

    def _finished(self, *args: Any) -> None:
        self._closing = True
        if not self._released and not self._queued:
            self._queued = True
            self.qt.QtCore.QTimer.singleShot(0, self.release)

    def _destroyed(self, *args: Any) -> None:
        self.scope.finish(destroyed=True)
        self._finished()

    def _close_children(self) -> None:
        owners = []
        for root in (*self._failed_owners, self.browser):
            glyphs = getattr(root, "browser", root)
            for child in (getattr(glyphs, "preview", None), glyphs, root):
                if child is not None and not any(child is other for other in owners):
                    owners.append(child)
        for owner in owners:
            try:
                if not owner._close_complete:
                    owner.close()
                if not owner._close_complete:
                    raise RuntimeError("Child cleanup is incomplete; owner retained")
            except BaseException as error:
                if self._stranded is None or self._stranded[0] is not owner:
                    self._stranded = (owner, error)
                raise
        self._stranded = None

    def release(self) -> bool:
        from fontlabapp.qt.widgets import release_owned

        self._queued = False
        if self._released:
            return True
        self._closing = True
        if self._busy:
            self._finished()
            return False
        try:
            complete = release_owned(
                self.scope, self.owned, self.problems,
                (SimpleNamespace(close=self._close_children),),
            )
        except Exception as error:
            self.problems.append(error)
            return False
        if not complete:
            return False
        self._released = True
        self._failed_owners.clear()
        _HANDLES.remove(self)
        self.world = self.browser = self.owned = self.report = None
        self.comparison = self.status = self.refresh_button = None
        return True


def show(world: Any, parent: Any = None) -> TabularAudit:
    """Open a retained nonmodal audit; never close or modify borrowed fonts."""
    from fontlabapp import _native
    from fontlabapp.qt.safe import main_window
    from fontlabapp.qt.widgets import create_dialog

    qt = _native("PythonQt")
    owner = TabularAudit(qt, world)
    _HANDLES.append(owner)
    try:
        host = parent if parent is not None else main_window(_native("fontlab"), qt)
        owner.owned = create_dialog(host, "Tabular Width Audit", owner.build)
    except BaseException as error:
        owner.problems.append(error)
        from fontlabapp.qt.widgets import OwnedWidget
        from .lifecycle import Owned

        pending = [error]
        while pending:
            failure = pending.pop()
            failed = getattr(failure, "owner", None)
            if isinstance(failed, OwnedWidget):
                owner.owned = failed
            elif isinstance(failed, Owned) and not any(
                failed is child for child in owner._failed_owners
            ):
                owner._failed_owners.append(failed)
            if isinstance(failure, BaseExceptionGroup):
                pending.extend(failure.exceptions)
        try:
            complete = owner.release()
        except BaseException as cleanup:
            owner.problems.append(cleanup)
            error.add_note("Audit cleanup was interrupted; controller retained")
        else:
            if not complete:
                error.add_note("Audit cleanup is incomplete; controller retained")
        raise
    return owner
