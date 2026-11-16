# this_file: tests/test_alignment_zones_dialog.py
"""Exercise the actual modeless editor with owned offscreen Qt and explicit I/O."""

import importlib
import os
import sys
from dataclasses import replace
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid

from fontlabapp.metrics.zones.data import Master, Origin, Snapshot, Zone, Zones

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class Backend:
    """Own every source value; simulate calls, never a native history guarantee."""

    def __init__(self):
        self.snapshot = Snapshot(
            31,
            "Regular",
            (
                Master("Thin", 400.5, 650.5),
                Master(
                    "Regular",
                    500.5,
                    700.5,
                    Zones(
                        (Zone(700, 14, "cap"), Zone(500, 12, ""), Zone(500, 12, "")),
                        (Zone(0, 12, "base"),),
                    ),
                ),
            ),
        )
        self.writes, self.bounds_calls = [], []
        self.stale, self.fail_capture, self.fail_apply = False, False, False
        self.during_apply = self.during_bounds = None

    def capture(self):
        if self.fail_capture:
            raise ValueError("Open a font first")
        return self.snapshot

    def check(self, snapshot):
        if self.stale or snapshot != self.snapshot:
            raise ValueError("Original source changed; reopen")

    def bounds(self, snapshot, master):
        self.bounds_calls.append(master)
        if self.during_bounds:
            self.during_bounds()
        return (-12.5, 514.0), (-15.0, 714.0)

    def apply(self, snapshot, changes):
        self.writes.append(changes)
        if self.during_apply:
            self.during_apply()
        if self.fail_apply:
            raise RuntimeError("partial write; use native Undo and reopen")
        values = {change.master: change.after for change in changes}
        self.snapshot = replace(
            snapshot,
            masters=tuple(
                replace(master, zones=values.get(master.name, master.zones))
                for master in snapshot.masters
            ),
        )
        return self.snapshot


@pytest.fixture
def panel(monkeypatch):
    class Dialog(QtWidgets.QDialog):
        palette = property(QtWidgets.QDialog.palette)

        def __setattr__(self, name, value):
            assert QtWidgets.QDialog.staticMetaObject.indexOfProperty(name) < 0
            assert not callable(getattr(QtWidgets.QDialog, name, None))
            super().__setattr__(name, value)

    class Label(QtWidgets.QLabel):
        font = property(QtWidgets.QLabel.font)

    class Item(QtWidgets.QTableWidgetItem):
        def setTextAlignment(self, alignment):
            """Bridge the documented Qt5 integer slot to Qt6's enum overload."""
            super().setTextAlignment(QtCore.Qt.AlignmentFlag(alignment))

    class Selection:
        def __init__(self, model):
            self.model = model

        def selectedRows(self, column):
            """Match the compiled declaration's required column parameter."""
            return self.model.selectedRows(column)

        def __getattr__(self, name):
            return getattr(self.model, name)

    class Table(QtWidgets.QTableWidget):
        def selectionModel(self):
            return Selection(super().selectionModel())

    gui = NS(
        **{name: getattr(QtGui, name) for name in dir(QtGui) if name.startswith("Q")}
    )
    gui.__dict__.update(
        {
            name: getattr(QtWidgets, name)
            for name in dir(QtWidgets)
            if name.startswith("Q")
        }
    )
    gui.QDialog, gui.QLabel, gui.QTableWidgetItem = Dialog, Label, Item
    gui.QTableWidget = Table
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=QtCore, QtGui=gui))
    for name in (
        "fontlabapp.glyphs.names.ui",
        "fontlabapp.metrics.zones.controls",
        "fontlabapp.metrics.zones.ui",
    ):
        monkeypatch.delitem(sys.modules, name, raising=False)
    mod = importlib.import_module("fontlabapp.metrics.zones.ui")
    backend = Backend()
    widget = mod.AlignmentZonesDialog(backend=backend)
    yield widget, mod, backend
    if isValid(widget):
        widget.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_actual_table_keeps_duplicate_row_metadata_through_edit_switch_remove_apply(
    panel,
):
    old, mod, backend = panel
    old.close()
    top = (
        Zone(500, 12, "", Origin("a", b"locked;red")),
        Zone(500, 12, "", Origin("b", b"unlocked;blue")),
    )
    backend.snapshot = replace(
        backend.snapshot,
        masters=(
            backend.snapshot.masters[0],
            replace(backend.snapshot.masters[1], zones=Zones(top)),
        ),
    )
    widget = mod.AlignmentZonesDialog(backend=backend)
    try:
        original = widget.editor.origins("Regular")
        widget.table.item(0, 3).setText("renamed")
        widget.master.setCurrentIndex(0)
        widget.add_bottom.click()
        widget.master.setCurrentIndex(1)
        assert widget.editor.origins("Regular")[0] == original[0]
        widget.table.selectRow(1)
        widget.remove_button.click()
        assert widget.editor.origins("Regular") == (original[0],)
        widget.apply_button.click()
        assert [change.master for change in backend.writes[0]] == ["Thin", "Regular"]
        assert backend.writes[0][1].after.top[0].origin == original[0]
        assert not widget.editor.pending() and widget._row_origins == (original[0],)
        widget.table.item(0, 1).setText("510")
        widget.apply_button.click()
        assert backend.writes[1][0].after.top[0].origin == original[0]
    finally:
        widget.close()
    assert widget._row_origins == () and widget._backend is None


