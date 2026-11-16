# this_file: src/fontlabapp/fontui/batch_recipes.py
# SPDX-License-Identifier: Apache-2.0
"""Recipe-only affine controls and explicit batch UFO execution in one window."""
from typing import Any

__all__ = ["show"]
_HANDLES = []


class _Workbench:
    """Retain the two real child owners until their distinct close ACKs."""

    def __init__(self, qt: Any, python: str | None) -> None:
        from fontlabapp.core.signals.scope import Scope

        self.qt, self.python = qt, python
        self.problems = []
        self.scope = Scope(self.problems.append)
        self.editor = self.panel = self.owned = None
        self.peers = []
        self._closing = self._released = self._queued = self._releasing = False
        self._building = True
        self._dispatching = False

    def build(self, content: Any) -> None:
        from fontlabapp.fontui import transform_editor, batch_panel

        gui = self.qt.QtGui
        layout = gui.QVBoxLayout(content)
        self.scope.connect(content.finished, self.release, closing=True)
        self.scope.connect(content.destroyed, self._destroyed, closing=True)
        note = gui.QLabel(
            "Edit an affine recipe; no font or geometry preview is opened. "
            "Choose source UFO directories, a destination and an external Python "
            "with Fontport. Start writes new UFOs without overwriting existing "
            "files. Cancel stops between files; completed outputs remain.", content)
        note.setWordWrap(True)
        layout.addWidget(note)
        self.editor = transform_editor(None, parent=content)
        self.peers.append(("editor", self.editor))
        if self._closing:
            raise RuntimeError("Workbench closed during construction")
        form = self.editor.layout.itemAt(0).layout()
        for control in (self.editor.glyph_control, self.editor.method_control):
            control.hide()
            label = form.labelForField(control)
            if label is not None:
                label.hide()
        for control in (self.editor.canvas, self.editor.compare_control,
                        self.editor.script_view,
                        *(button for key, button in self.editor.buttons.items() if key != "reset")):
            control.hide()
        layout.addWidget(self.editor.widget)
        self.panel = batch_panel(self.recipe, parent=content, python=self.python)
        self.peers.append(("panel", self.panel))
        if self._closing:
            raise RuntimeError("Workbench closed during construction")
        layout.addWidget(self.panel.widget)

    def recipe(self) -> Any:
        """Read the real controls once; a fenced workbench cannot start a run."""
        if self._closing or self.editor is None or self.editor.closed:
            raise RuntimeError("The batch recipe workbench is closed")
        if self._dispatching:
            raise RuntimeError("A batch recipe is already being captured")
        self._dispatching = True
        try:
            recipe = self.editor.recipe()
            if self._closing or self.editor.closed or self.panel.closed:
                raise RuntimeError("The batch recipe workbench is closed")
            return recipe
        finally:
            self._dispatching = False
            if self._closing:
                try:
                    self.release()
                except BaseException as error:
                    self.problems.append(error)

    def _fence(self) -> None:
        self._closing = True
        for role, peer in self.peers:
            peer.closed = True
            if role == "panel":
                peer.on_finish = None
            else:
                peer.on_change = peer.on_invalidate = None

    def _destroyed(self, *args: Any) -> None:
        self._fence()
        self.scope.finish(destroyed=True)
        # Parent destruction precedes deletion of the child senders. Drain now.
        for role, peer in self.peers:
            peer._parent_destroyed()
            try:
                peer.close()
            except BaseException as error:
                self.problems.append(error)
        self.release()

    def release(self, *args: Any) -> bool:
        """Fence immediately, then drain owners outside the current Qt callback."""
        if self._released:
            return True
        self._fence()
        if not self._queued:
            self._queued = True
            try:
                self.qt.QtCore.QTimer.singleShot(0, self._release_queued)
            except BaseException:
                self._queued = False
                raise
        return False

    def _release_queued(self) -> None:
        self._queued = False
        try:
            self._release_now()
        except BaseException as error:
            self.problems.append(error)

    def close(self) -> None:
        """A closer for release_owned; verify both real child ACKs explicitly."""
        for role, peer in reversed(self.peers):
            complete = (peer._batch_close is not None and peer._batch_close["complete"]
                        if role == "panel" else peer._close_complete)
            if complete:
                continue
            peer.close()
            complete = (peer._batch_close is not None and peer._batch_close["complete"]
                        if role == "panel" else peer._close_complete)
            if not complete:
                raise RuntimeError("Batch workbench child cleanup is incomplete")

    def _release_now(self) -> bool:
        from fontlabapp.qt.widgets import release_owned

        if self._released:
            return True
        self._fence()
        if self._building or self._dispatching or self._releasing:
            return False
        self._releasing = True
        try:
            complete = release_owned(self.scope, self.owned, self.problems, (self,))
        finally:
            self._releasing = False
        if complete:
            self._released = True
            _HANDLES.remove(self)
        return complete

    def _remember_failure(self, error: BaseException) -> None:
        from fontlabapp.qt.widgets import OwnedWidget
        from fontlabapp.fontui.batch import BatchPanel
        from fontlabapp.fontui.lifecycle import Owned

        failures = [error]
        while failures:
            failure = failures.pop()
            peer = getattr(failure, "owner", None)
            if isinstance(peer, OwnedWidget):
                self.owned = peer
            elif isinstance(peer, Owned) and all(peer is not item for _, item in self.peers):
                self.peers.append(("panel" if isinstance(peer, BatchPanel) else "editor", peer))
            if isinstance(failure, BaseExceptionGroup):
                failures.extend(failure.exceptions)


def show(parent: Any = None, python: str | None = None) -> _Workbench:
    """Open a retained recipe-only window; Start is the only batch-write action."""
    from fontlabapp import _native
    from fontlabapp.qt.safe import main_window
    from fontlabapp.qt.widgets import create_dialog

    qt = _native("PythonQt")
    owner = _Workbench(qt, python)
    _HANDLES.append(owner)
    try:
        host = parent if parent is not None else main_window(_native("fontlab"), qt)
        owner.owned = create_dialog(host, "Batch UFO Recipe Workbench", owner.build)
    except BaseException as error:
        owner.problems.append(error)
        owner._remember_failure(error)
        owner._building = False
        try:
            if not owner._release_now():
                error.add_note("Batch workbench cleanup incomplete; owner retained")
        except BaseException as cleanup:
            owner.problems.append(cleanup)
            error.add_note("Batch workbench cleanup interrupted; owner retained")
        raise
    finally:
        owner._building = False
    return owner
