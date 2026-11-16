# this_file: tests/test_feature_source_controls.py
# SPDX-License-Identifier: Apache-2.0
"""All 183 independent private boundary controls on the actual production module.

Admissions here are private observations, never font writes. Real font writes
are exercised separately by test_fontui_feature_source.
"""
import json
import traceback
from types import SimpleNamespace

import shiboken6
from PySide6 import QtCore, QtGui, QtWidgets

from _feature_source_qt import owned_application, qt_namespace
from fontlabapp.fontui import feature_source as component

shown, raw = component.shown, component.raw
qt = qt_namespace()
module = SimpleNamespace(component=component, qt=qt, raw=raw, shown=shown)

def SourceInput(source):
    """Keep old observation names; every authority decision is the real API."""
    callbacks, notices = [], []
    w = component.create_source_input(qt, is_closed=lambda: False,
        on_change=lambda: [callback() for callback in tuple(callbacks)],
        on_diagnostic=notices.append)
    assert w.load_source(source)
    w.test_change_callbacks = callbacks
    w.test_notices = notices
    w.admissions = []

    def gate():
        try:
            return w.source_text()
        except ValueError:
            return None

    def apply_gate():
        intent = gate()
        if intent is None or intent == shown(w.original):
            return False
        w.admissions.append(intent)  # private observation, not a font write
        return True

    def close_protocol():
        w.closed = True
        w._disconnect_document()
        w.close()
        w.deleteLater()

    w.gate, w.apply_gate = gate, apply_gate
    w.switch_gate = lambda: gate() is not None
    w.revert = w.load_source
    w.close_protocol = close_protocol
    # Old prototype observation only: product external-change/stale handling is
    # deliberately not implemented or claimed by this component adapter.
    w.external_notification = lambda latest: w._report('External source changed; explicit Revert may reload it.')
    return w

def editor(text="A\nB", a=0, b=0):
    w = SourceInput(text)
    widgets.append(w)
    cursor = w.textCursor()
    cursor.setPosition(a)
    cursor.setPosition(b, QtGui.QTextCursor.KeepAnchor)
    w.setTextCursor(cursor)
    return w

def snapshot(w):
    c = w.textCursor()
    return {"raw": QtGui.QTextDocument.toRawText(w.document()), "anchor": c.anchor(),
            "position": c.position(), "revision": QtGui.QTextDocument.revision(w.document()),
            "undo": w.document().isUndoAvailable(), "redo": w.document().isRedoAvailable()}

def check(value, message):
    if not value:
        raise AssertionError(message)

def case(name, call):
    start = len(widgets)
    row = {"name": name, "status": "RUNNING"}
    try:
        row["observations"] = call()
        row["status"] = "PASS"
    except BaseException as error:
        row.update(status="FAIL", error=repr(error), traceback=traceback.format_exc())
    finally:
        row["widgets"] = [{"view": snapshot(w), "quarantined": w.quarantined,
                           "accepted_intent": w.accepted, "active_receipt": w.active,
                           "admission_callbacks": w.admissions,
                           "diagnostic": w.diagnostic} for w in widgets[start:]]
        results.append(row)
        (OUT / "cases.json").write_text(json.dumps(results, indent=2) + "\n")

def weak_path():
    w = editor()
    QtWidgets.QPlainTextEdit.setPlainText(w, "A\u2029B")
    check(w.document().toRawText() == "A\u2029B", "Actual Qt canonicalization")
    check(w.toPlainText() == "A\nB", "Actual lossy getter")
    return {"ordinary_LF_and_literal_PS_indistinguishable": True,
            "weak_normalized_equality_would_pass": True, "candidate_gate": w.gate()}

def positive(payload, a, b, expected):
    w = editor("A😀\nB", a, b)
    check(w.insertPlainText(payload), "Required supported insertion was refused")
    check(w.gate() == expected, "Independent intended source differs")
    check(w.apply_gate(), "Supported edit must admit once")
    check(w.admissions == [expected], "Admission callback must receive exact intent")

def invoke(w, route, payload):
    if route == "setter":
        w.setPlainText(payload)
    elif route == "insert":
        w.insertPlainText(payload)
    elif route == "mime":
        mime = QtCore.QMimeData()
        try:
            mime.setText(payload)
            w.insertFromMimeData(mime)
        finally:
            shiboken6.delete(mime)
    elif route == "key":
        event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_unknown,
                               QtCore.Qt.NoModifier, payload)
        QtCore.QCoreApplication.sendEvent(w, event)
    elif route == "ime":
        event = QtGui.QInputMethodEvent()
        event.setCommitString(payload)
        QtCore.QCoreApplication.sendEvent(w, event)
    elif route == "drop":
        mime = QtCore.QMimeData()
        try:
            mime.setText(payload)
            event = QtGui.QDropEvent(QtCore.QPointF(1, 1), QtCore.Qt.CopyAction,
                                    mime, QtCore.Qt.NoButton, QtCore.Qt.NoModifier)
            w.dropEvent(event)
        finally:
            shiboken6.delete(mime)

def refusal(route, payload):
    w = editor("A😀\nB", 1, 4)
    before = snapshot(w)
    invoke(w, route, payload)
    check(snapshot(w) == before, "Supported-boundary refusal changed view/selection/history")
    check(not w.apply_gate() and not w.admissions, "Refusal admitted source")
    check(w.switch_gate(), "Clean refused input must not poison unchanged source")

def positive_route(route, payload, expected):
    w = editor("AB", 1, 1)
    invoke(w, route, payload)
    check(w.gate() == expected, "Required supported route failed exact intent")
    check(w.apply_gate() and w.admissions == [expected], "Expected private admission")

def enter(key):
    w = editor("AB", 1, 1)
    event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, QtCore.Qt.NoModifier, "\r")
    QtCore.QCoreApplication.sendEvent(w, event)
    check(w.gate() == "A\nB", "Ordinary Enter must remain supported")
    check(w.apply_gate() and w.admissions == ["A\nB"], "Enter source admission")

def opaque(w, route):
    if route == "document":
        w.document().setPlainText("A\u2029B")
    elif route == "base":
        QtWidgets.QPlainTextEdit.setPlainText(w, "A\u2029B")
    else:
        cursor = QtGui.QTextCursor(w.document())
        cursor.select(QtGui.QTextCursor.Document)
        if route == "blocked_cursor":
            prior = w.document().blockSignals(True)
            try:
                cursor.insertText("A\u2029B")
            finally:
                w.document().blockSignals(prior)
        else:
            cursor.insertText("A\u2029B")

def quarantine(route):
    w = editor()
    opaque(w, route)
    after = snapshot(w)
    check(not w.apply_gate() and not w.switch_gate(), "Opaque mutation borrowed authority")
    check(not w.admissions and snapshot(w) == after, "Quarantine altered observed draft")
    return {"observed_post_call_retained": after}

def reentrant(signal, action):
    w = editor("AB", 1, 2 if signal == "selectionChanged" else 1)
    expected = "A\n" if signal == "selectionChanged" else "A\nB"
    fired = []
    callback_errors = []
    def nested(*args):
        if fired:
            return
        fired.append(True)
        try:
            check(not w.apply_gate(), "Gate active inside notification")
            if action == "opaque":
                opaque(w, "cursor")
            else:
                check(not w.insertPlainText("\u2029"), "Nested public input acquired authority")
        except BaseException as error:
            callback_errors.append(repr(error))
    getattr(w, signal).connect(nested)
    w.insertPlainText("\n")
    check(fired, "Actual notification did not fire")
    check(not callback_errors, str(callback_errors))
    after = snapshot(w)
    if action == "opaque":
        check(not w.apply_gate() and not w.switch_gate(), "Reentrant opaque admission")
        check(not w.admissions and snapshot(w) == after, "Quarantine lost observed draft")
    else:
        check(w.gate() == expected, "Refused nested request spoiled valid outer source")
    getattr(w, signal).disconnect(nested)