def test_actual_invalid_row_repair_keeps_unselected_duplicate_identity(panel):
    old, mod, backend = panel
    old.close()
    top = (
        Zone(500, 12, "", Origin("a", b"first")),
        Zone(500, 12, "", Origin("b", b"second")),
    )
    backend.snapshot = replace(
        backend.snapshot,
        masters=(
            backend.snapshot.masters[0],
            replace(backend.snapshot.masters[1], zones=Zones(top)),
        ),
    )
    widget = mod.AlignmentZonesDialog(backend=backend)
    try:
        original = widget.editor.origins("Regular")
        widget.table.item(0, 1).setText("bad")
        assert not widget.apply_button.isEnabled() and widget._row_origins == original
        widget.master.setCurrentIndex(0)
        assert widget.master.currentText() == "Regular"
        widget.table.selectRow(0)
        widget.remove_button.click()
        assert widget.editor.origins("Regular") == (original[1],)
        widget.apply_button.click()
        assert backend.writes[0][0].after.top[0].origin == original[1]
    finally:
        widget.close()


def test_actual_identity_tracks_visual_rows_when_values_change_sort_order(panel):
    old, mod, backend = panel
    old.close()
    top = (
        Zone(500, 12, "", Origin("a", b"first")),
        Zone(500, 12, "", Origin("b", b"second")),
    )
    backend.snapshot = replace(
        backend.snapshot,
        masters=(
            backend.snapshot.masters[0],
            replace(backend.snapshot.masters[1], zones=Zones(top)),
        ),
    )
    widget = mod.AlignmentZonesDialog(backend=backend)
    try:
        first, second = widget._row_origins
        widget.table.item(0, 1).setText("100")
        assert widget.editor.origins("Regular") == (second, first)
        widget.table.item(0, 3).setText("still first visual row")
        assert widget.editor.zones("Regular").top[0].origin == first
        widget.table.selectRow(1)
        widget.remove_button.click()
        widget.apply_button.click()
        assert backend.writes[0][0].after.top == (
            Zone(100, 12, "still first visual row", first),
        )
    finally:
        widget.close()


