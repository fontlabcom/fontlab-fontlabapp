# this_file: src/fontlabapp/fontui/kerning_groups.py
# SPDX-License-Identifier: Apache-2.0
"""Groups and kerning editors linked over one explicitly borrowed font."""

from types import SimpleNamespace
from typing import Any

__all__ = ("show",)
_HANDLES = []


class KerningGroups:
    """Own two editors and their previews; retain failed cleanup for retry."""

    def __init__(self, qt: Any, font: Any) -> None:
        from fontlabapp.core.signals.scope import Scope

        self.qt, self.font = qt, font
        self.groups = self.kerning = self.owned = None
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
        from . import groups_editor, kerning_editor
        from .model import FontListState

        gui = self.qt.QtGui
        layout = gui.QVBoxLayout(content)
        self.target = gui.QLabel(content)
        try:
            label = (
                "No font supplied"
                if self.font is None
                else FontListState.label(self.font)
            )
        except Exception as error:
            label = f"Target unavailable: {error}"
        self.target.setText(label)
        layout.addWidget(self.target)
        note = gui.QLabel(
            "Font captured at launch; native edits follow that font's current master. "
            "Group actions and kerning Apply/Delete write this font. Proof uses the first members and their effective kerning, which may differ from the group row. Closing leaves the font open.",
            content,
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.scope.connect(content.finished, self._finished, closing=True)
        self.scope.connect(content.destroyed, self._destroyed, closing=True)
        self.groups = groups_editor(self.font, parent=content)
        # The first editor cannot act while the second factory may unwind.
        self.groups.closed = self.groups.preview.closed = True
        layout.addWidget(self.groups.widget)
        self.use_left = gui.QPushButton("Use selected group as left", content)
        self.use_right = gui.QPushButton("Use selected group as right", content)
        layout.addWidget(self.use_left)
        layout.addWidget(self.use_right)
        self.diagnostic = gui.QLabel(content)
        layout.addWidget(self.diagnostic)
        self.kerning = kerning_editor(self.font, parent=content)
        layout.addWidget(self.kerning.widget)
        self.scope.connect(self.use_left.clicked, lambda *args: self.use("left"))
        self.scope.connect(self.use_right.clicked, lambda *args: self.use("right"))
        if self._closing:
            self._fence()
        else:
            self.groups.closed = self.groups.preview.closed = False
            self.groups.on_apply = self._groups_applied

    def use(self, side: str) -> None:
        """Stage the actual selected group through one existing inspect route."""
        if self._closing or self._busy:
            return
        self._busy += 1
        try:
            name = self.groups.selected
            if name is None:
                self.diagnostic.setText("Select a group first.")
                return
            control = (
                self.kerning.left_control
                if side == "left"
                else self.kerning.right_control
            )
            if control.text == name:
                self.kerning.inspect()
            else:
                control.setText(name)
            if not self._closing:
                self.diagnostic.setText(
                    f"Selected group used as {side} key; Apply writes kerning."
                )
        finally:
            self._busy -= 1

    def _groups_applied(self, font: Any, values: Any) -> None:
        """Revalidate after accepted readback, without replaying a group write."""
        if self._closing or self._busy:
            return
        if font is not self.font:
            raise ValueError("Group callback target differs from the captured font")
        self._busy += 1
        try:
            self.kerning._changed()
        finally:
            self._busy -= 1

    def _fence(self) -> None:
        self._closing = True
        for editor in (*self._failed_owners, self.groups, self.kerning):
            if editor is not None:
                editor.closed = True
                editor.on_apply = None
                preview = getattr(editor, "preview", None)
                if preview is not None:
                    preview.closed = True

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
        for root in (*self._failed_owners, self.groups, self.kerning):
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
        self.font = self.groups = self.kerning = self.owned = self.target = None
        return True


def show(font: Any, parent: Any = None) -> KerningGroups:
    """Open both editors in one retained window without owning the font."""
    from fontlabapp import _native
    from fontlabapp.qt.safe import main_window
    from fontlabapp.qt.widgets import create_dialog

    qt = _native("PythonQt")
    owner = KerningGroups(qt, font)
    _HANDLES.append(owner)
    owner._busy = 1
    try:
        host = parent if parent is not None else main_window(_native("fontlab"), qt)
        owner.owned = create_dialog(host, "Kerning Group Explorer", owner.build)
    except BaseException as error:
        owner.problems.append(error)
        owner._remember_failure(error)
        owner._busy = 0
        try:
            complete = owner._release_now()
        except BaseException as cleanup:
            owner.problems.append(cleanup)
            error.add_note("Kerning group cleanup was interrupted; controller retained")
        else:
            if not complete:
                error.add_note(
                    "Kerning group cleanup is incomplete; controller retained"
                )
        raise
    finally:
        owner._busy = 0
    return owner
