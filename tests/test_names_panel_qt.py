# this_file: tests/test_names_panel_qt.py
"""Names' real controls, complete publication, guarded selection and owned Close."""

import sys
from types import SimpleNamespace as NS

import pytest
from legacy_panel_qt import (
    QtCore,
    QtGui,
    QtWidgets,
    font_host as font_host,
    legacy_qt as legacy_qt,
)
from shiboken6 import isValid


@pytest.fixture
def names_panel(legacy_qt, font_host):
    mod = legacy_qt.modules["_names_dialog"]
    panel = mod.NamesDialog(None, "Owned Names", "names-test")
    legacy_qt.owned.append(panel)
    font_host.package = NS(id=31, isNull=False)
    return panel, mod, font_host


def test_names_when_built_then_real_table_palette_and_complete_invalidation(
    names_panel,
):
    panel, _mod, _host = names_panel
    panel.table = panel.make_table(["Name", "Status"])
    panel.root.addWidget(panel.table)
    assert panel.windowTitle() == "Owned Names", "Keep the caller title"
    assert panel.table.editTriggers() == QtWidgets.QAbstractItemView.NoEditTriggers
    assert panel.table.selectionBehavior() == QtWidgets.QAbstractItemView.SelectRows
    assert not panel.table.showGrid() and panel.table.alternatingRowColors()
    panel.table.setRowCount(1)
    panel.select_button = QtWidgets.QPushButton("Select", panel)
    panel.copy_button = QtWidgets.QPushButton("Copy", panel)
    panel.missing_list = QtWidgets.QListWidget(panel)
    panel.extra_list = QtWidgets.QListWidget(panel)
    panel.missing_list.addItem("missing")
    panel.extra_list.addItem("extra")
    panel.fields = {"count": QtWidgets.QLabel("42", panel)}
    for name in ("pairs", "selection", "matches", "groups", "missing", "extra"):
        setattr(panel, name, ["partial"])
    panel.current, panel.last_result = {"unsafe": 1}, "partial"
    panel._snapshot_valid, panel._scanned_id = True, 31
    panel.invalidate()
    assert panel.table.rowCount() == 0 and panel.fields["count"].text() == "–"
    assert not panel.select_button.isEnabled() and not panel.copy_button.isEnabled()
    assert panel.missing_list.count() == panel.extra_list.count() == 0
    assert not panel.current and panel.last_result is None and not panel._snapshot_valid
    assert all(
        not getattr(panel, n)
        for n in ("pairs", "selection", "matches", "groups", "missing", "extra")
    )
    palette = panel.palette
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor("#dfcab5"))
    panel.setPalette(palette)
    assert "#96dfcab5" in panel.subtitle.styleSheet(), (
        "Palette changes reach the real subtitle"
    )
    panel.changeEvent(QtCore.QEvent(QtCore.QEvent.FontChange))


@pytest.mark.parametrize("outcome", ["success", "no-font", "changed", "failure"])
def test_names_when_refresh_finishes_then_only_complete_current_results_publish(
    names_panel, outcome
):
    panel, mod, host = names_panel
    if outcome == "no-font":
        host.package = None

    @mod.snapshot_refresh
    def read(owner):
        owner.last_result = "complete"
        if outcome == "changed":
            host.package = NS(id=32, isNull=False)
        if outcome == "failure":
            raise RuntimeError("native getter failed")
        return "detached result"

    if outcome in ("changed", "failure"):
        with pytest.raises((RuntimeError, ValueError), match="failed|Font changed"):
            read(panel)
        assert panel.last_result is None and not panel._snapshot_valid
    else:
        assert read(panel) == "detached result", "Preserve the complete detached return"
        assert panel._snapshot_valid is (outcome == "success")
        assert panel._scanned_id == (31 if outcome == "success" else None)


@pytest.mark.parametrize("fail", [False, True])
def test_names_when_selecting_then_font_window_writer_is_guarded(
    names_panel, monkeypatch, fail
):
    panel, _mod, host = names_panel
    frame = NS(inherits=lambda name: name == "YFrameWindow")
    window = NS(inherits=lambda name: name == "FontWindow", parentWidget=lambda: frame)
    workspace = sys.modules["fontlab"].flWorkspace.instance()
    workspace.activeFontPanel = None if fail else window
    selected = {0}
    glyphs = [NS(name="A"), NS(name="B")]
    monkeypatch.setitem(
        sys.modules,
        "FL",
        NS(
            fl=NS(
                font=glyphs,
                Selected=lambda i: i in selected,
                Unselect=selected.clear,
                Select=selected.add,
            )
        ),
    )
    panel._snapshot_valid, panel._scanned_id = True, 31
    if fail:
        with pytest.raises(ValueError, match="Font window"):
            panel.select_names(["B"])
        assert selected == {0} and not panel._snapshot_valid, (
            "Refuse before selection changes"
        )
    else:
        assert panel.select_names(["B"], add=True) == ["A", "B"]
        assert selected == {0, 1}, "Forward add mode and captured font id"
    host.package = None
    with pytest.raises(ValueError, match="stale"):
        panel.select_names(["A"])


def test_names_when_slot_fails_then_invalidates_and_native_close_stops_owned_timer(
    names_panel, monkeypatch
):
    panel, _mod, _host = names_panel
    panel.status = QtWidgets.QLabel(panel)
    panel.timer = QtCore.QTimer(panel)
    panel.timer.start(1000)
    button = QtWidgets.QPushButton("Read", panel)

    def failure():
        raise RuntimeError("read callback failure")

    panel._connect(button.clicked, lambda *args: failure())
    panel._snapshot_valid, panel._scanned_id = True, 31
    button.click()
    assert not panel._snapshot_valid and "read callback failure" in panel.slot_error
    monkeypatch.setattr(sys, "_fontlab_samples", {"names-test": panel}, raising=False)
    timer, life = panel.timer, panel._completion_lifetime
    panel.reject()
    assert life.closed and not panel._connections and not timer.isActive()
    assert not sys._fontlab_samples, (
        "Native completion removes only this owned registry entry"
    )
    panel.slot_error = ""
    button.click()
    assert panel.slot_error == "", (
        "A live child cannot deliver a disconnected owner callback"
    )
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(panel), "Native-base Close schedules actual Qt deletion"
