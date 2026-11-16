# this_file: tests/test_revision_compare_dialog.py
# SPDX-License-Identifier: Apache-2.0
"""Real offscreen controls with registered native-shaped revision sources."""

import importlib
import os
import sys
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid
from test_revision_compare import source  # noqa: F401 - shared owned fixture

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def panel(monkeypatch, source):  # noqa: F811 - imported pytest fixture
    class Dialog(QtWidgets.QDialog):
        palette = property(QtWidgets.QDialog.palette)

        def __setattr__(self, name, value):
            assert QtWidgets.QDialog.staticMetaObject.indexOfProperty(name) < 0
            assert not callable(getattr(QtWidgets.QDialog, name, None))
            super().__setattr__(name, value)

    class Label(QtWidgets.QLabel):
        font = property(QtWidgets.QLabel.font)

    class Line(QtWidgets.QLineEdit):
        text = property(QtWidgets.QLineEdit.text)

    class Combo(QtWidgets.QComboBox):
        currentIndex = property(QtWidgets.QComboBox.currentIndex)

    class Table(QtWidgets.QTableWidget):
        fail = False

        def setItem(self, *args):
            if self.fail:
                raise RuntimeError("render failure")
            return super().setItem(*args)

    gui = NS(**{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
    gui.__dict__.update(
        {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
    )
    gui.QDialog, gui.QLabel, gui.QLineEdit, gui.QComboBox, gui.QTableWidget = (
        Dialog,
        Label,
        Line,
        Combo,
        Table,
    )
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=QtCore, QtGui=gui))
    for name in ("fontlabapp.glyphs.names.ui", "fontlabapp.fonts.revisions.ui"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    package = importlib.import_module("fontlabapp")
    original_lookup = package.__getattr__
    monkeypatch.delattr(package, "revision_compare", raising=False)

    def guarded_lookup(name):
        assert name != "revision_compare", (
            "Submodule import must bypass native fallback"
        )
        return original_lookup(name)

    monkeypatch.setattr(package, "__getattr__", guarded_lookup)
    mod = importlib.import_module("fontlabapp.fonts.revisions.ui")
    workspace, packages = source
    monkeypatch.setattr(
        mod, "_native", lambda name: NS(flWorkspace=NS(instance=lambda: workspace))
    )
    dialog = mod.RevisionCompareDialog()
    yield dialog, packages, mod, Table
    if isValid(dialog):
        dialog.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    APP.processEvents()


def choose(dialog):
    dialog.left_font.setCurrentIndex(0)
    dialog.right_font.setCurrentIndex(1)
    dialog.left_master.setCurrentIndex(0)
    dialog.right_master.setCurrentIndex(0)


def test_query_change_during_final_validation_discards_rows(panel, monkeypatch):
    dialog, packages, _mod, _table = panel
    choose(dialog)
    packages[1].items[0].layers["Regular"].advanceWidth = 42
    dialog.compare_button.click()
    assert len(dialog.rows) == 1
    validate = dialog.ensure_snapshot
    calls = []

    def changed_query():
        validate()
        calls.append(True)
        if len(calls) == 2:
            blocked = dialog.search.blockSignals(True)
            dialog.search.setText("nonmatching-query")
            dialog.search.blockSignals(blocked)

    monkeypatch.setattr(dialog, "ensure_snapshot", changed_query)
    dialog.filter_rows()
    assert not dialog.rows and not dialog.shown, (
        "Never publish results for a superseded query"
    )
    assert "Search changed" in dialog.status.text()


def test_controls_explicit_sources_comparison_search_details_and_close(
    panel, monkeypatch
):
    d, packages, _mod, _ = panel
    assert not d.isModal() and d.close_button.isEnabled()
    assert d.left_font.currentIndex == -1 and d.right_font.currentIndex == -1
    assert "1 · A.vfj" in d.left_font.itemText(0)
    assert "2 · B.vfj" in d.left_font.itemText(1)
    assert d.left_font.itemData(0, QtCore.Qt.ToolTipRole).endswith("A.vfj")
    assert not d.rows and "Choose" in d.status.text()
    choose(d)
    packages[1].items[0].layers["Regular"].advanceWidth = 42
    d.compare_button.click()
    assert len(d.rows) == 1 and d.table.rowCount() == 1
    assert d.table.editTriggers() == QtWidgets.QAbstractItemView.NoEditTriggers
    d.table.selectRow(0)
    assert (
        "Advance width" in d.details.toPlainText() and "42.0" in d.details.toPlainText()
    )
    d.search.setText("missing")
    assert not d.shown and "0 shown" in d.status.text()
    d.search.setText("advance")
    assert len(d.shown) == 1
    monkeypatch.setattr(sys, "_fontlab_samples", {d.KEY: d}, raising=False)
    d.close_button.click()
    assert not d.rows and not d._connections and d.KEY not in sys._fontlab_samples


@pytest.mark.parametrize(
    "change", ["order", "closed", "path", "id", "masters", "glyph", "layer", "node"]
)
def test_stale_sources_clear_results_on_search_without_rebinding(panel, change):
    d, packages, _mod, _ = panel
    choose(d)
    d.compare_button.click()
    selected = d._selection()
    if change == "order":
        packages.reverse()
    elif change == "closed":
        packages.pop()
    elif change == "path":
        packages[0].path = "other.vfj"
    elif change == "id":
        packages[0].id += 1
    elif change == "masters":
        packages[0].masters.reverse()
    elif change == "glyph":
        packages[0].items.clear()
    elif change == "layer":
        packages[0].items[0].layers["Regular"].id += 1
    else:
        packages[0].items[0].layers["Regular"].shapes[0].contours[0].nodes()[
            0
        ].nodeState ^= 32
    d.search.setText("space")
    assert not d._snapshot_valid and not d.snapshots and not d.rows
    assert d.table.rowCount() == 0 and not d.details.toPlainText()
    assert "Error:" in d.status.text() and d.close_button.isEnabled()
    assert d._selection() == selected


def test_no_fonts_one_font_initial_failure_and_refresh_recovery(panel, monkeypatch):
    d, packages, mod, _ = panel
    saved = list(packages)
    packages.clear()
    d.refresh_button.click()
    assert "No open fonts" in d.status.text()
    packages.append(saved[0])
    d.refresh_button.click()
    assert "two open fonts" in d.status.text()
    original = mod.api.font_choices
    monkeypatch.setattr(
        mod.api,
        "font_choices",
        lambda ws: (_ for _ in ()).throw(ValueError("unreadable registration")),
    )
    other = mod.RevisionCompareDialog()
    assert "unreadable" in other.status.text() and other.close_button.isEnabled()
    assert other.table.rowCount() == 0 and other.left_master.count() == 0
    other.close()
    monkeypatch.setattr(mod.api, "font_choices", original)
    packages[:] = saved
    d.refresh_button.click()
    choose(d)
    d.compare_button.click()
    assert d._snapshot_valid


def test_scope_changes_missing_master_and_missing_layer_are_visible(panel):
    d, packages, _mod, _ = panel
    choose(d)
    d.right_master.setCurrentIndex(1)
    d.compare_button.click()
    assert "state" in d.rows[0].fields
    d.table.selectRow(0)
    assert "missing_layer" in d.details.toPlainText()
    packages[1].masters.remove("Bold")
    d.refresh_button.click()
    assert "missing" in d.right_master.itemText(d.right_master.currentIndex)
    d.compare_button.click()
    assert any("master_presence" in row.fields for row in d.rows)
    d.table.selectRow(0)
    assert "Master presence" in d.details.toPlainText()
    d.left_master.setCurrentIndex(1)
    assert not d.rows and not d.details.toPlainText()


def test_raw_flags_named_separately_and_missing_glyph_order_details(panel):
    d, packages, _mod, _ = panel
    choose(d)
    packages[1].items[0].layers["Regular"].shapes[0].contours[0].nodes()[
        0
    ].nodeState ^= 32
    d.compare_button.click()
    assert d.rows[0].fields == ("raw_node_state",)
    assert "Raw node flags (includes selection)" in d.table.item(0, 1).text()
    d.table.selectRow(0)
    assert "Raw node flags (includes selection)" in d.details.toPlainText()
    packages[1].items.clear()
    d.compare_button.click()
    assert d.rows[0].fields == ("glyph_order",)
    d.table.selectRow(1)
    assert (
        "Glyph presence" in d.details.toPlainText()
        and "null" in d.details.toPlainText()
    )


def test_publication_failure_clears_partial_rows_and_capture_can_recover(
    panel, monkeypatch
):
    d, packages, _mod, table = panel
    choose(d)
    packages[1].items.clear()
    table.fail = True
    d.compare_button.click()
    assert "render failure" in d.status.text() and not d.rows and not d.snapshots
    table.fail = False
    d.compare_button.click()
    assert d.rows
    d.table.selectRow(0)
    packages.reverse()
    d.show_details()
    assert not d.rows and "Error:" in d.status.text()
    d.compare_button.click()
    assert "Refresh Font List" in d.status.text()
    d.refresh_button.click()
    assert d.left_font.currentIndex == 1 and d.right_font.currentIndex == 0
    packages.pop()
    d.refresh_button.click()
    assert d.left_font.currentIndex == -1
    d.compare_button.click()
    assert "Choose" in d.status.text()


def test_same_font_missing_masters_and_mid_capture_selection_change(panel, monkeypatch):
    d, packages, mod, _ = panel
    choose(d)
    d.right_font.setCurrentIndex(0)
    d.compare_button.click()
    assert "different" in d.status.text()
    d.right_font.setCurrentIndex(1)
    packages[0].masters.clear()
    d.refresh_button.click()
    assert "missing" in d.left_master.itemText(0)
    d.left_master.setCurrentIndex(-1)
    d.compare_button.click()
    assert "Choose" in d.status.text()
    packages[0].masters.append("Regular")
    d.refresh_button.click()
    choose(d)
    capture = mod.api.capture

    def changed(*args, **kwargs):
        snapshot = capture(*args, **kwargs)
        d.left_master.setCurrentIndex(1)
        return snapshot

    monkeypatch.setattr(mod.api, "capture", changed)
    d.compare_button.click()
    assert not d.rows and "changed" in d.status.text()


def test_no_selection_detail_stale_direct_guard_and_post_close_callbacks(panel):
    d, _packages, _mod, _table = panel
    d.show_details()
    d.filter_rows()
    with pytest.raises(ValueError, match="stale"):
        d.ensure_snapshot()
    choose(d)
    d.compare_button.click()
    d.show_details()
    assert not d.details.toPlainText()
    # A queued Python action after Close must not touch its deleted widgets.
    d.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    d.refresh_fonts()
    d.compare_fonts()
    d.filter_rows()
    d.show_details()


def test_no_master_domain_and_duplicate_titles_are_explicit(panel):
    d, packages, _mod, _table = panel
    packages[0].masters.clear()
    packages[1].label = packages[0].label
    d.refresh_button.click()
    d.left_font.setCurrentIndex(0)
    d.right_font.setCurrentIndex(1)
    assert d.left_master.count() == 0
    assert d.left_font.itemText(0) != d.left_font.itemText(1)
    d.compare_button.click()
    assert "Choose" in d.status.text() and d.close_button.isEnabled()


def test_registry_replacement_closes_owned_old_panel_and_retains_new(
    panel, monkeypatch
):
    d, _packages, mod, _table = panel
    from fontlabapp.core import scripting

    monkeypatch.setattr(sys, "_fontlab_samples", {d.KEY: d}, raising=False)
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: (
            sys.modules["PythonQt"]
            if name == "PythonQt"
            else NS(MainWindow=lambda: None)
        ),
    )
    replacement = scripting.show_script_dialog(mod.RevisionCompareDialog, d.KEY)
    assert d._closed and not d._connections
    assert sys._fontlab_samples[d.KEY] is replacement and replacement.isVisible()
    replacement.close()


@pytest.mark.parametrize("owner", ["parent", "dialog"])
@pytest.mark.parametrize("queued", [False, True])
def test_actual_destruction_disables_retained_actions_and_slots(
    panel, monkeypatch, owner, queued
):
    _original, _packages, mod, _table = panel
    parent = QtWidgets.QWidget()
    dialog = mod.RevisionCompareDialog(parent)
    choose(dialog)
    dialog.compare_fonts()
    assert dialog.snapshots
    callbacks = [slot for _signal, slot in dialog._connections]
    monkeypatch.setattr(sys, "_fontlab_samples", {dialog.KEY: dialog}, raising=False)

    def forbidden(*args):
        pytest.fail("Destroyed revision panel must never read its workspace")

    monkeypatch.setattr(mod.api, "font_choices", forbidden)
    failures, delivered = [], []

    def late():
        try:
            dialog.refresh_fonts()
            dialog.compare_fonts()
            dialog.font_changed("left")
            dialog.choices_changed()
            dialog.filter_rows()
            dialog.show_details()
            dialog.invalidate()
            for callback in callbacks:
                callback()
        except Exception as error:  # noqa: BLE001 - report queued failures to pytest
            failures.append(repr(error))
        delivered.append(True)

    if queued:
        QtCore.QTimer.singleShot(0, late)
    (parent if owner == "parent" else dialog).deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(dialog), "Delete native Qt before delivering queued callbacks"
    if queued:
        APP.processEvents()
    else:
        late()
    assert delivered and not failures, failures
    assert dialog._closed and not dialog._connections
    assert not dialog.snapshots and not dialog.rows and not dialog.shown
    assert dialog.KEY not in sys._fontlab_samples
    if isValid(parent):
        parent.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_parent_destruction_preserves_replacement_registry_and_failed_panel(
    panel, monkeypatch
):
    _original, _packages, mod, _table = panel

    def failed(*args):
        raise ValueError("injected registration failure")

    monkeypatch.setattr(mod.api, "font_choices", failed)
    parent = QtWidgets.QWidget()
    dialog = mod.RevisionCompareDialog(parent)
    assert "registration failure" in dialog.status.text()
    replacement, unrelated = object(), object()
    registry = {dialog.KEY: replacement, "unrelated": unrelated}
    monkeypatch.setattr(sys, "_fontlab_samples", registry, raising=False)
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(dialog) and dialog._closed
    dialog.refresh_fonts()
    with pytest.raises(ValueError, match="closed"):
        dialog.ensure_snapshot()
    assert not dialog._connections and not dialog.snapshots
    assert registry == {dialog.KEY: replacement, "unrelated": unrelated}


@pytest.mark.parametrize("owner", ["parent", "dialog"])
def test_destruction_explicitly_disconnects_callbacks_before_live_children_die(
    panel, owner
):
    _original, _packages, mod, _table = panel
    parent = QtWidgets.QWidget()
    dialog = mod.RevisionCompareDialog(parent)
    connected = tuple(dialog._connections)
    children = (dialog.left_font, dialog.right_font, dialog.search, dialog.table)
    disconnected = []

    class CheckedSignal:
        def __init__(self, signal):
            self.signal = signal

        def disconnect(self, slot):
            assert all(isValid(widget) for widget in children)
            if owner == "parent":
                assert isValid(dialog), "Parent cleanup must precede dialog destruction"
            disconnected.append(slot)
            self.signal.disconnect(slot)

    dialog._connections[:] = [
        (CheckedSignal(signal), slot) for signal, slot in connected
    ]
    (parent if owner == "parent" else dialog).deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert len(disconnected) == len(connected), "Explicitly disconnect every owned slot"
    assert not dialog._connections and not dialog._disconnect_errors
    if isValid(parent):
        parent.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_destructor_disconnect_failure_is_retained_without_escaping_qt(panel):
    _original, _packages, mod, _table = panel
    parent = QtWidgets.QWidget()
    dialog = mod.RevisionCompareDialog(parent)
    attempts = []

    class FailedSignal:
        def disconnect(self, slot):
            attempts.append(slot)
            raise RuntimeError("injected disconnect failure")

    dialog._connections.append((FailedSignal(), lambda: None))
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert len(attempts) == 1 and not isValid(dialog)
    assert dialog._disconnect_errors == ["RuntimeError('injected disconnect failure')"]
    assert not dialog._connections and dialog._closed
