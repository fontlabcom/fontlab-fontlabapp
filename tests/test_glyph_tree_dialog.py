# this_file: tests/test_glyph_tree_dialog.py
"""Owned tree view, selection status, refresh failures and complete teardown."""

from module_paths import module_name as _module_name
import importlib
import os
import sys
from types import SimpleNamespace as NS

import pytest
from fontlabapp.qt.trees.data import Tree

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtGui, QtWidgets, sip

    valid = lambda value: not sip.isdeleted(value)
else:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import isValid as valid
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
ROWS = (
    (-1, ("A", "U+0041")),
    (0, ("Unicode", "U+0041")),
    (0, ("Modified", "2026-01-01")),
    (-1, ("a.alt", "Not encoded")),
)


@pytest.fixture(params=[False, True], ids=["part3-tree", "part2-outline"])
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
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=QtCore, QtGui=gui))
    for name in ["_names_dialog", "_glyph_tree_dialog"]:
        monkeypatch.delitem(sys.modules, _module_name(name), raising=False)
    module = importlib.import_module("fontlabapp.glyphs.tree.ui")
    state = NS(rows=ROWS, fail=False, calls=0, deadline=None)

    def capture(*, deadline):
        state.calls += 1
        state.deadline = deadline
        if state.fail:
            raise ValueError("source changed")
        return Tree(("Glyph", "Details"), state.rows)

    w = module.GlyphTreeDialog(
        None, "Owned metadata tree", "owned_tree", capture, request.param
    )
    yield w, state, request.param
    if valid(w):
        w.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_complete_model_tree_expansion_readonly_and_selection_status(panel):
    w, state, outline = panel
    assert w.model.rowCount() == 2 and w.view.model() is w.model and state.calls == 1
    assert w.view.editTriggers() == QtWidgets.QAbstractItemView.NoEditTriggers
    assert not w.isModal() and "2 glyphs" in w.status.text()
    a = w.model.index(0, 0)
    w.view.expand(a)
    assert w.view.isExpanded(a) and w.model.rowCount(a) == 2
    w.view.setCurrentIndex(w.model.index(1, 1, a))
    if outline:
        assert w.selection_status.text() == "Row 2, column 2"
        w.view.setCurrentIndex(QtCore.QModelIndex())
        assert w.selection_status.text() == "No selection"
    else:
        assert w.selection_status is None
    assert state.calls == 1


def test_refresh_replaces_selection_owner_and_failed_capture_removes_all_results(panel):
    w, state, outline = panel
    old, selection = w.model, w._selection
    state.rows = ()
    w.refresh_button.click()
    assert (
        old._active is False
        and w.model.rowCount() == 0
        and "0 glyphs" in w.status.text()
    )
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not valid(old) and not valid(selection)
    state.fail = True
    w.refresh()
    assert (
        w.model is None
        and w.view.model() is None
        and "source changed" in w.status.text()
    )
    state.fail = False
    state.rows = ROWS
    w.refresh()
    assert w.model.rowCount() == 2
    if outline:
        before = w.selection_status.text()
        w._selected(old, QtCore.QModelIndex())
        assert w.selection_status.text() == before


@pytest.mark.parametrize(
    "route", ["close", "reject", "accept", "done", "escape", "destroy"]
)
def test_every_completion_releases_model_selection_connections_and_late_refresh(
    panel, route
):
    w, state, _ = panel
    model, selection = w.model, w._selection
    sys.__dict__.setdefault("_fontlab_samples", {})[w.KEY] = w
    w.show()
    if route == "close":
        w.close_button.click()
    elif route == "reject":
        w.reject()
    elif route == "accept":
        w.accept()
    elif route == "done":
        w.done(0)
    elif route == "destroy":
        w.deleteLater()
    else:
        if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
            from PyQt5.QtTest import QTest
        else:
            from PySide6.QtTest import QTest
        QTest.keyClick(w, QtCore.Qt.Key_Escape)
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert w._closed and w._capture is None and not w._connections
    assert not model._active and not valid(model) and not valid(selection)
    assert w.KEY not in sys._fontlab_samples
    calls = state.calls
    w.refresh()
    assert state.calls == calls


@pytest.mark.parametrize("failure", ["wrong", "expired", "closed"])
def test_wrong_or_expired_or_closed_capture_never_installs_partial_model(
    panel, monkeypatch, failure
):
    w, _, _ = panel
    if failure == "wrong":
        w._capture = lambda **kw: None
    elif failure == "closed":

        def capture(**kw):
            w.close()
            return Tree(("A",), ())

        w._capture = capture
    else:
        module = sys.modules[w.__class__.__module__]
        monkeypatch.setattr(module, "monotonic", lambda: -10)
    w.refresh()
    assert w.model is None
    if failure != "closed":
        assert "complete immutable" in w.status.text() or "expired" in w.status.text()


def test_part2_file_exit_keeps_original_action_and_part3_has_no_menu(panel):
    w, _, outline = panel
    if outline:
        assert (
            w.exit_action.text() == "Exit" and w.menu_bar.actions()[0].text() == "File"
        )
        w.exit_action.trigger()
        assert w._closed
    else:
        assert w.exit_action is None


def test_view_detach_failure_still_fences_old_virtuals_and_records_cleanup(
    panel, monkeypatch
):
    w, _, _ = panel
    previous = w.model

    def fail(model):
        assert previous._active, "model must stay valid during view detachment"
        raise RuntimeError("owned detach failure")

    monkeypatch.setattr(w.view, "setModel", fail)
    w._dispose()
    assert not previous._active and previous._snapshot is None
    assert w._closed and not w._connections and w.model is None
    assert any("owned detach failure" in error for error in w._disconnect_errors)


def test_parent_destruction_releases_owned_model_and_callbacks(panel):
    w, _, outline = panel
    parent = QtWidgets.QWidget()
    other = w.__class__(
        parent,
        "Owned parent tree",
        "owned_parent_tree",
        lambda **kw: Tree(("A",), ((-1, ("one",)),)),
        outline,
    )
    model, selection = other.model, other._selection
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert other._closed and other._capture is None and not other._connections
    assert not model._active and not valid(model) and not valid(selection)
