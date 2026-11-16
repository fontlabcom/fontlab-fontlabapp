# this_file: tests/test_demo_scripts_widgets_gallery.py
"""Offline runs of the Widget Gallery demo over a fake PythonQt (Issue 208).

Each tab builder runs against the real ``fontlabapp.qt`` helper it demonstrates;
only the Qt classes (``tests/_widget_qt.py``) and the ``PythonQt``/``fontlab``
natives are replaced. Tests drive the controls through their signals and read
the results from the fake widgets. One test runs the whole window through
``main`` and its release. Offline results are not native FontLab acceptance.
"""

from types import SimpleNamespace

import pytest
from _demo_support import Recorder, run_script, script_path, stub_module
from _widget_qt import Completer, Label, make_qt

from fontlabapp.core.signals.scope import Scope

GALLERY = script_path("Widgets", "Widget Gallery Demo")
TITLES = [
    "Sliders", "Spin box", "Choices", "Colors", "Dialogs", "Calendar (classic)",
    "Calendar (official)", "Completion", "Regexp", "Trees", "Painting", "Events",
]


def host(monkeypatch):
    """Install the fake PythonQt and fontlab natives; return the fake Qt."""
    qt = make_qt()
    stub_module(monkeypatch, "PythonQt", QtGui=qt.QtGui, QtCore=qt.QtCore)
    stub_module(monkeypatch, "fontlab", MainWindow=lambda: "main-window")
    return qt


def tab(monkeypatch, builder):
    """Run one tab builder in a fresh Demo; return (qt, demo, page, layout)."""
    qt = host(monkeypatch)
    qt.labels = tracked(qt, "QLabel", Label)
    names = run_script(GALLERY, "imported")
    demo = names["Demo"](qt, Scope)
    demo.status = qt.QtGui.QLabel()
    page, layout = qt.QtGui.QWidget(), qt.QtGui.QVBoxLayout()
    names[builder](demo, page, layout)
    return qt, demo, page, layout


def added(layout) -> list:
    """The widgets a builder put in its layout, in order."""
    return [call[0][0] for call in layout.addWidget.calls]


def tracked(qt, name, base=None):
    """Replace ``QtGui.<name>`` by a subclass that records every instance."""
    made, parent = [], base or getattr(qt.QtGui, name)

    class Tracked(parent):
        def __init__(self, *args) -> None:
            super().__init__(*args)
            made.append(self)

    setattr(qt.QtGui, name, Tracked)
    return made


# --- Sliders ---------------------------------------------------------------------


def test_sliders_when_built_then_three_controls_and_a_bar_start_at_five(monkeypatch) -> None:
    qt, demo, page, layout = tab(monkeypatch, "tab_sliders")
    slider, scroll, dial, bar, label = added(layout)
    assert [control.limits for control in (slider, scroll, dial)] == [(0, 20)] * 3
    assert [control.number for control in (slider, scroll, dial)] == [5, 5, 5]
    assert bar.limits == (0, 1_000_000) and bar.number == 250_000
    assert label.shown == "Value 5 of 0..20 is step 250000 of 1000000"
    assert page.scope is demo.scope, "profiles.group connects through the page's scope"


def test_sliders_when_one_control_moves_then_the_others_and_the_bar_follow(monkeypatch) -> None:
    qt, demo, page, layout = tab(monkeypatch, "tab_sliders")
    slider, scroll, dial, bar, label = added(layout)
    scroll.setValue(12)
    assert (slider.number, dial.number) == (12, 12), "the scroll bar feeds the dial, which feeds the slider"
    assert bar.number == 600_000 and label.shown.startswith("Value 12 of 0..20")
    demo.release()
    scroll.setValue(3)
    assert label.shown.startswith("Value 12"), "a released demo no longer reacts"
    assert demo.scope.records == [] and demo.problems == []


# --- Spin box --------------------------------------------------------------------


def spin_parts(monkeypatch):
    qt, demo, page, layout = tab(monkeypatch, "tab_spinbox")
    view, label = added(layout)
    model = view.setModel.calls[0][0][0]
    delegate = view.setItemDelegate.calls[0][0][0]
    return qt, demo, model, delegate, label


