# this_file: tests/test_editable_glyph_tree_dialog.py
"""Complete original controller policies and owned modeless panel lifetimes."""

import importlib
import os
import sys
from types import SimpleNamespace as NS

import pytest

from fontlabapp.qt.trees.data import Tree

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtGui, QtWidgets, sip
    from PyQt5.QtTest import QTest

    valid = lambda item: not sip.isdeleted(item)
else:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtTest import QTest
    from shiboken6 import isValid as valid
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
APP.setFont(QtGui.QFont("Helvetica"))


@pytest.fixture(params=[False, True], ids=["part2", "part3"])
def panel(monkeypatch, request):
    gui = NS(**{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
    gui.__dict__.update(
        {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
    )
    gui.QItemSelectionModel = QtCore.QItemSelectionModel
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=QtCore, QtGui=gui))
    monkeypatch.delitem(
        sys.modules, "fontlabapp.glyphs.tree.editable.ui", raising=False
    )
    module = importlib.import_module("fontlabapp.glyphs.tree.editable.ui")
    source = Tree(
        ("Glyph", "Value"),
        ((-1, ("A", "")), (0, ("Unicode", "U+0041")), (-1, ("B", ""))),
    )
    state = NS(calls=0, fail=False, source=source)

    def capture(*, deadline):
        state.calls += 1
        if state.fail:
            raise ValueError("source changed")
        return state.source

    w = module.EditableGlyphTreeDialog(None, capture, official=request.param)
    yield w, state, module
    if valid(w):
        assert w.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_complete_original_menus_shortcuts_view_and_initial_capture(panel):
    w, state, _ = panel
    assert not w.isModal() and state.calls == 1 and w.editor.model.rowCount() == 2
    assert callable(w.actions) and not w.menu_bar.isNativeMenuBar()
    assert not w.testAttribute(QtCore.Qt.WA_QuitOnClose)
    assert not any(
        b.autoDefault() for b in (w.refresh_button, w.reset_button, w.close_button)
    )
    labels = (
        {
            "Insert Row",
            "Insert Child",
            "Remove Row",
            "Insert Column",
            "Remove Column",
            "Exit",
        }
        if w.official
        else {
            "Add row",
            "Add child",
            "Remove row",
            "Add column",
            "Remove column",
            "Exit",
        }
    )
    assert set(w.menu_actions) == labels
    if w.official:
        expected = {
            "Insert Row": "Ctrl+I, R",
            "Insert Column": "Ctrl+I, C",
            "Remove Row": "Ctrl+R, R",
            "Remove Column": "Ctrl+R, C",
            "Insert Child": "Ctrl+N",
            "Exit": "Ctrl+Q",
        }
        assert {
            n: a.shortcut().toString(QtGui.QKeySequence.PortableText)
            for n, a in w.menu_actions.items()
        } == expected
        assert not w.menu_actions["Insert Row"].isEnabled()
        assert w.menu_actions["Insert Child"].isEnabled()
        assert w.editor.view.allColumnsShowFocus()
    else:
        assert all(a.shortcut().isEmpty() for a in w.menu_actions.values())
    assert "local" in w.subtitle.text().lower()


def test_sibling_child_column_and_remove_actions_keep_both_original_policies(panel):
    w, _, _ = panel
    e, m = w.editor, w.editor.model
    e.view.setCurrentIndex(m.index(1, 0))
    w.menu_actions["Insert Row" if w.official else "Add row"].trigger()
    assert m.rowCount() == 3
    row = 2 if w.official else 1
    assert m.data(m.index(row, 0)) == ("[No data]" if w.official else "New entry")
    e.view.setCurrentIndex(m.index(0, 1))
    w.menu_actions["Insert Child" if w.official else "Add child"].trigger()
    parent = m.index(0, 0)
    assert m.rowCount(parent) == 2
    child_row = 0 if w.official else 1
    assert m.data(m.index(child_row, 0, parent)) == (
        "[No data]" if w.official else "New entry"
    )
    if w.official:
        assert e.view.currentIndex() == m.index(0, 0, parent)
    e.view.setCurrentIndex(m.index(0, 0))
    w.menu_actions["Insert Column" if w.official else "Add column"].trigger()
    col = 1 if w.official else 2
    assert m.columnCount() == 3
    assert m.headerData(col, QtCore.Qt.Horizontal) == (
        "[No header]" if w.official else "Column"
    )
    e.view.setCurrentIndex(m.index(0, col))
    w.menu_actions["Remove Column" if w.official else "Remove column"].trigger()
    assert m.columnCount() == 2
    e.view.setCurrentIndex(m.index(0, 0))
    w.menu_actions["Remove Row" if w.official else "Remove row"].trigger()
    assert m.rowCount() == 2 and m.data(m.index(0, 0)) != "A"


def test_selection_status_empty_tree_and_last_column_recovery(panel):
    w, state, _ = panel
    e, m = w.editor, w.editor.model
    e.view.setCurrentIndex(m.index(0, 1))
    assert (
        "Position: (0,1) in top level" if w.official else "Row 1, column 2"
    ) == w.selection_status.text()
    if w.official:
        assert w.menu_actions["Remove Row"].isEnabled()
        assert m.removeColumns(0, 2)
        w.controller.update()
        w.menu_actions["Insert Child"].trigger()
        assert m.columnCount() == m.rowCount() == 1
        assert m.headerData(0, QtCore.Qt.Horizontal) == "[No header]"
    else:
        assert m.removeColumns(1, 1)
        w.menu_actions["Remove column"].trigger()
        assert m.columnCount() == 1
    state.source = Tree(("Glyph", "Value"), ())
    w.refresh(discard=True)
    m = w.editor.model
    assert m.rowCount() == 0
    w.menu_actions["Insert Child" if w.official else "Add row"].trigger()
    assert m.rowCount() == 1


def test_refresh_refuses_implicit_discard_and_failures_keep_complete_draft(panel):
    w, state, _ = panel
    before = w.editor
    assert before.model.setData(before.model.index(0, 0), "A.review")
    w.refresh_button.click()
    assert w.editor is before and state.calls == 1 and "Reset Draft" in w.status.text()
    state.fail = True
    w.reset_button.click()
    assert (
        w.editor is before and before.model.data(before.model.index(0, 0)) == "A.review"
    )
    assert "source changed" in w.status.text()
    state.fail = False
    w.reset_button.click()
    assert w.editor is not before and before.released
    assert w.editor.model.data(w.editor.model.index(0, 0)) == "A"
    assert len(w._editors) == 1


@pytest.mark.parametrize(
    "route", ["close", "reject", "accept", "done", "escape", "destroy", "menu"]
)
def test_every_terminal_route_releases_owned_models_slots_and_registry(panel, route):
    w, _, _ = panel
    e = w.editor
    slots = [record[1] for record in w.scope.records + e.scope.records]
    sys.__dict__.setdefault("_fontlab_samples", {})[w.KEY] = w
    w.show()
    if route == "close":
        w.close_button.click()
    elif route == "menu":
        w.menu_actions["Exit"].trigger()
    elif route == "destroy":
        w.deleteLater()
    elif route == "escape":
        QTest.keyClick(w, QtCore.Qt.Key_Escape)
    elif route == "done":
        w.done(0)
    else:
        getattr(w, route)()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert w._closed and w.editor is None and not w._editors and e.released
    assert (
        not w.scope.records
        and not e.scope.records
        and w.KEY not in sys._fontlab_samples
    )
    for slot in slots:
        slot()
    w.refresh()
    w._dispose(destroyed=True)


def test_real_delegate_edits_local_text_without_return_activating_buttons(panel):
    w, state, _ = panel
    w.show()
    w.activateWindow()
    view, model = w.editor.view, w.editor.model
    index = model.index(0, 0)
    view.setCurrentIndex(index)
    view.edit(index)
    APP.processEvents()
    field = view.findChild(QtWidgets.QLineEdit)
    assert field is not None
    field.selectAll()
    QTest.keyClicks(field, "A.draft")
    QTest.keyClick(field, QtCore.Qt.Key_Return)
    APP.processEvents()
    assert model.data(index) == "A.draft" and state.calls == 1
    assert not w._closed and state.source.rows[0][1][0] == "A"


class FaultSignal:
    def __init__(self):
        self.fail = True

    def disconnect(self, slot):
        return False if self.fail else None


@pytest.mark.parametrize("where", ["panel", "editor", "button", "terminal"])
def test_disconnect_failure_retains_owner_and_usable_close_retry(panel, where):
    w, _, _ = panel
    editor = w.editor
    fault = FaultSignal()
    if where == "terminal":
        w._completion_lifetime.hooks.append((fault, lambda: None))
    else:
        scope = editor.scope if where == "editor" else w.scope
        scope.records.append((fault, lambda: None, where == "button"))
    sys.__dict__.setdefault("_fontlab_samples", {})[w.KEY] = w
    w.show()
    assert w.close() is False
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert valid(w) and sys._fontlab_samples[w.KEY] is w
    assert not w._completion_lifetime.closed
    if where == "editor":
        assert w.editor is editor and not editor.released
    fault.fail = False
    if where in {"panel", "editor"}:
        w.close_button.click()
    else:
        assert w.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert w.KEY not in sys._fontlab_samples and editor.released


@pytest.mark.parametrize("failed", [False, True])
def test_parent_destruction_cleans_even_after_failed_close(panel, failed):
    w, _, _ = panel
    parent = QtWidgets.QWidget()
    w.setParent(parent)
    editor = w.editor
    if failed:
        w.scope.records.append((FaultSignal(), lambda: None, True))
        assert w.close() is False
    sys.__dict__.setdefault("_fontlab_samples", {})[w.KEY] = w
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert w._closed and w._destroyed and editor.released
    assert w.editor is None and not w._editors and not w.scope.records
    assert w.KEY not in sys._fontlab_samples


@pytest.mark.parametrize("failure", ["type", "expired", "late", "editor", "attach"])
def test_reload_setup_failures_never_replace_or_erase_current_draft(
    panel, monkeypatch, failure
):
    w, _, module = panel
    before = w.editor
    if failure == "type":
        w._capture = lambda **kw: None
    elif failure == "expired":
        monkeypatch.setattr(module, "monotonic", lambda: 0)
    elif failure == "late":

        def capture(**kw):
            w.close()
            return Tree(("A",), ())

        w._capture = capture
    elif failure == "editor":

        def broken(*args, **kwargs):
            raise ValueError("staged editor failed")

        monkeypatch.setattr(module, "Editor", broken)
    else:
        w.container = NS(
            addWidget=lambda view: (_ for _ in ()).throw(ValueError("attach failed"))
        )
    w.refresh(discard=True)
    if failure == "late":
        assert w._closed and before.released
    else:
        assert w.editor is before and not before.released
        assert before.model.data(before.model.index(0, 0)) == "A"
        assert len(w._editors) == 1 and w.last_error


def test_failed_refresh_cleanup_fences_work_without_implicitly_closing_draft(panel):
    w, _, _ = panel
    editor = w.editor
    fault = FaultSignal()
    editor.scope.records.append((fault, lambda: None, False))
    w.refresh(discard=True)
    assert w._closed and w.editor is editor and not editor.released
    assert "Close" in w.status.text() and not editor.view.isEnabled()
    fault.fail = False
    w.close_button.click()
    assert editor.released


def test_actions_failure_is_contained_and_child_status_and_empty_actions_are_complete(
    panel, monkeypatch
):
    w, _, _ = panel
    e, m = w.editor, w.editor.model
    e.view.setCurrentIndex(m.index(0, 0, m.index(0, 0)))
    assert w.selection_status.text() == (
        "Position: (0,0)" if w.official else "Row 1, column 1"
    )
    if w.official:
        for action in w.menu_bar.actions():
            if action.text().replace("&", "") == "Actions":
                action.menu().aboutToShow.emit()
    original = m.insertRows
    monkeypatch.setattr(m, "insertRows", lambda *args: False)
    w.menu_actions["Insert Row" if w.official else "Add row"].trigger()
    assert "refused" in w.status.text()
    monkeypatch.setattr(m, "insertRows", original)
    with pytest.raises(ValueError, match="Unknown"):
        w.controller.run("unknown")
    e.selection.clear()
    w.controller.update()
    if not w.official:
        w.menu_actions["Remove row"].trigger()
        assert m.rowCount() == 2


def test_keyboard_shortcuts_activate_owned_original_actions(panel):
    w, _, _ = panel
    if not w.official:
        return
    w.show()
    w.activateWindow()
    w.editor.view.setFocus()
    APP.processEvents()
    count = len(w.editor.model._draft.identities())
    QTest.keyClick(w.editor.view, QtCore.Qt.Key_N, QtCore.Qt.ControlModifier)
    APP.processEvents()
    assert len(w.editor.model._draft.identities()) == count + 1
    QTest.keyClick(w.editor.view, QtCore.Qt.Key_I, QtCore.Qt.ControlModifier)
    QTest.keyClick(w.editor.view, QtCore.Qt.Key_R)
    APP.processEvents()
    assert len(w.editor.model._draft.identities()) == count + 2


@pytest.mark.parametrize("retained", [False, True])
def test_constructor_failure_closes_or_retains_the_complete_owner_for_retry(
    panel, monkeypatch, retained
):
    original, _, module = panel
    made = []
    fault = FaultSignal()

    def broken(w, qt):
        made.append(w)
        if retained:
            w.scope.records.append((fault, lambda: None, False))
        raise ValueError("form setup failed")

    monkeypatch.setattr(module, "build", broken)
    with pytest.raises(ValueError, match="form setup"):
        module.EditableGlyphTreeDialog(
            None, lambda **kw: None, official=original.official
        )
    w = made[0]
    assert w._closed
    if retained:
        assert sys._fontlab_samples[w.KEY] is w
        fault.fail = False
        assert w.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert w.KEY not in getattr(sys, "_fontlab_samples", {})


def test_partial_editor_setup_failure_is_owned_and_releases_without_erasing_old_draft(
    panel, monkeypatch
):
    import fontlabapp.qt.trees.editable.editor as editor_module

    w, _, _ = panel
    before = w.editor

    def fail(*args):
        raise ValueError("native model setup failed")

    monkeypatch.setattr(editor_module, "model_type", fail)
    w.refresh(discard=True)
    assert w.editor is before and not before.released and len(w._editors) == 1
    assert "setup failed" in w.status.text()


def test_detach_failure_refuses_close_and_preserves_view_model_until_retry(
    panel, monkeypatch
):
    w, _, _ = panel
    e = w.editor
    original = e.view.setModel
    monkeypatch.setattr(
        e.view,
        "setModel",
        lambda *args: (_ for _ in ()).throw(ValueError("detach failed")),
    )
    assert w.close() is False and w.editor is e and not e.released
    assert e.model is not None and "detach failed" in w.status.text()
    monkeypatch.setattr(e.view, "setModel", original)
    w.close_button.click()
    assert e.released


def test_late_error_label_failure_is_contained_without_touching_dead_widgets(panel):
    w, _, _ = panel
    old = w.status
    w.status = NS(setText=lambda value: (_ for _ in ()).throw(ValueError("dead label")))
    w._failure(ValueError("outer"))
    assert w._destroyed and w.last_error == "outer"
    w.status, w._destroyed = old, False


def test_terminal_false_connection_is_not_recorded_and_none_return_is_supported(panel):
    _, _, module = panel
    owner = NS(hooks=[])
    slot = lambda: None
    with pytest.raises(RuntimeError, match="connection"):
        module._terminal(owner, NS(connect=lambda call: False), slot)
    assert owner.hooks == []
    signal = NS(connect=lambda call: None)
    module._terminal(owner, signal, slot)
    assert owner.hooks == [(signal, slot)]


def test_close_during_staged_editor_setup_cannot_publish_a_late_view(
    panel, monkeypatch
):
    w, _, module = panel
    original = module.Editor
    made = []

    def construct(*args, **kw):
        editor = original(*args, **kw)
        made.append(editor)
        w.close()
        return editor

    monkeypatch.setattr(module, "Editor", construct)
    w.refresh(discard=True)
    assert w._closed and w.editor is None and made[0].released


def test_heading_works_with_pythonqt_window_title_property(panel):
    w, state, module = panel

    class NativeTitle(module.EditableGlyphTreeDialog):
        windowTitle = property(QtWidgets.QDialog.windowTitle)

    other = NativeTitle(None, lambda **kw: state.source, official=w.official)
    assert other.editor is not None
    assert other.close()


def test_constructor_retained_priority_before_show_preserves_exception(panel, monkeypatch):
    original, _state, module = panel
    kind = module.EditableGlyphTreeDialog
    original_close = kind.close
    error = RuntimeError("original constructor error")
    owners, shown = [], []

    def fail(owner, *args):
        owners.append(owner)
        raise error

    def show(owner):
        shown.append(owner.windowFlags())
        QtWidgets.QWidget.show(owner)

    monkeypatch.setattr(module, "build", fail)
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


@pytest.mark.parametrize("empty", [True, False])
def test_controller_when_pythonqt_selection_is_a_property_then_reads_value(empty):
    """FontLab's PythonQt exposes QItemSelectionModel.selection as a value, not a method."""
    from fontlabapp.qt.trees.editable.actions import Controller

    enabled = {}

    def action(label):
        return NS(setEnabled=lambda on: enabled.__setitem__(label, on))

    labels = ("Remove Row", "Remove Column", "Insert Row", "Insert Column", "Insert Child")
    invalid = NS(isValid=lambda: False)
    panel = NS(
        _closed=False,
        official=True,
        editor=NS(
            view=NS(currentIndex=lambda: invalid),
            selection=NS(selection=NS(isEmpty=lambda: empty)),  # PythonQt property shape
        ),
        menu_actions={label: action(label) for label in labels},
        selection_status=NS(setText=lambda text: None),
    )
    Controller(panel, NS(QtCore=NS(QModelIndex=lambda: invalid))).update(initial=True)
    assert enabled["Remove Row"] is (not empty) and enabled["Insert Child"] is True