def ambiguous():
    w = editor("A\u2029B", 1, 2)
    before = snapshot(w)
    check(not w.apply_gate(), "Original ambiguous source must be a no-op")
    check(w.switch_gate(), "Original unchanged block should switch safely")
    check(not w.insertPlainText("X"), "Literal PS source is inspect-only")
    check(snapshot(w) == before and not w.admissions, "Ambiguous source was changed")

def recovery():
    w = editor()
    opaque(w, "document")
    after = snapshot(w)
    check(not w.apply_gate() and not w.switch_gate() and snapshot(w) == after,
          "Quarantine failed")
    # Explicit fresh owned view is a recovery control, not FeaturesEditor.refresh proof.
    replacement = editor("A\nB")
    check(replacement.gate() == "A\nB" and not replacement.apply_gate(), "Fresh recovery")
    return {"recovery_surface": "explicit fresh owned view; existing-widget Revert unqualified"}

def replacement_document():
    w = editor("AB", 1, 1)
    check(w.insertPlainText("\n"), "Prepare trusted changed draft")
    document = QtGui.QTextDocument(w)
    document.setDocumentLayout(QtWidgets.QPlainTextDocumentLayout(document))
    document.setPlainText("A\u2029")
    cursor = QtGui.QTextCursor(document)
    cursor.movePosition(QtGui.QTextCursor.End)
    cursor.insertText("B")
    check(document.revision() == w.revision, "Counterexample requires actual equal revisions")
    check(document.toRawText() == w.document().toRawText(), "Counterexample requires equal raw view")
    QtWidgets.QPlainTextEdit.setDocument(w, document)
    after = snapshot(w)
    check(not w.apply_gate() and not w.switch_gate(), "Unobserved replacement document acquired authority")
    check(not w.admissions and snapshot(w) == after, "Replacement quarantine must retain observed draft")

def positive_drop():
    w = editor("AB", 1, 2)
    check(w.cursorForPosition(QtCore.QPoint(1, 1)).position() == 0, "Independent drop target")
    invoke(w, "drop", "X\nY")
    check(w.gate() == "X\nYAB", "Owned copy drop must retain source intent")
    check(w.apply_gate() and w.admissions == ["X\nYAB"], "Drop admission")

def original_noop(source):
    w = editor(source, 1, 1)
    before = snapshot(w)
    check(w.setPlainText(module.shown(source)), "No-op setter refused")
    check(not w.apply_gate() and w.switch_gate(), "No-op admission/switch")
    check(w.original == source and snapshot(w) == before, "Original bytes or view changed")

def single_line_refusal(payload):
    w = editor("AB", 0, 2)
    before = snapshot(w)
    invoke(w, "mime", payload)
    check(snapshot(w) == before and not w.apply_gate() and not w.admissions,
          "Single-line whole-payload refusal")

def complex_ime_refusal():
    w = editor("AB", 0, 2)
    before = snapshot(w)
    event = QtGui.QInputMethodEvent("preedit", [])
    event.setCommitString("X", -1, 1)
    QtCore.QCoreApplication.sendEvent(w, event)
    check(snapshot(w) == before and not w.apply_gate() and not w.admissions,
          "Unqualified complex IME must refuse before selection removal")

def reentrant_blocked():
    w = editor("AB", 1, 1)
    fired = []
    def nested():
        if not fired:
            fired.append(True)
            opaque(w, "blocked_cursor")
    w.textChanged.connect(nested)
    w.insertPlainText("\n")
    check(fired, "Actual callback required")
    after = snapshot(w)
    check(not w.apply_gate() and not w.switch_gate(), "Suppressed nested signals borrowed authority")
    check(not w.admissions and snapshot(w) == after, "Observed draft retained")
    w.textChanged.disconnect(nested)

def send_key(w, code, text="", modifiers=QtCore.Qt.NoModifier, repeat=False):
    e = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, code, modifiers, text, repeat, 1)
    QtCore.QCoreApplication.sendEvent(w, e)

def bad_return(code, payload, modifiers):
    w = editor("AB", 0, 2)
    before = snapshot(w)
    send_key(w, code, payload, modifiers)
    check(snapshot(w) == before and not w.apply_gate() and not w.admissions,
          "Raw Return payload must refuse before native classification/selection removal")

def native_command(kind):
    w = editor("AB", 1, 1)
    if kind == "backspace":
        send_key(w, QtCore.Qt.Key_Backspace, "\b")
        expected = "B"
    elif kind == "delete":
        send_key(w, QtCore.Qt.Key_Delete, "\x7f")
        expected = "A"
    elif kind == "left_insert":
        send_key(w, QtCore.Qt.Key_Left)
        send_key(w, QtCore.Qt.Key_X, "X")
        expected = "XAB"
    elif kind == "shift_right_replace":
        send_key(w, QtCore.Qt.Key_Right, "", QtCore.Qt.ShiftModifier)
        check(w.textCursor().selectedText() == "B", "Native selection must extend")
        send_key(w, QtCore.Qt.Key_X, "X")
        expected = "AX"
    elif kind == "repeat":
        send_key(w, QtCore.Qt.Key_X, "X", repeat=True)
        expected = "AXB"
    elif kind == "undo_redo":
        send_key(w, QtCore.Qt.Key_X, "X")
        for command, wanted in [(QtGui.QKeySequence.Undo,"AB"), (QtGui.QKeySequence.Redo,"AXB")]:
            binding = QtGui.QKeySequence.keyBindings(command)[0][0]
            send_key(w, binding.key(), "", binding.keyboardModifiers())
            check(w.document().toRawText() == wanted and w.gate() == wanted,
                  "Native history must remain usable and trusted")
        expected = "AXB"
    check(w.document().toRawText() == module.raw(expected), "Native editing semantics changed")
    check(w.gate() == expected, "Native edit persistence cannot silently be refused")

def same_widget_revert(foreign=False):
    w = editor("A\r\nB", 1, 1)
    identity = id(w)
    if foreign:
        donor = editor("foreign\u2029draft")
        doc = donor.document()
        doc_before = doc.toRawText()
        QtWidgets.QPlainTextEdit.setDocument(w, doc)
    else:
        opaque(w, "document")
    after = snapshot(w)
    check(not w.apply_gate() and not w.switch_gate(), "Untrusted draft must remain fenced")
    if hasattr(w, "external_notification"):
        w.external_notification("external\nlatest")
    check(snapshot(w) == after and not w.admissions, "External notification discarded draft")
    check(w.revert("latest\r\nsource"), "Explicit same-widget recovery must succeed")
    check(id(w) == identity and w.gate() == "latest\nsource" and not w.apply_gate(),
          "Recovered current source must be a no-op")
    if foreign:
        check(doc.toRawText() == doc_before, "Revert mutated borrowed foreign document")
    return {"same_widget": True, "font_or_staging_claim": False}

def layout_reentry():
    w = editor("AB", 1, 1)
    fired = []
    def nested(*args):
        if not fired:
            fired.append(True)
            opaque(w, "cursor")
    layout = w.document().documentLayout()
    layout.documentSizeChanged.connect(nested)
    send_key(w, QtCore.Qt.Key_Return, "\r")
    check(fired, "Actual native layout callback must execute for this counterexample")
    after = snapshot(w)
    check(not w.apply_gate() and not w.switch_gate(),
          "Layout callback inserted literal PS during native signal-isolated authority")
    check(not w.admissions and snapshot(w) == after, "Observed opaque draft must remain")
    layout.documentSizeChanged.disconnect(nested)

