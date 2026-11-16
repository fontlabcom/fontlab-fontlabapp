# this_file: src/fontlabapp/fontui/unicode_order.py
# SPDX-License-Identifier: Apache-2.0
"""Actual glyph catalogue order and sequence occurrence metadata."""

from dataclasses import dataclass
from typing import Any

__all__ = ("GlyphRecord", "records", "show")
_HANDLES = []


@dataclass(frozen=True)
class GlyphRecord:
    index: int
    name: str
    unicodes: tuple[int, ...]


def records(font: Any) -> tuple[GlyphRecord, ...]:
    """Freeze all ordered Unicode values without changing catalogue order."""
    from .model import BrowserState

    if font is None:
        raise ValueError("No font supplied")
    state = BrowserState(font)
    if state.error:
        raise ValueError(state.error)
    return tuple(
        GlyphRecord(i, name, tuple(font[name].unicodes))
        for i, name in enumerate(state.original)
    )


class UnicodeOrderExplorer:
    """Retain one modeless inspection and its borrowed-font callbacks."""

    def __init__(self, qt: Any, font: Any) -> None:
        from fontlabapp.core.signals.scope import Scope

        self.qt, self.font = qt, font
        self.browser = self.sequence = self.owned = None
        self.problems = []
        self._failed_owners = []
        self.scope = Scope(self.problems.append)
        self._released = self._closing = self._queued = self._parent_dead = False
        self.selected_rows = ()
        self.occurrence_index = None
        self._building, self._last_selection = True, None

    def build(self, content: Any) -> None:
        from . import _construct
        from .native import Browser
        from .sequence import Sequence

        gui = self.qt.QtGui
        layout = gui.QVBoxLayout(content)
        details = gui.QWidget(content)
        detail_layout = gui.QVBoxLayout(details)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        self.metadata_table, self.status = gui.QTreeWidget(details), gui.QLabel(details)
        self.metadata_table.setHeaderLabels(["Field", "Value"])
        detail_layout.addWidget(self.metadata_table)
        detail_layout.addWidget(self.status)
        self.sequence = _construct(
            Sequence, self.font, content, self.sequence_selected, self.sequence_updated
        )
        self.sequence.layout.setContentsMargins(0, 0, 0, 0)
        self.sequence.scroll.setFrameShape(gui.QFrame.NoFrame)
        layout.addWidget(self.sequence.widget)
        try:
            self._set_sequence(tuple(r.name for r in records(self.font)))
        except Exception as error:
            self._clear_occurrence(str(error))
        self.browser = _construct(
            Browser, self.font, content, None, True, True, self.selected
        )
        self.browser.selection_layout.addWidget(details, 2)
        layout.addWidget(self.browser.widget)
        self._building = False
        self._wire(content)

    def _set_sequence(self, names: tuple[str, ...], select: bool = False) -> None:
        seq = self.sequence
        mode_blocked = seq.mode_control.blockSignals(True)
        text_blocked = seq.text_control.blockSignals(True)
        try:
            seq.mode_control.setCurrentIndex(1)
            seq.text_control.setText(" ".join("/" + name for name in names))
        finally:
            seq.mode_control.blockSignals(mode_blocked)
            seq.text_control.blockSignals(text_blocked)
        seq.refresh()
        if select and names and seq.run is not None:
            seq.select_key(self.qt.QtCore.Qt.Key_Home)

    def _clear_occurrence(self, diagnostic: str) -> None:
        self.selected_rows, self.occurrence_index = (), None
        self._fill(self.metadata_table, ())
        self.status.setText(diagnostic)
        self._clear_preview()

    def selected(self, font: Any, names: tuple[str, ...]) -> None:
        if self._closing:
            return
        try:
            if font is not self.font:
                raise ValueError("Selection belongs to another font")
            changed = names != self._last_selection
            self._last_selection = names
            if self._building and not names:
                return
            if changed:
                self._set_sequence(names, select=bool(names))
            else:
                self.sequence.refresh()
        except Exception as error:
            self._clear_occurrence(str(error))

    def sequence_selected(self, glyph: Any, index: int) -> None:
        if self._closing:
            return
        try:
            if glyph is None:
                self._clear_occurrence("Missing sequence glyph")
                return
            name = glyph.name
            catalogue = records(self.font)
            codes = tuple(self.font[name].unicodes)
            text = tuple(f"U+{code:04X} {chr(code)}" for code in codes)
            positions = tuple(r.index for r in catalogue if r.name == name)
            self.occurrence_index = index
            self.selected_rows = (
                ("Name", name),
                ("Occurrence", index),
                ("Catalogue positions", positions),
                ("Unicodes", text or "Unencoded"),
            )
            self._fill(self.metadata_table, self.selected_rows)
            self.status.setText(name)
            if self.browser is not None:
                self.browser.preview.set_glyph(name)
        except Exception as error:
            self._clear_occurrence(str(error))

    def sequence_updated(self, owner: Any) -> None:
        if self._closing:
            return
        try:
            if owner.font is not self.font:
                raise ValueError("Sequence belongs to another font")
            index = owner.selected_index
            if owner.run is None or index is None:
                self._clear_occurrence(str(owner.diagnostic.text))
                return
            name = owner.run.glyphs[index].name
            self.sequence_selected(None if name is None else owner.font[name], index)
        except Exception as error:
            self._clear_occurrence(str(error))

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
        self.metadata_table = self.status = None
        return True


def show(font: Any, parent: Any = None) -> UnicodeOrderExplorer:
    """Open a retained read-only inspection window over a borrowed font."""
    from fontlabapp import _native
    from fontlabapp.qt.safe import main_window
    from fontlabapp.qt.widgets import create_dialog

    qt = _native("PythonQt")
    owner = UnicodeOrderExplorer(qt, font)
    _HANDLES.append(owner)
    try:
        host = parent if parent is not None else main_window(_native("fontlab"), qt)
        owner.owned = create_dialog(
            host, "Unicode and Glyph Order Explorer", owner.build
        )
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