def test_actual_apply_rebases_new_native_identity_and_preserves_it_on_next_edit(panel):
    old, mod, backend = panel
    old.close()
    backend.snapshot = replace(
        backend.snapshot,
        masters=(
            backend.snapshot.masters[0],
            replace(
                backend.snapshot.masters[1],
                zones=Zones((Zone(500, 12, "", Origin("old", b"keep")),)),
            ),
        ),
    )
    apply = backend.apply

    def bind_new(snapshot, changes):
        result = apply(snapshot, changes)
        masters = tuple(
            replace(
                master,
                zones=Zones(
                    tuple(
                        replace(
                            z, origin=z.origin or Origin(f"fresh-top-{i}", b"defaults")
                        )
                        for i, z in enumerate(master.zones.top)
                    ),
                    tuple(
                        replace(
                            z,
                            origin=z.origin or Origin(f"fresh-bottom-{i}", b"defaults"),
                        )
                        for i, z in enumerate(master.zones.bottom)
                    ),
                ),
            )
            for master in result.masters
        )
        backend.snapshot = replace(result, masters=masters)
        return backend.snapshot

    backend.apply = bind_new
    widget = mod.AlignmentZonesDialog(backend=backend)
    try:
        widget.add_bottom.click()
        widget.apply_button.click()
        fresh = widget.editor.zones("Regular").bottom[0].origin
        assert fresh == Origin("fresh-bottom-0", b"defaults")
        widget.table.item(1, 2).setText("15")
        widget.apply_button.click()
        assert backend.writes[1][0].after.bottom[0] == Zone(0, 15, "B: 0", fresh)
        assert widget.editor.zones("Regular").top[0].origin == Origin("old", b"keep")
    finally:
        widget.close()


def test_complete_modeless_controls_defaults_order_duplicates_and_no_initial_write(
    panel,
):
    widget, _, backend = panel
    assert not widget.isModal() and widget.master.currentText() == "Regular"
    assert [widget.table.horizontalHeaderItem(i).text() for i in range(4)] == [
        "Zone",
        "Position",
        "Width",
        "Name",
    ]
    assert widget.table.rowCount() == 4 and widget.table.item(3, 0).text() == "Bottom"
    assert widget.table.item(1, 3).text() == widget.table.item(2, 3).text() == ""
    assert widget.apply_button.isDefault() and not widget.apply_button.isEnabled()
    assert widget.close_button.isEnabled() and not backend.writes


def test_switching_masters_retains_all_edits_and_add_defaults(panel):
    widget, _, backend = panel
    widget.add_top.click()
    assert widget.editor.pending() == ("Regular",)
    widget.master.setCurrentIndex(0)
    widget.add_bottom.click()
    assert widget.table.item(0, 1).text() == "0"
    widget.master.setCurrentIndex(1)
    assert widget.editor.pending() == ("Thin", "Regular")
    assert ("Top", 500, 12, "") in widget.editor.rows("Regular")
    assert "unsaved: Thin, Regular" in widget.status.text() and not backend.writes


@pytest.mark.parametrize("value", ["bad", "nan", "inf", ""])
def test_invalid_rows_keep_complete_table_and_stages_block_switch_and_apply(
    panel, value
):
    widget, _, backend = panel
    widget.add_top.click()
    staged = widget.editor
    widget.table.item(0, 1).setText(value)
    assert widget.editor is staged and widget.table.item(0, 1).text() == value
    assert "row 1" in widget.status.text() and not widget.apply_button.isEnabled()
    widget.master.setCurrentIndex(0)
    assert widget.master.currentText() == "Regular" and widget.editor is staged
    widget.apply_button.click()
    assert not backend.writes
    widget.table.item(0, 1).setText("701.5")
    assert (
        widget.editor.rows("Regular")[0][1] == 702 and widget.apply_button.isEnabled()
    )


def test_remove_multiple_selected_rows_and_invalid_row_repairs_without_data_loss(panel):
    widget, _, _ = panel
    widget.table.item(0, 1).setText("bad")
    selection = widget.table.selectionModel()
    for row in (0, 2):
        selection.select(
            widget.table.model().index(row, 0),
            QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows,
        )
    widget.remove_button.click()
    assert widget.table.rowCount() == 2 and widget.editor.pending() == ("Regular",)
    assert widget.editor.rows("Regular") == (
        ("Top", 500, 12, ""),
        ("Bottom", 0, 12, "base"),
    )


def test_suggest_replaces_only_selected_stage_and_apply_sends_one_ordered_batch(panel):
    widget, _, backend = panel
    widget.master.setCurrentIndex(0)
    widget.add_bottom.click()
    widget.master.setCurrentIndex(1)
    widget.suggest_button.click()
    assert backend.bounds_calls == ["Regular"]
    assert widget.editor.rows("Regular") == (
        ("Top", 700, 14, "cap height"),
        ("Top", 500, 14, "x-height"),
        ("Bottom", 0, 15, "baseline"),
    )
    widget.apply_button.click()
    assert len(backend.writes) == 1 and [
        change.master for change in backend.writes[0]
    ] == ["Thin", "Regular"]
    assert widget.editor.pending() == () and widget.last_result == {"masters": 2}
    assert "Wrote the zones of 2 masters" in widget.status.text()
    widget.apply()
    assert len(backend.writes) == 1 and widget.last_result == {"masters": 0}