def native_notifications():
    w = editor("AB", 1, 1)
    calls = {"text": 0, "cursor": 0, "document": 0, "intent": 0}
    def tick(name):
        calls[name] += 1
    w.textChanged.connect(lambda: tick("text"))
    w.cursorPositionChanged.connect(lambda: tick("cursor"))
    w.document().contentsChanged.connect(lambda: tick("document"))
    w.test_change_callbacks.append(lambda: tick("intent"))
    send_key(w, QtCore.Qt.Key_X, "X")
    check(w.gate() == "AXB", "Native source edit must be retained")
    check(all(calls[n] > 0 for n in ("text", "cursor", "document")),
          "Existing native consumer notifications were suppressed: " + repr(calls))
    return calls

def post_authority_reentry():
    w = editor("AB", 1, 1)
    fired = []
    def nested():
        fired.append(w.active)
        opaque(w, "cursor")
    w.test_change_callbacks.append(nested)
    send_key(w, QtCore.Qt.Key_X, "X")
    check(fired == [None], "Own notification must run after authority ends")
    after = snapshot(w)
    check(not w.apply_gate() and not w.switch_gate() and not w.admissions,
          "Post-authority opaque callback escaped quarantine")
    check(snapshot(w) == after, "Quarantine changed observed draft")

def restore_signal_states(block_doc, block_widget):
    w = editor("AB", 1, 1)
    w.document().blockSignals(block_doc)
    w.blockSignals(block_widget)
    send_key(w, QtCore.Qt.Key_X, "X")
    check(w.document().signalsBlocked() == block_doc and w.signalsBlocked() == block_widget,
          "Previous signal blocking states not restored")
    check(w.gate() == "AXB", "Native operation must retain source intent")

def close_after_publication():
    w = editor("AB", 1, 1)
    fired = []
    def close():
        fired.append(w.active)
        w.close_protocol()
    w.test_change_callbacks.append(close)
    send_key(w, QtCore.Qt.Key_X, "X")
    check(fired == [None] and w.closed, "Owned close callback must execute after authority")
    after = snapshot(w)
    send_key(w, QtCore.Qt.Key_Y, "Y")
    check(snapshot(w) == after and not w.apply_gate() and not w.admissions, "Closed ingress mutated")

def revert_original_ps():
    w = editor("AB", 1, 1)
    send_key(w, QtCore.Qt.Key_X, "X")
    check(w.revert("A\u2029B"), "Explicit original-PS inspect recovery")
    before = snapshot(w)
    send_key(w, QtCore.Qt.Key_X, "X")
    check(snapshot(w) == before and w.original == "A\u2029B" and not w.apply_gate(),
          "Readonly literal PS source changed")

def unexpected_return():
    w = editor("AB", 0, 2)
    before = snapshot(w)
    send_key(w, QtCore.Qt.Key_Return, "X", QtCore.Qt.ControlModifier)
    check(snapshot(w) == before and not w.apply_gate(), "Inconsistent Return text must refuse")

def native_signal_fault(name, blocked=False):
    w = editor("AB", 1, 1)
    if name == "doc.modificationChanged":
        w.document().setModified(False)
        check(not w.document().isModified(), "Explicit unmodified signal premise")
    source = w if name.startswith("widget.") else w.document()
    signal = getattr(source, name.split(".")[-1])
    fired = []
    def nested(*args):
        if not fired:
            fired.append({"active": w.active is not None,
                          "owned_observations_before_callback": list(w.active.get("observations", [])) if w.active else []})
            opaque(w, "blocked_cursor" if blocked else "cursor")
    signal.connect(nested)
    send_key(w, QtCore.Qt.Key_Return, "\r")
    check(fired and fired[0]["active"], "Actual callback must execute during native operation")
    after = snapshot(w)
    check(not w.apply_gate(), "Native signal opaque mutation admitted")
    check(not w.switch_gate() and not w.admissions and snapshot(w) == after,
          "Opaque draft quarantine/retention failed")
    signal.disconnect(nested)
    return {"callbacks": fired}

def early_selection_fault(blocked):
    w = editor("A\nB", 0, 1)
    fired = []
    def nested(*args):
        if fired:
            return
        before = snapshot(w)
        fired.append({"before": before, "owned_observations": dict(w.active["checkpoint"]) if w.active["checkpoint"] is not None else None})
        # Actual early undoAvailable occurs after selected A removal, before X insertion.
        check(before["raw"] == "\u2029B", "Early partial state must be real")
        cursor = QtGui.QTextCursor(w.document())
        cursor.setPosition(0)
        cursor.setPosition(1, QtGui.QTextCursor.KeepAnchor)
        prior = w.document().blockSignals(True) if blocked else None
        try:
            cursor.insertText("\u2029")
        finally:
            if blocked:
                w.document().blockSignals(prior)
        fired[0]["after_opaque"] = snapshot(w)
    w.document().undoAvailable.connect(nested)
    send_key(w, QtCore.Qt.Key_X, "X")
    check(fired and "after_opaque" in fired[0], "Actual early opaque callback did not complete")
    after = snapshot(w)
    check(not w.apply_gate() and not w.switch_gate(),
          "Same-canonical early mutation borrowed terminal checkpoint authority")
    check(not w.admissions and snapshot(w) == after, "Observed opaque draft retention")
    w.document().undoAvailable.disconnect(nested)
    return {"callbacks": fired}

def grouped_history():
    w = editor("AB", 1, 1)
    for char in "XY":
        send_key(w, QtCore.Qt.Key_unknown, char)
    check(w.gate() == "AXYB", "Grouped typing intent")
    for command, expected in [(QtGui.QKeySequence.Undo,"AB"), (QtGui.QKeySequence.Redo,"AXYB")]:
        binding = QtGui.QKeySequence.keyBindings(command)[0][0]
        send_key(w, binding.key(), "", binding.keyboardModifiers())
        check(w.gate() == expected, "Native grouped history intent")

def owner_fence(during):
    w = editor("AB", 1, 1)
    owner = {"closed": not during}
    w.owner_closed = lambda: owner["closed"]
    fired = []
    def close_owner():
        fired.append(True)
        owner["closed"] = True
    if during:
        w.textChanged.connect(close_owner)
    before = snapshot(w)
    send_key(w, QtCore.Qt.Key_X, "X")
    check(bool(fired) == during, "Actual close callback ordering")
    check(shiboken6.isValid(w), "Owner close must not assume physical child destruction")
    retained = snapshot(w)
    send_key(w, QtCore.Qt.Key_Y, "Y")
    check(snapshot(w) == retained and not w.apply_gate() and not w.switch_gate(),
          "Retained cleanup owner allowed ingress/persistence")
    check(not w.revert("replacement") and snapshot(w) == retained, "Closed recovery must refuse")
    if not during:
        check(retained == before, "Closed owner received first edit")

