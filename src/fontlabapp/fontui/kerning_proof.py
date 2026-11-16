# this_file: src/fontlabapp/fontui/kerning_proof.py
# SPDX-License-Identifier: Apache-2.0
"""Retained kerning editor and proof over one explicitly borrowed font."""

from types import SimpleNamespace
from typing import Any

__all__ = ("show",)
_HANDLES = []


class KerningProof:
    """Own the window and nested editor; retain failed cleanup for retry."""

    def __init__(self, qt: Any, font: Any) -> None:
        from fontlabapp.core.signals.scope import Scope

        self.qt, self.font = qt, font
        self.editor = self.owned = None
        self.problems, self._failed_owners = [], []
        self.scope = Scope(self.problems.append)
        self._released = self._closing = self._queued = False
        self._busy = 0
        self._stranded = None

    def build(self, content: Any) -> None:
        from . import kerning_editor
        from .model import FontListState

        gui = self.qt.QtGui
        layout = gui.QVBoxLayout(content)
        self.target = gui.QLabel(content)
        try:
            label = "No font supplied" if self.font is None else FontListState.label(self.font)
        except Exception as error:
            label = f"Target unavailable: {error}"
        self.target.setText(label)
        layout.addWidget(self.target)
        note = gui.QLabel(
            "Font captured at launch; native edits follow that font's current master. "
            "Apply and Delete change kerning. Closing this window leaves the font open.",
            content,
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.scope.connect(content.finished, self._finished, closing=True)
        self.scope.connect(content.destroyed, self._destroyed, closing=True)
        self.editor = kerning_editor(self.font, parent=content)
        layout.addWidget(self.editor.widget)

    def _fence(self) -> None:
        self._closing = True
        if self.editor is not None:
            self.editor.closed = self.editor.preview.closed = True
            self.editor.on_apply = None

    def _finished(self, *args: Any) -> None:
        self._fence()
        if not self._released and not self._queued:
            self._queued = True
            self.qt.QtCore.QTimer.singleShot(0, self.release)

    def _destroyed(self, *args: Any) -> None:
        self.scope.finish(destroyed=True)
        self._finished()

    def _close_children(self) -> None:
        owners = []
        for root in (*self._failed_owners, self.editor):
            for child in (getattr(root, "preview", None), root):
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
        self._fence()
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
        self.font = self.editor = self.owned = self.target = None
        return True


def show(font: Any, parent: Any = None) -> KerningProof:
    """Open one retained nonmodal editor without closing the borrowed font."""
    from fontlabapp import _native
    from fontlabapp.qt.safe import main_window
    from fontlabapp.qt.widgets import create_dialog

    qt = _native("PythonQt")
    owner = KerningProof(qt, font)
    _HANDLES.append(owner)
    owner._busy = 1
    try:
        host = parent if parent is not None else main_window(_native("fontlab"), qt)
        owner.owned = create_dialog(host, "Kerning Proof Workbench", owner.build)
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
        owner._busy = 0
        try:
            complete = owner.release()
        except BaseException as cleanup:
            owner.problems.append(cleanup)
            error.add_note("Kerning proof cleanup was interrupted; controller retained")
        else:
            if not complete:
                error.add_note("Kerning proof cleanup is incomplete; controller retained")
        raise
    finally:
        owner._busy = 0
    return owner