def test_spinbox_when_built_then_the_table_holds_integers_in_a_four_by_two_grid(monkeypatch) -> None:
    qt, demo, model, delegate, label = spin_parts(monkeypatch)
    assert model.cells == {(r, c): 10 * (r + 1) + c for r in range(4) for c in range(2)}
    assert all(type(number) is int for number in model.cells.values()), "the delegate refuses non-integers"
    assert delegate.model is model and delegate.official is False and delegate.active
    assert label.shown == "Double-click a cell and enter a number from 0 to 100."


def test_spinbox_when_a_cell_edit_commits_then_the_model_and_counter_change(monkeypatch) -> None:
    qt, demo, model, delegate, label = spin_parts(monkeypatch)
    index = model.index(1, 1)
    editor = delegate.createEditor(None, None, index)
    delegate.setEditorData(editor, index)
    assert editor.number == 21, "the editor starts with the cell value"
    editor.setValue(77)
    delegate.setModelData(editor, model, index)
    assert model.cells[(1, 1)] == 77 and label.shown == "Cell edits committed: 1"
    assert demo.problems == [] and delegate.commits == 1


def test_spinbox_when_the_editor_is_given_a_value_above_the_range_then_it_holds_the_maximum(monkeypatch) -> None:
    qt, demo, model, delegate, label = spin_parts(monkeypatch)
    editor = delegate.createEditor(None, None, model.index(0, 0))
    editor.setValue(150)
    assert editor.number == 100, "a QSpinBox clamps to the range the delegate set"


def test_spinbox_when_qt_refuses_the_cell_commit_then_the_demo_shows_the_failure(monkeypatch) -> None:
    qt, demo, model, delegate, label = spin_parts(monkeypatch)
    index = model.index(0, 0)
    editor = delegate.createEditor(None, None, index)
    editor.setValue(42)
    model.setData = Recorder(False)
    delegate.setModelData(editor, model, index)
    assert model.cells[(0, 0)] == 10 and label.shown.startswith("Double-click")
    assert demo.status.shown == "Callback error: Qt refused the worksheet cell commit."
    assert [str(error) for error in demo.problems] == [delegate.error]


def test_spinbox_when_released_then_open_editors_are_cancelled_and_the_delegate_stops(monkeypatch) -> None:
    qt, demo, model, delegate, label = spin_parts(monkeypatch)
    index = model.index(2, 0)
    editor = delegate.createEditor(None, None, index)
    assert delegate.active_editor() is editor
    demo.release()
    assert delegate.active_editor() is None and delegate.active is False
    assert delegate.scope.closed and demo.problems == []


# --- Choices ---------------------------------------------------------------------


def choices_parts(monkeypatch):
    qt, demo, page, layout = tab(monkeypatch, "tab_choices")
    return (qt, demo, *added(layout))


def test_choices_when_built_then_the_combo_is_editable_and_never_inserts(monkeypatch) -> None:
    qt, demo, combo, report, set_text, line, set_nul, shown = choices_parts(monkeypatch)
    assert combo.items == ["Regular", "Italic", "Bold"]
    assert combo.setEditable.calls == [((True,), {})]
    assert combo.setInsertPolicy.calls == [((qt.QtGui.QComboBox.NoInsert,), {})]


def test_choices_when_activated_then_only_the_index_overload_reports(monkeypatch) -> None:
    qt, demo, combo, report, set_text, line, set_nul, shown = choices_parts(monkeypatch)
    combo.line.text_value, combo.line.modified = "Bold", True
    combo.activated.emit("Bold")
    assert report.shown.startswith("Pick a choice"), "the QString overload is ignored"
    assert combo.line.modified is True
    combo.activated.emit(2)
    assert report.shown == "Activated: Bold" and combo.line.modified is False, "activation acknowledges the edit"


