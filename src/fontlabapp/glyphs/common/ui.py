# this_file: src/fontlabapp/glyphs/common/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Owned nonmodal report with explicit default-off unavailable charcoal action.

Standalone Qt exercises controls; PythonQt rendering/lifecycle remain native
acceptance gates. No Output, preferences or font writer is used; the clipboard is
written only by the literal-copy action (explicit user click).
"""

from collections.abc import Callable
from time import monotonic
from typing import Any
from fontlabapp.glyphs.common.model import MARK_HOLD, checkpoint, render
import fontlabapp.glyphs.common.lifetime as lifetime
from fontlabapp.core.signals.scope import Scope
from fontlabapp.glyphs.common.mime import LiteralCopy
from fontlabapp.qt.properties import value


def panel_type(gui: Any, *, qt: Any = None) -> type:
    """Bind lazily to host QtGui or injected real standalone Qt widgets."""

    class CommonGlyphsPanel(gui.QDialog):
        """One complete detached snapshot; failed cleanup stays explicitly owned."""

        def __init__(
            self,
            parent: Any,
            report: dict,
            refresh: Callable,
            *,
            deadline: float | None = None,
            copy_sink: Callable | None = None,
        ) -> None:
            """Stage one complete report and retain any failed construction cleanup."""
            limit = monotonic() + 3 if deadline is None else deadline
            checkpoint(limit - 0.5, monotonic)
            lifetime.require_clear()
            gui.QDialog.__init__(self, parent)
            try:
                self.closed = self.busy = self._native_destroyed = (
                    self._delete_scheduled
                ) = False
                self.scopes, self.last_failure = [], None
                self.snapshot, self.refresh_report = None, refresh
                check = lambda: checkpoint(
                    limit - 0.5, monotonic, cancelled=lambda: self.closed
                )
                self.terminal = Scope(self.failure)
                self.terminal.connect(
                    self.destroyed, lambda *args: self.destroyed_cleanup(), closing=True
                )
                self.setWindowTitle("Common Glyphs")
                self.setModal(False)
                self.resize(760, 650)
                root = gui.QVBoxLayout(self)
                self.status = gui.QLabel(
                    "Detached report; Refresh after changing open fonts."
                )
                self.status.setWordWrap(True)
                root.addWidget(self.status)
                self.representation = gui.QLabel(
                    "Plain-text copying can normalize Unicode spaces/separators. "
                    "Use Copy Characters/Copy Original Report for exact source MIME payloads. "
                    "Escaped JSON also retains exact strings. Native MIME/clipboard handoff "
                    "and rendering remain unqualified."
                )
                self.representation.setWordWrap(True)
                root.addWidget(self.representation)
                self.editor = gui.QPlainTextEdit()
                self.editor.setReadOnly(True)
                root.addWidget(self.editor)
                self.literal_copy = LiteralCopy(
                    qt,
                    self.editor,
                    copy_sink
                    if copy_sink is not None
                    else lambda mime: value(gui.QApplication, "clipboard").setMimeData(
                        mime
                    ),
                )
                self.charcoal = gui.QCheckBox(
                    "Mark common glyphs charcoal in every open font (unavailable)"
                )
                self.charcoal.setChecked(False)
                self.charcoal.setEnabled(False)
                self.charcoal.setToolTip(MARK_HOLD)
                root.addWidget(self.charcoal)
                self.hold = gui.QLabel(MARK_HOLD)
                self.hold.setWordWrap(True)
                root.addWidget(self.hold)
                for attr, title in (
                    ("refresh_button", "Refresh report"),
                    ("copy_characters_button", "Copy Characters"),
                    ("copy_report_button", "Copy Original Report"),
                    ("mark_button", "Mark all open fonts — unavailable"),
                    ("close_button", "Close"),
                ):
                    check()
                    button = gui.QPushButton(title)
                    setattr(self, attr, button)
                    root.addWidget(button)
                self.mark_button.setEnabled(False)
                self.connect_owned(
                    self.refresh_button.clicked, lambda *args: self.refresh()
                )
                self.connect_owned(
                    self.copy_characters_button.clicked,
                    lambda *args: self.copy_text("characters"),
                )
                self.connect_owned(
                    self.copy_report_button.clicked,
                    lambda *args: self.copy_text("source_text"),
                )
                self.connect_owned(
                    self.close_button.clicked,
                    lambda *args: self.close(),
                    closing=True,
                    retry=True,
                )
                self.publish(report, limit - 0.5)
                check()
            except Exception as error:
                try:
                    self.recover_owned(limit)
                except Exception as cleanup:
                    failure = ExceptionGroup(
                        "Common Glyphs construction and cleanup failed.",
                        [error, cleanup],
                    )
                    lifetime.retain(self, failure)
                    raise failure
                raise

        def failure(self, error: Exception) -> None:
            """Store the original failure without escaping a Qt callback."""
            self.last_failure = error
            label = getattr(self, "status", None)
            if label is not None and not getattr(self, "_native_destroyed", False):
                label.setText(str(error))

        def connect_owned(
            self, signal: Any, callback: Callable, **options: Any
        ) -> None:
            """Keep one exact signal pair per scope for bounded disconnection."""
            scope = Scope(self.failure)
            self.scopes.append(scope)
            scope.connect(signal, callback, **options)

        def publish(self, report: dict, deadline: float) -> None:
            """Stage complete serialization before replacing either report view."""
            check = lambda: checkpoint(
                deadline, monotonic, cancelled=lambda: self.closed
            )
            complete = render(report, check=check)
            check()
            self.editor.setPlainText(complete)
            self.snapshot = report
            check()

        def refresh(self) -> None:
            """Replace complete fresh facts; a capture refusal keeps the last snapshot."""
            if self.closed or self.busy:
                return
            deadline = monotonic() + 3
            self.busy = True
            self.refresh_button.setEnabled(False)
            try:
                report = self.refresh_report(
                    deadline=deadline - 0.5, cancelled=lambda: self.closed
                )
                self.publish(report, deadline - 0.5)
                self.status.setText(
                    "Detached report refreshed. Charcoal marking remains unavailable."
                )
            except Exception as error:
                self.failure(error)
            finally:
                self.busy = False
                if not self.closed:
                    self.refresh_button.setEnabled(True)

        def mark_common(self) -> None:
            """Diagnose even programmatic invocation; never guess a native writer."""
            if not self.closed:
                self.failure(RuntimeError(MARK_HOLD))

        def copy_text(self, field: str) -> None:
            """Copy exact detached source data only after an explicit user action."""
            if self.closed or self.busy:
                return
            deadline = monotonic() + 3
            try:
                check = lambda: checkpoint(
                    deadline - 0.5, monotonic, cancelled=lambda: self.closed
                )
                self.literal_copy.send(self.snapshot[field], check)
                self.status.setText("Literal source MIME text sent to clipboard.")
            except Exception as error:
                if self.literal_copy.mime is not None:
                    try:
                        self.literal_copy.dispose(
                            lambda: checkpoint(deadline, monotonic)
                        )
                    except Exception as cleanup:
                        failure = ExceptionGroup(
                            "Literal copy and cleanup failed.", [error, cleanup]
                        )
                        lifetime.retain(self, failure)
                        self.failure(failure)
                        self.status.setText(f"Literal copy failed: {error}; {cleanup}")
                        return
                self.failure(error)
                if self.literal_copy.last_transfer:
                    self.status.setText(
                        str(error)
                        + " Literal MIME transfer completed before this failure; it was not rolled back."
                    )

        def recover_owned(
            self, deadline: float, *, cancelled: Callable = lambda: False
        ) -> None:
            """Fence work and disconnect exact owned pairs before deferred deletion."""
            check = lambda: checkpoint(deadline, monotonic, cancelled=cancelled)
            check()
            self.closed = True
            copy = getattr(self, "literal_copy", None)
            if copy is not None:
                copy.dispose(check)
            for scope in (
                *getattr(self, "scopes", ()),
                getattr(self, "terminal", None),
            ):
                check()
                if scope is not None and not scope.finish(
                    destroyed=getattr(self, "_native_destroyed", False)
                ):
                    raise RuntimeError(
                        "Common Glyphs signal cleanup is incomplete."
                    ) from self.last_failure
                check()
            self.refresh_report = self.snapshot = None
            if not getattr(self, "_delete_scheduled", False):
                self.hide()
                check()
                self.deleteLater()
                self._delete_scheduled = True
                check()

        def destroyed_cleanup(self) -> None:
            """Release dead emitters without calling their native wrappers again."""
            self._native_destroyed = self._delete_scheduled = True
            try:
                self.recover_owned(monotonic() + 0.5)
                lifetime.release(self)
            except Exception as error:
                lifetime.retain(self, error)

        def closeEvent(self, event: Any) -> None:
            """Contain Close failures and keep the owner available for recovery."""
            deadline = monotonic() + 0.5
            try:
                self.recover_owned(deadline)
                gui.QDialog.closeEvent(self, event)
                checkpoint(deadline, monotonic)
                lifetime.release(self)
            except Exception as error:
                lifetime.retain(self, error)
                self.failure(error)
                event.ignore()

    return CommonGlyphsPanel