def early_within_inserted_span(blocked):
    w = editor("AB", 1, 1)
    fired = []
    def nested(*args):
        if fired:
            return
        fired.append({"observations": dict(w.active["checkpoint"]) if w.active["checkpoint"] is not None else None})
        check(w.document().toRawText() == "A\u2029B", "Real newly inserted paragraph exists")
        cursor = QtGui.QTextCursor(w.document())
        cursor.setPosition(1)
        cursor.setPosition(2, QtGui.QTextCursor.KeepAnchor)
        prior = w.document().blockSignals(True) if blocked else None
        try:
            cursor.insertText("\u2029")
        finally:
            if blocked:
                w.document().blockSignals(prior)
        fired[0]["completed"] = True
    w.document().undoAvailable.connect(nested)
    send_key(w, QtCore.Qt.Key_Return, "\r")
    check(fired and fired[0].get("completed"), "Within-span callback must execute")
    after = snapshot(w)
    check(not w.apply_gate() and not w.switch_gate() and not w.admissions,
          "Same-span early PS replacement borrowed authority")
    check(snapshot(w) == after, "Opaque observed draft changed")
    w.document().undoAvailable.disconnect(nested)
    return {"callbacks": fired}

def native_undo_fault(signal, blocked):
    w = editor("AB", 1, 1)
    send_key(w, QtCore.Qt.Key_Return, "\r")
    check(w.gate() == "A\nB", "Trusted history precondition")
    fired = []
    def nested(*args):
        if not fired:
            fired.append(True)
            opaque(w, "blocked_cursor" if blocked else "cursor")
    emitter = getattr(w.document(), signal)
    emitter.connect(nested)
    binding = QtGui.QKeySequence.keyBindings(QtGui.QKeySequence.Undo)[0][0]
    send_key(w, binding.key(), "", binding.keyboardModifiers())
    check(fired, "Undo fault callback must execute")
    after = snapshot(w)
    check(not w.apply_gate() and not w.switch_gate() and not w.admissions,
          "Opaque Undo callback borrowed trusted history")
    check(snapshot(w) == after, "Undo quarantine discarded observed draft")
    emitter.disconnect(nested)

def native_word_delete():
    w = editor("one two", 7, 7)
    binding = QtGui.QKeySequence.keyBindings(QtGui.QKeySequence.DeleteStartOfWord)[0][0]
    send_key(w, binding.key(), "", binding.keyboardModifiers())
    check(w.document().toRawText() == "one " and w.gate() == "one ",
          "Native standard word deletion must remain supported")

def selected_mime_history():
    w = editor("A😀\nB", 1, 4)
    invoke(w, "mime", "X\nY")
    check(w.gate() == "AX\nYB", "Independent selected MIME intent")
    for command, expected in [(QtGui.QKeySequence.Undo,"A😀\nB"),
                              (QtGui.QKeySequence.Redo,"AX\nYB")]:
        binding = QtGui.QKeySequence.keyBindings(command)[0][0]
        send_key(w, binding.key(), "", binding.keyboardModifiers())
        check(w.gate() == expected, "Native selected MIME grouped history")

def cursor_route_early_fault(route, blocked):
    w = editor("AB", 1, 1)
    fired = []
    def nested(*args):
        if fired:
            return
        fired.append(False)
        check(w.document().toRawText() == "A\u2029B", "Early actual inserted paragraph")
        cursor = QtGui.QTextCursor(w.document())
        cursor.setPosition(1)
        cursor.setPosition(2, QtGui.QTextCursor.KeepAnchor)
        prior = w.document().blockSignals(True) if blocked else None
        try:
            cursor.insertText("\u2029")
        finally:
            if blocked:
                w.document().blockSignals(prior)
        fired[0] = True
    w.document().undoAvailable.connect(nested)
    invoke(w, route, "\n")
    check(fired == [True], "Cursor route early callback must execute completely")
    after = snapshot(w)
    check(not w.apply_gate() and not w.switch_gate() and not w.admissions,
          "Owned cursor route borrowed early callback authority")
    check(snapshot(w) == after, "Opaque draft changed after refusal")
    w.document().undoAvailable.disconnect(nested)

def selected_ime(reverse=False, history=False):
    w = editor("A😀\nB", 4 if reverse else 1, 1 if reverse else 4)
    event = QtGui.QInputMethodEvent()
    event.setCommitString("X\nY")
    QtCore.QCoreApplication.sendEvent(w, event)
    check(event.isAccepted() and w.gate() == "AX\nYB", "Selected commit-only IME intent/acceptance")
    if history:
        for command, expected in [(QtGui.QKeySequence.Undo,"A😀\nB"),
                                  (QtGui.QKeySequence.Redo,"AX\nYB")]:
            binding = QtGui.QKeySequence.keyBindings(command)[0][0]
            send_key(w, binding.key(), "", binding.keyboardModifiers())
            check(w.gate() == expected, "Commit-only IME native grouped history")

def ime_native_notifications():
    w = editor("AB", 1, 1)
    calls = {"text": 0, "cursor": 0, "document": 0}
    def tick(name):
        calls[name] += 1
    w.textChanged.connect(lambda: tick("text"))
    w.cursorPositionChanged.connect(lambda: tick("cursor"))
    w.document().contentsChanged.connect(lambda: tick("document"))
    invoke(w, "ime", "X\nY")
    check(w.gate() == "AX\nYB" and all(v > 0 for v in calls.values()),
          "Commit-only IME must preserve native notifications")
    return calls

def ime_owner_close(during):
    w = editor("AB", 1, 1)
    owner = {"closed": not during}
    w.owner_closed = lambda: owner["closed"]
    fired = []
    def close():
        fired.append(True)
        owner["closed"] = True
    if during:
        w.textChanged.connect(close)
    before = snapshot(w)
    invoke(w, "ime", "X\nY")
    check(bool(fired) == during and shiboken6.isValid(w), "Actual retained-owner close premise")
    after = snapshot(w)
    invoke(w, "ime", "Z")
    check(snapshot(w) == after and not w.apply_gate() and not w.admissions,
          "Closed owner IME ingress/persistence must refuse")
    if not during:
        check(after == before, "Closed owner received an IME edit")

def original_ps_signals(w):
    calls = {"intent": 0, "text": 0, "document": 0, "cursor": 0, "selection": 0}
    def tick(name):
        calls[name] += 1
    w.test_change_callbacks.append(lambda: tick("intent"))
    for signal, name in [(w.textChanged, "text"),
                         (w.document().contentsChanged, "document"),
                         (w.cursorPositionChanged, "cursor"), (w.selectionChanged, "selection")]:
        signal.connect(lambda name=name: tick(name))
    return calls

def original_ps_clean(w, source, before, calls, position=None, anchor=None):
    # The expected intent is the original fixture, never a normalized post-state.
    admitted = w.apply_gate()
    switchable = w.switch_gate()
    after = snapshot(w)
    expected = dict(before)
    if position is not None:
        expected.update(position=position, anchor=anchor)
    check(not admitted and not w.admissions, "Original PS no-op admitted changed source")
    check(w.original == source and w.accepted == source and w.gate() == source,
          "Original literal PS/mixed LF intent must remain exact")
    check(switchable and not w.quarantined and w.isReadOnly(), "Original inspect state lost")
    check(after == expected, "Original PS view/selection/revision/history changed")
    check(w.document().availableUndoSteps() == w.document().availableRedoSteps() == 0,
          "Read-only no-op created native history")
    check(calls["intent"] == calls["text"] == calls["document"] == 0,
          "Read-only no-op published source/document change")

def original_ps_history(source, selection, command):
    a, b = selection
    w = editor(source, a, b)
    before = snapshot(w)
    check(w.isReadOnly() and w.original == w.accepted == source,
          "Original literal-PS fixture must enter inspect-only state")
    check(not before["undo"] and not before["redo"], "Empty native history premise")
    calls = original_ps_signals(w)
    binding = QtGui.QKeySequence.keyBindings(command)[0][0]
    send_key(w, binding.key(), "", binding.keyboardModifiers())
    original_ps_clean(w, source, before, calls)
    check(calls["cursor"] == calls["selection"] == 0, "No-op history changed selection")
    return {"source": source, "before": before, "calls": calls, "native_noop": True}