def test_choices_when_the_edit_finishes_then_it_commits_once(monkeypatch) -> None:
    qt, demo, combo, report, set_text, line, set_nul, shown = choices_parts(monkeypatch)
    combo.line.text_value, combo.line.modified = "Light", True
    combo.line.editingFinished.emit()
    assert report.shown == "Committed: Light"
    report.setText("marker")
    combo.line.editingFinished.emit()
    assert report.shown == "marker", "a repeated Return with no new edit stays silent"


def test_choices_when_text_is_set_by_the_program_then_it_is_not_a_user_commit(monkeypatch) -> None:
    qt, demo, combo, report, set_text, line, set_nul, shown = choices_parts(monkeypatch)
    set_text.clicked.emit()
    assert combo.currentText == "Condensed" and combo.line.modified is False
    report.setText("marker")
    combo.line.editingFinished.emit()
    assert report.shown == "marker"


def test_choices_when_a_nul_is_put_in_the_line_then_the_literal_text_keeps_it(monkeypatch) -> None:
    qt, demo, combo, report, set_text, line, set_nul, shown = choices_parts(monkeypatch)
    set_nul.clicked.emit()
    assert line.text_value == "a\0b"
    assert shown.shown == "Line text is 'a\\x00b'"
    assert demo.problems == []


# --- Colors ----------------------------------------------------------------------


def color_parts(monkeypatch):
    qt, demo, page, layout = tab(monkeypatch, "tab_colors")
    picker, box, swatch = added(layout)
    (label,) = [item for item in qt.labels if item.shown == "Text color follows the preset"]
    return qt, demo, picker, box, swatch, label


def test_colors_when_built_then_every_styled_part_uses_the_first_preset(monkeypatch) -> None:
    qt, demo, picker, box, swatch, label = color_parts(monkeypatch)
    assert picker.items == ["Amber", "Teal", "Plum"]
    assert box.setStyleSheet.calls[-1][0][0] == (
        "QGroupBox { background-color: rgba(242, 191, 76, 255); border: 2px solid black; border-radius: 6px; }"
    )
    assert swatch.setStyleSheet.calls[-1][0][0] == "background-color: rgba(242, 191, 76, 255);"
    role, color = label.palette.setColor.calls[-1][0]
    assert role == qt.QtGui.QPalette.WindowText and color.args == (242, 191, 76, 255)
    assert label.setPalette.calls[-1][0][0] is label.palette


def test_colors_when_another_preset_is_chosen_then_every_styled_part_follows(monkeypatch) -> None:
    qt, demo, picker, box, swatch, label = color_parts(monkeypatch)
    picker.setCurrentIndex(1)
    picker.currentIndexChanged.emit(1)
    assert "background-color: rgba(51, 166, 166, 255)" in box.setStyleSheet.calls[-1][0][0]
    assert swatch.setStyleSheet.calls[-1][0][0] == "background-color: rgba(51, 166, 166, 255);"
    assert label.palette.setColor.calls[-1][0][1].args == (51, 166, 166, 255) and demo.problems == []


def test_colors_when_released_then_choosing_a_preset_changes_nothing(monkeypatch) -> None:
    qt, demo, picker, box, swatch, label = color_parts(monkeypatch)
    styled = len(box.setStyleSheet.calls)
    demo.release()
    picker.currentIndexChanged.emit(2)
    assert len(box.setStyleSheet.calls) == styled and demo.problems == []


# --- Dialogs ---------------------------------------------------------------------


def test_dialogs_when_the_button_is_clicked_then_a_modeless_owned_box_shows(monkeypatch) -> None:
    qt, demo, page, layout = tab(monkeypatch, "tab_dialogs")
    button, note = added(layout)
    assert note.shown == "dialogs.name_filters(['png', 'jpg']) = ['Files (*.png *.jpg)']"
    button.clicked.emit()
    (box,) = demo.boxes
    assert box.args == (page,) and box.setText.calls == [(("Owned message box",), {})]
    assert box.setIcon.calls == [((qt.QtGui.QMessageBox.Information,), {})]
    assert box.setWindowTitle.calls == [(("Dialogs",), {})]
    assert box.setModal.calls == [((False,), {})] and box.show.calls == [((), {})]


