# this_file: src/fontlabapp/fontui/anchor_components.py
# SPDX-License-Identifier: Apache-2.0
"""Ordered anchors and direct component records linked to one preview."""

from dataclasses import dataclass
from typing import Any
from math import isfinite

__all__ = ("GlyphDetails", "details", "show")
_HANDLES = []


@dataclass(frozen=True)
class GlyphDetails:
    name: str
    anchors: tuple[tuple[str | None, float, float], ...]
    components: tuple[tuple[str, tuple[float, ...]], ...]
    diagnostic: str | None


def details(font: Any, name: str) -> GlyphDetails:
    """Retain useful direct records even when outline validation fails."""
    from .model import outline

    if font is None:
        raise ValueError("No font supplied")
    glyph = font[name]
    anchors = tuple((a.name, a.x, a.y) for a in glyph.anchors)
    components = tuple((c.baseGlyph, tuple(c.transformation)) for c in glyph.components)
    diagnostic = None
    try:
        if any(not isfinite(v) for _, x, y in anchors for v in (x, y)) or any(
            len(t) != 6 or not all(isfinite(v) for v in t) for _, t in components
        ):
            raise ValueError("Non-finite anchor or invalid component transformation")
        drawing = outline(font, name)
        if drawing.bounds is not None and not all(isfinite(v) for v in drawing.bounds):
            raise ValueError("Non-finite outline bounds")
    except Exception as error:
        diagnostic = str(error)
    return GlyphDetails(name, anchors, components, diagnostic)


class AnchorComponentInspector:
    """Retain one modeless inspection and its borrowed-font callbacks."""

    def __init__(self, qt: Any, font: Any) -> None:
        from fontlabapp.core.signals.scope import Scope

        self.qt, self.font = qt, font
        self.browser = self.sequence = self.owned = None
        self.problems = []
        self._failed_owners = []
        self.scope = Scope(self.problems.append)
        self._released = self._closing = self._queued = self._parent_dead = False
        self.anchor_rows = self.component_rows = ()

    def build(self, content: Any) -> None:
        from . import _construct
        from .native import Browser

        gui = self.qt.QtGui
        layout = gui.QVBoxLayout(content)
        details = gui.QWidget(content)
        detail_layout = gui.QVBoxLayout(details)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        self.anchor_table, self.component_table = (
            gui.QTreeWidget(details),
            gui.QTreeWidget(details),
        )
        self.anchor_table.setHeaderLabels(["Anchor", "X", "Y"])
        self.component_table.setHeaderLabels(["Base glyph", "Transformation"])
        self.status = gui.QLabel(details)
        for widget in (self.anchor_table, self.component_table, self.status):
            detail_layout.addWidget(widget)
        self.browser = _construct(
            Browser, self.font, content, None, False, True, self.selected
        )
        self.browser.selection_layout.addWidget(details, 2)
        layout.addWidget(self.browser.widget)
        for option in ("anchors", "oncurve", "offcurve"):
            self.browser.preview.set_option(option, True)
        self._wire(content)

    def selected(self, font: Any, names: tuple[str, ...]) -> None:
        if self._closing:
            return
        self.anchor_rows = self.component_rows = ()
        self._fill(self.anchor_table, ())
        self._fill(self.component_table, ())
        try:
            if font is not self.font:
                raise ValueError("Selection belongs to another font")
            if not names:
                self.status.setText(
                    "No font supplied" if font is None else "Select a glyph"
                )
                self._clear_preview()
                return
            value = details(font, names[0])
            self.anchor_rows, self.component_rows = value.anchors, value.components
            self._fill(self.anchor_table, self.anchor_rows)
            self._fill(self.component_table, self.component_rows)
            self.status.setText(value.diagnostic or value.name)
        except Exception as error:
            self._clear_preview()
            self.status.setText(str(error))

    def _fill(self, table: Any, rows: tuple) -> None:
        table.clear()
        for row in rows:
            table.addTopLevelItem(
                self.qt.QtGui.QTreeWidgetItem(
                    ["—" if v is None else str(v) for v in row]
                )
            )

    def _clear_preview(self) -> None:
        if self.browser is not None and not self.browser.closed:
            self.browser.preview.set_glyph(None)

    def _wire(self, content: Any) -> None:
        self.scope.connect(content.finished, self._finished, closing=True)
        self.scope.connect(content.destroyed, self._destroyed, closing=True)

    def _finished(self, *args: Any) -> None:
        if not self._released and not self._queued:
            self._closing, self._queued = True, True
            self.qt.QtCore.QTimer.singleShot(0, self.release)

    def _destroyed(self, *args: Any) -> None:
        self._parent_dead = True
        self.scope.finish(destroyed=True)
        self._finished()

    def refresh(self) -> None:
        if not self._closing and self.browser is not None:
            self.browser.refresh()

    def _close_child(self, child: Any) -> None:
        """Keep exact failed ownership while allowing substantive cleanup retries."""
        preview = getattr(child, "preview", None)
        owners = (child,) if preview is None else (child, preview)
        try:
            child.close()
            if any(not owner._close_complete for owner in owners):
                raise RuntimeError("Child cleanup is incomplete; owner retained")
        except BaseException as error:
            for owner in reversed(owners):
                if not owner._close_complete:
                    self._stranded = (owner, error)
                    break
            raise
        self._stranded = None

    def release(self) -> bool:
        from types import SimpleNamespace

        from fontlabapp.qt.widgets import release_owned

        self._queued = False
        if self._released:
            return True
        self._closing = True
        children = []
        for child in (*self._failed_owners, self.browser, self.sequence):
            if child is not None and not any(child is other for other in children):
                children.append(child)
        owners = (*children, *(c.preview for c in children if hasattr(c, "preview")))
        if self._parent_dead and (
            any(not c._close_complete and not c.destroying for c in owners)
            or (self.owned is not None and not self.owned.closed)
        ):
            self.problems.append(
                RuntimeError("Destroyed parent has unfinished child cleanup")
            )
            return False
        try:
            closers = tuple(
                SimpleNamespace(close=lambda child=child: self._close_child(child))
                for child in children
            )
            complete = release_owned(self.scope, self.owned, self.problems, closers)
        except Exception as error:
            self.problems.append(error)
            return False
        if not complete or any(not c._close_complete for c in owners):
            return False
        self._released = True
        self._failed_owners.clear()
        if self in _HANDLES:
            _HANDLES.remove(self)
        self.font = self.browser = self.sequence = self.owned = None
        self.anchor_table = self.component_table = self.status = None
        return True


def show(font: Any, parent: Any = None) -> AnchorComponentInspector:
    """Open a retained read-only inspection window over a borrowed font."""
    from fontlabapp import _native
    from fontlabapp.qt.safe import main_window
    from fontlabapp.qt.widgets import create_dialog

    qt = _native("PythonQt")
    owner = AnchorComponentInspector(qt, font)
    _HANDLES.append(owner)
    try:
        host = parent if parent is not None else main_window(_native("fontlab"), qt)
        owner.owned = create_dialog(host, "Anchor and Component Inspector", owner.build)
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
            error.add_note(
                "Inspection cleanup was interrupted; its controller and diagnostic are retained"
            )
        else:
            if not complete:
                error.add_note(
                    "Inspection cleanup is incomplete; its controller is retained"
                )
        raise
    return owner
