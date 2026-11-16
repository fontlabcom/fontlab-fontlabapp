# this_file: tests/test_glyph_completion_dialog.py
"""Owned Qt pair: complete refresh, distinct menus and every terminal route."""

from module_paths import module_name as _module_name
import importlib
import os
import sys
from types import SimpleNamespace as NS

import pytest

from fontlabapp.qt.tables.filter.model import Table

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtGui, QtWidgets, sip

    valid = lambda item: not sip.isdeleted(item)
else:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import isValid as valid
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture(params=[False, True], ids=["part2", "part3"])
def panel(monkeypatch, request):
    class Dialog(QtWidgets.QDialog):
        palette = property(QtWidgets.QDialog.palette)

    class Label(QtWidgets.QLabel):
        font = property(QtWidgets.QLabel.font)

    gui = NS(**{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
    gui.__dict__.update(
        {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
    )
    gui.QDialog, gui.QLabel = Dialog, Label
    gui.QStringListModel, gui.QSortFilterProxyModel = (
        QtCore.QStringListModel,
        QtCore.QSortFilterProxyModel,
    )
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=QtCore, QtGui=gui))
    for name in ("_names_dialog", "_glyph_completion_dialog"):
        monkeypatch.delitem(sys.modules, _module_name(name), raising=False)
    module = importlib.import_module("fontlabapp.glyphs.completion.ui")
    monkeypatch.setattr(
        module,
        "_string_boundary",
        (module._connect_string, module._disconnect_string),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "_connect_string",
        lambda sender, slot: sender.activated[str].connect(slot),
    )
    monkeypatch.setattr(
        module,
        "_disconnect_string",
        lambda sender, slot: sender.activated[str].disconnect(slot),
    )
    state = NS(
        names=("anchor", "anchor.top", "f_f_i", "Æ<test>", "😀"), calls=0, fail=False
    )

    def capture(*, deadline):
        state.calls += 1
        if state.fail:
            raise ValueError("source changed")
        return Table(
            ("Name", "Unicode", "Modified"), tuple((n, "", "") for n in state.names)
        )

    w = module.GlyphCompletionDialog(None, capture, official=request.param)
    yield w, state, module
    if valid(w):
        w.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_initial_complete_capture_and_original_variant_menus(panel):
    w, state, _ = panel
    assert not w.isModal() and w.words == state.names and len(w._legacy) == 1
    assert set(w.menu_actions) == (
        {"Exit", "About", "About Qt"} if w.official else {"New", "Close", "Vocabulary"}
    )
    if w.official:
        w.menu_actions["About"].trigger()
        assert "custom-completer" in w.status.text()
        w.menu_actions["About Qt"].trigger()
        assert "Qt 5.15" in w.status.text()
    else:
        w.menu_actions["Vocabulary"].trigger()
        assert "Æ&lt;test&gt;" in w.controls.widget.toolTip(), (
            "Names are plain data, never tooltip markup"
        )
        w.controls.widget.setPlainText("draft")
        w.menu_actions["New"].trigger()
        assert w.controls.widget.toPlainText() == ""


def test_panel_state_never_shadows_qwidget_native_action_slot(panel):
    w, _, _ = panel
    assert callable(w.actions), "PythonQt forbids overwriting QWidget.actions with panel state"
    assert isinstance(w.menu_actions, dict) and w.menu_actions


def test_owned_dialog_cannot_quit_application_when_last_window_closes(panel):
    w, _, _ = panel
    assert not w.testAttribute(QtCore.Qt.WA_QuitOnClose), "Retain the original owned-window quit guard"


def test_refresh_failure_and_empty_keep_draft_but_discard_all_old_names(panel):
    w, state, _ = panel
    w.controls.widget.setPlainText("My /anchor.top draft\n😀")
    state.fail = True
    w.refresh_button.click()
    assert w.words == () and w.controls.completer is None and not w._legacy
    assert "source changed" in w.status.text()
    assert w.controls.widget.toPlainText() == "My /anchor.top draft\n😀"
    state.fail, state.names = False, ()
    w.refresh()
    assert w.words == () and w.controls.completer is not None
    state.names = ("replacement",)
    w.refresh()
    assert w.words == ("replacement",) and len(w._legacy) == 1 and state.calls == 4


@pytest.mark.parametrize("failure", ["wrong", "expired", "duplicate", "closed"])
def test_bad_capture_or_expiry_or_close_cannot_publish_partial_names(
    panel, monkeypatch, failure
):
    w, state, module = panel
    if failure == "wrong":
        w._capture = lambda **kw: None
    elif failure == "expired":
        monkeypatch.setattr(module, "monotonic", lambda: -10)
    elif failure == "duplicate":
        state.names = ("A", "A")
    else:

        def capture(**kw):
            w.close()
            return Table(("Name", "Unicode", "Modified"), (("late", "", ""),))

        w._capture = capture
    w.refresh()
    assert not w.words and not w._legacy


@pytest.mark.parametrize(
    "route", ["close", "reject", "accept", "done", "escape", "destroy", "menu"]
)
def test_every_terminal_route_releases_models_callbacks_and_registry(panel, route):
    w, _state, _ = panel
    c = w.controls
    slots = list(w._connections)
    activations = list(w._legacy)
    sys.__dict__.setdefault("_fontlab_samples", {})[w.KEY] = w
    w.show()
    if route == "close":
        w.close_button.click()
    elif route == "menu":
        w.menu_actions["Exit" if w.official else "Close"].trigger()
    elif route == "destroy":
        w.deleteLater()
    elif route == "done":
        w.done(0)
    elif route == "escape":
        if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
            from PyQt5.QtTest import QTest
        else:
            from PySide6.QtTest import QTest
        QTest.keyClick(w, QtCore.Qt.Key_Escape)
    else:
        getattr(w, route)()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert w._closed and w._capture is None and not w.words and w.controls is None
    assert c._closed and c.completer is None and not w._legacy and not w._connections
    assert w.KEY not in sys._fontlab_samples
    for _, slot in slots:
        slot()
    for _, slot in activations:
        slot("late")
    w.refresh()
    w.invalidate()
    w._failure(ValueError("late"))
    w._dispose()


def test_activation_error_is_contained_and_invalidates_model(panel, monkeypatch):
    w, _, _ = panel
    c = w.controls

    def fail(word):
        raise ValueError("activation failed")

    monkeypatch.setattr(c.widget, "setTextCursor", fail)
    c.widget.setPlainText("anc")
    cursor = c.widget.textCursor()
    cursor.movePosition(QtGui.QTextCursor.End)
    QtWidgets.QTextEdit.setTextCursor(c.widget, cursor)
    c.completer.setCompletionPrefix("anc")
    c.completer.activated[str].emit("anchor")
    assert (
        not w.words and c.completer is None and "activation failed" in w.status.text()
    )


def test_close_disconnect_failure_refuses_destruction_then_retry_succeeds(
    panel, monkeypatch
):
    w, _, module = panel
    original = module._disconnect_string

    def fail(*args):
        raise RuntimeError("disconnect failed")

    monkeypatch.setattr(module, "_disconnect_string", fail)
    w.show()
    assert w.close() is False and len(w._legacy) == 1 and w.controls is not None
    assert "disconnect failed" in w.status.text()
    monkeypatch.setattr(module, "_disconnect_string", original)
    w.close_button.click()
    assert w.controls is None and not w._legacy, (
        "The visible Close button must support retry"
    )


def test_explicit_string_overload_boundary_keeps_exact_signature(panel):
    _, _, module = panel
    calls, slot = [], object()
    sender = NS(
        connect=lambda *args: calls.append(args),
        disconnect=lambda *args: calls.append(args),
    )
    connect, disconnect = module._string_boundary
    connect(sender, slot)
    disconnect(sender, slot)
    assert calls == [("activated(QString)", slot), ("activated(QString)", slot)]


@pytest.mark.parametrize("operation", [0, 1])
def test_legacy_boundary_rejects_explicit_false_result(panel, operation):
    _, _, module = panel
    sender = NS(connect=lambda *args: False, disconnect=lambda *args: False)
    with pytest.raises(RuntimeError, match="refused"):
        module._string_boundary[operation](sender, lambda *args: None)


def test_signal_false_connect_is_not_recorded_as_a_live_connection(panel):
    w, _, _ = panel
    before = list(w._connections)
    with pytest.raises(RuntimeError, match="refused"):
        w._connect(NS(connect=lambda *args: False), lambda: None)
    assert w._connections == before


def test_signal_false_disconnect_retains_record_and_refuses_deletion(panel):
    w, _, _ = panel
    signal, slot = NS(disconnect=lambda *args: False), object()
    w._connections.append((signal, slot))
    w.show()
    assert w.close() is False and w._connections == [(signal, slot)]
    signal.disconnect = lambda *args: True
    assert w.close() is True


def test_parent_destruction_releases_models_and_callbacks(panel):
    _, _, module = panel
    parent = QtWidgets.QWidget()
    w = module.GlyphCompletionDialog(
        parent, lambda **kw: Table(("N", "U", "M"), (("A", "", ""),))
    )
    c = w.controls
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert w._closed and c._closed and not w._connections and not w._legacy


def test_setup_failure_disposes_created_editor(panel, monkeypatch):
    _, _, module = panel
    controls, original = [], module.CompletionEditor

    def create(*args, **kw):
        result = original(*args, **kw)
        controls.append(result)
        return result

    def fail(*args):
        raise ValueError("setup failed")

    monkeypatch.setattr(module, "CompletionEditor", create)
    monkeypatch.setattr(module, "build_controls", fail)
    with pytest.raises(ValueError, match="setup failed"):
        module.GlyphCompletionDialog(None, lambda **kw: None)
    assert len(controls) == 1 and controls[0]._closed


def test_setup_failure_with_failed_cleanup_retains_visible_owner_for_retry(panel, monkeypatch):
    _, _, module = panel
    created = []
    signal = NS(disconnect=lambda *args: False)
    def fail_setup(owner, gui):
        created.append(owner)
        owner._connections.append((signal, lambda: None))
        raise ValueError("setup failed with an owned connection")
    monkeypatch.setattr(module, "build_controls", fail_setup)
    with pytest.raises(ValueError, match="setup failed"):
        module.GlyphCompletionDialog(None, lambda **kw: None)
    owner = created[0]
    assert sys._fontlab_samples.get(owner.KEY) is owner and owner.isVisible()
    assert owner._closed and owner._connections
    signal.disconnect = lambda *args: True
    assert owner.close() is True and owner.KEY not in sys._fontlab_samples


def test_deadline_after_model_creation_discards_new_model(panel, monkeypatch):
    w, _, module = panel
    clock = iter((1.0, 4.0))
    monkeypatch.setattr(module, "monotonic", lambda: next(clock))
    monkeypatch.setattr(
        module, "vocabulary", lambda table, **kw: tuple(row[0] for row in table.rows)
    )
    w.refresh()
    assert not w.words and w.controls.completer is None and "expired" in w.status.text()


def test_failure_during_invalidation_fences_old_callbacks_until_close_retry(
    panel, monkeypatch
):
    w, _, module = panel
    old = module._disconnect_string

    def fail(*args):
        raise RuntimeError("disconnect failed")

    monkeypatch.setattr(module, "_disconnect_string", fail)
    w._failure(ValueError("original error"))
    assert (
        w._closed and w.controls._closed and not w.words and "Close" in w.status.text()
    )
    monkeypatch.setattr(module, "_disconnect_string", old)
    w.close_button.click()
    assert w.controls is None


def test_other_signal_failure_also_refuses_deletion_until_window_close_retry(panel):
    w, _, _ = panel

    def fail(*args):
        raise RuntimeError("other disconnect failed")

    signal, slot = NS(disconnect=fail), object()
    w._connections.append((signal, slot))
    w.show()
    assert w.close() is False and w._connections == [(signal, slot)]
    signal.disconnect = lambda *args: None
    assert w.close() is True and not w._connections


def test_constructor_retained_priority_before_show_preserves_exception(panel, monkeypatch):
    original, _state, module = panel
    kind = module.GlyphCompletionDialog
    original_close = kind.close
    error = RuntimeError("original constructor error")
    owners, shown = [], []

    def fail(owner, *args):
        owners.append(owner)
        raise error

    def show(owner):
        shown.append(owner.windowFlags())
        QtWidgets.QWidget.show(owner)

    monkeypatch.setattr(module, "build_controls", fail)
    monkeypatch.setattr(kind, "close", lambda owner: False)
    monkeypatch.setattr(kind, "show", show)
    try:
        with pytest.raises(RuntimeError) as caught:
            kind(None, original._capture, official=original.official)
        assert caught.value is error, "Preserve original setup failure"
        owner = owners[0]
        assert sys._fontlab_samples[owner.KEY] is owner, "Retain exact refusal owner"
        assert shown and shown[0] & QtCore.Qt.WindowStaysOnTopHint, "Set priority before retained error show"
        assert shown[0] == original.windowFlags(), "Retain all normal dialog chrome flags"
        assert shown[0] & QtCore.Qt.WindowType_Mask == QtCore.Qt.Dialog, "Preserve dialog type"
    finally:
        monkeypatch.setattr(kind, "close", original_close)
        for owner in owners:
            assert owner.close(), "Retry original owned cleanup after injected failure"
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