@pytest.mark.parametrize(
    "action", ["add_top", "remove_button", "suggest_button", "apply_button"]
)
def test_stale_source_disables_all_editing_keeps_stages_and_close_usable(panel, action):
    widget, _, backend = panel
    widget.add_bottom.click()
    staged = widget.editor
    backend.stale = True
    getattr(widget, action).click()
    assert widget.editor is staged and widget._invalid
    assert "changed" in widget.status.text() and not widget.table.isEnabled()
    assert widget.close_button.isEnabled() and not backend.writes


def test_no_font_opening_is_diagnosed_after_close_exists(panel):
    _, mod, backend = panel
    backend.fail_capture = True
    widget = mod.AlignmentZonesDialog(backend=backend)
    assert widget.editor is None and "Open a font" in widget.status.text()
    assert not widget.master.isEnabled() and widget.close_button.isEnabled()
    widget.close()


def test_writer_failure_keeps_stages_disables_actions_and_reports_partial_state(panel):
    widget, _, backend = panel
    widget.add_bottom.click()
    staged = widget.editor
    backend.fail_apply = True
    widget.apply_button.click()
    assert widget.editor is staged and widget._invalid
    assert "partial write" in widget.status.text() and widget.close_button.isEnabled()
    assert len(backend.writes) == 1 and not widget.apply_button.isEnabled()


@pytest.mark.parametrize("route", ["close", "direct", "parent"])
@pytest.mark.filterwarnings("error:libpyside:RuntimeWarning")
def test_every_destruction_route_disconnects_releases_backend_and_fences_saved_slots(
    panel, route, monkeypatch
):
    _, mod, backend = panel
    parent = QtWidgets.QWidget()
    widget = mod.AlignmentZonesDialog(parent, backend=backend)
    monkeypatch.setattr(sys, "_fontlab_samples", {widget.KEY: widget}, raising=False)
    slots = [slot for _, slot in widget._connections]
    if route == "close":
        widget.close_button.click()
    else:
        (parent if route == "parent" else widget).deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert widget._closed and not widget._connections and widget._backend is None
    assert not widget._disconnect_errors and not sys._fontlab_samples
    for slot in slots:
        slot()
    assert not backend.writes
    if isValid(parent):
        parent.deleteLater()


def test_close_during_bounds_does_not_touch_deleted_controls_or_publish_result(panel):
    widget, _, backend = panel
    backend.during_bounds = widget.close
    widget.suggest_button.click()
    assert widget._closed and not backend.writes and widget.editor is None


def test_reentrant_apply_is_fenced_and_close_during_write_is_safe(panel):
    widget, _, backend = panel
    widget.add_bottom.click()
    backend.during_apply = lambda: widget.apply_button.clicked.emit()
    widget.apply_button.click()
    assert len(backend.writes) == 1
    widget.add_top.click()
    backend.during_apply = widget.close
    widget.apply_button.click()
    assert widget._closed and len(backend.writes) == 2


@pytest.mark.parametrize("failure", ["foreign", "master", "order", "metric", "zones"])
def test_invalid_writer_result_never_rebases_or_discards_stages(panel, failure):
    widget, _, backend = panel
    widget.add_bottom.click()
    staged = widget.editor
    apply = backend.apply

    def wrong_result(snapshot, changes):
        result = apply(snapshot, changes)
        if failure == "foreign":
            return replace(result, package_id=999)
        if failure == "master":
            return replace(result, current_master="Thin")
        if failure == "order":
            return replace(result, masters=tuple(reversed(result.masters)))
        if failure == "metric":
            return replace(
                result,
                masters=(replace(result.masters[0], x_height=399), result.masters[1]),
            )
        return replace(result, masters=snapshot.masters)

    backend.apply = wrong_result
    widget.apply_button.click()
    assert widget.editor is staged and widget._invalid and not widget.table.isEnabled()
    assert "differs" in widget.status.text() and widget.close_button.isEnabled()


