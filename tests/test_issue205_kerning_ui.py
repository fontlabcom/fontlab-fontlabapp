# this_file: tests/test_issue205_kerning_ui.py
"""Native kerning snapshots, staged cells, batch history and UI refusal states."""

import importlib
import sys
from types import SimpleNamespace as NS

import pytest
from legacy_panel_qt import QtCore, QtWidgets, legacy_qt as legacy_qt
from test_kerning_batch import font_double


@pytest.fixture
def editor(legacy_qt, monkeypatch):
    package, kerns, history, state = font_double(monkeypatch)
    from fontlabapp.core import scripting

    native = scripting._native("fontlab")
    native.UpdateAll = lambda: None
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: NS(QtCore=QtCore, QtGui=legacy_qt.gui)
        if name == "PythonQt"
        else native,
    )
    monkeypatch.setitem(sys.modules, "fontlab", native)
    names = (
        "fontlabapp.kerning.inspect.ui",
        "fontlabapp.kerning.edit.ui",
        "fontlabapp.kerning.edit.values_ui",
    )
    modules = []
    for name in names:
        parent, _, child = name.rpartition(".")
        monkeypatch.delattr(importlib.import_module(parent), child, raising=False)
        monkeypatch.delitem(sys.modules, name, raising=False)
        modules.append(importlib.import_module(name))
    panel = modules[1].KerningEditDialog(None, "Owned kerning", "owned-kerning")
    legacy_qt.owned.append(panel)
    panel.status = QtWidgets.QLabel()
    panel.table = modules[1].make_table(["Pair", "Master", "Before", "After"])
    panel.apply_button, panel.add_button, panel.revert_button = [
        QtWidgets.QPushButton() for _ in range(3)
    ]
    panel.staged, panel.errors, panel.glyph = {}, {}, "A"
    panel.chosen_masters = lambda: package.masters
    panel.explain = lambda: "Owned scale/removal preview"

    def plan():
        result = {}
        for master, new in (("Light", -20), ("Bold", None)):
            old = kerns[master].values.get(("A", "V"))
            if old != new:
                result[master] = {("A", "V"): (old, new)}
        return result

    panel.plan = plan
    panel.refresh = (
        modules[1].editor_refresh(lambda self: self.refresh_values()).__get__(panel)
    )
    return NS(
        panel=panel,
        modules=modules,
        package=package,
        kerns=kerns,
        history=history,
        state=state,
    )


def test_editors_when_refreshed_then_numeric_rows_stage_and_named_history_match(editor):
    panel, inspect, module, values = editor.panel, *editor.modules
    panel.refresh()
    assert panel._snapshot_valid and panel.table.rowCount() == 2
    assert panel.table.item(0, 3).text() == "-20"
    assert panel.table.item(1, 3).text() == "removed"
    assert panel.apply_button.isEnabled() and panel.add_button.isEnabled()
    assert panel.stage_editor_cell(("A", "V"), "Light", "-11", -10) is None
    assert panel.staged[(("A", "V"), "Light")] == -11
    assert "valid kerning value" in panel.stage_editor_cell(
        ("A", "V"), "Light", "bad", -10
    )
    assert "Unknown glyph" in panel.stage_editor_cell(
        ("absent", "V"), "Light", "1", None
    )
    panel.ensure_edit_snapshot()
    module.editor_apply(lambda self: self.apply_values("Owned adjustment"))(panel)
    assert editor.kerns["Light"].values["A", "V"] == -20
    assert ("A", "V") not in editor.kerns["Bold"].values
    assert len(editor.history) == 2 and editor.history[0] != editor.history[1]
    assert panel.last_result == {"Light": 1, "Bold": 1}
    assert "Changed 2 pairs" in panel.status.text()
    panel.apply_values("Owned no-op")
    assert len(editor.history) == 2 and "Changed 0 pairs" in panel.status.text()


@pytest.mark.parametrize("failure", ["no-font", "master", "pair", "stale"])
def test_refresh_when_sources_change_then_diagnosis_disables_staging_and_write(
    editor, failure
):
    panel, module = editor.panel, editor.modules[1]
    panel.refresh()
    if failure == "no-font":
        panel.package = None
    elif failure == "master":
        editor.package.masters.append("New")
    elif failure == "pair":
        editor.kerns["Light"].values["A", "V"] = -40
        with pytest.raises(ValueError, match="stale"):
            panel.ensure_edit_snapshot()
        return
    else:
        editor.state.package = None
    panel.refresh()
    assert not panel._snapshot_valid and not panel.apply_button.isEnabled()
    assert panel.staged == {} and editor.history == []
    with pytest.raises(ValueError, match="stale"):
        panel.ensure_edit_snapshot()


def test_apply_when_display_fails_then_completed_write_is_not_reported_as_rollback(
    editor,
):
    panel, module = editor.panel, editor.modules[1]
    panel.refresh()

    def failing(self):
        self.write_edits({"Light": {("A", "V"): -25}}, "Owned committed edit")
        raise ValueError("owned display failure")

    with pytest.raises(RuntimeError, match="Kerning was applied"):
        module.editor_apply(failing)(panel)
    assert editor.kerns["Light"].values["A", "V"] == -25 and len(editor.history) == 2
    assert not panel._snapshot_valid and not panel.add_button.isEnabled()
    for completed in (False, True):
        panel._batch_written = completed
        with pytest.raises(RuntimeError, match="preview failed"):
            panel.refresh_after_apply(lambda: None)
    footer = QtWidgets.QHBoxLayout()
    calls = []
    panel.add_refresh(footer, lambda: calls.append("refresh"))
    panel.refresh_button.click()
    assert calls == ["refresh"]


def test_inspection_when_refresh_fails_then_all_selectable_outputs_are_invalidated(
    editor,
):
    panel, inspect = editor.panel, editor.modules[0]
    panel.rows, panel.shown, panel.names = ["A"], ["A"], ["A"]
    panel.copy_button = QtWidgets.QPushButton()
    panel.list, panel.title, panel.members = (
        QtWidgets.QListWidget(),
        QtWidgets.QLabel("old"),
        QtWidgets.QLabel("old"),
    )
    panel.list.addItem("old")
    panel.canvas = NS(update=lambda: None)
    callback = inspect.snapshot_refresh(lambda self: "complete")
    assert callback(panel) == "complete" and panel._snapshot_valid
    editor.state.package = None
    with pytest.raises(ValueError, match="no longer current"):
        callback(panel)
    assert not panel.copy_button.isEnabled() and panel.list.count() == 0
    assert panel.title.text() == panel.members.text() == ""
    editor.state.package = editor.package
    panel.package = None
    assert callback(panel) == "complete" and not panel._snapshot_valid