def test_dialogs_when_clicked_twice_then_the_closed_box_is_released_first(monkeypatch) -> None:
    qt, demo, page, layout = tab(monkeypatch, "tab_dialogs")
    button, note = added(layout)
    button.clicked.emit()
    first = demo.boxes[0]
    assert first.isVisible()
    first.close()
    button.clicked.emit()
    assert first.deleteLater.calls == [((), {})] and len(demo.boxes) == 1 and demo.boxes[0] is not first


def test_dialogs_when_clicked_twice_with_the_first_box_open_then_both_are_kept(monkeypatch) -> None:
    qt, demo, page, layout = tab(monkeypatch, "tab_dialogs")
    button, note = added(layout)
    button.clicked.emit()
    button.clicked.emit()
    first, second = demo.boxes
    assert first is not second and first.deleteLater.calls == [] and second.isVisible()


def test_dialogs_when_released_then_every_box_is_closed_and_deleted(monkeypatch) -> None:
    qt, demo, page, layout = tab(monkeypatch, "tab_dialogs")
    button, note = added(layout)
    button.clicked.emit()
    (box,) = demo.boxes
    demo.release()
    assert box.close.calls == [((), {})] and box.deleteLater.calls == [((), {})] and demo.boxes == []


# --- Calendars -------------------------------------------------------------------


@pytest.mark.parametrize("builder", ["tab_calendar_classic", "tab_calendar_official"])
def test_calendars_when_built_then_the_controls_widget_is_hosted_and_closed_on_release(monkeypatch, builder) -> None:
    qt, demo, page, layout = tab(monkeypatch, builder)
    controls = demo.closers[-1].__self__
    assert added(layout) == [controls.widget] and controls.widget.args == (page,)
    assert controls.calendar.args == (controls.widget,)
    assert set(controls.dates) == {"selected", "minimum", "maximum"}
    demo.release()
    assert controls._closed and demo.problems == [] and demo.scope.records == []


def test_calendars_when_classic_locale_changes_then_the_calendar_gets_that_locale(monkeypatch) -> None:
    qt, demo, page, layout = tab(monkeypatch, "tab_calendar_classic")
    controls = demo.closers[-1].__self__
    assert controls.combos["locale"].items == ["en_US", "pl_PL", "de_DE"]
    controls.combos["locale"].currentIndexChanged.emit(1)
    assert controls.calendar.setLocale.calls[-1][0][0].language == "pl_PL"


def test_calendars_when_classic_special_dates_are_switched_on_then_first_friday_and_new_year_mark(monkeypatch) -> None:
    qt, demo, page, layout = tab(monkeypatch, "tab_calendar_classic")
    controls = demo.closers[-1].__self__
    controls.checks["special"].setChecked(True)
    controls.checks["special"].toggled.emit(True)
    assert [date.args for date in controls._marked] == [(2026, 5, 1), (2026, 1, 1)]
    controls.checks["special"].setChecked(False)
    controls.checks["special"].toggled.emit(False)
    assert controls._marked == (), "turning the switch off clears the owned marks"


def test_calendars_when_official_locale_changes_then_the_calendar_gets_that_locale(monkeypatch) -> None:
    qt, demo, page, layout = tab(monkeypatch, "tab_calendar_official")
    controls = demo.closers[-1].__self__
    assert controls.combos["locale"].items == ["English/United States", "Polish/Poland"]
    controls.combos["locale"].currentIndexChanged.emit(1)
    assert controls.calendar.setLocale.calls[-1][0][0] is controls.locales[1]
    assert controls.combos["locale"].setToolTip.calls[-1] == (("Polish/Poland",), {})


def test_calendars_when_official_holiday_is_switched_on_then_may_first_is_marked(monkeypatch) -> None:
    qt, demo, page, layout = tab(monkeypatch, "tab_calendar_official")
    controls = demo.closers[-1].__self__
    controls.checks["holiday"].setChecked(True)
    controls.checks["holiday"].toggled.emit(True)
    assert [date.args for date in controls._marked] == [(2026, 5, 1)]


