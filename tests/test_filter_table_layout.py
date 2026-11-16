# this_file: tests/test_filter_table_layout.py
"""Measure complete table contents and compact controls in real offscreen Qt."""
import pytest
import test_filter_table_dialog as ui
from fontlabapp.qt.tables.filter.model import Table

panel = ui.panel
ROWS = (
    ("A", "Latin capital A <U+0041>", "2026-01-05 09:30:00"),
    ("B", "Latin capital B <U+0042>", "2026-01-12 14:05:00"),
    ("a", "Latin small a <U+0061>", "2026-02-02 11:00:00"),
    ("Aacute", "Latin capital A acute <U+00C1>", "2026-02-20 16:45:00"),
    ("alpha", "Greek small alpha <U+03B1>", "2026-03-08 08:10:00"),
    ("Alpha", "Greek capital alpha <U+0391>", "2026-03-09 10:20:00"),
    ("zero", "Digit zero <U+0030>", "2026-04-01 13:15:00"),
    ("space", "Space <U+0020>", "2026-04-15 17:55:00"),
)


@pytest.fixture(params=[None, 13.0], ids=["default-font", "13pt-font"])
def app_font(request):
    before = ui.APP.font()
    if request.param is not None:
        font = ui.QtGui.QFont(before)
        font.setPointSizeF(request.param)
        ui.APP.setFont(font)
    yield
    ui.APP.setFont(before)


@pytest.fixture(params=[False, True], ids=["text-dates", "typed-dates"])
def layout_panel(panel, request, app_font):
    base, _state, custom = panel
    state = {"rows": ROWS}
    w = base.__class__(
        None, "Table Filter Demo", "owned_compact_table",
        lambda: Table(("Glyph", "Description", "Modified"), state["rows"]),
        custom, "Sample rows only. Filter the top table into the bottom one.",
        official=request.param,
    )
    w.show()
    ui.APP.processEvents()
    yield w, state, custom, request.param
    if ui.valid(w):
        w.close()
    ui.QtCore.QCoreApplication.sendPostedEvents(None, ui.QtCore.QEvent.DeferredDelete)


def test_table_when_shown_at_preferred_size_then_all_eight_rows_and_text_fit(layout_panel):
    w, _state, _custom, _official = layout_panel
    assert w.font().pointSizeF() == ui.APP.font().pointSizeF()
    for view in (w.source_view, w.proxy_view):
        assert view.model().rowCount() == 8
        for row in range(8):
            rectangle = view.visualRect(view.model().index(row, 0))
            assert rectangle.top() >= 0 and rectangle.bottom() < view.viewport().height()
        for column in range(3):
            rendered = [
                view.itemDelegate().displayText(
                    view.model().data(view.model().index(row, column)), view.locale()
                )
                for row in range(8)
            ]
            text_width = max(view.fontMetrics().horizontalAdvance(text) for text in rendered)
            option = ui.QtWidgets.QStyleOptionViewItem()
            option.initFrom(view)
            option.locale = view.locale()
            delegate_width = max(
                view.itemDelegate().sizeHint(option, view.model().index(row, column)).width()
                for row in range(8)
            )
            assert view.columnWidth(column) >= max(text_width, delegate_width), (column, rendered)
            if column == 2:
                assert view.columnWidth(column) <= text_width + 32, "dates must not consume description space"
        assert view.columnWidth(1) > view.columnWidth(2)
        assert view.horizontalScrollBar().maximum() == 0
    assert w.width() * w.height() < 720 * 680


def center_y(w, control):
    return control.mapTo(w, control.rect().center()).y()


def test_controls_when_compact_then_related_fields_share_rows_and_remain_accessible(layout_panel):
    w, _state, custom, official = layout_panel
    assert abs(center_y(w, w.pattern) - center_y(w, w.syntax)) <= 4
    if not w.sort_case.isHidden():
        assert abs(center_y(w, w.filter_case) - center_y(w, w.sort_case)) <= 4
    if custom:
        assert abs(center_y(w, w.limit_dates) - center_y(w, w.date_from)) <= 4
        assert abs(center_y(w, w.date_from) - center_y(w, w.date_to)) <= 4
    w.resize(w.minimumSize())
    ui.APP.processEvents()
    controls = [w.pattern, w.syntax, w.filter_case, w.refresh_button, w.close_button]
    if not (custom and official):
        controls.extend((w.column, w.sort_case))
    if custom:
        controls.extend((w.limit_dates, w.date_from, w.date_to))
    for control in controls:
        top_left = control.mapTo(w, ui.QtCore.QPoint())
        assert w.rect().contains(ui.QtCore.QRect(top_left, control.size()))
    assert w.column.isHidden() is (custom and official)
    assert w.sort_case.isHidden() is (custom and official)
    for text, control in (("Pattern", w.pattern), ("Syntax", w.syntax), ("Filter column", w.column)):
        label = next(label for label in w.findChildren(ui.QtWidgets.QLabel) if label.text() == text)
        assert label.buddy() is control
        if text == "Filter column":
            assert label.isHidden() is (custom and official)
    if custom:
        for text, control in (("From", w.date_from), ("To", w.date_to)):
            label = next(label for label in w.findChildren(ui.QtWidgets.QLabel) if label.text() == text)
            assert label.buddy() is control


def test_refresh_when_user_resized_or_row_count_changes_then_geometry_is_retained(layout_panel):
    w, state, _custom, _official = layout_panel
    w.resize(w.width() + 120, w.height() + 80)
    ui.APP.processEvents()
    before = w.size()
    for rows in ((), ROWS * 20, ROWS):
        state["rows"] = rows
        w.refresh()
        ui.APP.processEvents()
        assert w.size() == before
        assert w.model.rowCount() == len(rows)
        assert not w.model.item(0, 0) or not w.model.item(0, 0).isEditable()


def test_initial_layout_when_refresh_closes_then_no_late_size_access(panel):
    base, _state, custom = panel

    class Closing(base.__class__):
        def refresh(self):
            self.close()

    closed = Closing(
        None, "Closing capture", "owned_closing_layout", lambda: Table(
            ("Glyph", "Description", "Modified"), ROWS
        ), custom, "Capture closes during construction.",
    )
    assert closed._closed and closed._capture is None
    ui.QtCore.QCoreApplication.sendPostedEvents(None, ui.QtCore.QEvent.DeferredDelete)