def original_ps_navigation(source, kind):
    w = editor(source)
    # Qt's read-only default is mouse-only; this fixture opts into native keyboard selection.
    w.setTextInteractionFlags(w.textInteractionFlags() | QtCore.Qt.TextSelectableByKeyboard)
    check(w.isReadOnly() and w.textInteractionFlags() & QtCore.Qt.TextSelectableByKeyboard,
          "Native keyboard-selection fixture must remain read-only")
    before = snapshot(w)
    calls = original_ps_signals(w)
    if kind == "right":
        send_key(w, QtCore.Qt.Key_Right)
        position, anchor = 1, 1
    elif kind == "shift_right":
        send_key(w, QtCore.Qt.Key_Right, modifiers=QtCore.Qt.ShiftModifier)
        position, anchor = 1, 0
    else:
        binding = QtGui.QKeySequence.keyBindings(QtGui.QKeySequence.SelectAll)[0][0]
        send_key(w, binding.key(), "", binding.keyboardModifiers())
        position, anchor = len(source), 0
    original_ps_clean(w, source, before, calls, position, anchor)
    check(calls["cursor"] > 0, "Native cursor notification must remain enabled")
    if kind != "right":
        check(w.textCursor().hasSelection() and calls["selection"] > 0,
              "Native selection and its notifications must remain enabled")
    return {"source": source, "kind": kind, "calls": calls}

def original_ps_default_arrow_noop(source, shift):
    w = editor(source)
    before = snapshot(w)
    calls = original_ps_signals(w)
    check(w.textInteractionFlags() == QtCore.Qt.TextSelectableByMouse,
          "Qt default read-only mouse-only interaction premise")
    send_key(w, QtCore.Qt.Key_Right,
             modifiers=QtCore.Qt.ShiftModifier if shift else QtCore.Qt.NoModifier)
    original_ps_clean(w, source, before, calls)
    check(calls["cursor"] == calls["selection"] == 0, "Default no-op moved selection")
    return {"source": source, "shift": shift, "calls": calls}

def original_ps_refusals(source):
    w = editor(source, len(source), 0)
    before = snapshot(w)
    calls = original_ps_signals(w)
    for route in ("setter", "insert", "mime", "key", "ime", "drop"):
        invoke(w, route, "X\nY")
        original_ps_clean(w, source, before, calls)
    w.external_notification("external\nsource")
    original_ps_clean(w, source, before, calls)
    return {"source": source, "calls": calls, "editing_success_claim": False}

def original_ps_recovery(source):
    w = editor(source, 1, 1)
    opaque(w, "cursor")
    retained = snapshot(w)
    check(not w.apply_gate() and not w.switch_gate() and not w.admissions,
          "Original PS opaque mutation must quarantine")
    w.external_notification("external\nsource")
    check(snapshot(w) == retained, "Quarantine must retain observed opaque draft")
    check(w.revert(source), "Explicit same-widget original-PS recovery must succeed")
    before = snapshot(w)
    calls = original_ps_signals(w)
    for command in (QtGui.QKeySequence.Undo, QtGui.QKeySequence.Redo):
        binding = QtGui.QKeySequence.keyBindings(command)[0][0]
        send_key(w, binding.key(), "", binding.keyboardModifiers())
        original_ps_clean(w, source, before, calls)
    check(not w.insertPlainText("X"), "Recovered original PS is still inspect-only")
    original_ps_clean(w, source, before, calls)
    return {"source": source, "observed_opaque_draft": retained, "calls": calls}

def api_run(namespace):
    g = namespace
    case, editor, check, snapshot = (g[n] for n in ('case', 'editor', 'check', 'snapshot'))
    module, widgets, QtCore, QtGui, QtWidgets = (g[n] for n in ('module', 'widgets', 'QtCore', 'QtGui', 'QtWidgets'))
    component, qt = module.component, module.qt

    def readonly_loads():
        w = editor('A\u2029B')
        w.setReadOnly(False)
        check(w.isReadOnly(), 'Ambiguous source overrides editable model')
        w.setReadOnly(True)
        check(w.load_source('AB') and w.isReadOnly(), 'Load must retain backend read-only')
        before = snapshot(w)
        check(not w.insertPlainText('X') and snapshot(w) == before, 'Read-only native/programmatic ingress')
        w.setReadOnly(False)
        check(not w.isReadOnly() and w.insertPlainText('X'), 'Model unlock must permit supported source')
        check(w.load_source('C\u2029D') and w.isReadOnly(), 'Later ambiguous block remains read-only')
        check(w.load_source('CD') and not w.isReadOnly(), 'Ambiguity must not become model read-only')

    def source_refuses_opaque():
        w = editor('AB')
        w.document().setPlainText('A\u2029B')
        before = snapshot(w)
        try:
            w.source_text()
        except ValueError as error:
            check(bool(str(error)), 'Refusal carries diagnostic')
        else:
            raise AssertionError('Opaque source_text returned authority')
        check(snapshot(w) == before and w.load_source('current\r\nsource'), 'Explicit actual recovery')
        check(w.source_text() == 'current\nsource', 'Module-level shown must normalize display only')

    def constructor_silent():
        notices = []
        w = component.create_source_input(qt, is_closed=lambda: False,
                                         on_change=lambda: None, on_diagnostic=notices.append)
        widgets.append(w)
        w.close_protocol = lambda: (setattr(w, 'closed', True), w._disconnect_document(), w.close(), w.deleteLater())
        w.admissions = []
        check(not notices, 'Constructor must not notify controls before FeaturesEditor.build completes')
        check(w.source_text() == '', 'New empty owned source')

    def load_notice_fault():
        w = editor('AB')
        error = KeyboardInterrupt('load notice')
        def fail(message):
            raise error
        w.on_diagnostic = fail
        check(not w.load_source('latest'), 'A quarantined load must not acknowledge successful display')
        check(w.last_error is error and w.quarantined, 'Retain original callback failure and fence')

    def load_owner_close():
        w = editor('AB')
        owner = {'closed': False}
        w.owner_closed = lambda: owner['closed']
        w.on_diagnostic = lambda message: owner.update(closed=True)
        check(not w.load_source('latest'), 'Owner close during reload notification must refuse ACK')
        check(w.gate() is None, 'Closed owner remains fenced')

    def publication_fault():
        w = editor('AB')
        error = SystemExit('publication')
        def fail():
            raise error
        w.on_change = fail
        check(not w.insertPlainText('X'), 'Failing publication quarantines persistence')
        check(w.last_error is error and w.gate() is None, 'Original callback error retained')

    def native_property_document():
        # These properties read the genuine native document; no synthetic raw text.
        class PropertyDocument(QtGui.QTextDocument):
            revision = property(QtGui.QTextDocument.revision)
            availableUndoSteps = property(QtGui.QTextDocument.availableUndoSteps)
            availableRedoSteps = property(QtGui.QTextDocument.availableRedoSteps)
            toRawText = property(QtGui.QTextDocument.toRawText)
        from types import SimpleNamespace
        adapted = SimpleNamespace(QtCore=QtCore, QtGui=SimpleNamespace(**vars(qt.QtGui)))
        adapted.QtGui.QTextDocument = PropertyDocument
        w = component.create_source_input(adapted, is_closed=lambda: False,
                                         on_change=lambda: None, on_diagnostic=lambda text: None)
        widgets.append(w)
        # Snapshot helper accesses method-shaped Qt; use actual document base methods
        # only for this additional case's direct checks and provide a test snapshot adapter.
        w.close_protocol = lambda: (setattr(w, 'closed', True), w._disconnect_document(), w.close(), w.deleteLater())
        w.admissions = []
        check(w.load_source('A\xa0B\u2028C') and w.insertPlainText('X'), 'Known Q_PROPERTY values use real native document')
        check(w.source_text() == 'XA\xa0B\u2028C', 'Property-shaped raw extraction must preserve intent')
        # Restore method shape after the actual property-surface operation so the
        # shared observation collector records the native view without a fake getter.
        doc = w.document()
        for name in ('revision','availableUndoSteps','availableRedoSteps','toRawText'):
            setattr(PropertyDocument, name, getattr(QtGui.QTextDocument, name))
        check(doc.toRawText() == 'XA\xa0B\u2028C', 'Actual raw text after property checks')

    def repeated_load_disconnects():
        w = editor('AB')
        old = w.document()
        keeper = QtCore.QObject(w)
        old.setParent(keeper)
        check(len(w.connections) == 10, 'Exactly local owned observers')
        check(w.load_source('CD'), 'Explicit load')
        old.setPlainText('unrelated old document')
        check(w.source_text() == 'CD' and not w.quarantined, 'Old local observer was disconnected')
        check(len(w.connections) == 10, 'Reload does not accumulate observers')

    def load_after_callback_edit():
        w = editor('AB')
        fired = []
        def change(message):
            fired.append(w.active)
            check(w.insertPlainText('X'), 'Independent post-authority edit premise')
        w.on_diagnostic = change
        check(not w.load_source('latest'), 'Reload ACK cannot accept a subsequent different draft')
        check(fired == [None] and w.quarantined, 'Callback executes outside authority; changed draft is quarantined')
        check(w.document().toRawText() == 'Xlatest', 'Keep the actual observed changed draft')

    def load_native_owner_close():
        w = editor('AB')
        owner, fired = {'closed': False}, []
        w.owner_closed = lambda: owner['closed']
        def close():
            fired.append(True)
            owner['closed'] = True
        w.textChanged.connect(close)
        check(not w.load_source('latest'), 'Native reload callback close cannot acknowledge source')
        check(fired and w.gate() is None, 'Actual native signal must execute and fence owner')

    def closed_constructor_cleanup():
        parent = QtWidgets.QWidget()
        try:
            try:
                component.create_source_input(qt, parent, is_closed=lambda: True,
                                              on_change=lambda: None, on_diagnostic=lambda text: None)
            except ValueError as error:
                check('closed' in str(error), 'Retain original constructor reason')
            else:
                raise AssertionError('Closed owner constructed a usable source widget')
            children = parent.findChildren(QtWidgets.QPlainTextEdit)
            for child in children:
                QtCore.QCoreApplication.sendPostedEvents(child, QtCore.QEvent.DeferredDelete)
            check(not parent.findChildren(QtWidgets.QPlainTextEdit), 'Failed owned child must be deleted')
            return {'failed_children_reaped': len(children)}
        finally:
            g['shiboken6'].delete(parent)

    for name, call in [('api_model_and_ambiguous_readonly_independent', readonly_loads),
                       ('api_source_text_refuses_opaque_and_recovers', source_refuses_opaque),
                       ('api_constructor_does_not_publish_to_unbuilt_owner', constructor_silent),
                       ('api_load_diagnostic_error_cannot_ack', load_notice_fault),
                       ('api_load_owner_close_cannot_ack', load_owner_close),
                       ('api_on_change_original_error_contained', publication_fault),
                       ('api_real_document_property_adaptation', native_property_document),
                       ('api_reload_disconnects_only_old_local_observers', repeated_load_disconnects),
                       ('api_reload_post_notification_edit_cannot_ack', load_after_callback_edit),
                       ('api_reload_native_callback_closed_owner', load_native_owner_close),
                       ('api_closed_constructor_releases_owned_child', closed_constructor_cleanup)]:
        case(name, call)