# --- Completion ------------------------------------------------------------------


def completion_parts(monkeypatch):
    qt, demo, page, layout = tab(monkeypatch, "tab_completion")
    hint, widget = added(layout)
    return qt, demo, hint, widget, demo.closers[-1].__self__


def test_completion_when_built_then_the_editor_completes_the_demo_words(monkeypatch) -> None:
    qt, demo, hint, widget, editor = completion_parts(monkeypatch)
    assert widget is editor.widget and "anc" in hint.shown
    completer = editor.completer
    assert completer.connect.calls == [(("activated(QString)", editor.insert), {})]
    proxy = completer.setModel.calls[0][0][0]
    assert proxy.setSourceModel.calls[0][0][0].args[0] == list(run_script(GALLERY, "imported")["WORDS"])


def test_completion_when_released_then_the_activation_is_disconnected_once(monkeypatch) -> None:
    qt, demo, hint, widget, editor = completion_parts(monkeypatch)
    completer = editor.completer
    demo.release()
    assert completer.disconnect.calls == [(("activated(QString)", editor.insert), {})]
    assert editor.completer is None and demo.problems == []


def test_completion_when_qt_refuses_the_disconnect_then_release_reports_and_runs_the_other_closers(monkeypatch) -> None:
    qt, demo, hint, widget, editor = completion_parts(monkeypatch)
    editor.completer.disconnect = Recorder(False)
    ran = []
    demo.closers.insert(0, lambda: ran.append("earlier closer"))
    demo.release()
    assert ran == ["earlier closer"], "closers after the failing one still run"
    assert [str(error) for error in demo.problems][0] == "Qt refused the completion disconnection."
    assert str(demo.problems[-1]).startswith("Qt refused part of the release"), "the refusal keeps the demo"


def test_completion_when_qt_refuses_the_connection_then_the_tab_fails_before_hosting_the_editor(monkeypatch) -> None:
    class Refusing(Completer):
        def __init__(self, *args) -> None:
            super().__init__(*args)
            self.connect = Recorder(False)

    qt = host(monkeypatch)
    qt.QtGui.QCompleter = Refusing
    names = run_script(GALLERY, "imported")
    demo = names["Demo"](qt, Scope)
    layout = qt.QtGui.QVBoxLayout()
    with pytest.raises(RuntimeError, match="Qt refused the completion connection"):
        names["tab_completion"](demo, qt.QtGui.QWidget(), layout)
    assert layout.addWidget.calls == [] and demo.closers == []


def test_demo_when_a_callback_fails_before_the_window_has_a_status_line_then_the_error_is_kept(monkeypatch) -> None:
    qt = host(monkeypatch)
    demo = run_script(GALLERY, "imported")["Demo"](qt, Scope)
    error = ValueError("early")
    demo.fail(error)
    assert demo.problems == [error] and demo.status is None


# --- Regexp ----------------------------------------------------------------------


def test_regexp_when_built_then_the_start_pattern_matches_the_start_text(monkeypatch) -> None:
    qt, demo, page, layout = tab(monkeypatch, "tab_regexp")
    _, pattern, _, text, result = added(layout)
    assert (pattern.text_value, text.text_value) == (r"(s\w+)", "small stones")
    assert result.shown == "Match at 0, length 5, captures ['small', 'small']"


def test_regexp_when_the_text_or_pattern_changes_then_the_result_updates(monkeypatch) -> None:
    qt, demo, page, layout = tab(monkeypatch, "tab_regexp")
    _, pattern, _, text, result = added(layout)
    text.setText("no match here")
    assert result.shown == "Match at -1, length -1, captures []"
    pattern.setText("(")
    assert result.shown.startswith("Invalid pattern: ")
    pattern.setText("h(e)re")
    assert result.shown == "Match at 9, length 4, captures ['here', 'e']"


