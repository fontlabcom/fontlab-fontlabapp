# this_file: src/fontlabapp/fontui/feature_proof.py
# SPDX-License-Identifier: Apache-2.0
"""Feature source and a fresh independent glyph proof over one borrowed font."""

from types import SimpleNamespace
from typing import Any

__all__ = ["show"]
_HANDLES = []


class FeatureProof:
    """Own the source editor and sequence; retain failed cleanup for retry."""

    def __init__(self, qt: Any, font: Any) -> None:
        from fontlabapp.core.signals.scope import Scope

        self.qt, self.font = qt, font
        self.editor = self.proof = self.owned = None
        self.problems, self._failed_owners = [], []
        self.scope = Scope(self.problems.append)
        self._released = self._closing = self._queued = self._releasing = False
        self._busy = 0
        self._stranded = None

    def build(self, content: Any) -> None:
        """Fence partial children before the outer dialog factory unwinds."""
        try:
            self._build(content)
        except BaseException as error:
            self._remember_failure(error)
            self._fence()
            raise

    def _build(self, content: Any) -> None:
        from . import features_editor, glyph_sequence
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
            "Feature source is stored, not compiled. Glyph sequence uses Unicode "
            "and kerning; OpenType substitutions/positioning are not applied. "
            "The font is captured at launch. External changes keep dirty drafts; "
            "explicit Apply may overwrite newer source. Revert reloads it. "
            "Closing leaves the font open.", content,
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.scope.connect(content.finished, self._finished, closing=True)
        self.scope.connect(content.destroyed, self._destroyed, closing=True)
        self.editor = features_editor(self.font, parent=content)
        self.editor.closed = True
        layout.addWidget(self.editor.widget)
        self.proof = glyph_sequence(self.font, parent=content)
        layout.addWidget(self.proof.widget)
        self.refresh_button = gui.QPushButton("Refresh proof", content)
        layout.addWidget(self.refresh_button)
        self.scope.connect(self.refresh_button.clicked, lambda *args: self.refresh_proof())
        if self._closing:
            self._fence()
        else:
            self.editor.closed = False
            self.editor.on_apply = self._source_applied

    def refresh_proof(self) -> None:
        """Retry only the proof; its run/diagnostic reports success or failure."""
        if self._closing or self._busy:
            return
        self._busy += 1
        try:
            self.proof.refresh()
        finally:
            self._busy -= 1

    def _source_applied(self, font: Any, text: str) -> None:
        """Refresh once after accepted source readback without replaying its write."""
        if self._closing or self._busy:
            return
        if font is not self.font:
            raise ValueError("Feature callback target differs from the captured font")
        self.refresh_proof()

    def _fence(self) -> None:
        self._closing = True
        for editor in (*self._failed_owners, self.editor, self.proof):
            if editor is not None:
                editor.closed = True
                editor.on_apply = None
                if hasattr(editor, "on_update"):
                    editor.on_update = None
                if hasattr(editor, "on_select"):
                    editor.on_select = None

    def _finished(self, *args: Any) -> None:
        self._fence()
        if not self._released and not self._queued:
            self._queued = True
            self.qt.QtCore.QTimer.singleShot(0, self._release_queued)

    def _release_queued(self) -> None:
        """Consume the one queued cleanup without duplicating active requests."""
        self._queued = False
        try:
            self._release_now()
        except BaseException as error:
            self.problems.append(error)

    def _destroyed(self, *args: Any) -> None:
        self._fence()
        self.scope.finish(destroyed=True)
        self._finished()

    def _remember_failure(self, error: BaseException) -> None:
        """Keep exact partial owners carried by the existing factory errors."""
        from fontlabapp.qt.widgets import OwnedWidget
        from .lifecycle import Owned

        pending = [error]
        while pending:
            failure = pending.pop()
            failed = getattr(failure, "owner", None)
            if isinstance(failed, OwnedWidget):
                self.owned = failed
            elif isinstance(failed, Owned) and not any(
                failed is child for child in self._failed_owners
            ):
                self._failed_owners.append(failed)
            if isinstance(failure, BaseExceptionGroup):
                pending.extend(failure.exceptions)

    def _close_children(self) -> None:
        owners = []
        for child in (*self._failed_owners, self.editor, self.proof):
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
        """Fence now and queue cleanup; return True only after actual completion."""
        if self._released:
            return True
        self._finished()
        return False

    def _release_now(self) -> bool:
        """Clean up after dispatch or during the unwound constructor."""
        from fontlabapp.qt.widgets import release_owned

        if self._released:
            return True
        self._fence()
        if self._busy:
            self._finished()
            return False
        if self._releasing:
            return False
        self._releasing = True
        try:
            complete = release_owned(
                self.scope,
                self.owned,
                self.problems,
                (SimpleNamespace(close=self._close_children),),
            )
        except Exception as error:
            self.problems.append(error)
            return False
        finally:
            self._releasing = False
        if not complete:
            return False
        self._released = True
        self._failed_owners.clear()
        _HANDLES.remove(self)
        self.font = self.editor = self.proof = self.owned = self.target = None
        return True


def show(font: Any, parent: Any = None) -> FeatureProof:
    """Open the source editor and proof in one retained window without owning the font."""
    from fontlabapp import _native
    from fontlabapp.qt.safe import main_window
    from fontlabapp.qt.widgets import create_dialog

    qt = _native("PythonQt")
    owner = FeatureProof(qt, font)
    _HANDLES.append(owner)
    owner._busy = 1
    try:
        host = parent if parent is not None else main_window(_native("fontlab"), qt)
        owner.owned = create_dialog(host, "Feature Source and Proof", owner.build)
    except BaseException as error:
        owner.problems.append(error)
        owner._remember_failure(error)
        owner._busy = 0
        try:
            complete = owner._release_now()
        except BaseException as cleanup:
            owner.problems.append(cleanup)
            error.add_note("Feature proof cleanup was interrupted; controller retained")
        else:
            if not complete:
                error.add_note(
                    "Feature proof cleanup is incomplete; controller retained"
                )
        raise
    finally:
        owner._busy = 0
    return owner