def test_missing_numeric_cell_preserves_stages_and_is_removable(panel):
    widget, _, _ = panel
    widget.table.insertRow(4)
    staged = widget.editor
    widget.apply_button.clicked.emit()
    assert widget.editor is staged and "row 5" in widget.status.text()
    widget.table.selectRow(4)
    widget.remove_button.click()
    assert widget.editor.pending() == () and widget.table.rowCount() == 4


def test_kind_width_and_name_edits_keep_source_parsing_and_rounding(panel):
    widget, _, _ = panel
    widget.table.item(0, 0).setText("bottom edge")
    widget.table.item(0, 2).setText("-11.5")
    widget.table.item(0, 3).setText("é")
    assert ("Bottom", 700, 12, "é") in widget.editor.rows("Regular")


def test_bounds_source_change_is_refused_before_suggest_replaces_stage(panel):
    widget, _, backend = panel
    widget.add_bottom.click()
    staged = widget.editor
    backend.during_bounds = lambda: setattr(backend, "stale", True)
    widget.suggest_button.click()
    assert widget._invalid and widget.editor is staged and not backend.writes


def test_registry_replacement_and_actual_close_reopen_use_shared_lifecycle(
    panel, monkeypatch
):
    widget, mod, backend = panel
    from fontlabapp.core import scripting
    from fontlabapp.metrics.zones import editor as zone_editor

    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: (
            NS(MainWindow=lambda: None)
            if name == "fontlab"
            else sys.modules["PythonQt"]
        ),
    )
    monkeypatch.setattr(sys, "_fontlab_samples", {widget.KEY: widget}, raising=False)
    callbacks = zone_editor.Backend(
        backend.capture, backend.check, backend.bounds, backend.apply
    )
    second = zone_editor.show(callbacks)
    assert widget._closed and second is sys._fontlab_samples[mod.KEY]
    second.close_button.click()
    assert not sys._fontlab_samples
    third = zone_editor.show(callbacks)
    assert third.editor.pending() == () and third.close_button.isEnabled()
    third.close()


def test_disposal_never_removes_another_registry_owner(panel, monkeypatch):
    widget, _, _ = panel
    other = object()
    monkeypatch.setattr(sys, "_fontlab_samples", {widget.KEY: other}, raising=False)
    widget.close_button.click()
    assert sys._fontlab_samples[widget.KEY] is other


def test_direct_calls_after_close_never_access_deleted_widgets_or_adapter(panel):
    widget, _, backend = panel
    widget.close_button.click()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert widget.store() is False
    widget.choose()
    widget.add("Top")
    widget.remove_selected()
    widget.suggest()
    widget.apply()
    assert not backend.writes and not backend.bounds_calls


def test_failed_disconnect_still_releases_other_slots_and_registry(panel, monkeypatch):
    widget, _, _ = panel

    class Signal:
        def disconnect(self, slot):
            raise RuntimeError("owned disconnect failure")

    widget._connections.append((Signal(), lambda: None))
    monkeypatch.setattr(sys, "_fontlab_samples", {widget.KEY: widget}, raising=False)
    widget.close_button.click()
    assert widget._closed and not widget._connections and not sys._fontlab_samples
    assert (
        len(widget._disconnect_errors) == 1
        and "disconnect failure" in widget._disconnect_errors[0]
    )


def test_invalid_source_repeated_callback_stays_diagnosed_and_never_writes(panel):
    widget, _, backend = panel
    backend.stale = True
    widget.add_top.click()
    widget.add_top.clicked.emit()
    assert "Reopen" in widget.status.text() and widget._invalid and not backend.writes


@pytest.mark.parametrize("stage", ["bounds", "apply"])
def test_error_after_close_is_retained_without_touching_controls(panel, stage):
    widget, _, backend = panel
    widget.add_bottom.click()
    messages = []
    widget.status = NS(setText=messages.append)

    def close_and_fail():
        widget.close()
        messages.clear()
        raise RuntimeError("backend failed after Close")

    setattr(backend, "during_" + stage, close_and_fail)
    (widget.suggest_button if stage == "bounds" else widget.apply_button).click()
    assert widget._closed and not messages
    assert "after Close" in widget.slot_error