def test_regexp_when_released_then_typing_no_longer_updates_the_result(monkeypatch) -> None:
    qt, demo, page, layout = tab(monkeypatch, "tab_regexp")
    _, pattern, _, text, result = added(layout)
    demo.release()
    text.setText("stones")
    assert result.shown == "Match at 0, length 5, captures ['small', 'small']" and demo.problems == []


# --- Trees -----------------------------------------------------------------------


class TreeIndex:
    """An index of the editable tree model: owner, node identity, row and column."""

    def __init__(self, model, identity: int, row: int, column: int) -> None:
        self.model_, self.identity, self.row_, self.column_ = model, identity, row, column

    def isValid(self) -> bool:
        return True

    def model(self):
        return self.model_

    def internalId(self) -> int:
        return self.identity

    def row(self) -> int:
        return self.row_

    def column(self) -> int:
        return self.column_


def tree_parts(monkeypatch):
    qt, demo, page, layout = tab(monkeypatch, "tab_trees")
    read_view, edit_view, label = added(layout)
    return qt, demo, label, read_view, edit_view, read_view.setModel.calls[0][0][0], edit_view.setModel.calls[0][0][0]


def test_trees_when_built_then_both_views_show_the_same_two_top_level_rows(monkeypatch) -> None:
    qt, demo, label, read_view, edit_view, read_model, edit_model = tree_parts(monkeypatch)
    assert type(read_model).__name__ == "TreeModel" and type(edit_model).__name__ == "EditableModel"
    assert [(m.rowCount(), m.columnCount()) for m in (read_model, edit_model)] == [(2, 2), (2, 2)]
    assert read_view.expandAll.calls == edit_view.expandAll.calls == [((), {})]
    assert edit_model.edited is False and "editable local draft" in label.shown


def test_trees_when_a_draft_cell_is_edited_then_the_label_reports_it(monkeypatch) -> None:
    qt, demo, label, read_view, edit_view, read_model, edit_model = tree_parts(monkeypatch)
    cell = TreeIndex(edit_model, identity=1, row=0, column=0)
    assert edit_model.setData(cell, "Latin letters", qt.QtCore.Qt.EditRole) is True
    assert edit_model.data(cell, qt.QtCore.Qt.DisplayRole) == "Latin letters" and edit_model.error == ""
    assert label.shown == "Draft edited: True"
    assert read_model.rowCount() == 2 and read_model.data(TreeIndex(read_model, 1, 0, 0), qt.QtCore.Qt.DisplayRole) == "Latin"


def test_trees_when_released_then_both_views_detach_and_both_models_go_inert(monkeypatch) -> None:
    qt, demo, label, read_view, edit_view, read_model, edit_model = tree_parts(monkeypatch)
    demo.release()
    assert read_view.setModel.calls[-1] == ((None,), {}) and edit_view.setModel.calls[-1] == ((None,), {})
    assert read_model._active is False and edit_model._active is False
    assert read_model.rowCount() == 0 and edit_model.rowCount() == 0, "an inert model answers empty"


# --- Painting --------------------------------------------------------------------


def test_painting_when_the_overlay_paints_then_it_draws_the_two_shapes(monkeypatch) -> None:
    qt, demo, page, layout = tab(monkeypatch, "tab_painting")
    drawing = demo.closers[-1].__self__
    label, frame = added(layout)
    assert drawing.widget.args == (frame,) and "painting.drawing.Drawing" in label.shown
    drawing.widget.paintEvent(None)
    (painter,) = qt.painters
    assert [call[0] for call in painter.drawEllipse.calls] == [(10, 10, 80, 80)]
    assert [call[0] for call in painter.drawRect.calls] == [(100, 40, 80, 50)]
    assert painter.end.calls == [((), {})] and drawing.paint_count == 1 and drawing.last_error is None


def test_painting_when_released_then_the_timer_stops_and_the_overlay_is_deleted(monkeypatch) -> None:
    qt, demo, page, layout = tab(monkeypatch, "tab_painting")
    drawing = demo.closers[-1].__self__
    timer, overlay = drawing._timer, drawing.widget
    demo.release()
    assert drawing.closed and timer.stop.calls == [((), {})] and overlay.deleteLater.calls == [((), {})]
    overlay.paintEvent(None)
    assert qt.painters == [], "a closed drawing paints nothing"