def mime_run(g):
    case, editor, check, snapshot = (g[n] for n in ('case', 'editor', 'check', 'snapshot'))
    module, QtCore, QtGui, QtWidgets, shiboken = (g[n] for n in ('module', 'QtCore', 'QtGui', 'QtWidgets', 'shiboken6'))
    records = []

    class LazyMime(QtCore.QMimeData):
        def __init__(self, values, plain=True, callback=None):
            super().__init__()
            self.values, self.plain, self.callback = values, plain, callback
            self.calls, self.format_calls = [], []

        def formats(self):
            self.format_calls.append(['formats'])
            return ['text/plain'] if self.plain else []

        def hasFormat(self, mime):
            self.format_calls.append(['hasFormat', mime])
            return self.plain and mime.startswith('text/plain')

        def retrieveData(self, mime, preferred):
            result = self.values[min(len(self.calls), len(self.values) - 1)]
            self.calls.append({'mime': mime, 'preferred': str(preferred.name()),
                               'python_type': type(result).__name__,
                               'value': repr(result) if isinstance(result, BaseException) else result})
            if self.callback is not None:
                callback, self.callback = self.callback, None
                callback()
            if isinstance(result, BaseException):
                raise result
            return result

    def observe(w, provider, escaped=None, result=None):
        row = {'calls': list(provider.calls), 'format_calls': list(provider.format_calls),
               'view': snapshot(w), 'accepted': w.accepted,
               'gate': w.gate(), 'admissions': list(w.admissions),
               'borrowed_provider_still_live': shiboken.isValid(provider),
               'escaped': repr(escaped) if escaped is not None else None,
               'result': result}
        records.append(row)
        (g['OUT'] / 'mime-observations.json').write_text(json.dumps(records, indent=2) + '\n')
        return row

    def varying(values, expected, refuse=False):
        w = editor('AB', 1, 1)
        provider = LazyMime(values)
        before = snapshot(w)
        try:
            result = w.insertFromMimeData(provider)
            admitted = w.apply_gate()
            row = observe(w, provider, result=result)
            if refuse:
                check(snapshot(w) == before and not admitted and w.gate() == 'AB', 'PS-first must refuse without changing selection/source')
            else:
                check(w.gate() == expected and admitted and w.admissions == [expected], 'Only the first validated MIME snapshot may be admitted')
            check(len(provider.calls) == 1, 'Borrowed lazy text must be retrieved exactly once')
            check(shiboken.isValid(provider), 'Borrowed MIME must not be deleted')
            return row
        finally:
            shiboken.delete(provider)

    def closed(kind):
        w = editor('A\u2029B' if kind == 'ambiguous' else 'AB', 1, 1)
        if kind == 'local':
            w.closed = True
        elif kind == 'owner':
            w.owner_closed = lambda: True
        elif kind == 'model':
            w.setReadOnly(True)
        provider = LazyMime(['X'])
        before = snapshot(w)
        try:
            result = w.insertFromMimeData(provider)
            row = observe(w, provider, result=result)
            check(not provider.calls and not provider.format_calls, 'Closed/read-only entry must not consult borrowed MIME')
            check(snapshot(w) == before, 'Closed/read-only MIME changed view or selection')
            return row
        finally:
            shiboken.delete(provider)

    def provider_error(error):
        w = editor('AB', 0, 2)
        provider = LazyMime([error])
        before, escaped, result = snapshot(w), None, None
        try:
            try:
                result = w.insertFromMimeData(provider)
            except BaseException as caught:
                escaped = caught
            row = observe(w, provider, escaped, result)
            row['same_original_error'] = w.last_error is error
            check(escaped is None, 'Provider exception escaped the virtual boundary')
            check(w.last_error is error and snapshot(w) == before, 'Original provider error or pre-call draft lost')
            check(not result and not w.apply_gate(), 'Provider failure admitted source')
            return row
        finally:
            shiboken.delete(provider)

    def native_empty(selected, plain=True):
        w = editor('AB', 0 if selected else 1, 2 if selected else 1)
        baseline = QtWidgets.QPlainTextEdit()
        provider = LazyMime(['' if plain else None], plain=plain)
        native_mime = QtCore.QMimeData()
        try:
            baseline.setPlainText('AB')
            cursor = baseline.textCursor()
            cursor.setPosition(0 if selected else 1)
            cursor.setPosition(2 if selected else 1, QtGui.QTextCursor.KeepAnchor)
            baseline.setTextCursor(cursor)
            if plain:
                native_mime.setText('')
            QtWidgets.QPlainTextEdit.insertFromMimeData(baseline, native_mime)
            native_after = snapshot(baseline)
            result = w.insertFromMimeData(provider)
            row = observe(w, provider, result=result)
            row['independent_native_empty_or_absent_plain'] = native_after
            check(snapshot(w) == native_after, 'Empty/no-plain MIME differs from independent native reference')
            check(w.gate() == 'AB' and not w.apply_gate(), 'Native no-op must remain trusted and must not delete selection')
            check(len(provider.calls) == (1 if plain else 0), 'No-plain must not retrieve text; empty plain reads once')
            return row
        finally:
            shiboken.delete(provider)
            shiboken.delete(native_mime)
            shiboken.delete(baseline)

    def history():
        w = editor('AB', 1, 2)
        provider = LazyMime(['X\n\xa0\u2028Y', 'other'])
        calls = {'text': 0, 'document': 0, 'change': 0}
        def tick(name):
            calls[name] += 1
        w.textChanged.connect(lambda: tick('text'))
        w.document().contentsChanged.connect(lambda: tick('document'))
        w.test_change_callbacks.append(lambda: tick('change'))
        try:
            result = w.insertFromMimeData(provider)
            observe(w, provider, result=result)
            check(result, 'Snapshot MIME native insertion must succeed')
            check(w.gate() == 'AX\n\xa0\u2028Y', 'Native selected insertion intent')
            for command, expected in [(QtGui.QKeySequence.Undo, 'AB'), (QtGui.QKeySequence.Redo, 'AX\n\xa0\u2028Y')]:
                binding = QtGui.QKeySequence.keyBindings(command)[0][0]
                g['send_key'](w, binding.key(), '', binding.keyboardModifiers())
                check(w.gate() == expected, 'Native MIME history must preserve exact intent')
            row = observe(w, provider)
            check(all(calls.values()), 'Native and own notifications must remain live')
            check(len(provider.calls) == 1, 'History cannot retrieve borrowed source again')
            return {**row, 'notifications': calls}
        finally:
            shiboken.delete(provider)

    def owned_lifetime(mode):
        made, destroyed = [], []
        error = RuntimeError('owned MIME ' + mode)
        class OwnedMime(QtCore.QMimeData):
            def __init__(self):
                super().__init__()
                made.append(self)
                self.destroyed.connect(lambda: destroyed.append(True))
            def setText(self, text):
                if mode == 'set_error':
                    raise error
                super().setText(text)
        def allocate():
            if mode == 'factory_error':
                raise error
            return OwnedMime()
        core = SimpleNamespace(**{n: getattr(QtCore, n) for n in dir(QtCore) if not n.startswith('_')})
        core.QMimeData = allocate
        qt = SimpleNamespace(QtCore=core, QtGui=module.qt.QtGui)
        w = module.component.create_source_input(qt, is_closed=lambda: False,
                on_change=lambda: None, on_diagnostic=lambda text: None)
        g['widgets'].append(w)
        w.admissions = []
        w.gate = lambda: w._gate()
        w.close_protocol = lambda: (setattr(w, 'closed', True), w._disconnect_document(), w.close(), w.deleteLater())
        check(w.load_source('AB'), 'Owned MIME fixture load')
        cursor = w.textCursor(); cursor.setPosition(1); w.setTextCursor(cursor)
        provider = LazyMime(['X'])
        before, escaped, result = snapshot(w), None, None
        try:
            try:
                result = w.insertFromMimeData(provider)
            except BaseException as caught:
                escaped = caught
            row = observe(w, provider, escaped, result)
            row.update(owned_created=len(made), owned_destroyed=len(destroyed),
                       owned_all_deleted=all(not shiboken.isValid(x) for x in made))
            check(escaped is None, 'Owned MIME materialization failure escaped')
            if mode == 'success':
                check(result and w.gate() == 'AXB' and len(made) == len(destroyed) == 1, 'Exactly one actual owned snapshot must be destroyed')
            else:
                check(not result and w.last_error is error and snapshot(w) == before, 'Materialization failure must preserve original error/draft')
                check(len(made) == (1 if mode == 'set_error' else 0), 'Actual factory fault premise')
            check(all(not shiboken.isValid(x) for x in made), 'Temporary snapshot leaked')
            check(shiboken.isValid(provider), 'Borrowed provider was destroyed')
            return row
        finally:
            shiboken.delete(provider)
            for obj in made:
                if shiboken.isValid(obj):
                    shiboken.delete(obj)

    def provider_callback(kind):
        w = editor('AB', 1, 1)
        calls = []
        def callback():
            if kind == 'close':
                w.owner_closed = lambda: True
                calls.append('closed')
            elif kind == 'public':
                calls.append(w.insertPlainText('Y'))
            else:
                w.document().setPlainText('A\u2029B')
                calls.append(snapshot(w))
        provider = LazyMime(['X'], callback=callback)
        before = snapshot(w)
        try:
            result = w.insertFromMimeData(provider)
            row = observe(w, provider, result=result)
            check(len(provider.calls) == 1 and len(calls) == 1, 'One actual lazy retrieval/callback')
            if kind == 'public':
                check(calls == [False] and w.gate() == 'AXB', 'Provider callback must not borrow input authority')
            elif kind == 'close':
                check(not result and snapshot(w) == before and w.gate() is None, 'Owner close in retrieval must fence native insertion')
            else:
                check(not result and snapshot(w) == calls[0] and w.gate() is None, 'Opaque provider mutation retains observed draft under quarantine')
            return row
        finally:
            shiboken.delete(provider)

    jobs = [('mime_varying_X_PS_LF', lambda: varying(['X', '\u2029', '\n'], 'AXB')),
            ('mime_varying_X_Y_Z', lambda: varying(['X', 'Y', 'Z'], 'AXB')),
            ('mime_PS_first_later_safe', lambda: varying(['\u2029', 'X', '\n'], 'AB', True))]
    jobs += [('mime_no_read_' + k, lambda k=k: closed(k)) for k in ('local','owner','model','ambiguous')]
    jobs += [('mime_provider_RuntimeError', lambda: provider_error(RuntimeError('provider retrieval'))),
             ('mime_provider_KeyboardInterrupt', lambda: provider_error(KeyboardInterrupt('provider retrieval'))),
             ('mime_empty_selected_native_noop', lambda: native_empty(True)),
             ('mime_empty_collapsed_native_noop', lambda: native_empty(False)),
             ('mime_no_plain_native_noop', lambda: native_empty(True, False)),
             ('mime_snapshot_selection_native_history_notifications', history)]
    jobs += [('mime_owned_' + mode, lambda mode=mode: owned_lifetime(mode)) for mode in ('success','set_error','factory_error')]
    jobs += [('mime_provider_callback_' + kind, lambda kind=kind: provider_callback(kind)) for kind in ('close','public','opaque')]
    for name, function in jobs:
        start = len(records)
        case(name, function)
        for row in records[start:]:
            row['case'] = name
        (g['OUT'] / 'mime-observations.json').write_text(json.dumps(records, indent=2) + '\n')