@pytest.mark.parametrize("route", ["reject", "accept", "done", "escape"])
def test_dialog_completion_routes_release_and_destroy_owned_panel(
    panel, route, monkeypatch
):
    widget, _, backend = panel
    monkeypatch.setattr(sys, "_fontlab_samples", {widget.KEY: widget}, raising=False)
    if route == "escape":
        from PySide6.QtTest import QTest

        widget.show()
        QTest.keyClick(widget, QtCore.Qt.Key_Escape)
    elif route == "done":
        widget.done(0)
    else:
        getattr(widget, route)()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert widget._closed and widget._backend is None and not widget._connections
    assert not sys._fontlab_samples and not isValid(widget) and not backend.writes


@pytest.mark.parametrize("kind", ["row", "rolled-back"])
def test_apply_when_refused_without_font_change_then_panel_stays_usable(panel, kind):
    widget, _, backend = panel
    row_refusal = importlib.import_module("fontlabapp.metrics.zones.native").RowRefusal
    rolled = importlib.import_module("fontlabapp.core.history.masters").RolledBackError

    def refuse(snapshot, changes):
        if kind == "row":
            raise row_refusal("Zone names repeat in Top of 'Regular'.")
        raise rolled("Alignment Zones", ValueError("FontLab did not store master Regular"))

    widget.add_bottom.click()
    staged = widget.editor
    backend.apply = refuse
    widget.apply_button.click()
    assert not widget._invalid, "a refusal that changed nothing must not lock the panel"
    assert widget.editor is staged, "the staged rows must stay"
    assert widget.table.isEnabled() and widget.apply_button.isEnabled(), "controls must be enabled again"
    expected = "repeat" if kind == "row" else "refused"
    assert expected in widget.status.text(), f"the refusal text must be shown: {widget.status.text()!r}"


@pytest.mark.parametrize("text", ["WINDOW_TEXT", "THREAD_TEXT"])
def test_apply_when_window_or_thread_guard_refuses_then_panel_stays_usable(panel, text):
    widget, _, backend = panel
    message = getattr(importlib.import_module("fontlabapp.core.history.masters"), text)

    def refuse(snapshot, changes):
        raise ValueError(message)  # as require_font_window raises, before any master switch

    widget.add_bottom.click()
    staged = widget.editor
    backend.apply = refuse
    widget.apply_button.click()
    assert not widget._invalid, f"{text}: a guard refusal before any write must not lock the panel"
    assert widget.editor is staged, f"{text}: the staged rows must stay"
    assert widget.table.isEnabled() and widget.apply_button.isEnabled(), f"{text}: controls must be enabled again"
    assert widget.status.text() == message, f"{text}: the refusal text must be shown: {widget.status.text()!r}"


def test_apply_when_writer_result_differs_then_check_result_locks(panel):
    widget, _, backend = panel
    widget.add_bottom.click()
    backend.apply = lambda snapshot, changes: snapshot  # a result without the planned rows
    widget.apply_button.click()
    assert widget._invalid and not widget.table.isEnabled(), "a foreign result (ValueError) must lock the panel"
    assert "differs from the complete plan" in widget.status.text(), f"the result text must be shown: {widget.status.text()!r}"


@pytest.mark.parametrize("kind", ["stale", "unrestored", "not-stored"])
def test_apply_when_font_may_have_changed_then_panel_locks(panel, kind):
    widget, _, backend = panel
    history = importlib.import_module("fontlabapp.core.history.glyphs")
    font_history = importlib.import_module("fontlabapp.core.history.masters")

    def fail(snapshot, changes):
        if kind == "stale":
            raise ValueError("The font, its masters or its zones changed; reopen Alignment Zones.")
        if kind == "unrestored":
            raise font_history.UnrestoredError("Alignment Zones", [OSError("restore")])
        raise history.unstored_error(["zones of master Regular"])

    widget.add_bottom.click()
    backend.apply = fail
    widget.apply_button.click()
    assert widget._invalid and not widget.table.isEnabled(), f"{kind} must lock the panel"
    assert widget.close_button.isEnabled(), "Close must stay usable"