# --- Events ----------------------------------------------------------------------


def event_parts(monkeypatch):
    qt = host(monkeypatch)
    labels = tracked(qt, "QLabel", Label)
    names = run_script(GALLERY, "imported")
    demo = names["Demo"](qt, Scope)
    layout = qt.QtGui.QVBoxLayout()
    names["tab_events"](demo, qt.QtGui.QWidget(), layout)
    keys, field, sizes, panel = added(layout)
    chips = [label for label in labels if label.shown in ("one", "two", "three")]
    return qt, demo, keys, field, sizes, panel, chips


def key_event(code, accept=None):
    return SimpleNamespace(key=lambda: code, accept=accept or Recorder())


def test_events_when_an_ordinary_key_is_pressed_then_the_field_handles_it(monkeypatch) -> None:
    qt, demo, keys, field, sizes, panel, chips = event_parts(monkeypatch)
    event = key_event(65)
    field.keyPressEvent(event)
    assert field.base_keys == [event] and event.accept.calls == []
    assert keys.shown == "Key code 65: passed to the field"


def test_events_when_escape_is_pressed_then_the_demo_clears_the_field_and_accepts(monkeypatch) -> None:
    qt, demo, keys, field, sizes, panel, chips = event_parts(monkeypatch)
    field.setText("draft")
    event = key_event(qt.QtCore.Qt.Key_Escape)
    field.keyPressEvent(event)
    assert field.text_value == "" and field.base_keys == [] and event.accept.calls == [((), {})]
    assert keys.shown == f"Key code {qt.QtCore.Qt.Key_Escape}: Escape cleared the field"


def resize_event(width, height):
    return SimpleNamespace(size=lambda: SimpleNamespace(width=lambda: width, height=lambda: height))


def test_events_when_the_panel_resizes_then_the_strip_fits_and_the_chips_share_the_width(monkeypatch) -> None:
    qt, demo, keys, field, sizes, panel, chips = event_parts(monkeypatch)
    event = resize_event(320, 90)
    panel.resizeEvent(event)
    assert panel.base_resizes == [event], "the native resize handler still runs"
    strip = chips[0].args[1]
    assert strip.setGeometry.calls == [((0, 0, 300, 80), {})]
    assert [chip.setGeometry.calls[0][0] for chip in chips] == [(0, 0, 97, 24), (101, 0, 97, 24), (203, 0, 97, 24)]
    assert sizes.shown == "Panel 320 x 90; content fitted to 300 x 80"


def test_events_when_released_then_a_late_resize_changes_nothing(monkeypatch) -> None:
    qt, demo, keys, field, sizes, panel, chips = event_parts(monkeypatch)
    demo.release()
    event = resize_event(500, 500)
    panel.resizeEvent(event)
    assert panel.base_resizes == [event] and sizes.shown == "" and chips[0].setGeometry.calls == []


# --- The whole window --------------------------------------------------------------


def test_gallery_when_main_then_one_owned_dialog_holds_every_tab(monkeypatch) -> None:
    qt = host(monkeypatch)
    tabs = tracked(qt, "QTabWidget")
    names = run_script(GALLERY)
    (demo,) = names["_HANDLES"]
    dialog = demo.owned.widget
    assert dialog.args == ("main-window",) and dialog.setWindowTitle.calls == [(("Widget Gallery Demo",), {})]
    assert dialog.setModal.calls == [((False,), {})] and dialog.show.calls == [((), {})]
    assert dialog.resize.calls == [((780, 600), {})]
    (tab_widget,) = tabs
    assert [call[0][1] for call in tab_widget.addTab.calls] == TITLES
    assert [title for title, _ in names["TABS"]] == TITLES
    assert demo.problems == [] and demo.status.shown.startswith("Each tab uses")