def test_all_183_controls_when_production_boundary_then_original_oracles(tmp_path):
    global OUT, widgets, results
    OUT, widgets, results = tmp_path, [], []
    with owned_application():
        try:
            case("baseline_plain_getter_loses_new_PS", weak_path)
            for payload, a, b, expected in [
                ("X", 1, 1, "AX😀\nB"), ("\n", 1, 1, "A\n😀\nB"),
                ("\r\n", 1, 1, "A\n😀\nB"), ("\r", 1, 1, "A\n😀\nB"),
                ("\u00a0", 1, 1, "A\u00a0😀\nB"), ("\u2028", 1, 1, "A\u2028😀\nB"),
                ("日e\u0301", 1, 3, "A日e\u0301\nB"), ("Z", 1, 4, "AZB")]:
                case("positive_insert_" + repr(payload), lambda p=payload,a=a,b=b,e=expected: positive(p,a,b,e))
            for route in ["setter", "insert", "mime", "key", "ime", "drop"]:
                for payload in ["\u2029XY", "X\u2029Y", "XY\u2029"]:
                    case("refuse_" + route + "_" + repr(payload), lambda r=route,p=payload: refusal(r,p))
            for route in ["setter", "mime", "key", "ime"]:
                expected = "X\nY" if route == "setter" else "AX\nYB"
                case("positive_" + route, lambda r=route,e=expected: positive_route(r,"X\nY",e))
            for key in [QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter]:
                case("ordinary_enter_" + str(key), lambda k=key: enter(k))
            for route in ["document", "base", "cursor", "blocked_cursor"]:
                case("opaque_same_canonical_" + route, lambda r=route: quarantine(r))
            for signal in ["textChanged", "selectionChanged", "cursorPositionChanged"]:
                for action in ["opaque", "public"]:
                    case("reentrant_" + signal + "_" + action,
                         lambda s=signal,a=action: reentrant(s,a))
            case("original_PS_inspect_noop", ambiguous)
            case("quarantine_explicit_fresh_view_recovery", recovery)
            case("opaque_replacement_document_equal_revision_raw", replacement_document)
            case("positive_owned_copy_drop", positive_drop)
            for source in ["A\u00a0B", "A\u2028B", "A\r\nB", "A\rB", "A\nB"]:
                case("original_noop_" + repr(source), lambda s=source: original_noop(s))
            for payload in ["\u2029XY", "X\u2029Y", "XY\u2029"]:
                case("single_line_mime_refusal_" + repr(payload), lambda p=payload: single_line_refusal(p))
            case("complex_IME_refused_before_selection_removal", complex_ime_refusal)
            case("reentrant_document_signals_suppressed", reentrant_blocked)
            for code in [QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter]:
                for payload in ["\u2029X", "X\u2029Y", "X\u2029"]:
                    for mods in [QtCore.Qt.NoModifier, QtCore.Qt.ControlModifier]:
                        case("raw_return_refusal_" + str(code) + repr(payload) + str(mods),
                             lambda c=code,p=payload,m=mods: bad_return(c,p,m))
            for kind in ["backspace", "delete", "left_insert", "shift_right_replace", "repeat", "undo_redo"]:
                case("native_command_" + kind, lambda k=kind: native_command(k))
            case("same_widget_explicit_revert", same_widget_revert)
            case("same_widget_foreign_document_revert", lambda: same_widget_revert(True))
            case("layout_callback_opaque_reentry_during_native_key", layout_reentry)
            case("native_document_widget_notifications_preserved", native_notifications)
            case("post_authority_own_notification_quarantines_opaque", post_authority_reentry)
            for a,b in [(True,False),(False,True),(True,True)]:
                case("restore_prior_signal_states_" + str((a,b)), lambda a=a,b=b: restore_signal_states(a,b))
            case("close_after_own_publication_and_closed_ingress", close_after_publication)
            case("same_widget_revert_original_PS_inspect", revert_original_ps)
            case("inconsistent_Return_payload_refused", unexpected_return)
            for name in ["doc.undoCommandAdded", "doc.undoAvailable", "doc.modificationChanged",
                         "doc.contentsChange", "doc.contentsChanged", "widget.textChanged",
                         "widget.cursorPositionChanged"]:
                for blocked in [False, True]:
                    case("native_signal_fault_" + name + "_" + str(blocked),
                         lambda n=name,b=blocked: native_signal_fault(n,b))
            for blocked in [False,True]:
                case("early_undo_available_selection_same_raw_" + str(blocked),
                     lambda b=blocked: early_selection_fault(b))
            case("native_grouped_typing_undo_redo", grouped_history)
            case("owner_closed_retains_live_child", lambda: owner_fence(False))
            case("owner_closed_during_native_callback", lambda: owner_fence(True))
            for blocked in [False,True]:
                case("early_same_inserted_span_" + str(blocked), lambda b=blocked: early_within_inserted_span(b))
            for name in ["contentsChange", "undoAvailable", "redoAvailable"]:
                for blocked in [False,True]:
                    case("native_Undo_fault_" + name + "_" + str(blocked),
                         lambda n=name,b=blocked: native_undo_fault(n,b))
            case("native_standard_word_delete", native_word_delete)
            case("native_selected_mime_grouped_history", selected_mime_history)
            for route in ["insert", "mime", "ime"]:
                for blocked in [False,True]:
                    case("cursor_route_early_fault_" + route + "_" + str(blocked),
                         lambda r=route,b=blocked: cursor_route_early_fault(r,b))
            case("simple_IME_selected_forward", selected_ime)
            case("simple_IME_selected_reverse", lambda: selected_ime(True))
            case("simple_IME_native_grouped_history", lambda: selected_ime(False,True))
            case("simple_IME_native_notifications", ime_native_notifications)
            case("simple_IME_closed_owner", lambda: ime_owner_close(False))
            case("simple_IME_owner_closes_in_callback", lambda: ime_owner_close(True))

            for source in ("A\u2029B", "A\nB\u2029C"):
                for selection in ((1, 1), (0, len(source)), (len(source), 0)):
                    for command, name in ((QtGui.QKeySequence.Undo, "Undo"),
                                          (QtGui.QKeySequence.Redo, "Redo")):
                        case("original_PS_empty_" + name + "_" + repr(source) + "_" + repr(selection),
                             lambda s=source,a=selection,c=command: original_ps_history(s,a,c))
                for kind in ("right", "shift_right", "select_all"):
                    case("original_PS_native_" + kind + "_" + repr(source),
                         lambda s=source,k=kind: original_ps_navigation(s,k))
                for shift in (False, True):
                    case("original_PS_default_arrow_noop_" + str(shift) + "_" + repr(source),
                         lambda s=source,m=shift: original_ps_default_arrow_noop(s,m))
                case("original_PS_all_ingress_refusals_" + repr(source),
                     lambda s=source: original_ps_refusals(s))
                case("original_PS_same_widget_recovery_history_" + repr(source),
                     lambda s=source: original_ps_recovery(s))





            api_run(globals())
            mime_run(globals())
        finally:
            for widget in widgets:
                widget.close_protocol()
                QtCore.QCoreApplication.sendPostedEvents(widget, QtCore.QEvent.DeferredDelete)
            assert all(not shiboken6.isValid(widget) for widget in widgets)
    assert len(results) == 183
    assert all(row['status'] == 'PASS' for row in results), [row for row in results if row['status'] != 'PASS']
