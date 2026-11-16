# this_file: src/fontlabapp/fontui/feature_source.py
# SPDX-License-Identifier: Apache-2.0
"""Feature-source input intent at an injected native Qt text boundary.

FeatureState owns source blocks and EOL restoration. This widget owns only the
current native document and admitted display intent; opaque mutations quarantine
persistence until explicit reload. It neither stages nor writes a font.
"""

from collections.abc import Callable
from typing import Any

from fontlabapp.fontui.features_state import shown
from fontlabapp.qt.properties import value
from fontlabapp.qt.literal_text import read_text, set_mime_text


def raw(text: str) -> str:
    """Native document separators for an independently known display intent."""
    return shown(text).replace("\n", "\u2029")


def supported(text: str) -> bool:
    return not any(c in text for c in ("\u2029", "\ufdd0", "\ufdd1"))


def create_source_input(
    qt: Any,
    parent: Any = None,
    *,
    is_closed: Callable[[], bool],
    on_change: Callable[[], None],
    on_diagnostic: Callable[[str], None],
) -> Any:
    """Create a feature-only native editor; callbacks and Qt remain owner supplied."""
    core, gui = qt.QtCore, qt.QtGui

    class SourceInput(gui.QPlainTextEdit):
        """Validate intent before one owned cursor operation; quarantine bypasses."""

        def __init__(self) -> None:
            gui.QPlainTextEdit.__init__(self, parent)
            self.active = None
            self.owner_closed = is_closed
            self.closed = False
            self.model_readonly = False
            self.quarantined = False
            self.diagnostic = ""
            self.last_error = None
            self.on_change = on_change
            self.on_diagnostic = lambda message: None
            self.original = self.accepted = ""
            self.ambiguous = False
            self.connections = []
            if not self.load_source(""):
                raise ValueError("Cannot initialize feature source for a closed owner.")
            self.on_diagnostic = on_diagnostic

        def _report(self, message: str) -> None:
            self.diagnostic = message
            try:
                self.on_diagnostic(message)
            except BaseException as error:
                self.last_error = error
                self.quarantined = True

        def setReadOnly(self, readonly: bool) -> None:
            """Keep backend capability separate from an inspect-only source block."""
            self.model_readonly = bool(readonly)
            gui.QPlainTextEdit.setReadOnly(self, self.model_readonly or self.ambiguous)

        def source_text(self) -> str:
            """Return admitted display intent; refuse before any staging or font write."""
            text = self._gate()
            if text is None:
                raise ValueError(
                    self.diagnostic or "Feature source input is not trusted."
                )
            return text

        def _change(self, position: int, removed: int, added: int) -> None:
            event = (position, removed, added)
            if self.active is None:
                self.quarantined = True
                self._report("Opaque document mutation: persistence refused.")
            else:
                if len(self.active["events"]) < 2:
                    self.active["events"].append(event)
                if len(self.active["events"]) > 1:
                    self.quarantined = True

        def _gate(self) -> str | None:
            """Return approved display intent or None; do not mutate a model."""
            if self.closed or self.owner_closed() or self.active is not None:
                return None
            if self.document() is not self.observed_document:
                self.quarantined = True
                self._report("Unobserved replacement document: persistence refused.")
            if value(self.document(), "revision") != self.revision:
                self.quarantined = True
            if self.quarantined or read_text(
                qt, value(self.document(), "toRawText")
            ) != raw(self.accepted):
                return None
            return self.accepted

        def _replace(self, text: str, cursor: Any = None) -> bool:
            if self.active is not None:
                self._report("Reentrant input refused.")
                return False
            if (
                self._gate() is None
                or self.model_readonly
                or self.ambiguous
                or not supported(text)
            ):
                self._report("Unsupported or untrusted source input refused.")
                return False
            cursor = gui.QTextCursor(cursor or self.textCursor())
            try:
                planned = self._payload(text, cursor)
            except UnicodeError:
                self._report("Selection splits a Unicode character.")
                return False
            if planned[0] == self.accepted:
                return True

            def insert() -> None:
                cursor.insertText(shown(text))
                self.setTextCursor(cursor)

            return self._native(insert, planned)

        def setPlainText(self, text: str) -> bool:
            cursor = self.textCursor()
            cursor.select(gui.QTextCursor.Document)
            return self._replace(text, cursor)

        def insertPlainText(self, text: str) -> bool:
            return self._replace(text)

        def _connect(self, signal: Any, callback: Callable) -> None:
            signal.connect(callback)
            self.connections.append((signal, callback))

        def _disconnect_document(self) -> None:
            while self.connections:
                signal, callback = self.connections[-1]
                signal.disconnect(callback)
                self.connections.pop()

        def _bind(self, document: Any) -> None:
            """Observe the owned document before native widget forwarding attaches."""
            self.observed_document = document
            self._connect(document.contentsChange, self._change)
            for name in (
                "undoCommandAdded",
                "contentsChange",
                "contentsChanged",
                "undoAvailable",
                "redoAvailable",
                "modificationChanged",
            ):
                self._connect(
                    getattr(document, name),
                    lambda *args, name=name: self._checkpoint(name),
                )
            for name in ("documentSizeChanged", "update", "updateBlock"):
                self._connect(
                    getattr(document.documentLayout(), name),
                    lambda *args, name=name: self._checkpoint("layout." + name),
                )

        def _state(self) -> dict[str, Any]:
            d = self.observed_document
            return {
                "raw": read_text(qt, value(d, "toRawText")),
                "revision": value(d, "revision"),
                "undo_steps": value(d, "availableUndoSteps"),
                "redo_steps": value(d, "availableRedoSteps"),
            }

        def _checkpoint(self, name: str) -> None:
            if self.closed or self.owner_closed():
                self.quarantined = True
                return
            receipt = self.active
            if receipt is None or not receipt.get("native"):
                return
            state = self._state()
            full_intent = receipt["intended"] is not None and state["raw"] == raw(
                receipt["intended"]
            )
            early = name in ("undoAvailable", "redoAvailable") and (
                full_intent or receipt["intended"] is None
            )
            terminal = (
                early
                or name in ("undoCommandAdded", "contentsChange")
                or name.startswith("layout.")
            )
            if receipt["checkpoint"] is None and terminal:
                receipt["checkpoint"] = state
            checkpoint = receipt["checkpoint"]
            if checkpoint is not None and state != checkpoint:
                self.quarantined = True

        def _intent(self, text: str, cursor: Any = None) -> str:
            cursor = cursor or self.textCursor()
            a, b = value(cursor, "selectionStart"), value(cursor, "selectionEnd")
            before = self.accepted.encode("utf-16-le")
            return (
                before[: 2 * a].decode("utf-16-le")
                + shown(text)
                + before[2 * b :].decode("utf-16-le")
            )

        def _payload(self, text: str, cursor: Any = None) -> tuple:
            cursor = cursor or self.textCursor()
            return (
                self._intent(text, cursor),
                (
                    value(cursor, "selectionStart"),
                    value(cursor, "selectionEnd") - value(cursor, "selectionStart"),
                    len(shown(text).encode("utf-16-le")) // 2,
                ),
            )

        def _key_intent(self, event: Any) -> tuple:
            if self.model_readonly or self.ambiguous:
                return self.accepted, None
            if event.matches(gui.QKeySequence.Undo) or event.matches(
                gui.QKeySequence.Redo
            ):
                return None, None
            if event.matches(gui.QKeySequence.InsertLineSeparator):
                return self._payload("\u2028")
            if event.matches(gui.QKeySequence.InsertParagraphSeparator):
                return self._payload("\n")
            if value(event, "modifiers") & (
                core.Qt.ControlModifier | core.Qt.MetaModifier
            ):
                return None, None
            if value(event, "key") in (core.Qt.Key_Backspace, core.Qt.Key_Delete):
                cursor = self.textCursor()
                if not value(cursor, "hasSelection"):
                    move = (
                        gui.QTextCursor.PreviousCharacter
                        if value(event, "key") == core.Qt.Key_Backspace
                        else gui.QTextCursor.NextCharacter
                    )
                    cursor.movePosition(move, gui.QTextCursor.KeepAnchor)
                return self._payload("", cursor)
            text = read_text(qt, value(event, "text"))
            if text and (text[0].isprintable() or text[0] == "\t"):
                return self._payload(text)
            return self.accepted, None

        def _native(
            self, operation: Callable[[], None], planned: tuple = (None, None)
        ) -> bool:
            """Validate one unblocked native command against owned checkpoints."""
            if self.active is not None or self._gate() is None:
                self._report("Reentrant/untrusted native input refused.")
                return False
            intended, span = planned
            document = self.observed_document
            before = self._state()
            receipt = {
                "native": True,
                "before": self.accepted,
                "events": [],
                "intended": intended,
                "span": span,
                "document_signals_blocked_before": value(document, "signalsBlocked"),
                "checkpoint": None,
            }
            self.active = receipt
            try:
                operation()
            except BaseException as error:
                self.quarantined = True
                self.last_error = error
                receipt["error"] = repr(error)
            finally:
                self.active = None
            if self.closed or self.owner_closed() or self.document() is not document:
                self.quarantined = True
            final = self._state()
            checkpoint = receipt["checkpoint"]
            unchanged = final == before
            correlated_span = (
                span is None
                or unchanged
                or receipt["events"] == [span]
                or (
                    not receipt["events"] and receipt["document_signals_blocked_before"]
                )
            )
            valid = (
                not self.quarantined
                and (unchanged or checkpoint == final)
                and correlated_span
                and (intended is None or final["raw"] == raw(intended))
            )
            if not valid:
                self.quarantined = True
                self._report("Native command/checkpoint mismatch: persistence refused.")
            else:
                self.accepted = (
                    intended
                    if intended is not None
                    else final["raw"].replace("\u2029", "\n")
                )
                self.revision = final["revision"]
            receipt["accepted"] = valid
            if valid and self.accepted != receipt["before"]:
                try:
                    self.on_change()
                except BaseException as error:
                    self.last_error = error
                    self.quarantined = True
                    self._report(str(error))
            return valid and self._gate() is not None

        def insertFromMimeData(self, mime: Any) -> bool:
            """Validate one borrowed text snapshot, then insert only owned MIME."""
            if (
                self.closed
                or self.owner_closed()
                or self.active is not None
                or self.model_readonly
                or self.ambiguous
            ):
                return False
            snapshot = None
            failure = None
            try:
                if self._gate() is None:
                    return False
                cursor = gui.QTextCursor(self.textCursor())
                selection = (value(cursor, "anchor"), value(cursor, "position"))
                self.active = {"mime": True, "events": []}
                try:
                    text = None
                    if value(mime, "hasText"):
                        text = read_text(qt, value(mime, "text"))
                        if not supported(text):
                            self._report(
                                "Unsupported MIME payload refused before insertion."
                            )
                            return False
                        snapshot = core.QMimeData()
                        snapshot.setParent(self)
                        set_mime_text(qt, snapshot, text)
                finally:
                    self.active = None
                if (
                    self.closed
                    or self.owner_closed()
                    or self.model_readonly
                    or self.ambiguous
                    or self._gate() is None
                ):
                    return False
                current = self.textCursor()
                if (value(current, "anchor"), value(current, "position")) != selection:
                    self.quarantined = True
                    self._report(
                        "Selection changed during MIME retrieval; insertion refused."
                    )
                    return False
                if text is None:
                    return True
                # Native empty MIME leaves a selected range intact, unlike an
                # explicit cursor insertion of an empty string.
                planned = self._payload(text, cursor) if text else (self.accepted, None)
                return self._native(
                    lambda: gui.QPlainTextEdit.insertFromMimeData(self, snapshot),
                    planned,
                )
            except BaseException as error:
                failure = error
                self.quarantined = True
                self._report(str(error))
                self.last_error = error
                return False
            finally:
                if snapshot is not None:
                    try:
                        snapshot.deleteLater()
                        core.QCoreApplication.sendPostedEvents(
                            snapshot, core.QEvent.DeferredDelete
                        )
                    except BaseException as error:
                        self.quarantined = True
                        self._report(str(error))
                        if failure is not None:
                            failure.add_note(
                                "Owned MIME cleanup failed: " + repr(error)
                            )
                        self.last_error = failure if failure is not None else error
                        return False

        def keyPressEvent(self, event: Any) -> None:
            try:
                if not supported(read_text(qt, value(event, "text"))):
                    self._report("Unsupported raw key payload refused.")
                    event.ignore()
                    return
                if value(event, "key") in (core.Qt.Key_Return, core.Qt.Key_Enter):
                    if read_text(qt, value(event, "text")) not in ("", "\r", "\n"):
                        self._report("Inconsistent Return payload refused.")
                        event.ignore()
                        return
                if event.matches(gui.QKeySequence.Paste):
                    # Native Paste delegates to the guarded immutable MIME route.
                    gui.QPlainTextEdit.keyPressEvent(self, event)
                    return
                if any(
                    event.matches(k)
                    for k in (
                        gui.QKeySequence.Copy,
                        gui.QKeySequence.Cut,
                    )
                ):
                    self._report("OS clipboard route is not admitted.")
                    event.ignore()
                    return
                self._native(
                    lambda: gui.QPlainTextEdit.keyPressEvent(self, event),
                    self._key_intent(event),
                )
            except BaseException as error:
                self.quarantined = True
                self._report(repr(error))

        def inputMethodEvent(self, event: Any) -> None:
            try:
                if (
                    not supported(read_text(qt, value(event, "commitString")))
                    or not supported(read_text(qt, value(event, "preeditString")))
                    or value(event, "replacementStart")
                    or value(event, "replacementLength")
                    or read_text(qt, value(event, "preeditString"))
                    or value(event, "attributes")
                    or self.model_readonly
                    or self.ambiguous
                ):
                    self._report(
                        "Unsupported IME event refused before selection removal."
                    )
                    event.ignore()
                    return
                # Root-admitted narrow domain: native cursor receipt, not base IME dispatch.
                if self._replace(read_text(qt, value(event, "commitString"))):
                    event.accept()
                else:
                    event.ignore()
            except BaseException as error:
                self.quarantined = True
                self._report(repr(error))

        def load_source(self, source: str) -> bool:
            """Explicitly replace this view's document, never mutate a foreign document."""
            if self.closed or self.owner_closed() or self.active is not None:
                return False
            document = gui.QTextDocument(self)
            document.setDocumentLayout(gui.QPlainTextDocumentLayout(document))
            document.setPlainText(shown(source))
            revision = value(document, "revision")
            self._disconnect_document()
            self.active = {"recovery": True, "events": []}
            self.quarantined = True
            self._bind(document)
            try:
                gui.QPlainTextEdit.setDocument(self, document)
                valid = (
                    not self.closed
                    and self.document() is document
                    and value(document, "revision") == revision
                    and read_text(qt, value(document, "toRawText")) == raw(source)
                    and not self.active["events"]
                )
            finally:
                self.active = None
                self.observed_document = document

            if not valid:
                return False
            self.original = source
            self.accepted = shown(source)
            self.revision = revision
            self.ambiguous = not supported(source)
            gui.QPlainTextEdit.setReadOnly(self, self.model_readonly or self.ambiguous)
            self.quarantined = False
            self._report("Explicitly reloaded current source.")
            valid = (
                self.observed_document is document
                and self._gate() == shown(source)
                and self.revision == revision
                and self.original == source
            )
            if not valid:
                self.quarantined = True
            return valid

        def dropEvent(self, event: Any) -> None:
            try:
                text = read_text(qt, value(value(event, "mimeData"), "text"))
                if (
                    not supported(text)
                    or value(event, "proposedAction") != core.Qt.CopyAction
                ):
                    self._report("Unsupported drop refused.")
                    event.ignore()
                    return
                point = (
                    value(event, "position").toPoint()
                    if hasattr(event, "position")
                    else value(event, "pos")
                )
                cursor = self.cursorForPosition(point)
                if self._replace(text, cursor):
                    event.acceptProposedAction()
                else:
                    event.ignore()
            except BaseException as error:
                self.quarantined = True
                self._report(repr(error))

    widget = SourceInput.__new__(SourceInput)
    try:
        SourceInput.__init__(widget)
    except BaseException as error:
        try:
            widget.close()
            widget.deleteLater()
        except BaseException as cleanup_error:
            error.add_note("Feature source cleanup failed: " + repr(cleanup_error))
        raise
    return widget