def test_gallery_when_the_window_finishes_then_everything_is_released_after_dispatch(monkeypatch) -> None:
    qt = host(monkeypatch)
    names = run_script(GALLERY)
    (demo,) = names["_HANDLES"]
    dialog = demo.owned.widget
    assert len(demo.closers) == 8, "eight tabs own something that needs releasing"
    dialog.finished.emit(0)
    assert [delay for delay, _ in qt.shots] == [0] and names["_HANDLES"] == [demo], "release waits for dispatch"
    qt.shots[0][1]()
    assert names["_HANDLES"] == [] and demo.owned.closed and demo.scope.closed
    assert demo.scope.records == [] and demo.closers == [] and demo.problems == []
    demo.release()  # a second release is harmless
    assert demo.problems == []


def test_gallery_when_qt_refuses_a_disconnect_then_the_window_and_demo_are_kept_until_it_succeeds(monkeypatch) -> None:
    qt = host(monkeypatch)
    names = run_script(GALLERY)
    (demo,) = names["_HANDLES"]
    signal = qt.QtGui.QWidget().valueChanged
    demo.scope.connect(signal, lambda: None)
    signal.disconnect = Recorder(False)
    demo.release()
    assert names["_HANDLES"] == [demo] and not demo.owned.closed and len(demo.closers) == 8
    assert [str(error) for error in demo.problems] == [
        "Qt refused the owned signal disconnection.",
        "Qt refused part of the release; the window is kept open.",
    ]
    assert demo.status.shown.startswith("Callback error: Qt refused part")
    signal.disconnect = Recorder()
    demo.release()
    assert names["_HANDLES"] == [] and demo.owned.closed and demo.closers == []


def test_gallery_when_a_closer_reports_failure_then_the_window_and_demo_are_kept(monkeypatch) -> None:
    qt = host(monkeypatch)
    names = run_script(GALLERY)
    (demo,) = names["_HANDLES"]
    demo.closers.append(lambda: False)
    demo.release()
    assert names["_HANDLES"] == [demo] and not demo.owned.closed


def test_gallery_when_a_closer_raises_anything_then_the_others_run_and_the_demo_is_kept(monkeypatch) -> None:
    qt = host(monkeypatch)
    names = run_script(GALLERY)
    (demo,) = names["_HANDLES"]
    ran = []

    def destroyed_wrapper() -> None:
        raise ValueError("wrapped C++ object has been deleted")

    demo.closers[:] = [lambda: ran.append("first"), destroyed_wrapper, lambda: ran.append("last")]
    demo.release()
    assert ran == ["last", "first"] and names["_HANDLES"] == [demo]
    assert str(demo.problems[0]) == "wrapped C++ object has been deleted"


def test_gallery_when_the_window_close_is_refused_or_raises_then_the_demo_is_kept(monkeypatch) -> None:
    qt = host(monkeypatch)
    names = run_script(GALLERY)
    (demo,) = names["_HANDLES"]
    demo.owned.close = lambda: False
    demo.release()
    assert names["_HANDLES"] == [demo]

    def refuse() -> bool:
        raise RuntimeError("Owned widget callback disconnect refused")

    demo.owned.close = refuse
    demo.release()
    assert names["_HANDLES"] == [demo]
    assert "Owned widget callback disconnect refused" in [str(error) for error in demo.problems]


@pytest.mark.parametrize("failing", ["QTabWidget", "QCompleter"])
def test_gallery_when_a_widget_cannot_be_created_then_the_demo_releases_and_reraises(monkeypatch, failing) -> None:
    qt = host(monkeypatch)

    def broken(*args):
        raise RuntimeError("no " + failing)

    setattr(qt.QtGui, failing, broken)
    names = run_script(GALLERY, "imported")
    with pytest.raises(RuntimeError, match="no " + failing):
        names["main"]()
    assert names["_HANDLES"] == [], "a failed build leaves no retained demo"


def test_gallery_when_imported_then_nothing_runs(monkeypatch) -> None:
    qt = host(monkeypatch)
    names = run_script(GALLERY, "imported")
    assert names["_HANDLES"] == [] and qt.shots == [] and callable(names["main"])
